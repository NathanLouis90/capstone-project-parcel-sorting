"""Shared pose and finite-difference settling checks, without hardware imports."""
import numpy as np
from experiments.experiments_config import MEDIA, RUN_INFERENCE, SUPERVISOR
from experiments.kinematics import forward_kinematics
from scripts.scripts_config import MANIPULATE_UTILS, PREPARE_ACT_DATASETS


def home_action():
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = RUN_INFERENCE['closed_gripper_command']
    return home


def arm_pose(joints, arm):
    side = 0 if arm == 'left' else 1
    return forward_kinematics(*np.asarray(joints)[:6], 0,
                              RUN_INFERENCE['robot_types'][side], return_transform=True)


def handoff_pose_ok(action, medium, scan_joints, config=SUPERVISOR):
    action = np.asarray(action)
    if action.shape != (14,) or not np.isfinite(action).all():
        return False
    arm = MEDIA[medium]['holding_arm']
    offset, idle = (0, 7) if arm == 'left' else (7, 0)
    target, actual = arm_pose(scan_joints, arm), arm_pose(action[offset:offset + 6], arm)
    position = np.linalg.norm(actual[:3, 3] - target[:3, 3])
    cosine = (np.trace(target[:3, :3].T @ actual[:3, :3]) - 1) / 2
    orientation = np.arccos(np.clip(cosine, -1, 1))
    return bool(position <= config['position_tolerance_m']
                and orientation <= config['orientation_tolerance_rad']
                and np.max(np.abs(action[idle:idle + 6] - home_action()[idle:idle + 6]))
                <= PREPARE_ACT_DATASETS['idle_tolerance_rad']
                and np.max(np.abs(action[[6, 13]] - RUN_INFERENCE['closed_gripper_command']))
                <= PREPARE_ACT_DATASETS['gripper_tolerance'])


class HandoffCheck:
    def __init__(self, medium, scan_joints, config=SUPERVISOR):
        self.medium, self.scan_joints, self.config = medium, scan_joints, config
        self.previous = self.previous_time = self.stable_since = None

    def update(self, action, timestamp):
        action = np.asarray(action, dtype=float)
        valid = handoff_pose_ok(action, self.medium, self.scan_joints, self.config)
        if self.previous is None or timestamp <= self.previous_time:
            valid = False
        else:
            joints = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
            speed = np.max(np.abs(action[joints] - self.previous[joints])) / (timestamp - self.previous_time)
            valid = valid and speed <= self.config['velocity_threshold_rad_s']
        if not valid:
            self.stable_since = None
        elif self.stable_since is None:
            self.stable_since = timestamp
        self.previous, self.previous_time = action.copy(), timestamp
        return valid and timestamp - self.stable_since >= self.config['settle_s'] - 1e-9
