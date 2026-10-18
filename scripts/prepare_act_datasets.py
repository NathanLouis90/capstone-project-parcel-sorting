"""Validate and convert the ACT projects configured in scripts_config.py offline."""

import argparse
import json
import os
import pickle
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from barcode_scanning.recording import inspect_episode
from scripts.review_episodes import set_review_status
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts.dataset_checks import episode_warnings
from scripts.scripts_config import PREPARE_ACT_DATASETS
from scripts.dataset_integrity import require_fresh, require_rollout_opt_in


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
    parser.add_argument('--rebuild-to', help='Copy accepted raw episodes into this NEW registered project and convert there')
    parser.add_argument('--allow-rollouts', action='store_true', help='Allow rollout data only in explicitly named rollout projects')
    parser.add_argument("--review-episode", type=Path, help="Raw episode folder to review")
    parser.add_argument("--review-status", choices=("accepted", "rejected", "unreviewed"))
    args = parser.parse_args(argv)
    if args.review_episode is not None or args.review_status is not None:
        if args.review_episode is None or args.review_status is None or args.convert or args.rebuild_to:
            parser.error("Use --review-episode and --review-status together without --convert")
        matched = set_review_status(args.review_episode, args.review_status)
        print("Synchronized {} matching HDF5 review statuses".format(matched))
        print("{}: {}".format(args.review_episode, args.review_status))
        return 0
    root = args.root.expanduser().resolve()
    if args.rebuild_to:
        if not args.dataset_name or not args.convert:
            parser.error('--rebuild-to requires --dataset-name and --convert')
        if args.rebuild_to not in PROJECTS:
            parser.error('Register the fresh --rebuild-to project in scripts_config.py first')
        if (root / args.rebuild_to).exists():
            parser.error('--rebuild-to requires a fresh project; destination already exists')
    names = [args.dataset_name] if args.dataset_name else [
        name for name in PROJECTS if (root / name / 'collect_data').is_dir()]
    if not names:
        parser.error('No registered recording projects exist under {}'.format(root))
    plan = []
    for name in names:
        if not args.rebuild_to:
            try:
                require_fresh(root / name)
            except ValueError as error:
                parser.error(str(error))
        collect_dir = root / name / 'collect_data'
        if not collect_dir.is_dir():
            parser.error('Missing recording folder: {}'.format(collect_dir))
        episodes = sorted(path for path in collect_dir.iterdir()
                          if path.is_dir() and not path.name.startswith('.'))
        if not episodes:
            parser.error('No episodes in {}'.format(collect_dir))
        lengths = []
        output_name = args.rebuild_to or name
        project = PROJECTS[output_name]
        for episode in episodes:
            try:
                metadata = json.loads((episode / RECORDING['metadata_filename']).read_text())
            except (OSError, ValueError) as error:
                parser.error('{}: {}'.format(episode, error))
            if args.convert and metadata.get('review_status') != 'accepted':
                print('Skip {}: review status is {}'.format(episode.name, metadata.get('review_status')))
                continue
            if metadata.get('source') == 'rollout' and not args.allow_rollouts:
                print('Skip {}: rollout excluded by default'.format(episode.name))
                continue
            try:
                require_rollout_opt_in(metadata, root / output_name, args.allow_rollouts)
            except ValueError as error:
                parser.error(str(error))
            try:
                report = inspect_episode(episode)
                if args.rebuild_to:
                    from scripts.curate_datasets import signature, compatible
                    assumptions = set()
                    compatible(signature(episode, assumptions), project, episode)
                    for warning in sorted(assumptions):
                        print('[Warn]: ' + warning)
            except (OSError, ValueError, KeyError) as error:
                parser.error('{}: {}'.format(episode, error))
            if report['medium'] != project['medium'] or report['legacy_recording']:
                parser.error('Require fresh pick-to-scan recordings of the registered medium: {}'.format(episode))
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
            output_index = len(lengths) - 1
            target = root / output_name / 'train_data' / 'episode_init_{}.hdf5'.format(output_index)
            if args.convert and target.exists():
                parser.error('Refuse to overwrite {}; use an unused output project or inspect existing conversion'.format(target))
            plan.append((output_name, episode, output_index))
        if not lengths:
            print('{}: no accepted episodes to convert'.format(name))
            continue
        print('{}: {} episodes, {}-{} frames, {} total frames'.format(
            name, len(lengths), min(lengths), max(lengths), sum(lengths)), flush=True)
        print('Longest episode: {} / {} configured steps'.format(max(lengths), project['episode_len']))

    if not args.convert:
        print('Validation passed. Add --convert to create HDF5 files and review videos.')
        return 0
    rebuild_marker = None
    if args.rebuild_to:
        if not plan:
            parser.error('No accepted episodes to rebuild')
        # Validate the whole selection before creating the fresh project. Copy
        # through a temporary sibling so a failed copy leaves no partial project.
        from scripts.curate_datasets import hashes
        destination = root / args.rebuild_to
        temporary = Path(tempfile.mkdtemp(prefix='.rebuild-', dir=str(root)))
        try:
            operations = []
            for name, episode, index in plan:
                target = temporary / 'collect_data' / episode.name
                original = hashes(episode)
                shutil.copytree(str(episode), str(target))
                if hashes(target) != original:
                    raise ValueError('Source changed during fresh rebuild: {}'.format(episode))
                operations.append(dict(source=str(episode), destination=str(destination / 'collect_data' / episode.name),
                                       operation='copy', sha256=original))
            (temporary / 'curation_log.jsonl').write_text(json.dumps(dict(
                timestamp=datetime.now(timezone.utc).isoformat(), command='prepare --rebuild-to',
                episode_ids=[episode.name for _, episode, _ in plan], operations=operations)) + '\n')
            (temporary / 'train_data').mkdir()
            (temporary / 'train_data' / 'BUILDING.json').write_text(json.dumps(dict(reason='Fresh rebuild conversion in progress; incomplete until all files succeed')) + '\n')
            if destination.exists():
                raise ValueError('Fresh rebuild destination appeared during validation')
            os.rename(str(temporary), str(destination))
        finally:
            if temporary.exists():
                shutil.rmtree(str(temporary))
        plan = [(name, destination / 'collect_data' / episode.name, index) for name, episode, index in plan]
        rebuild_marker = destination / 'train_data' / 'BUILDING.json'
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
                *(['--allow-rollouts'] if args.allow_rollouts else []),
            ], stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO_ROOT))
        if result.returncode:
            print('Conversion failed. Read {}'.format(log_path), file=sys.stderr)
            return result.returncode
    if rebuild_marker is not None:
        rebuild_marker.unlink()
    print('Converted {} episodes. Review videos in each project/output_videos folder.'.format(len(plan)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
