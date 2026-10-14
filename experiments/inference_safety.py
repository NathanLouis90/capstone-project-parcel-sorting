"""Pure checks for proposed 14-D joint/gripper commands; no robot imports."""
import numpy as np
from experiments.experiments_config import RUN_INFERENCE
from experiments.kinematics import claw_width, forward_kinematics


def joint_jump_exceeds(action, previous, limit):
    delta = np.asarray(action) - np.asarray(previous)
    return bool(np.abs(delta[0:6]).max() > limit or np.abs(delta[7:13]).max() > limit)


def joint_limits_ok(action, config=RUN_INFERENCE):
    return bool(config['left_j3_min_rad'] < action[2] < 0
                and action[3] > config['left_j4_min_rad']
                and 0 < action[9] < config['right_j3_max_rad']
                and action[10] < config['right_j4_max_rad'])


def commanded_workspace_ok(action, config=RUN_INFERENCE):
    # The legacy claw_width convention disagrees with the command convention.
    # Check the full possible jaw span conservatively until geometry is calibrated.
    width = max(claw_width(0), claw_width(1))
    for side, offset, robot_type in zip(('left', 'right'), (0, 7), config['robot_types']):
        for signed_width in (-width, width):
            xyz = forward_kinematics(*action[offset:offset + 6], signed_width, robot_type) * 1000
            if not (config[side + '_x_min_mm'] < xyz[0] < config[side + '_x_max_mm']
                    and config['y_min_mm'] < xyz[1] < config['y_max_mm']
                    and xyz[2] > config['z_min_mm']):
                return False
    return True


def validate_action(action, previous, config=RUN_INFERENCE):
    action = np.asarray(action)
    if action.shape != (14,) or not np.isfinite(action).all():
        raise ValueError('Action must contain 14 finite joint/gripper values')
    if joint_jump_exceeds(action, previous, config['max_joint_increment_rad']):
        raise ValueError('Joint increment exceeds configured limit')
    if not joint_limits_ok(action, config):
        raise ValueError('Commanded J3/J4 joints exceed configured limits')
    if not commanded_workspace_ok(action, config):
        raise ValueError('Commanded jaw tips exceed configured workspace')


def resolve_episode_length(task, requested, tasks):
    if task not in tasks:
        raise ValueError('Unknown task: {}'.format(task))
    limit = tasks[task]['episode_len']
    length = limit if requested is None else requested
    if length <= 0 or length > limit:
        raise ValueError('Requested length must be in 1..{} for {}'.format(limit, task))
    return length
