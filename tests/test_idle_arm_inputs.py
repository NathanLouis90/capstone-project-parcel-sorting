"""Check that runtime arm roles match what a checkpoint saw during training."""

import numpy as np
import pytest

from config.settings import MEDIA
from parcel_sorting.policies.robomimic_policy import idle_arm_inputs

HOME_LEFT = [-1.5708, 0.0, -1.5708, 0.0, 1.5708, 1.5708, 0.9942]


def stats(left_moves, right_moves):
    mean = np.array(HOME_LEFT + [1.04, 0.32, 1.59, -0.55, -1.22, -1.63, 0.39])
    std = np.full(14, 0.001)
    std[[6, 13]] = 0.0015
    if left_moves:
        std[0:6] = 0.3
    if right_moves:
        std[7:13] = 0.3
    return {'mean': mean.reshape(1, 14), 'std': std.reshape(1, 14)}


def test_parked_arm_is_fed_its_training_inputs_including_gripper():
    inputs = idle_arm_inputs(stats(left_moves=False, right_moves=True), [0, 1])
    assert list(inputs) == [0]
    np.testing.assert_allclose(inputs[0], HOME_LEFT, rtol=0, atol=1e-6)


def test_commanding_an_arm_that_never_moved_in_training_is_refused():
    with pytest.raises(ValueError, match='left arm never moved'):
        idle_arm_inputs(stats(left_moves=False, right_moves=True), [1, 1])


def test_parking_an_arm_that_moved_in_training_is_refused():
    with pytest.raises(ValueError, match='right arm moved'):
        idle_arm_inputs(stats(left_moves=True, right_moves=True), [1, 0])


def test_both_arms_active_when_both_moved_in_training():
    assert idle_arm_inputs(stats(left_moves=True, right_moves=True), [1, 1]) == {}


def test_mailer_recordings_are_right_arm_only():
    assert MEDIA['poly_mailer']['active_arms'] == [0, 1]
