"""Separate command steps, feedback lag, and initial policy alignment without hardware."""
import json

import h5py
import numpy as np
import pytest

from parcel_sorting.safety import inference_safety
from config.settings import RUNTIME, SUPERVISOR
from parcel_sorting.safety.handoff import home_action
from parcel_sorting.safety.inference_safety import JOINT_INDICES, prepare_recording_action, validate_joint_gap
from parcel_sorting.runtime.cycle import Cycle, FakeScanner
from parcel_sorting.runtime.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints
from parcel_sorting.training.rollout_compatibility import audit_dataset, main as audit_main
from config.settings import MANIPULATE_UTILS


@pytest.fixture
def motion(monkeypatch):
    # These tests isolate joint gaps; workspace rejection is tested separately.
    monkeypatch.setattr(inference_safety, 'commanded_workspace_ok', lambda action, config: True)
    clock = VirtualClock()
    return MotionLoop(SimulatedEnv(), simulation_waypoints(), clock=clock, sleep=clock.sleep)


def target(offset, index=0):
    action = home_action()
    action[index] += offset
    return action


def test_recording_and_rollout_share_bounds():
    assert MANIPULATE_UTILS['servo_max_delta_rad'] == RUNTIME['max_joint_increment_rad'] == 0.17
    assert MANIPULATE_UTILS['obs_max_delta_rad'] == SUPERVISOR['tracking_tolerance_rad'] == 0.6
    assert MANIPULATE_UTILS['pose_max_delta_rad'] == SUPERVISOR['policy_approach_max_rad'] == 0.6
    assert SUPERVISOR['policy_approach_speed_rad_s'] == pytest.approx(
        MANIPULATE_UTILS['approach_step_rad'] * 1000 / MANIPULATE_UTILS['approach_period_ms'])


@pytest.mark.parametrize('sign', [-1, 1])
def test_recording_wrap_correction_still_enforces_command_step(sign):
    action = target(sign * (2 * np.pi + 0.1))
    corrected = prepare_recording_action(action, home_action(), 0.17)
    assert corrected[0] == pytest.approx(home_action()[0] + sign * 0.1)
    np.testing.assert_allclose(action, target(sign * (2 * np.pi + 0.1)))
    with pytest.raises(ValueError, match='Joint increment'):
        prepare_recording_action(target(sign * (2 * np.pi + 0.3)), home_action(), 0.17)


@pytest.mark.parametrize('offset', [-0.61, 0.61])
def test_recording_alignment_checks_both_directions(offset):
    with pytest.raises(ValueError, match='tracking'):
        validate_joint_gap(target(offset), home_action(), 0.6, 'Leader tracking limit')


def test_feedback_lag_is_not_treated_as_a_command_increment(motion):
    # Last target leads feedback by 0.3 rad, while the new command changes by 0.01.
    motion.last_action = target(0.3)
    motion.command(target(0.31))
    assert len(motion.env.commands) == 1


def test_later_command_jump_still_faults_with_joint_details(motion):
    with pytest.raises(ValueError, match=r'Joint increment.*left J1.*difference=0.200000.*limit=0.170000'):
        motion.command_policy(target(0.2))
    assert not motion.env.commands


def test_initial_approach_sends_only_small_paced_steps(motion):
    assert motion.command_policy(target(0.3), initial=True, deadline=10)
    sent = np.stack([home_action()] + motion.env.commands)
    assert np.abs(np.diff(sent[:, list(JOINT_INDICES)], axis=0)).max() <= 0.008 + 1e-12
    np.testing.assert_allclose(sent[-1], target(0.3))
    assert motion.clock() >= 0.3 / SUPERVISOR['policy_approach_speed_rad_s']


def test_small_first_target_does_not_add_an_approach(motion):
    assert not motion.command_policy(target(0.01), initial=True)
    assert len(motion.env.commands) == 1


def test_large_initial_target_is_rejected_before_movement(motion):
    with pytest.raises(ValueError, match='limit=0.600000'):
        motion.command_policy(target(0.61), initial=True)
    assert not motion.env.commands


def test_unsafe_raw_target_is_not_hidden_by_small_approach_steps(motion, monkeypatch):
    monkeypatch.setattr(inference_safety, 'commanded_workspace_ok',
                        lambda action, config: action[0] < home_action()[0] + 0.25)
    with pytest.raises(ValueError, match='workspace'):
        motion.command_policy(target(0.3), initial=True)
    assert not motion.env.commands


def test_initial_target_respects_taught_cable_limits(motion):
    motion.waypoints['joint_limits_rad'][0][1] = home_action()[0] + 0.2
    with pytest.raises(ValueError, match='taught joint/cable limits'):
        motion.command_policy(target(0.3), initial=True)
    assert not motion.env.commands


@pytest.mark.parametrize('invalid_gripper', [-0.1, 1.1, float('nan')])
def test_initial_approach_rejects_invalid_gripper_commands(motion, invalid_gripper):
    action = target(0.3)
    action[13] = invalid_gripper
    with pytest.raises(ValueError):
        motion.command_policy(action, initial=True)
    assert not motion.env.commands


