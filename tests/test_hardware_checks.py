"""Hardware-free guards for the three manual check entry points."""
import json

import numpy as np
import pytest
import yaml

from experiments.experiments_config import SUPERVISOR
from experiments.handoff import home_action
from experiments.hardware_checks import (
    CheckCancelled, execute_waypoints, execute_wrist, preflight, waypoint_main, waypoint_plan,
    wrist_main, wrist_plan,
)
from experiments.run_cycle import main as cycle_main
from experiments.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints


def points_and_motion():
    points = simulation_waypoints()
    points['rotation_direction'] = dict(left=1, right=-1)
    clock = VirtualClock()
    motion = MotionLoop(SimulatedEnv(), points, clock=clock, sleep=clock.sleep, grippers=(.4, .7))
    return points, motion


def test_waypoint_route_preserves_other_arm_and_both_grippers():
    points, motion = points_and_motion()
    points['routes']['drop_bin0_left'] = ['scan_left']
    start = motion.observe()['joint_positions']
    plan = waypoint_plan(points, start, 'drop_bin0_left')
    preflight(points, start, plan, SUPERVISOR)
    execute_waypoints(motion, plan)
    assert [name for name, _ in plan] == ['scan_left', 'drop_bin0_left']
    for command in motion.env.commands:
        np.testing.assert_array_equal(command[7:13], start[7:13])
        np.testing.assert_array_equal(command[[6, 13]], [.4, .7])


def test_declining_move_sends_no_command():
    points, motion = points_and_motion()
    plan = waypoint_plan(points, motion.last_action, 'drop_bin0_left')

    def decline(*args):
        raise CheckCancelled()

    with pytest.raises(CheckCancelled):
        execute_waypoints(motion, plan, decline)
    assert not motion.env.commands


@pytest.mark.parametrize('arm,offset,direction', [('left', 0, 1), ('right', 7, -1)])
def test_wrist_preflight_rejects_later_cable_limit_without_live_commands(arm, offset, direction):
    points, motion = points_and_motion()
    start = home_action()
    start[offset:offset + 6] = points['poses']['scan_' + arm]
    plan = wrist_plan(points, start, arm)
    assert [degrees for degrees, _ in plan] == [0, 90, 180, 270]
    assert plan[-1][1][offset + 5] == pytest.approx(start[offset + 5] + direction * 1.5 * np.pi)
    points['joint_limits_rad'][5 if arm == 'left' else 11] = [-2, 2]
    with pytest.raises(ValueError, match='joint/cable'):
        preflight(points, start, plan, SUPERVISOR)
    assert not motion.env.commands


def test_wrist_requires_taught_start_pose():
    points, _ = points_and_motion()
    with pytest.raises(ValueError, match='Manually position'):
        wrist_plan(points, home_action(), 'left')


def test_scanner_failure_blocks_wrist_move():
    from barcode_scanning.scanner_reader import ScanWindow
    points, motion = points_and_motion()
    start = home_action()
    start[:6] = points['poses']['scan_left']
    plan = wrist_plan(points, start, 'left')

    def failed_reader():
        raise RuntimeError('Scanner disconnected')

    with pytest.raises(RuntimeError, match='Scanner disconnected'):
        execute_wrist(motion, plan, ScanWindow(), failed_reader, 1, 'left')
    assert not motion.env.commands


@pytest.mark.parametrize('entry,args', [
    (waypoint_main, ['--name', 'scan_left']),
    (wrist_main, []),
])
def test_live_requires_explicit_grippers_before_connecting(entry, args, monkeypatch):
    import experiments.hardware_runtime as hardware
    monkeypatch.setattr(hardware, 'LiveRuntime', lambda **kwargs: pytest.fail('Must not connect'))
    with pytest.raises(SystemExit) as error:
        entry(['--live'] + args)
    assert error.value.code == 2


def test_simulation_file_cannot_be_used_for_live_commissioning(tmp_path, monkeypatch):
    import experiments.hardware_runtime as hardware
    import sys
    path = tmp_path / 'points.yaml'
    path.write_text(yaml.safe_dump(simulation_waypoints()))
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(hardware, 'LiveRuntime', lambda **kwargs: pytest.fail('Must not connect'))
    assert waypoint_main(['--live', '--grippers', '1', '1', '--name', 'scan_left', '--waypoints', str(path)]) == 2


def test_partial_taught_file_can_be_checked_without_commissioning(tmp_path):
    points = simulation_waypoints()
    points['poses'] = {'scan_left': points['poses']['scan_left']}
    path = tmp_path / 'points.yaml'
    path.write_text(yaml.safe_dump(points))
    assert waypoint_main(['--dry-run', '--name', 'scan_left', '--waypoints', str(path)]) == 0


def test_fault_stops_without_return_move_and_keeps_progress(tmp_path, monkeypatch):
    import experiments.hardware_checks as checks
    points, motion = points_and_motion()
    points['routes']['drop_bin0_left'] = ['scan_left']
    path = tmp_path / 'points.yaml'
    path.write_text(yaml.safe_dump(points))
    report = tmp_path / 'report.jsonl'
    monkeypatch.setattr(checks, 'open_motion', lambda *args: (motion, None))
    original = motion.move
    count = [0]

    def fail_second(target):
        count[0] += 1
        if count[0] == 2:
            raise RuntimeError('Injected tracking fault')
        return original(target)

    monkeypatch.setattr(motion, 'move', fail_second)
    code = waypoint_main(['--dry-run', '--name', 'drop_bin0_left', '--waypoints', str(path), '--report', str(report)])
    row = json.loads(report.read_text())
    assert code == 2
    assert motion.env.stopped
    assert row['outcome'] == 'fault'
    assert [result['waypoint'] for result in row['results']] == ['scan_left']
    assert count[0] == 2


@pytest.mark.parametrize('no_read', [False, True])
def test_wrist_scan_is_fresh_at_each_stationary_orientation(tmp_path, no_read):
    report = tmp_path / 'report.jsonl'
    args = ['--dry-run', '--waypoints', str(tmp_path / 'missing.yaml'), '--report', str(report)]
    args += ['--fake-no-read'] if no_read else ['--fake-read-at', '180']
    assert wrist_main(args) == (2 if no_read else 0)
    row = json.loads(report.read_text())
    assert row['outcome'] == ('no_read' if no_read else 'success')
    assert [result['rotation_deg'] for result in row['results']] == [0, 90, 180, 270]
    assert [result['rotation_deg'] for result in row['results'] if result['scan']] == ([] if no_read else [180])


@pytest.mark.parametrize('token,bin_index', [('DEST-A-S138683', 0), ('DEST-B-S828608', 1)])
def test_full_cycle_maps_each_scanned_destination(tmp_path, capsys, token, bin_index):
    code = cycle_main(['--medium', 'poly_mailer', '--dry-run', '--fake-token', token,
                       '--waypoints', str(tmp_path / 'missing.yaml'), '--csv', str(tmp_path / 'cycle.csv')])
    row = json.loads(capsys.readouterr().out)
    assert code == 0
    assert row['outcome'] == 'success'
    assert row['bin'] == bin_index


def test_full_cycle_no_read_does_not_select_a_bin(tmp_path, capsys):
    code = cycle_main(['--medium', 'poly_mailer', '--dry-run',
                       '--waypoints', str(tmp_path / 'missing.yaml'), '--csv', str(tmp_path / 'cycle.csv')])
    row = json.loads(capsys.readouterr().out)
    assert code == 2
    assert row['outcome'] == 'no_read'
    assert row['bin'] == ''
