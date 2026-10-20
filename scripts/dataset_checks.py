"""Hardware-free advisory checks for trusted local demonstration files."""
from pathlib import Path
import numpy as np
import yaml
from experiments.experiments_config import CONTROL, RUN_INFERENCE, SUPERVISOR
from experiments.inference_safety import joint_limits_ok
from experiments.handoff import home_action, HandoffCheck
from scripts.scripts_config import PREPARE_ACT_DATASETS
from barcode_scanning.dataset_metadata import recording_period_ms


def episode_warnings(qpos, metadata, config=PREPARE_ACT_DATASETS, waypoints=None):
    qpos = np.asarray(qpos)
    if qpos.ndim != 2 or not len(qpos) or qpos.shape[1] != 14 or not np.isfinite(qpos).all():
        raise ValueError('Episode qpos must have shape (frames, 14) and finite values')
    warnings = []
    joints = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    if np.max(np.abs(qpos[0, joints] - home_action()[joints])) > config['home_tolerance_rad']:
        warnings.append('Start joints differ from home')
    if np.max(np.abs(qpos[0, [6, 13]] - RUN_INFERENCE['closed_gripper_command'])) > config['gripper_tolerance']:
        warnings.append('Start grippers are not closed')
    if waypoints is None:
        path = Path(SUPERVISOR['waypoint_file'])
        waypoints = yaml.safe_load(path.read_text()) if path.exists() else {}
    from experiments.experiments_config import MEDIA
    key = 'scan_' + MEDIA[metadata['medium']]['holding_arm']
    poses = waypoints.get('poses', waypoints)
    if key not in poses or poses[key] is None:
        warnings.append('Scan pose is unconfigured; teach {}'.format(key))
    else:
        check = HandoffCheck(metadata['medium'], poses[key])
        period = recording_period_ms(metadata) / 1000
        for i, frame in enumerate(qpos):
            settled = check.update(frame, i * period)
        if not settled:
            warnings.append('End must hold the scan pose, closed grippers and idle arm home, settled for 0.5 s')
    violations = sum(not joint_limits_ok(frame) for frame in qpos)
    if violations:
        warnings.append('{} frames exceed inference joint limits'.format(violations))
    duration = metadata.get('ended_at', 0) - metadata.get('started_at', 0)
    hz = metadata.get('frame_count', len(qpos)) / duration if duration > 0 else None
    target = 1000 / CONTROL['control_period_ms']
    if hz is None:
        warnings.append('Missing or invalid episode duration; cannot measure Hz')
    elif abs(hz / target - 1) > config['rate_tolerance_fraction']:
        warnings.append('Measured rate {:.2f} Hz differs from {:.2f} Hz'.format(hz, target))
    return hz, warnings
