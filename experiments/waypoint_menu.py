"""Persistent waypoint commissioning with one moving arm and a home interlock."""

import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import uuid

import numpy as np
import yaml

from experiments.handoff import home_action
from experiments.experiments_config import SUPERVISOR
from experiments.hardware_checks import (
    CheckCancelled, append_report, execute_waypoints, open_motion, preflight,
    read_points, waypoint_plan,
)


class WaypointBlocked(ValueError):
    """A requested movement violates the idle-arm home requirement."""


class MenuQuit(CheckCancelled):
    """The operator requested exit while no movement was in progress."""


def read_catalog(args):
    if args.waypoints.exists():
        points = yaml.safe_load(args.waypoints.read_text())
        if not isinstance(points, dict) or points.get('units') != 'radians':
            raise ValueError('Waypoint file must be a mapping with units: radians')
        if not isinstance(points.get('poses', {}), dict):
            raise ValueError('Waypoint poses must be a mapping')
        return points
    return dict(units='radians', poses={})


def menu_names(points):
    names = ['{}_{}'.format(point, arm) for arm in ('left', 'right')
             for point in ('home', 'scan', 'drop_bin0', 'drop_bin1', 'drop_receiving')]
    names.extend(sorted(name for name in points.get('poses', {})
                        if name.endswith(('_left', '_right')) and name not in names))
    return names


