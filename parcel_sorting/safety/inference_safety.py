"""Pure checks for proposed 14-D joint/gripper commands; no robot imports."""
import numpy as np
from config.settings import RUNTIME
from parcel_sorting.safety.kinematics import claw_width, forward_kinematics

JOINT_INDICES = (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12)


def validate_joint_gap(action, reference, limit, reason):
    """Check joint angles only and identify the largest offending difference."""
    action, reference = np.asarray(action), np.asarray(reference)
    if (action.shape != (14,) or reference.shape != (14,)
            or not np.isfinite(action).all() or not np.isfinite(reference).all()):
        raise ValueError('Expected 14 finite action/reference values')
    if not np.isfinite(limit) or limit <= 0:
        raise ValueError('Joint gap limit must be positive and finite')
    gaps = np.abs(action[list(JOINT_INDICES)] - reference[list(JOINT_INDICES)])
    if np.max(gaps) > limit:
        index = JOINT_INDICES[int(np.argmax(gaps))]
        arm, joint = ('left', index + 1) if index < 7 else ('right', index - 6)
        raise ValueError('{}: {} J{}, target={:.6f} rad, reference={:.6f} rad, '
                         'difference={:.6f} rad, limit={:.6f} rad'.format(
                             reason, arm, joint, action[index], reference[index],
                             abs(action[index] - reference[index]), limit))


def joint_jump_exceeds(action, previous, limit):
    delta = np.asarray(action) - np.asarray(previous)
    return bool(np.abs(delta[0:6]).max() > limit or np.abs(delta[7:13]).max() > limit)


def prepare_recording_action(action, previous, limit):
    """Preserve leader wrap correction, then enforce the shared command bound."""
    action, previous = np.asarray(action, dtype=float).copy(), np.asarray(previous, dtype=float)
    if (action.shape != (14,) or previous.shape != (14,)
            or not np.isfinite(action).all() or not np.isfinite(previous).all()):
        raise ValueError('Expected 14 finite action/reference values')
    for index in JOINT_INDICES:
        delta = action[index] - previous[index]
        if 1.85 < abs(delta / np.pi) < 2.15:
            action[index] -= np.copysign(2 * np.pi, delta)
    # Correcting a wrap does not excuse a remaining oversized step.
    validate_joint_gap(action, previous, limit, 'Joint increment exceeds configured limit')
    if np.any((action[[6, 13]] < 0) | (action[[6, 13]] > 1)):
        raise ValueError('Gripper command outside 0..1')
    return action


def joint_limits_ok(action, config=RUNTIME):
    return bool(config['left_j3_min_rad'] < action[2] < 0
                and action[3] > config['left_j4_min_rad']
                and 0 < action[9] < config['right_j3_max_rad']
                and action[10] < config['right_j4_max_rad'])


def workspace_violation(action, config=RUNTIME):
    """Describe the first jaw tip outside the configured box, or return None."""
    # claw_width uses the opposite convention to gripper commands.
    # Check the full possible jaw span conservatively until geometry is calibrated.
    width = max(claw_width(0), claw_width(1))
    for side, offset, robot_type in zip(('left', 'right'), (0, 7), config['robot_types']):
        for signed_width in (-width, width):
            xyz = forward_kinematics(*action[offset:offset + 6], signed_width, robot_type) * 1000
            for axis, value, low, high in (
                    ('x', xyz[0], config[side + '_x_min_mm'], config[side + '_x_max_mm']),
                    ('y', xyz[1], config['y_min_mm'], config['y_max_mm']),
                    ('z', xyz[2], config['z_min_mm'], np.inf)):
                if not low < value < high:
                    edge, limit = ('min', low) if value <= low else ('max', high)
                    return '{} jaw tip {}={:.0f} mm, {}_{}={:.0f} mm, beyond by {:.0f} mm'.format(
                        side, axis, value, axis, edge, limit, abs(value - limit))
    return None


def commanded_workspace_ok(action, config=RUNTIME):
    return workspace_violation(action, config) is None


def validate_action(action, previous, config=RUNTIME):
    action = np.asarray(action)
    if action.shape != (14,) or not np.isfinite(action).all():
        raise ValueError('Action must contain 14 finite joint/gripper values')
    validate_joint_gap(action, previous, config['max_joint_increment_rad'],
                       'Joint increment exceeds configured limit')
    if not joint_limits_ok(action, config):
        raise ValueError('Commanded J3/J4 joints exceed configured limits')
    if not commanded_workspace_ok(action, config):
        detail = workspace_violation(action, config)
        raise ValueError('Commanded jaw tips exceed configured workspace' + (': ' + detail if detail else ''))

