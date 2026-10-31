"""Compare recorded joint gaps with rollout bounds without opening robot devices.

Read only the joint/action arrays and split masks, never camera payloads. A pass
checks software gap bounds; it does not establish physical safety or policy quality.
"""
import argparse
import json
from pathlib import Path

import h5py
import numpy as np

from config.settings import DATASETS, RUNTIME, SUPERVISOR
from parcel_sorting.safety.handoff import home_action
from parcel_sorting.safety.inference_safety import JOINT_INDICES


def audit_dataset(path, split='train'):
    limits = dict(command_step=RUNTIME['max_joint_increment_rad'],
                  target_tracking=SUPERVISOR['tracking_tolerance_rad'],
                  previous_command_tracking=SUPERVISOR['tracking_tolerance_rad'],
                  initial_approach=SUPERVISOR['policy_approach_max_rad'])
    maxima = {key: 0.0 for key in limits}
    violations = {key: 0 for key in limits}
    demos = frames = initial_approaches = starts_away = 0
    joints = list(JOINT_INDICES)
    with h5py.File(str(path), 'r') as source:
        names = sorted(source['data']) if split == 'all' else [
            name.decode() if isinstance(name, bytes) else str(name)
            for name in source['mask/' + split][:]]
        if not names:
            raise ValueError('The selected dataset split is empty')
        for name in names:
            demo = source['data/' + name]
            qpos, actions = demo['obs/qpos'][:], demo['actions'][:]
            if (qpos.shape != actions.shape or qpos.ndim != 2 or qpos.shape[1] != 14
                    or not len(qpos) or not np.isfinite(qpos).all() or not np.isfinite(actions).all()):
                raise ValueError('Expected matching nonempty finite (frames, 14) arrays in ' + name)
            qpos, actions = qpos[:, joints], actions[:, joints]
            initial_gap = np.max(np.abs(actions[0] - home_action()[joints]))
            gaps = dict(command_step=np.max(np.abs(np.diff(actions, axis=0)), axis=1),
                        target_tracking=np.max(np.abs(actions - qpos), axis=1),
                        previous_command_tracking=np.max(np.abs(qpos[1:] - actions[:-1]), axis=1),
                        initial_approach=np.asarray([initial_gap]))
            for key, values in gaps.items():
                if len(values):
                    maxima[key] = max(maxima[key], float(np.max(values)))
                    violations[key] += int(np.sum(values > limits[key]))
            initial_approaches += int(initial_gap > limits['command_step'])
            starts_away += int(np.max(np.abs(qpos[0] - home_action()[joints])) >
                               DATASETS['home_tolerance_rad'])
            demos += 1
            frames += len(qpos)
    return dict(dataset=str(Path(path).resolve()), split=split, demonstrations=demos, frames=frames,
                limits_rad=limits, maximum_gaps_rad=maxima, violations=violations,
                initial_targets_needing_approach=initial_approaches,
                recorded_starts_outside_home_tolerance=starts_away,
                compatible_joint_gaps=not any(violations.values()),
                scope='Joint gaps only; excludes workspace/cable clearance and live policy predictions')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--dataset', type=Path, help='Prepared robomimic HDF5 dataset')
    source.add_argument('--checkpoint', type=Path, help='Trusted local checkpoint; inspect its saved training dataset')
    parser.add_argument('--split', choices=('train', 'valid', 'all'), default='train')
    args = parser.parse_args(argv)
    path = args.dataset
    if args.checkpoint is not None:
        import torch
        saved = torch.load(str(args.checkpoint.expanduser()), map_location='cpu')
        config = json.loads(saved['config'])
        datasets = config['train']['data']
        if len(datasets) != 1:
            parser.error('Use --dataset to inspect each dataset in a multi-dataset checkpoint')
        path = Path(datasets[0]['path']).expanduser()
        del saved
    report = audit_dataset(path, args.split)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['compatible_joint_gaps'] else 2
