"""Review local demonstrations and synchronize decisions with converted HDF5 files.

No robot interfaces are imported. Physical success is an operator decision.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import pickle
import sys
import time

import cv2
import h5py
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from barcode_scanning.barcode_scanning_config import RECORDING
from barcode_scanning.recording import inspect_episode, write_metadata
from scripts.scripts_config import REVIEW_EPISODES, SCRIPT_COLLECT2TRAIN

CAMERA_FOLDERS = (('top', 'topImg'), ('left_wrist', 'leftImg'), ('right_wrist', 'rightImg'))
STATUSES = ('accepted', 'rejected', 'unreviewed')
REVIEW_FIELDS = {'review_status', 'reviewed_at'}


def read_metadata(episode):
    metadata = json.loads((Path(episode) / RECORDING['metadata_filename']).read_text())
    if metadata.get('episode_id') != Path(episode).name:
        raise ValueError('Episode ID differs from folder name: {}'.format(episode))
    return metadata


def converted_index(project):
    index = {}
    for path in sorted((Path(project) / 'train_data').glob('episode_init_*.hdf5')):
        with h5py.File(str(path), 'r') as source:
            text = source.attrs.get('episode_metadata_json')
            if text is None:
                print('[Warn]: {} has no episode metadata; cannot synchronize it'.format(path))
                continue
            metadata = json.loads(text)
            identifier = metadata.get('episode_id')
            if not identifier:
                raise ValueError('Converted file has no episode ID: {}'.format(path))
            index.setdefault(identifier, []).append(path)
    return index


def check_converted_recording(episode, metadata, source, verify_payload):
    """Require matching episode identity; acceptance also verifies original data."""
    saved = json.loads(source.attrs['episode_metadata_json'])
    for key in ('episode_id', 'cycle_id', 'medium', 'label_face'):
        if saved.get(key) != metadata.get(key):
            raise ValueError('Raw/HDF5 {} differs: {}'.format(key, source.filename))
        if key != 'episode_id' and source.attrs.get(key) != metadata.get(key):
            raise ValueError('HDF5 {} attribute differs: {}'.format(key, source.filename))
    if not verify_payload:
        return saved
    raw_details = {key: value for key, value in metadata.items() if key not in REVIEW_FIELDS}
    converted_details = {key: value for key, value in saved.items() if key not in REVIEW_FIELDS}
    if raw_details != converted_details:
        raise ValueError('Recording details changed since conversion; rebuild {}'.format(source.filename))
    frames = sorted((Path(episode) / 'observation').glob('*.pkl'), key=lambda path: int(path.stem))
    count = len(frames)
    if source['observations/qpos'].shape != (count, 14) or source['action'].shape != (count, 14):
        raise ValueError('Raw/HDF5 joint or action shape differs: {}'.format(source.filename))
    mirror = np.asarray(source.attrs.get('mirror_state_multiply', SCRIPT_COLLECT2TRAIN['MIRROR_STATE_MULTIPLY']))
    if mirror.shape != (7,):
        raise ValueError('Invalid conversion mirror settings')
    multiplier = np.tile(mirror, 2)
    compressed = bool(source.attrs.get('compress', False))
    quality = int(source.attrs.get('jpeg_quality', SCRIPT_COLLECT2TRAIN['jpeg_quality']))
    for camera, folder in CAMERA_FOLDERS:
        if len(source['observations/images/' + camera]) != count:
            raise ValueError('Raw/HDF5 camera length differs: {}'.format(source.filename))
    for i, frame in enumerate(frames):
        # Pickles are trusted local recordings, as in the existing converter.
        with frame.open('rb') as stream:
            observation = pickle.load(stream)
        for key, dataset in (('joint_positions', 'observations/qpos'), ('control', 'action')):
            expected = np.asarray(observation[key]) * multiplier
            actual = source[dataset][i]
            if (not np.isfinite(expected).all() or not np.isfinite(actual).all()
                    or not np.array_equal(expected.astype(actual.dtype), actual)):
                raise ValueError('Raw/HDF5 {} differs at frame {}; rebuild {}'.format(key, frame.stem, source.filename))
        for camera, folder in CAMERA_FOLDERS:
            image = cv2.imread(str(Path(episode) / folder / (frame.stem + '.jpg')))
            if image is None:
                raise ValueError('Unreadable raw camera frame: {} / {}'.format(folder, frame.stem))
            actual = source['observations/images/' + camera][i]
            if compressed:
                ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                if not ok:
                    raise ValueError('Could not encode camera frame')
                expected = encoded.ravel()
                matches = (actual.ndim == 1 and len(actual) >= len(expected)
                           and np.array_equal(actual[:len(expected)], expected)
                           and not np.any(actual[len(expected):]))
            else:
                matches = np.array_equal(actual, image)
            if not matches:
                raise ValueError('Raw/HDF5 {} image differs at frame {}; rebuild {}'.format(camera, frame.stem, source.filename))
    return saved


def set_review_status(episode, status, converted=None, dry_run=False, sync_only=False):
    """Check all files before changing review fields; never rewrite camera/actions."""
    if status not in STATUSES:
        raise ValueError('Unknown review status: {}'.format(status))
    episode = Path(episode).expanduser().resolve()
    metadata = read_metadata(episode)
    if status == 'accepted':
        inspect_episode(episode)
        from scripts.dataset_checks import episode_warnings
        qpos = []
        for frame in sorted((episode / 'observation').glob('*.pkl'), key=lambda p: int(p.stem)):
            with frame.open('rb') as stream:
                qpos.append(pickle.load(stream)['joint_positions'])
        for warning in episode_warnings(qpos, metadata)[1]:
            print('[Warn]: ' + warning)
    if converted is None:
        converted = converted_index(episode.parent.parent).get(episode.name, [])
    mode = 'r' if dry_run else 'r+'
    with ExitStack() as stack:
        files = [stack.enter_context(h5py.File(str(path), mode)) for path in converted]
        saved_metadata = [check_converted_recording(episode, metadata, source, status == 'accepted')
                          for source in files]
        if dry_run:
            return len(files)
        updated = dict(metadata)
        updated['review_status'] = status
        if not sync_only:
            updated['reviewed_at'] = time.time()
        # Raw status is authoritative. If an HDF5 write fails, rerun --sync-review-status.
        # Both raw and converted statuses must be accepted before robomimic conversion.
        if not sync_only:
            write_metadata(episode / RECORDING['metadata_filename'], updated)
        for source, saved in zip(files, saved_metadata):
            original = dict(saved)
            saved['review_status'] = status
            if 'reviewed_at' in updated:
                saved['reviewed_at'] = updated['reviewed_at']
            else:
                saved.pop('reviewed_at', None)
            if saved != original:
                source.attrs['episode_metadata_json'] = json.dumps(saved)
                source.flush()
    return len(files)


def frame_delay_ms(metadata):
    count = metadata.get('frame_count', 0)
    duration = metadata.get('ended_at', 0) - metadata.get('started_at', 0)
    period = duration / count * 1000 if count > 0 and duration > 0 else REVIEW_EPISODES['fallback_period_ms']
    speed = REVIEW_EPISODES['playback_speed']
    if speed <= 0:
        raise ValueError('Playback speed must be positive')
    return max(1, round(period / speed))


def key_decision(key):
    character = chr(key & 0xff).lower()
    return {'a': 'accepted', 'r': 'rejected', 's': 'skip',
            'q': 'quit', 'p': 'replay', ' ': 'pause'}.get(character)


def play_episode(episode, metadata):
    """Stream raw camera frames; a decision is a key press in the video window."""
    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise RuntimeError('No graphical display. Use --terminal-only after reviewing videos elsewhere.')
    files = sorted((episode / 'topImg').glob('*.jpg'), key=lambda path: int(path.stem))
    if not files:
        raise ValueError('No raw camera frames to play')
    title = REVIEW_EPISODES['window_name']
    height, width = REVIEW_EPISODES['preview_camera_size']
    delay = frame_delay_ms(metadata)
    index, paused, displayed = 0, False, None
    try:
        while True:
            start = time.monotonic()
            if index != displayed:
                views = []
                for camera, folder in CAMERA_FOLDERS:
                    image = cv2.imread(str(episode / folder / files[index].name))
                    if image is None:
                        raise ValueError('Unreadable {} frame {}'.format(camera, files[index].name))
                    views.append(cv2.resize(image, (width, height)))
                canvas = np.hstack(views)
                displayed = index
            cv2.imshow(title, canvas)
            command = key_decision(cv2.waitKey(max(1, round(delay - (time.monotonic() - start) * 1000))))
            if command in STATUSES or command in ('skip', 'quit'):
                return command
            if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                return 'quit'
            if command == 'replay':
                index, paused = 0, False
                continue
            if command == 'pause':
                paused = not paused
            if not paused:
                index = min(index + 1, len(files) - 1)
            # At the end, keep the last frame visible until a decision or replay.
    finally:
        cv2.destroyAllWindows()


def terminal_decision(episode, metadata):
    print('Review video: {}'.format(episode.parent.parent / 'output_videos' / (episode.name + '_video.mp4')))
    while True:
        answer = input('a accept / r reject / s skip / q quit: ').strip().lower()
        if answer in ('a', 'r', 's', 'q'):
            return key_decision(ord(answer))


def review_project(project, episode_ids=None, status=None, sync=False, include_reviewed=False,
                   dry_run=False, decision_fn=None, only_rejected=False):
    if only_rejected and include_reviewed:
        raise ValueError('Use --only-rejected or --include-reviewed, not both')
    project = Path(project).expanduser().resolve()
    collect = project / 'collect_data'
    if not collect.is_dir():
        raise ValueError('Missing collect_data: {}'.format(collect))
    episodes = sorted(path for path in collect.iterdir() if path.is_dir() and not path.name.startswith('.'))
    if episode_ids:
        requested = set(episode_ids)
        if any(Path(name).name != name or name in ('.', '..') for name in requested):
            raise ValueError('Use episode folder names, not paths')
        if requested - {episode.name for episode in episodes}:
            raise ValueError('Unknown episode IDs: {}'.format(sorted(requested - {episode.name for episode in episodes})))
        episodes = [episode for episode in episodes if episode.name in requested]
    converted = converted_index(project)
    selected = [(episode, read_metadata(episode)) for episode in episodes]
    if only_rejected:
        selected = [(episode, metadata) for episode, metadata in selected
                    if metadata.get('review_status') == 'rejected']
    elif not sync and not include_reviewed and not episode_ids:
        selected = [(episode, metadata) for episode, metadata in selected
                    if metadata.get('review_status', 'unreviewed') == 'unreviewed']
    summary = dict(accepted=0, rejected=0, unreviewed=0, skipped=0, errors=0, converted=0)
    if not selected:
        if only_rejected:
            print('No rejected episodes selected.')
        else:
            print('No episodes selected; use --include-reviewed to review earlier decisions.')
        return summary
    # Batch changes are checked for the entire selection before writing any decision.
    checked_counts = {}
    if status or sync:
        for i, (episode, metadata) in enumerate(selected, 1):
            print('Checking [{}/{}] {}'.format(i, len(selected), episode.name), flush=True)
            decision = metadata.get('review_status', 'unreviewed') if sync else status
            checked_counts[episode.name] = set_review_status(episode, decision, converted.get(episode.name, []), dry_run=True)
    for i, (episode, metadata) in enumerate(selected, 1):
        print('[{}/{}] {}: {}'.format(i, len(selected), episode.name, metadata.get('review_status', 'unreviewed')), flush=True)
        try:
            decision = metadata.get('review_status', 'unreviewed') if sync else status
            if decision is None:
                decision = (decision_fn or play_episode)(episode, metadata)
            if decision == 'quit':
                break
            if decision == 'skip':
                summary['skipped'] += 1
                continue
            if dry_run and episode.name in checked_counts:
                count = checked_counts[episode.name]
            else:
                count = set_review_status(episode, decision, converted.get(episode.name, []), dry_run=dry_run, sync_only=sync)
            summary[decision] += 1
            summary['converted'] += count
            print('{}{}; {} matching HDF5 review statuses {}'.format(
                'Would mark ' if dry_run else 'Marked ', decision, count,
                'checked' if dry_run else 'synchronized'), flush=True)
        except (OSError, ValueError, KeyError, cv2.error) as error:
            summary['errors'] += 1
            print('[Error]: {}: {}'.format(episode.name, error), file=sys.stderr)
    summary['remaining_unreviewed'] = sum(read_metadata(episode).get('review_status', 'unreviewed') == 'unreviewed'
                                        for episode in episodes)
    print(('Dry-run checks: ' if dry_run else 'Review results: ') + json.dumps(summary, sort_keys=True))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path, help='Project folder containing collect_data and optional train_data')
    parser.add_argument('--episodes', nargs='+', help='Selected episode folder names; default selects unreviewed episodes')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--set-status', choices=STATUSES, help='Batch decision for episodes you have already reviewed')
    mode.add_argument('--sync-review-status', action='store_true', help='Copy existing raw decisions into matching HDF5 files')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--include-reviewed', action='store_true', help='Include previously accepted/rejected episodes')
    selection.add_argument('--only-rejected', action='store_true', help='Review only episodes currently marked rejected')
    parser.add_argument('--terminal-only', action='store_true', help='Ask in the terminal without opening video; review videos elsewhere first')
    parser.add_argument('--dry-run', action='store_true', help='Check a batch operation without changing files')
    args = parser.parse_args(argv)
    if args.dry_run and not (args.set_status or args.sync_review_status):
        parser.error('--dry-run requires --set-status or --sync-review-status')
    if args.terminal_only and (args.set_status or args.sync_review_status):
        parser.error('--terminal-only applies to interactive review')
    try:
        summary = review_project(args.project, args.episodes, args.set_status, args.sync_review_status,
                                 args.include_reviewed, args.dry_run,
                                 terminal_decision if args.terminal_only else None,
                                 only_rejected=args.only_rejected)
        return 1 if summary['errors'] else 0
    except (OSError, ValueError, KeyError, RuntimeError, cv2.error) as error:
        print('Review failed: {}'.format(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('Review stopped; earlier decisions are saved.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
