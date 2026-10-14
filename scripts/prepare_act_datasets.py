"""Validate and convert the ACT projects configured in scripts_config.py offline."""

import argparse
import json
import pickle
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from barcode_scanning.recording import inspect_episode
from scripts.review_episodes import set_review_status
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts.dataset_checks import episode_warnings
from scripts.scripts_config import PREPARE_ACT_DATASETS


PROJECTS = PREPARE_ACT_DATASETS['projects']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path(PREPARE_ACT_DATASETS['root_dir']),
                        help='Dataset root; use the same root for training tasks')
    parser.add_argument('--dataset-name', choices=sorted(PROJECTS),
                        help='Prepare one project; by default prepare all configured projects')
    parser.add_argument('--convert', action='store_true',
                        help='Write HDF5 files and review videos after validation')
    parser.add_argument("--review-episode", type=Path, help="Raw episode folder to review")
    parser.add_argument("--review-status", choices=("accepted", "rejected", "unreviewed"))
    args = parser.parse_args(argv)
    if args.review_episode is not None or args.review_status is not None:
        if args.review_episode is None or args.review_status is None or args.convert:
            parser.error("Use --review-episode and --review-status together without --convert")
        matched = set_review_status(args.review_episode, args.review_status)
        print("Synchronized {} matching HDF5 review statuses".format(matched))
        print("{}: {}".format(args.review_episode, args.review_status))
        return 0
    root = args.root.expanduser().resolve()
    names = [args.dataset_name] if args.dataset_name else list(PROJECTS)
    plan = []
    for name in names:
        collect_dir = root / name / 'collect_data'
        if not collect_dir.is_dir():
            parser.error('Missing recording folder: {}'.format(collect_dir))
        episodes = sorted(path for path in collect_dir.iterdir()
                          if path.is_dir() and not path.name.startswith('.'))
        if not episodes:
            parser.error('No episodes in {}'.format(collect_dir))
        lengths = []
        project = PROJECTS[name]
        expected_stage = project['policy_stage']
        expected_bin = project['bin_index']
        for index, episode in enumerate(episodes):
            try:
                metadata = json.loads((episode / RECORDING['metadata_filename']).read_text())
            except (OSError, ValueError) as error:
                parser.error('{}: {}'.format(episode, error))
            if args.convert and metadata.get('review_status') != 'accepted':
                print('Skip {}: review status is {}'.format(episode.name, metadata.get('review_status')))
                continue
            try:
                report = inspect_episode(episode)
            except (OSError, ValueError, KeyError) as error:
                parser.error('{}: {}'.format(episode, error))
            if (report['policy_stage'] != expected_stage
                    or report['medium'] != project['medium']
                    or (expected_bin is not None and report['bin_index'] != expected_bin)):
                parser.error('Incorrect stage, medium, or destination: {}'.format(episode))
            if report['frames'] > project['episode_len']:
                parser.error('{} exceeds the configured {}-step episode length'.format(
                    episode, project['episode_len']))
            frames = sorted((episode / 'observation').glob('*.pkl'), key=lambda p: int(p.stem))
            qpos = []
            for frame in frames:
                # Pickles are trusted local recordings, never untrusted downloaded files.
                with frame.open('rb') as stream:
                    qpos.append(pickle.load(stream)['joint_positions'])
            hz, warnings = episode_warnings(qpos, metadata)
            print('{}: {} frames, {} Hz, {} overruns, review={}'.format(
                episode.name, report['frames'], 'unknown' if hz is None else '{:.2f}'.format(hz),
                metadata.get('control_overruns', 'unknown'), report['review_status']))
            for warning in warnings:
                print('[Warn]: {}: {}'.format(episode.name, warning))
            lengths.append(report['frames'])
            target = root / name / 'train_data' / 'episode_init_{}.hdf5'.format(index)
            if args.convert and target.exists():
                parser.error('Refuse to overwrite {}; use an unused output project or inspect existing conversion'.format(target))
            plan.append((name, episode, index))
        if not lengths:
            print('{}: no accepted episodes to convert'.format(name))
            continue
        print('{}: {} episodes, {}-{} frames, {} total frames'.format(
            name, len(lengths), min(lengths), max(lengths), sum(lengths)), flush=True)
        print('Longest episode: {} / {} configured steps'.format(max(lengths), project['episode_len']))

    if not args.convert:
        print('Validation passed. Add --convert to create HDF5 files and review videos.')
        return 0
    converter = REPO_ROOT / 'scripts' / 'script_collect2train.py'
    for number, (name, episode, index) in enumerate(plan, start=1):
        log_dir = root / name / 'conversion_logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / '{}.log'.format(episode.name)
        print('[{}/{}] {} / {}'.format(number, len(plan), name, episode.name), flush=True)
        with log_path.open('w') as log:
            result = subprocess.run([
                sys.executable, str(converter), '--root_dir', str(root),
                '--dataset_name', name, '--date_collect', episode.name,
                '--idx', str(index),
            ], stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO_ROOT))
        if result.returncode:
            print('Conversion failed. Read {}'.format(log_path), file=sys.stderr)
            return result.returncode
    print('Converted {} episodes. Review videos in each project/output_videos folder.'.format(len(plan)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