def load_defaults(config_path=None):
    root = Path(__file__).resolve().parent.parent
    path = root / 'tests' / 'waypoint_config.py' if config_path is None else Path(config_path)
    defaults = runpy.run_path(str(path)).get('WAYPOINT_DEFAULTS')
    if not isinstance(defaults, dict):
        raise ValueError('WAYPOINT_DEFAULTS must be a dictionary')
    speed = float(defaults['speed_rad_s'])
    if not np.isfinite(speed) or not 0 < speed <= SUPERVISOR['joint_speed_rad_s']:
        raise ValueError('speed_rad_s must be positive, finite, and at most {}'.format(
            SUPERVISOR['joint_speed_rad_s']))
    grippers = []
    for key in ('left_gripper', 'right_gripper'):
        value = defaults[key]
        if isinstance(value, str):
            value = {'open': 0.0, 'closed': 1.0}.get(value.strip().lower(), value)
        try:
            position = float(value)
        except (TypeError, ValueError):
            raise ValueError('{} must be open, closed, or a number from 0 to 1'.format(key))
        if not np.isfinite(position) or not 0 <= position <= 1:
            raise ValueError('{} must be open, closed, or a number from 0 to 1'.format(key))
        grippers.append(position)

    def resolve(value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else root / path

    report = defaults.get('report_file')
    report = None if report is None else resolve(report)
    if report is not None and report.is_dir():
        raise ValueError('report_file must be a filename or None')
    return SimpleNamespace(live=True, dry_run=False, speed=speed, grippers=grippers,
                           waypoints=resolve(defaults['waypoint_file']), report=report)


def gripper_description(value):
    position = 'open' if value == 0 else 'closed' if value == 1 else 'partial'
    return '{} ({:g})'.format(position, value)


def show_defaults(args):
    print('\nDefaults: tests/waypoint_config.py | Speed: {:g} rad/s ({:.2f} degrees/s)'.format(
        args.speed, np.rad2deg(args.speed)), flush=True)
    print('Left gripper: {} | Right gripper: {}'.format(
        gripper_description(args.grippers[0]), gripper_description(args.grippers[1])), flush=True)
    print('Waypoint report: {}'.format(args.report if args.report is not None else 'off'), flush=True)
    print('Waypoint file: {}'.format(args.waypoints), flush=True)


def display_menu(points, args=None):
    names = menu_names(points)
    if args is not None:
        show_defaults(args)
    print('\nWaypoints (joint angles in degrees):', flush=True)
    print('Return the active arm home before selecting the other arm.', flush=True)
    for number, name in enumerate(names, 1):
        if name in ('home_left', 'home_right'):
            offset = 0 if name == 'home_left' else 7
            pose = home_action()[offset:offset + 6]
            label = 'configured home '
        else:
            pose = points.get('poses', {}).get(name)
            label = ''
        try:
            joints = np.asarray(pose, dtype=float)
            recorded = joints.shape == (6,) and np.isfinite(joints).all()
        except (TypeError, ValueError):
            recorded = False
        angles = label + json.dumps(np.round(np.rad2deg(joints), 2).tolist()) if recorded else 'unrecorded'
        print('{:2d}. {}: {}'.format(number, name, angles), flush=True)
    print('q. Quit without moving, releasing, or returning home.', flush=True)
    return names


def check_other_arm_home(observed, arm, tolerance):
    if arm not in ('left', 'right'):
        raise ValueError('Arm must be left or right')
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Waypoint home tolerance must be positive and finite')
    observed = np.asarray(observed, dtype=float)
    if observed.shape != (14,) or not np.isfinite(observed).all():
        raise ValueError('Invalid robot joint feedback')
    other = 'right' if arm == 'left' else 'left'
    offset = 7 if arm == 'left' else 0
    error = np.max(np.abs(observed[offset:offset + 6] - home_action()[offset:offset + 6]))
    if error > tolerance:
        raise WaypointBlocked(
            '{} arm must be home before moving {} (max joint error {:.4f} rad; tolerance {:.4f}). '
            'Select home_{} first. If both arms are away, use manual recovery.'.format(
                other.capitalize(), arm, error, tolerance, other))


def configure_motion(motion, name):
    arm = 'left' if name.endswith('_left') else 'right'
    tolerance = motion.config['waypoint_home_tolerance_rad']

    def guard(action, observed):
        check_other_arm_home(observed, arm, tolerance)
        check_other_arm_home(action, arm, tolerance)

    motion.active_arm = arm
    motion.command_guard = guard


def confirm_menu_move(name, target, input_fn):
    print('{}: joints (degrees) {}'.format(name, np.round(np.rad2deg(target), 2).tolist()), flush=True)
    answer = input_fn('Inspect the complete path. Enter MOVE, q to quit, or Enter to cancel: ').strip()
    if answer.lower() == 'q':
        raise MenuQuit('Quit at the current pose')
    if answer != 'MOVE':
        raise CheckCancelled('Move cancelled; returning to the menu')


def run_menu(args, input_fn=None):
    input_fn = input if input_fn is None else input_fn
    motion = runtime = None
    try:
        while True:
            try:
                catalog = read_catalog(args)
            except (OSError, ValueError, yaml.YAMLError) as error:
                print('Cannot read waypoint file: {}. Edit tests/waypoint_config.py and restart.'.format(error), flush=True)
                catalog = dict(poses={})
            names = display_menu(catalog, args)
            choice = input_fn('Select a waypoint number or name, or q: ').strip()
            if choice.lower() == 'q':
                return 0
            name = names[int(choice) - 1] if choice.isdecimal() and 1 <= int(choice) <= len(names) else choice
            if name not in names:
                print('Unknown selection; choose a listed waypoint or q.', flush=True)
                continue
            if name not in ('home_left', 'home_right') and catalog.get('poses', {}).get(name) is None:
                print('{} is unrecorded; teach it before moving.'.format(name), flush=True)
                continue
            report = dict(check_id=uuid.uuid4().hex, check='waypoint', waypoint=name,
                          menu=True, dry_run=args.dry_run, results=[], waypoints=str(args.waypoints),
                          speed_rad_s=args.speed, grippers=args.grippers)
            started = False
            try:
                if not sys.stdin.isatty():
                    raise ValueError('Robot movement requires an interactive terminal')
                grippers = args.grippers
                report['grippers'] = grippers
                required = [] if name in ('home_left', 'home_right') else [name]
                points = read_points(args, required)
                if motion is None:
                    motion, runtime = open_motion(args, points)
                motion.waypoints = points
                motion.config = dict(motion.config, joint_speed_rad_s=args.speed)
                motion.last_action[[6, 13]] = grippers
                configure_motion(motion, name)
                start = motion.observe()['joint_positions']
                arm = 'left' if name.endswith('_left') else 'right'
                check_other_arm_home(start, arm, motion.config['waypoint_home_tolerance_rad'])
                plan = waypoint_plan(points, start, name)
                count = preflight(points, start, plan, motion.config)
                print('Preflight passed for {} commands. Inspect physical clearance before MOVE.'.format(count), flush=True)

                def confirm(point, target):
                    nonlocal started
                    confirm_menu_move(point, target, input_fn)
                    started = True

                execute_waypoints(motion, plan, confirm, report['results'])
                report['outcome'] = 'completed'
            except MenuQuit as error:
                report.update(outcome='cancelled', detail=str(error))
                return 0
            except CheckCancelled as error:
                report.update(outcome='cancelled', detail=str(error))
                print(str(error), flush=True)
            except (ValueError, KeyError) as error:
                report.update(outcome='fault' if started else 'blocked', detail=str(error))
                print(str(error), file=sys.stderr, flush=True)
                if started:
                    try:
                        motion.halt()
                    except Exception as stop_error:
                        report['detail'] += '; stop failed: ' + str(stop_error)
                    return 2
            except (Exception, KeyboardInterrupt) as error:
                report.update(outcome='fault', detail=str(error) or 'Operator interrupted')
                if started and motion is not None:
                    try:
                        motion.halt()
                    except Exception as stop_error:
                        report['detail'] += '; stop failed: ' + str(stop_error)
                print(report['detail'], file=sys.stderr, flush=True)
                return 2
            finally:
                append_report(args.report, report)
    except (MenuQuit, EOFError, KeyboardInterrupt):
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr, flush=True)
        return 2
    finally:
        if runtime is not None:
            runtime.close()
