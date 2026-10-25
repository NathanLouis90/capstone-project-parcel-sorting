"""Operator-stepped commissioning checks using the normal validated motion loop.

Importing this module does not open a robot, camera, or scanner device.
"""
import argparse
import json
from pathlib import Path
import sys
import uuid

import numpy as np
import yaml

from barcode_scanning.scanner_reader import ScanWindow, ScannerReader, destination_mapping
from experiments.experiments_config import SUPERVISOR
from experiments.handoff import home_action
from experiments.scripted_motion import (
    MotionLoop, SimulatedEnv, VirtualClock, load_waypoints, simulation_waypoints,
)


class CheckCancelled(Exception):
    """The operator declined the next move while the robot was stationary."""


def confirm_move(name, target):
    print('{}: joints (degrees) {}'.format(name, np.round(np.rad2deg(target), 2).tolist()), flush=True)
    answer = input('Inspect the complete path. Enter MOVE to execute, or q to finish here: ')
    if answer.strip() != 'MOVE':
        raise CheckCancelled('Stopped at the current pose; no release or return move')


def waypoint_plan(points, start, name):
    """Expand the configured route while preserving both gripper commands."""
    arm = 'left' if name.endswith('_left') else 'right' if name.endswith('_right') else None
    if arm is None:
        raise ValueError('Waypoint name must end in _left or _right')
    offset = 0 if arm == 'left' else 7
    names = list(points.get('routes', {}).get(name, [])) + [name]
    action = np.asarray(start, dtype=float).copy()
    plan = []
    for point in names:
        if point == 'home_' + arm and point == name:
            joints = home_action()[offset:offset + 6]
        elif point not in points['poses'] or not point.endswith('_' + arm):
            raise ValueError('Unknown or wrong-arm waypoint: ' + point)
        else:
            joints = np.asarray(points['poses'][point], dtype=float)
        if np.shape(joints) != (6,) or not np.isfinite(joints).all():
            raise ValueError('Unrecorded waypoint: ' + point)
        action[offset:offset + 6] = joints
        plan.append((point, action.copy()))
    return plan


def wrist_plan(points, start, arm):
    """Visit four faces without a fourth turn or an automatic wrist unwind."""
    offset = 0 if arm == 'left' else 7
    if np.max(np.abs(start[offset:offset + 6] - points['poses']['scan_' + arm])) > .025:
        raise ValueError('Manually position the holding arm at scan_' + arm + ' before the wrist check')
    direction = points.get('rotation_direction', {}).get(arm)
    if direction not in (-1, 1):
        raise ValueError('Set rotation_direction for ' + arm + ' to 1 or -1')
    plan = []
    for degrees in (0, 90, 180, 270):
        target = start.copy()
        target[offset + 5] += direction * np.deg2rad(degrees)
        plan.append((degrees, target))
    return plan


def preflight(points, start, plan, config):
    """Validate every interpolated command before sending any hardware command."""
    clock = VirtualClock()
    simulated = MotionLoop(SimulatedEnv(start), points, config=config,
                           clock=clock, sleep=clock.sleep, grippers=start[[6, 13]])
    simulated.command(start)
    for _, target in plan:
        simulated.move(target)
    return len(simulated.env.commands)


def execute_waypoints(motion, plan, confirm=None, results=None):
    results = [] if results is None else results
    for name, target in plan:
        offset = 0 if name.endswith('_left') else 7
        if confirm is not None:
            confirm(name, target[offset:offset + 6])
        motion.move(target)
        motion.hold(.5)
        observed = motion.observe()['joint_positions']
        result = dict(waypoint=name, target_rad=target[offset:offset + 6].tolist(),
                      observed_rad=observed[offset:offset + 6].tolist(),
                      max_error_rad=float(np.max(np.abs(observed[offset:offset + 6] - target[offset:offset + 6]))))
        results.append(result)
        print(json.dumps(result), flush=True)
        if result['max_error_rad'] > .025:
            raise RuntimeError('Robot drifted away from waypoint ' + name)
    return results


def execute_wrist(motion, plan, window, poll, dwell, arm, confirm=None, after_arm=None, results=None):
    results = [] if results is None else results
    offset = 0 if arm == 'left' else 7
    for degrees, target in plan:
        if confirm is not None:
            confirm('Wrist offset {} degrees'.format(degrees), target[offset:offset + 6])

        def scanner_health():
            poll()
            return None

        # Check reader health during movement, but ignore reads until settled.
        scanner_health()
        motion.move(target, scanner_health)
        motion.hold(.5, scanner_health)
        # Accept only new scans after the robot settles at this orientation.
        window.arm(uuid.uuid4().hex, dwell + .5)
        if after_arm is not None:
            after_arm(degrees)
        event = motion.hold(dwell, poll)
        window.close('no read at this orientation' if event is None else 'closed')
        result = dict(rotation_deg=degrees, scan=event, scanner_status=window.status())
        results.append(result)
        print(json.dumps(result), flush=True)
    return results


