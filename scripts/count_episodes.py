"""Count raw episode folders without opening hardware or changing datasets."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts.scripts_config import COUNT_EPISODES


def count_project(collect_dir):
    counts = dict(total=0, complete=0, incomplete=0, unknown=0)
    media = set()
    for episode in collect_dir.iterdir():
        if not episode.is_dir() or episode.name.startswith('.'):
            continue
        counts['total'] += 1
        try:
            metadata = json.loads((episode / RECORDING['metadata_filename']).read_text())
            if not isinstance(metadata, dict):
                raise ValueError('Metadata must be an object')
            medium = metadata.get('medium')
            if medium:
                media.add(medium)
            frames = metadata.get('frame_count')
            if (metadata.get('recording_complete') is True
                    and type(frames) is int and frames > 0):
                counts['complete'] += 1
            else:
                counts['incomplete'] += 1
        except (OSError, ValueError):
            counts['unknown'] += 1
    return ','.join(sorted(media)) or '-', counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path(COUNT_EPISODES['root_dir']),
                        help='Dataset root containing project folders')
    parser.add_argument('--project', help='Show one exact project folder name')
    parser.add_argument('--details', action='store_true', help='Print each episode medium, label face and review status')
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error('Dataset root does not exist: {}'.format(root))

    projects = sorted(path for path in root.iterdir()
                      if path.is_dir() and (path / 'collect_data').is_dir())
    if args.project:
        projects = [path for path in projects if path.name == args.project]
        if not projects:
            parser.error('No project with collect_data: {}'.format(args.project))
    print('Dataset root: {}'.format(root))
    if not projects:
        print('No projects with collect_data folders found.')
        return 0
    width = max(len('Project'), max(len(path.name) for path in projects))
    row = '{:<{width}}  {:<5}  {:>5}  {:>8}  {:>10}  {:>7}'
    print(row.format('Project', 'Medium', 'Total', 'Complete', 'Incomplete',
                     'Unknown', width=width))
    for project in projects:
        medium, counts = count_project(project / 'collect_data')
        print(row.format(project.name, medium, counts['total'], counts['complete'],
                         counts['incomplete'], counts['unknown'], width=width))
        if args.details:
            for episode in sorted((project / 'collect_data').iterdir()):
                if not episode.is_dir() or episode.name.startswith('.'):
                    continue
                try:
                    metadata = json.loads((episode / RECORDING['metadata_filename']).read_text())
                    print('  {}: medium={}, label_face={}, review={}{}'.format(
                        episode.name, metadata.get('medium'), metadata.get('label_face'),
                        metadata.get('review_status', 'unreviewed'),
                        ' [episode_id differs from folder name]' if metadata.get('episode_id') != episode.name else ''))
                except (OSError, ValueError) as error:
                    print('  {}: {}'.format(episode.name, error))
    print('\nComplete: stopped recording with a nonzero metadata frame count.')
    print('Incomplete: active, interrupted, or zero-frame recording.')
    print('Unknown: missing or unreadable metadata, including older recordings.')
    print('Counts do not verify frame files or physical task success.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
