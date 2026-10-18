import numpy as np
import pytest
from experiments.inference_safety import joint_jump_exceeds, resolve_episode_length, validate_action
from experiments.kinematics import forward_kinematics
from scripts.control_timing import wait_period


@pytest.mark.parametrize('index', [0, 5, 7, 12])
@pytest.mark.parametrize('jump', [-0.18, 0.18])
def test_joint_jump_both_directions(index, jump):
    previous = np.zeros(14)
    proposed = previous.copy()
    proposed[index] = jump
    assert joint_jump_exceeds(proposed, previous, 0.17)


def test_grippers_do_not_trigger_joint_jump():
    proposed = np.zeros(14)
    proposed[[6, 13]] = 1
    assert not joint_jump_exceeds(proposed, np.zeros(14), 0.17)


def test_invalid_action_rejected():
    with pytest.raises(ValueError, match='finite'):
        validate_action(np.full(14, np.nan), np.zeros(14))


def test_task_horizon():
    tasks = {'parcel': {'episode_len': 400}}
    assert resolve_episode_length('parcel', None, tasks) == 400
    with pytest.raises(ValueError):
        resolve_episode_length('parcel', 401, tasks)
    with pytest.raises(ValueError):
        resolve_episode_length('unknown', 1, tasks)


def test_pacing_and_overrun():
    sleeps = []
    wait_period(40, 1, clock=lambda: 1.01, sleep=sleeps.append)
    assert sleeps == pytest.approx([0.03])
    wait_period(40, 1, clock=lambda: 1.05, sleep=sleeps.append)
    assert len(sleeps) == 1


def test_unsupported_robot_type_fails_closed():
    with pytest.raises(ValueError):
        forward_kinematics(0, 0, 0, 0, 0, 0, 0, 'unknown')


def test_commanded_workspace_checked_before_action(monkeypatch):
    import experiments.inference_safety as safety
    previous = np.zeros(14)
    previous[2], previous[9] = -1, 1
    proposed = previous.copy()
    proposed[0] = 0.05
    checked = []

    def commanded_fk(*args):
        checked.append(args[0])
        return np.array([10., -0.4, 0.2])  # commanded endpoint outside workspace

    monkeypatch.setattr(safety, 'forward_kinematics', commanded_fk)
    with pytest.raises(ValueError, match='workspace'):
        safety.validate_action(proposed, previous)
    assert checked == [0.05]


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf])
def test_nonfinite_gripper_prediction_rejected_before_clipping(value):
    from experiments.inference_safety import prepare_vendor_action
    prediction = np.zeros(16)
    prediction[6] = value
    with pytest.raises(ValueError, match='finite'):
        prepare_vendor_action(prediction)


def test_vendor_base_dimensions_removed_and_grippers_clipped():
    from experiments.inference_safety import prepare_vendor_action
    prediction = np.zeros(16)
    prediction[[6, 13]] = [-1, 2]
    action = prepare_vendor_action(prediction)
    assert action.shape == (14,)
    np.testing.assert_array_equal(action[[6, 13]], [0, 1])


def test_medium_metadata_required():
    from experiments.inference_safety import resolve_task_metadata
    assert resolve_task_metadata('poly_mailer', {'poly_mailer': {'medium': 'poly_mailer'}}, {}) == {'medium': 'poly_mailer'}
    with pytest.raises(ValueError): resolve_task_metadata('unknown', {}, {})