def parser_for(description):
    parser = argparse.ArgumentParser(description=description)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='Use a virtual robot; open no devices')
    mode.add_argument('--live', action='store_true', help='Connect to the running follower server')
    parser.add_argument('--waypoints', type=Path, default=Path(SUPERVISOR['waypoint_file']))
    parser.add_argument('--grippers', type=float, nargs=2, metavar=('LEFT', 'RIGHT'),
                        help='Jaw positions, 0=open and 1=closed; required with --live')
    parser.add_argument('--speed', type=float, default=.1, help='Joint speed in radians/s (default: 0.1)')
    parser.add_argument('--report', type=Path, help='Append check results as JSON lines')
    return parser


def check_options(parser, args):
    if not np.isfinite(args.speed) or not 0 < args.speed <= SUPERVISOR['joint_speed_rad_s']:
        parser.error('--speed must be positive and no greater than {}'.format(SUPERVISOR['joint_speed_rad_s']))
    if args.live and not sys.stdin.isatty():
        parser.error('Live movement requires an interactive terminal')
    if args.live and args.grippers is None:
        parser.error('--live requires --grippers LEFT RIGHT for a single check')
    if args.grippers is not None:
        values = np.asarray(args.grippers)
        if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
            parser.error('--grippers values must be finite and in 0..1')


def read_points(args, required):
    if args.waypoints.exists():
        # Commissioning checks intentionally allow commissioned:false. A full
        # cycle still requires commissioned:true through load_waypoints(live=True).
        points = load_waypoints(args.waypoints, required_poses=required)
    elif args.dry_run:
        points = simulation_waypoints()
        points['rotation_direction'] = dict(left=1, right=-1)
    else:
        raise ValueError('Teach local waypoints first: ' + str(args.waypoints))
    if args.live and points.get('simulation_only'):
        raise ValueError('Simulation waypoints cannot be used on hardware')
    return points


def open_motion(args, points, initial=None):
    config = dict(SUPERVISOR, joint_speed_rad_s=args.speed)
    grippers = args.grippers if args.grippers is not None else (1, 1)
    if args.dry_run:
        clock = VirtualClock()
        return MotionLoop(SimulatedEnv(initial), points, config=config,
                          clock=clock, sleep=clock.sleep, grippers=grippers), None
    from experiments.hardware_runtime import LiveRuntime
    runtime = LiveRuntime(with_cameras=False)
    try:
        motion = MotionLoop(runtime.env, points, config=config, stop=runtime.stop,
                            health=runtime.health, grippers=grippers)
    except BaseException:
        runtime.close()
        raise
    return motion, runtime


def append_report(path, report):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as stream:
            stream.write(json.dumps(report) + '\n')


def run_check(args, make_plan, execute, initial=None, evaluate=None):
    runtime = None
    motion = None
    started = False
    report = dict(check_id=uuid.uuid4().hex, dry_run=args.dry_run, results=[],
                  waypoints=str(args.waypoints), speed_rad_s=args.speed,
                  grippers=args.grippers)
    if hasattr(args, 'label_face'):
        report.update(check='wrist', arm=args.arm, label_face=args.label_face)
    else:
        report.update(check='waypoint', waypoint=args.name)
    try:
        points = read_points(args, args.required_poses)
        initial = initial(points) if initial is not None else None
        motion, runtime = open_motion(args, points, initial)
        start = motion.observe()['joint_positions']
        plan = make_plan(points, start)
        count = preflight(points, start, plan, motion.config)
        print('Preflight passed for {} commands. Physical collision clearance is not checked.'.format(count), flush=True)
        print('Starting joints (radians): ' + json.dumps(start.tolist()), flush=True)
        # The execution functions require MOVE before every live step.
        started = True
        execute(motion, plan, report['results'])
        report['outcome'] = 'completed'
        if evaluate is not None:
            report.update(evaluate(report['results']))
        return (0 if report['outcome'] in ('completed', 'success') else 2), report
    except CheckCancelled as error:
        report.update(outcome='cancelled', detail=str(error))
        print(str(error), file=sys.stderr)
        return 130, report
    except (Exception, KeyboardInterrupt) as error:
        report.update(outcome='fault', detail=str(error) or 'Operator interrupted')
        if started and motion is not None:
            try:
                motion.halt()
            except Exception as stop_error:
                report['detail'] += '; stop failed: ' + str(stop_error)
        print(report['detail'], file=sys.stderr)
        return 2, report
    finally:
        if runtime is not None:
            runtime.close()
        append_report(args.report, report)


