"""Gripper commands follow the recordings: 1.0 opens the jaws and 0.0 closes them."""

import numpy as np

from parcel_sorting.safety import inference_safety
from config.settings import RUNTIME
from parcel_sorting.safety.handoff import handoff_pose_ok, home_action
from parcel_sorting.runtime.cycle import Cycle, FakeScanner
from parcel_sorting.policies.policy_step import SimulatedPolicy
from parcel_sorting.runtime.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints

OPEN, CLOSED = RUNTIME['open_gripper_command'], RUNTIME['closed_gripper_command']


def scan_action(holding, idle):
    points = simulation_waypoints()
    action = home_action()
    action[7:13] = points['poses']['scan_right']
    action[13], action[6] = holding, idle
    return action, points['poses']['scan_right']


def test_convention_matches_recordings():
    assert (OPEN, CLOSED) == (1.0, 0.0)
    assert home_action()[[6, 13]].tolist() == [OPEN, OPEN]


def test_handoff_requires_a_closed_holding_gripper_and_an_open_idle_gripper():
    action, scan = scan_action(holding=CLOSED, idle=OPEN)
    assert handoff_pose_ok(action, 'poly_mailer', scan)
    for holding, idle in ((OPEN, OPEN), (CLOSED, CLOSED)):
        action, scan = scan_action(holding, idle)
        assert not handoff_pose_ok(action, 'poly_mailer', scan)


def test_drop_opens_the_holding_gripper(monkeypatch, tmp_path):
    monkeypatch.setattr(inference_safety, 'commanded_workspace_ok', lambda action, config: True)
    clock = VirtualClock()
    points = simulation_waypoints()
    motion = MotionLoop(SimulatedEnv(), points, clock=clock, sleep=clock.sleep)
    cycle = Cycle(motion, SimulatedPolicy('poly_mailer', points['poses']['scan_right']),
                  FakeScanner('DEST-A-S138683'), 'poly_mailer', tmp_path / 'cycles.csv',
                  dry_run=True, outcome=lambda: 'success')
    assert cycle.run()['outcome'] == 'success'
    right = np.array([command[13] for command in motion.env.commands])
    first_open_after_hold = np.argmax((right == OPEN) & (np.arange(len(right)) > np.argmax(right == CLOSED)))
    assert right.min() == CLOSED and first_open_after_hold > 0
    assert motion.env.commands[-1][[6, 13]].tolist() == [OPEN, OPEN]


def test_waypoint_check_gripper_words_follow_runtime_convention(tmp_path):
    from parcel_sorting.runtime.waypoint_menu import gripper_description, load_defaults
    config = tmp_path / 'settings.py'
    config.write_text('WAYPOINT_DEFAULTS = {"speed_rad_s": 0.1, "left_gripper": "closed", '
                      '"right_gripper": "open", "waypoint_file": "waypoints.yaml", "report_file": None}\n')
    defaults = load_defaults(config)
    assert defaults.grippers == [CLOSED, OPEN]
    assert gripper_description(OPEN).startswith('open')
    assert gripper_description(CLOSED).startswith('closed')
