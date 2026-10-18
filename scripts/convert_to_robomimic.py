"""Convert reviewed vendor episodes from multiple projects to one robomimic dataset."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys

import cv2
import h5py
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from scripts.scripts_config import PREPARE_ACT_DATASETS, ROBOMIMIC
from barcode_scanning.barcode_scanning_config import RECORDING
from scripts.dataset_integrity import require_fresh, require_rollout_opt_in, explicit_rollout_name


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def inspect_sources(projects, recipe, allow_rollouts=False):
    entries = []
    for project in projects:
        require_fresh(project)
        for path in sorted((Path(project) / 'train_data').glob('episode_init_*.hdf5')):
            with h5py.File(str(path), 'r') as source:
                medium = source.attrs.get('medium')
                if medium != recipe['medium']:
                    continue
                metadata = json.loads(source.attrs.get('episode_metadata_json', '{}'))
                if metadata.get('schema_version', 0) < 3 or metadata.get('legacy_recording'):
                    raise ValueError('Require fresh pick-to-scan recordings: {}'.format(path))
                if metadata.get('source') == 'rollout' and not allow_rollouts:
                    print('Skip {}: rollout excluded by default'.format(path))
                    continue
                require_rollout_opt_in(metadata, project, allow_rollouts)
                raw_metadata = Path(project) / 'collect_data' / str(metadata.get('episode_id', '')) / RECORDING['metadata_filename']
                raw_status = json.loads(raw_metadata.read_text()).get('review_status') if raw_metadata.is_file() else 'accepted'
                if metadata.get('review_status') != 'accepted' or raw_status != 'accepted':
                    print('Skip {}: not accepted'.format(path))
                    continue
                if medium not in ('envelope', 'poly_mailer', 'carton') or not source.attrs.get('cycle_id'):
                    raise ValueError('Missing medium/cycle provenance: {}'.format(path))
                qpos, actions = source['observations/qpos'], source['action']
                if qpos.shape != actions.shape or qpos.ndim != 2 or qpos.shape[1] != 14 or not len(qpos):
                    raise ValueError('Expected nonempty matching (frames, 14) qpos/action: {}'.format(path))
                if not np.isfinite(qpos[:]).all() or not np.isfinite(actions[:]).all():
                    raise ValueError('Nonfinite qpos/action: {}'.format(path))
                for camera in ROBOMIMIC['cameras']:
                    if len(source['observations/images/' + camera]) != len(qpos):
                        raise ValueError('Camera length mismatch: {}'.format(path))
                identifier = Path(project).name + '/' + path.name
                entries.append(dict(id=identifier, path=str(path.resolve()), medium=medium,
                                    cycle=str(source.attrs['cycle_id']), sha256=digest(path)))
    if not entries:
        raise ValueError('No accepted matching episodes; review raw episodes and reconvert first')
    if len({entry['id'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate source project/episode identifiers')
    return entries


def make_split(entries, recipe, split_path):
    # Keep repeated demonstrations of one parcel cycle together to avoid leakage.
    strata = defaultdict(lambda: defaultdict(list))
    cycle_strata = {}
    for index, entry in enumerate(entries):
        key = entry['medium']
        if entry['cycle'] in cycle_strata and cycle_strata[entry['cycle']] != key:
            raise ValueError('A cycle belongs to conflicting strata')
        cycle_strata[entry['cycle']] = key
        strata[key][entry['cycle']].append('demo_{}'.format(index))
    expected = [{k: entry[k] for k in ('id', 'sha256', 'cycle')} for entry in entries]
    if split_path.exists():
        split = json.loads(split_path.read_text())
        if split['sources'] != expected or split['recipe'] != recipe:
            raise ValueError('Split sources changed; create a new dataset and split')
    else:
        rng = random.Random(ROBOMIMIC['seed'])
        split = dict(recipe=recipe, sources=expected, train=[], valid=[], seed=ROBOMIMIC['seed'])
        for key, cycles in sorted(strata.items()):
            keys = sorted(cycles)
            if len(keys) < 2:
                raise ValueError('Need at least two independent cycles for stratum {}'.format(key))
            rng.shuffle(keys)
            count = max(1, min(len(keys) - 1, round(len(keys) * (1 - ROBOMIMIC['train_fraction']))))
            for i, cycle in enumerate(keys):
                split['valid' if i < count else 'train'].extend(cycles[cycle])
    names = {'demo_{}'.format(i) for i in range(len(entries))}
    train, valid = set(split['train']), set(split['valid'])
    if not train or not valid or train & valid or train | valid != names:
        raise ValueError('Split must cover every demo exactly once with nonempty disjoint filters')
    for key, cycles in strata.items():
        members = {demo for demos in cycles.values() for demo in demos}
        if not (members & train and members & valid):
            raise ValueError('Both filters must represent stratum {}'.format(key))
        for demos in cycles.values():
            if set(demos) & train and set(demos) & valid:
                raise ValueError('Split leaks a parcel cycle across train/valid')
    return split


def decode_frame(dataset, index, compressed):
    frame = dataset[index]
    if compressed:
        frame = cv2.imdecode(np.asarray(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError('Invalid camera frame {}'.format(index))
    # Vendor conversion writes OpenCV BGR. robomimic image encoders expect RGB.
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width = ROBOMIMIC['image_size']
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA).astype(np.uint8)


def convert(projects, recipe_name, output, split_path, allow_rollouts=False):
    output, split_path = Path(output), Path(split_path)
    if output.resolve() == split_path.resolve():
        raise ValueError('Dataset and split must have different paths')
    if output.exists():
        raise FileExistsError('Refuse to overwrite {}'.format(output))
    recipe = ROBOMIMIC['recipes'][recipe_name]
    if allow_rollouts and not explicit_rollout_name(output.stem):
        raise ValueError('Including rollouts requires an output dataset name containing rollout or rollouts')
    entries = inspect_sources(projects, recipe, allow_rollouts)
    split = make_split(entries, recipe, split_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.partial')
    if temporary.exists():
        raise FileExistsError('Refuse to overwrite existing partial output {}'.format(temporary))
    try:
        with h5py.File(str(temporary), 'x') as target:
            data = target.create_group('data')
            data.attrs['env_args'] = json.dumps(dict(env_name='DobotParcelOffline', type=1, env_kwargs={}))
            data.attrs['recipe'] = recipe_name
            data.attrs['split_file'] = str(split_path.resolve())
            data.attrs['split_json'] = json.dumps(split, sort_keys=True)
            total = 0
            for i, entry in enumerate(entries):
                with h5py.File(entry['path'], 'r') as source:
                    demo = data.create_group('demo_{}'.format(i))
                    from barcode_scanning.dataset_metadata import write_hdf5_metadata
                    metadata = json.loads(source.attrs['episode_metadata_json'])
                    write_hdf5_metadata(demo, metadata, len(source['action']))
                    demo.attrs['recording_id'] = entry['id']
                    n = len(source['action'])
                    demo.attrs['num_samples'] = n
                    demo.create_dataset('actions', data=source['action'][:].astype(np.float32))
                    obs = demo.create_group('obs')
                    obs.create_dataset('qpos', data=source['observations/qpos'][:].astype(np.float32))
                    for camera in ROBOMIMIC['cameras']:
                        h, w = ROBOMIMIC['image_size']
                        images = obs.create_dataset(camera, shape=(n, h, w, 3), dtype=np.uint8,
                                                    chunks=(1, h, w, 3), compression='gzip')
                        for t in range(n):
                            images[t] = decode_frame(source['observations/images/' + camera], t,
                                                     bool(source.attrs.get('compress', False)))
                    total += n
            data.attrs['total'] = total
            mask = target.create_group('mask')
            for key in ('train', 'valid'):
                mask.create_dataset(key, data=np.asarray(split[key], dtype='S'))
        split_path.parent.mkdir(parents=True, exist_ok=True)
        if not split_path.exists():
            with split_path.open('x') as stream:
                json.dump(split, stream, indent=2)
                stream.write('\n')
        temporary.rename(output)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    print('Wrote {} demos: {} train, {} valid to {}'.format(len(entries), len(split['train']), len(split['valid']), output))
    return split


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', required=True, choices=sorted(ROBOMIMIC['recipes']))
    parser.add_argument('--projects', nargs='+', type=Path, help='Project folders, each containing train_data')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--split-file', required=True, type=Path)
    parser.add_argument('--allow-rollouts', action='store_true')
    args = parser.parse_args(argv)
    projects = args.projects or [Path(PREPARE_ACT_DATASETS['root_dir']) / name
                                for name in PREPARE_ACT_DATASETS['projects']]
    for project in projects:
        if not (project / 'train_data').is_dir():
            parser.error('Missing train_data: {}'.format(project))
    convert(projects, args.recipe, args.output, args.split_file, args.allow_rollouts)


if __name__ == '__main__':
    main()