def test_initial_approach_respects_rollout_deadline(motion):
    with pytest.raises(TimeoutError, match='timeout'):
        motion.command_policy(target(0.3), initial=True, deadline=0.1)
    assert motion.clock() < 0.1 + 0.04
    assert len(motion.env.commands) == 3


def test_feedback_divergence_still_faults(motion):
    motion.env.action = target(-0.61)
    with pytest.raises(ValueError, match='Robot feedback diverged'):
        motion.command(target(0.01))
    assert not motion.env.commands


def test_new_target_also_respects_measured_feedback_bound(motion):
    motion.env.action = target(-0.5)
    with pytest.raises(ValueError, match='Target exceeds measured tracking limit'):
        motion.command(target(0.11))
    assert not motion.env.commands


def test_joint_diagnostics_name_right_arm_and_exclude_grippers():
    action = target(0.2, index=12)
    with pytest.raises(ValueError, match='right J6'):
        validate_joint_gap(action, home_action(), 0.17, 'Too far')
    action = home_action()
    action[[6, 13]] = 0
    validate_joint_gap(action, home_action(), 0.17, 'Too far')


def make_dataset(path, offsets=(0.25, 0.26), split='train'):
    actions = np.stack([target(offset) for offset in offsets])
    with h5py.File(str(path), 'w') as output:
        demo = output.create_group('data/demo_0')
        demo.create_dataset('actions', data=actions)
        demo.create_dataset('obs/qpos', data=np.stack([home_action()] * len(actions)))
        output.create_dataset('mask/' + split, data=np.asarray(['demo_0'], dtype='S'))
    return path


def test_audit_distinguishes_lag_from_command_steps(tmp_path):
    report = audit_dataset(make_dataset(tmp_path / 'data.hdf5'))
    assert report['compatible_joint_gaps']
    assert report['maximum_gaps_rad']['command_step'] == pytest.approx(0.01)
    assert report['maximum_gaps_rad']['target_tracking'] == pytest.approx(0.26)
    assert report['initial_targets_needing_approach'] == 1


def test_audit_reports_recordings_that_need_fixing(tmp_path):
    report = audit_dataset(make_dataset(tmp_path / 'data.hdf5', offsets=(0.2, 0.4)))
    assert not report['compatible_joint_gaps']
    assert report['violations']['command_step'] == 1


def test_audit_cli_uses_the_dataset_saved_in_checkpoint(tmp_path, capsys):
    import torch
    dataset = make_dataset(tmp_path / 'data.hdf5')
    checkpoint = tmp_path / 'best.pth'
    torch.save({'config': json.dumps({'train': {'data': [{'path': str(dataset)}]}})}, str(checkpoint))
    assert audit_main(['--checkpoint', str(checkpoint)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['dataset'] == str(dataset)
    assert report['frames'] == 2


def test_cycle_resets_policy_history_after_initial_approach(motion, tmp_path, monkeypatch):
    from parcel_sorting.runtime import cycle as run_cycle

    class Handoff:
        def __init__(self, *args):
            self.calls = 0

        def update(self, *args):
            self.calls += 1
            return self.calls >= 3

    class Policy:
        policy_type = 'ACT'
        resets = 0

        def reset(self):
            self.resets += 1

        def step(self, observation):
            return target(0.3)

    monkeypatch.setattr(run_cycle, 'HandoffCheck', Handoff)
    policy = Policy()
    cycle = Cycle(motion, policy, FakeScanner('DEST-A-S138683'), 'poly_mailer',
                  tmp_path / 'cycles.csv', dry_run=True, outcome=lambda: 'success')
    row = cycle.run()
    assert row['outcome'] == 'success'
    assert policy.resets == 2
    assert row['t_pick_s'] >= 0.3 / SUPERVISOR['policy_approach_speed_rad_s']


def test_cycle_fault_stops_without_sending_an_out_of_bounds_initial_target(motion, tmp_path):
    class Policy:
        policy_type = 'ACT'

        def reset(self):
            pass

        def step(self, observation):
            return target(0.61)

    scanner = FakeScanner('DEST-A-S138683')
    row = Cycle(motion, Policy(), scanner, 'poly_mailer', tmp_path / 'cycles.csv', dry_run=True).run()
    assert row['outcome'] == 'fault'
    assert 'limit=0.600000' in row['fault_detail']
    assert not motion.env.commands
    assert motion.env.stopped
    assert not hasattr(scanner, 'cycle_id')


def test_workspace_fault_names_the_arm_axis_and_overshoot():
    action = home_action()
    config = dict(RUNTIME, right_x_min_mm=500)
    with pytest.raises(ValueError, match=r'right jaw tip x=.* mm, x_min=500 mm, beyond by \d+ mm'):
        inference_safety.validate_action(action, home_action(), config)
