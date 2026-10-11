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
    stages = set()
    for episode in collect_dir.iterdir():
        if not episode.is_dir() or episode.name.startswith('.'):
            continue
        counts['total'] += 1
        try:
            metadata = json.loads((episode / RECORDING['metadata_filename']).read_text())
            if not isinstance(metadata, dict):
                raise ValueError('Metadata must be an object')
            stage = metadata.get('policy_stage')
            if stage in ('A', 'B'):
                stages.add(stage)
            frames = metadata.get('frame_count')
            if (metadata.get('recording_complete') is True
                    and type(frames) is int and frames > 0):
                counts['complete'] += 1
            else:
                counts['incomplete'] += 1
        except (OSError, ValueError):
            counts['unknown'] += 1
    return ','.join(sorted(stages)) or '-', counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path(COUNT_EPISODES['root_dir']),
                        help='Dataset root containing project folders')
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error('Dataset root does not exist: {}'.format(root))

    projects = sorted(path for path in root.iterdir()
                      if path.is_dir() and (path / 'collect_data').is_dir())
    print('Dataset root: {}'.format(root))
    if not projects:
        print('No projects with collect_data folders found.')
        return 0
    width = max(len('Project'), max(len(path.name) for path in projects))
    row = '{:<{width}}  {:<5}  {:>5}  {:>8}  {:>10}  {:>7}'
    print(row.format('Project', 'Stage', 'Total', 'Complete', 'Incomplete',
                     'Unknown', width=width))
    for project in projects:
        stage, counts = count_project(project / 'collect_data')
        print(row.format(project.name, stage, counts['total'], counts['complete'],
                         counts['incomplete'], counts['unknown'], width=width))
    print('\nComplete: stopped recording with a nonzero metadata frame count.')
    print('Incomplete: active, interrupted, or zero-frame recording.')
    print('Unknown: missing or unreadable metadata, including older recordings.')
    print('Counts do not verify frame files or physical task success.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
