import numpy as np
from scripts.dataset_checks import episode_warnings
from scripts.scripts_config import MANIPULATE_UTILS


def sample(stage='A', medium='poly_mailer'):
    home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                           np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
    home[[6, 13]] = 1
    return np.tile(home, (25, 1)), dict(policy_stage=stage, medium=medium,
                                       frame_count=25, started_at=10, ended_at=11)


def test_home_idle_and_rate_valid():
    qpos, metadata = sample()
    hz, warnings = episode_warnings(qpos, metadata)
    assert hz == 25
    assert not warnings


def test_b_idle_and_negative_joint_limits():
    qpos, metadata = sample('B')
    qpos[10, 0] += 0.2
    qpos[10, 10] = 0.7
    hz, warnings = episode_warnings(qpos, metadata)
    assert any('Idle arm' in warning for warning in warnings)
    assert any('J3/J4' in warning for warning in warnings)


def test_envelope_exempts_idle_arm():
    qpos, metadata = sample(medium='envelope')
    qpos[10, 0] += 0.2
    assert not episode_warnings(qpos, metadata)[1]


def test_rate_warning():
    qpos, metadata = sample()
    metadata['ended_at'] = 12
    assert any('Measured rate' in warning for warning in episode_warnings(qpos, metadata)[1])
