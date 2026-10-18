"""Hardware-free advisory checks for trusted local demonstration files."""
import numpy as np
from experiments.experiments_config import CONTROL, RUN_INFERENCE
from experiments.inference_safety import joint_limits_ok
from scripts.scripts_config import MANIPULATE_UTILS, PREPARE_ACT_DATASETS


def episode_warnings(qpos, metadata, config=PREPARE_ACT_DATASETS):
    qpos = np.asarray(qpos)
    if qpos.ndim != 2 or qpos.shape[1] != 14 or not np.isfinite(qpos).all():
        raise ValueError('Episode qpos must have shape (frames, 14) and finite values')
    warnings = []
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = RUN_INFERENCE['closed_gripper_command']
    joints = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    for name, frame in (('start', qpos[0]), ('end', qpos[-1])):
        if np.abs(frame[joints] - home[joints]).max() > config['home_tolerance_rad']:
            warnings.append('{} joints differ from home'.format(name))
        if np.abs(frame[[6, 13]] - home[[6, 13]]).max() > config['gripper_tolerance']:
            warnings.append('{} grippers are not closed'.format(name))
    stage, medium = metadata['policy_stage'], metadata['medium']
    idle = 0 if stage == 'B' else 7 if medium != 'envelope' else None
    if idle is not None:
        if np.abs(qpos[:, idle:idle + 6] - home[idle:idle + 6]).max() > config['idle_tolerance_rad']:
            warnings.append('Idle arm moves away from home')
        if np.abs(qpos[:, idle + 6] - home[idle + 6]).max() > config['gripper_tolerance']:
            warnings.append('Idle gripper is not closed throughout episode')
    violations = sum(not joint_limits_ok(frame) for frame in qpos)
    if violations:
        warnings.append('{} frames exceed inference J3/J4 limits (right J4 < {} rad)'.format(
            violations, RUN_INFERENCE['right_j4_max_rad']))
    duration = metadata.get('ended_at', 0) - metadata.get('started_at', 0)
    hz = metadata['frame_count'] / duration if duration > 0 else None
    target = 1000 / CONTROL['control_period_ms']
    if hz is None:
        warnings.append('Missing or invalid episode duration; cannot measure Hz')
    elif abs(hz / target - 1) > config['rate_tolerance_fraction']:
        warnings.append('Measured rate {:.2f} Hz differs by more than {:.0%} from {:.2f} Hz'.format(
            hz, config['rate_tolerance_fraction'], target))
    return hz, warnings