def waypoint_main(argv=None):
    from experiments.waypoint_menu import (
        check_other_arm_home, configure_motion, display_menu, load_defaults, read_catalog, run_menu,
    )
    parser = argparse.ArgumentParser(
        description='Choose real-robot waypoints. Defaults are in tests/waypoint_config.py; require MOVE before movement.')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--name', help='Optional single check, then exit; omit for the persistent menu')
    selection.add_argument('--list', action='store_true', help='List saved poses without opening devices')
    selection_args = parser.parse_args(argv)
    try:
        args = load_defaults()
    except (OSError, ValueError, KeyError, SyntaxError, TypeError, NameError) as error:
        parser.error('Invalid tests/waypoint_config.py: ' + str(error))
    args.name, args.list = selection_args.name, selection_args.list
    if args.list:
        display_menu(read_catalog(args))
        return 0
    if args.name is None:
        return run_menu(args)
    check_options(parser, args)
    args.required_poses = [] if args.name in ('home_left', 'home_right') else [args.name]

    def make_plan(points, start):
        arm = 'left' if args.name.endswith('_left') else 'right'
        check_other_arm_home(start, arm, SUPERVISOR['waypoint_home_tolerance_rad'])
        return waypoint_plan(points, start, args.name)

    def execute(motion, plan, results):
        configure_motion(motion, args.name)
        return execute_waypoints(motion, plan, confirm_move if args.live else None, results)

    code, _ = run_check(args, make_plan, execute)
    return code


def wrist_main(argv=None):
    parser = parser_for('Check carton scanning at 0, 90, 180 and 270 degree wrist offsets.')
    parser.add_argument('--arm', choices=('left', 'right'), default='left')
    parser.add_argument('--label-face', choices=('top', 'bottom', 'front', 'rear'),
                        help='Known starting label face, for the report')
    parser.add_argument('--dwell', type=float, default=3, help='Stationary scan window in seconds')
    parser.add_argument('--device', help='Dedicated scanner path; configured identity must match')
    parser.add_argument('--expect-token', choices=sorted(destination_mapping()), help='Fail if a different parcel token is read')
    parser.add_argument('--fake-read-at', type=int, choices=(0, 90, 180, 270), help='Dry-run only (default: 90)')
    parser.add_argument('--fake-no-read', action='store_true', help='Dry-run only: simulate no barcode')
    args = parser.parse_args(argv)
    check_options(parser, args)
    if not np.isfinite(args.dwell) or not .1 <= args.dwell <= 120:
        parser.error('--dwell must be finite and between 0.1 and 120 seconds')
    if args.live and (args.fake_read_at is not None or args.fake_no_read):
        parser.error('Fake scanner options require --dry-run')
    args.required_poses = ['scan_' + args.arm]
    reader = None
    window = None

    def execute(motion, plan, results):
        nonlocal reader, window
        window = ScanWindow(clock=motion.clock)
        if args.live:
            reader = ScannerReader(window, args.device).start()

        def poll():
            if reader is not None:
                reader.check_health()
            return window.status()['scan']

        def fake_scan(degrees):
            if not args.fake_no_read and degrees == (90 if args.fake_read_at is None else args.fake_read_at):
                for char in (args.expect_token or next(iter(destination_mapping()))) + '\n':
                    window.feed(char)

        return execute_wrist(motion, plan, window, poll, args.dwell, args.arm,
                             confirm_move if args.live else None, fake_scan if args.dry_run else None, results)

    def initial(points):
        from experiments.handoff import home_action
        action = home_action()
        offset = 0 if args.arm == 'left' else 7
        action[offset:offset + 6] = points['poses']['scan_' + args.arm]
        return action

    def evaluate(results):
        scans = [result['scan'] for result in results if result['scan'] is not None]
        outcome = 'success' if scans else 'no_read'
        if any(args.expect_token is not None and scan['barcode'] != args.expect_token for scan in scans):
            outcome = 'wrong_token'
        print('Sweep complete; {} orientations read. Left at the final scan angle; release and recovery are manual.'.format(len(scans)))
        return dict(outcome=outcome, orientations_read=len(scans))

    try:
        code, _ = run_check(args, lambda points, start: wrist_plan(points, start, args.arm),
                            execute, initial, evaluate)
        return code
    finally:
        if reader is not None:
            reader.close()
