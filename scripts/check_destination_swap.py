"""Offline held-out B destination swap check; never imports robot interfaces."""
import argparse
import json
from pathlib import Path
import random
import sys
import time

import h5py
import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / 'robomimic-r2d2'))
from scripts.scripts_config import ROBOMIMIC


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compare_episode(policy, demo, seed, max_steps):
    n = min(int(demo.attrs['num_samples']), max_steps)
    observations = {key: demo['obs/' + key][:n] for key in policy.policy.obs_key_shapes}
    stack = policy.policy.global_config.train.frame_stack
    destination = observations.get('destination')
    bin_index = int(demo.attrs.get('bin_index', -1))
    if bin_index not in (0, 1) or destination is None or not np.all(destination == np.eye(2)[bin_index]):
        raise ValueError('Expected B episode with a constant destination matching bin_index')
    predictions, timings = [], []
    for swapped in (False, True):
        # Match stochastic noise and reset action queues / temporal history for both passes.
        set_seed(seed)
        policy.start_episode()
        actions = []
        start = time.monotonic()
        with torch.no_grad():
            for t in range(n):
                indices = [max(0, t - stack + 1 + j) for j in range(stack)]
                observation = {key: (value[indices].copy() if stack > 1 else value[t].copy())
                               for key, value in observations.items()}
                if swapped:
                    observation['destination'] = observation['destination'][..., ::-1].copy()
                actions.append(np.asarray(policy(observation)))
        timings.append((time.monotonic() - start) / n * 1000)
        predictions.append(np.asarray(actions))
    true, swapped = predictions
    if true.shape != (n, 14) or not np.isfinite(true).all() or not np.isfinite(swapped).all():
        raise ValueError('Expected finite 14-D predicted actions')
    joints = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    right = list(range(7, 13))
    actual = demo['actions'][:n]
    result = {
        'medium': str(demo.attrs['medium']), 'bin_index': bin_index, 'steps': n,
        'true_joint_rmse_rad': float(np.sqrt(np.mean((true[:, joints] - actual[:, joints]) ** 2))),
        'swapped_joint_rmse_rad': float(np.sqrt(np.mean((swapped[:, joints] - actual[:, joints]) ** 2))),
        'swap_joint_rms_rad': float(np.sqrt(np.mean((swapped[:, joints] - true[:, joints]) ** 2))),
        'swap_right_joint_rms_rad': float(np.sqrt(np.mean((swapped[:, right] - true[:, right]) ** 2))),
        'swap_gripper_rms': float(np.sqrt(np.mean((swapped[:, [6, 13]] - true[:, [6, 13]]) ** 2))),
        'true_prediction_motion_rad': float(np.linalg.norm(true[-1, right] - true[0, right])),
        'swapped_prediction_motion_rad': float(np.linalg.norm(swapped[-1, right] - swapped[0, right])),
        'true_ms_per_step': timings[0], 'swapped_ms_per_step': timings[1],
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-episodes', type=int, default=ROBOMIMIC['swap_max_episodes'])
    parser.add_argument('--max-steps', type=int, default=ROBOMIMIC['swap_max_steps'])
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args(argv)
    if args.max_episodes <= 0 or args.max_steps <= 0:
        parser.error('Limits must be positive')
    import robomimic.utils.file_utils as FileUtils
    device = torch.device('cpu' if args.cpu or not torch.cuda.is_available() else 'cuda')
    policy, checkpoint = FileUtils.policy_from_checkpoint(ckpt_path=args.checkpoint, device=device, verbose=False)
    config = json.loads(checkpoint['config'])
    if 'destination' not in config['observation']['modalities']['obs']['low_dim']:
        raise ValueError('Checkpoint is not destination-conditioned B')
    with h5py.File(str(args.dataset), 'r') as source:
        if source['data'].attrs['recipe'] != 'policy_B_conditioned':
            raise ValueError('Dataset must use policy_B_conditioned')
        split = json.loads(source['data'].attrs['split_json'])
        training_path = Path(config['train']['data'][0]['path'])
        if not training_path.is_file():
            raise ValueError('Training dataset required to verify held-out split provenance')
        with h5py.File(str(training_path), 'r') as training:
            if json.loads(training['data'].attrs['split_json']) != split:
                raise ValueError('Evaluation split differs from checkpoint training split')
        train = {key.decode() for key in source['mask/train'][:]}
        valid = [key.decode() for key in source['mask/valid'][:]]
        if train & set(valid) or not valid:
            raise ValueError('Held-out filter must be nonempty and disjoint')
        reports = []
        for i, name in enumerate(valid[:args.max_episodes]):
            result = compare_episode(policy, source['data/' + name], ROBOMIMIC['seed'] + i, args.max_steps)
            result['demo'] = name
            reports.append(result)
            print(json.dumps(result, sort_keys=True))
    mean = float(np.mean([report['swap_right_joint_rms_rad'] for report in reports]))
    summary = {'checkpoint': args.checkpoint, 'episodes': reports, 'mean_swap_right_joint_rms_rad': mean,
               'possible_destination_ignored': mean < ROBOMIMIC['swap_joint_rms_warning_rad']}
    print('Mean right-joint swap RMS: {:.6f} rad; threshold {:.6f} rad'.format(mean, ROBOMIMIC['swap_joint_rms_warning_rad']))
    if summary['possible_destination_ignored']:
        print('[Warn]: Swapping destination barely changes actions; investigate conditioning.')
    print('Offline sensitivity does not establish correct-bin placement or physical task success.')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    main()
