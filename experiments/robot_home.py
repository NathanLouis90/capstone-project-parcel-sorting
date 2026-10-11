#!/usr/bin/env python3
"""Inspect, recover, lift, or explicitly home Dobot V3 controllers.

No robot SDK, cameras, leader arms, gripper commands, or ZMQ server are needed.
Run without flags to inspect status. See --help before using --move.
"""
from pathlib import Path as _ConfigPath
import sys as _config_sys
_config_sys.path.insert(0, str(_ConfigPath(__file__).resolve().parent))
from experiments_config import ROBOT_HOME


import argparse
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
import time
from contextlib import ExitStack


ARMS = ROBOT_HOME["ARMS"]
MODES = {3: "powered off", 4: "disabled", 5: "enabled and idle", 6: "dragging",
         7: "running", 8: "single movement", 9: "error", 10: "paused", 11: "jogging"}
ALARM_DESCRIPTIONS = {-2: "collision detection", -3: "safety skin collision detection"}


class ControllerError(RuntimeError):
    pass


def parse_reply(reply, command):
    match = re.fullmatch(r"\s*(-?\d+)\s*,\s*\{(.*)\}\s*,\s*(\w+)\(.*\);\s*",
                         reply, re.DOTALL)
    if not match or match[3] != command.split("(", 1)[0]:
        raise ControllerError("Malformed or unexpected reply: {!r}".format(reply))
    if int(match[1]) != 0:
        raise ControllerError("Command rejected: " + reply.strip())
    return match[2].strip()


class Channel:
    def __init__(self, ip, port):
        self.socket = socket.create_connection((ip, port), timeout=ROBOT_HOME["socket_timeout_s"])
        self.buffer = b""

    def close(self):
        self.socket.close()

    def command(self, command):
        self.socket.sendall(command.encode("ascii"))
        while b";" not in self.buffer:
            data = self.socket.recv(4096)
            if not data:
                raise ControllerError("Controller closed the connection")
            self.buffer += data
            if len(self.buffer) > 65536:
                raise ControllerError("Controller reply is too large")
        reply, self.buffer = self.buffer.split(b";", 1)
        return parse_reply(reply.decode("utf-8") + ";", command)


def status(dashboard):
    mode = int(dashboard.command("RobotMode()"))
    alarms = json.loads(dashboard.command("GetErrorID()"))
    if (not isinstance(alarms, list) or len(alarms) != 7 or
            any(not isinstance(group, list) or
                any(type(code) is not int for code in group) for group in alarms)):
        raise ControllerError("Unexpected alarm data: {!r}".format(alarms))
    return mode, alarms


def require_no_alarms(alarms):
    if any(alarms):
        raise ControllerError("Active alarms: {}. Resolve the cause before recovery or movement.".format(alarms))


def check_preflight(mode, alarms, args):
    if mode not in (3, 4, 5, 9):
        raise ControllerError("Controller must be stopped; current mode is {}".format(mode))
    if any(alarms) and not args.clear_errors:
        require_no_alarms(alarms)
    if mode == 9 and not args.clear_errors:
        raise ControllerError("Error mode requires resolving the cause and --clear-errors")
    if mode == 3 and not args.power_on:
        raise ControllerError("Arm power is off; --power-on is required")


def wait_mode(dashboard, allowed, timeout):
    deadline = time.monotonic() + timeout
    while True:
        mode, alarms = status(dashboard)
        require_no_alarms(alarms)
        if mode in allowed:
            return mode
        if mode == 9 or time.monotonic() >= deadline:
            raise ControllerError("Controller did not reach mode {}; current mode {}".format(allowed, mode))
        time.sleep(ROBOT_HOME["poll_interval_s"])


def prepare(dashboard, args, home_motion=True):
    mode, alarms = status(dashboard)
    check_preflight(mode, alarms, args)
    if args.clear_errors:
        dashboard.command("ClearError()")
        time.sleep(ROBOT_HOME["clear_errors_settle_s"])
        mode, alarms = status(dashboard)
    require_no_alarms(alarms)
    if mode == 3:
        if not args.power_on:
            raise ControllerError("Arm power is off; --power-on is required")
        dashboard.command("PowerOn()")
        mode = wait_mode(dashboard, (4, 5), ROBOT_HOME["power_on_timeout_s"])
    if mode not in (4, 5):
        raise ControllerError("Cannot prepare an arm in mode {}".format(mode))
    # Stop previous execution before enabling or issuing any new target.
    dashboard.command("ResetRobot()")
    mode = wait_mode(dashboard, (4, 5), ROBOT_HOME["reset_timeout_s"])
    if mode == 4:
        dashboard.command("EnableRobot()")
        mode = wait_mode(dashboard, (5,), ROBOT_HOME["enable_timeout_s"])
    if mode != 5:
        raise ControllerError("Cannot home in mode {}".format(mode))
    if home_motion:
        dashboard.command("SpeedFactor({})".format(args.speed))


def read_coordinates(dashboard, query):
    values = [float(value) for value in dashboard.command(query).split(",")]
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise ControllerError("Invalid measured coordinates from " + query)
    return values


def base_flange_pose(dashboard, joints):
    query = "PositiveSolution({},0,0)".format(
        ",".join("{:.6f}".format(value) for value in joints))
    return read_coordinates(dashboard, query)


def pose_errors(first, second):
    return ([abs(first[i] - second[i]) for i in range(3)] +
            [abs((first[i] - second[i] + 180) % 360 - 180) for i in range(3, 6)])


def stable_base_pose(dashboard, timeout=ROBOT_HOME["pose_settle_timeout_s"]):
    """Require a settled, idle pose that agrees with explicit base/flange FK."""
    deadline = time.monotonic() + timeout
    previous = None
    stable = 0
    while True:
        mode, alarms = status(dashboard)
        require_no_alarms(alarms)
        if mode != 5:
            raise ControllerError("Controller is not idle while checking the starting pose")
        joints_before = read_coordinates(dashboard, "GetAngle()")
        pose = read_coordinates(dashboard, "GetPose()")
        calculated = base_flange_pose(dashboard, joints_before)
        joints_after = read_coordinates(dashboard, "GetAngle()")
        joints_still = all(abs(a - b) <= 0.05 for a, b in zip(joints_before, joints_after))
        frames_agree = all(error <= 0.5 for error in pose_errors(pose, calculated))
        settled = previous is not None and all(error <= 0.1 for error in pose_errors(pose, previous))
        stable = stable + 1 if joints_still and frames_agree and settled else 0
        if stable >= ROBOT_HOME["stable_samples"]:
            return pose
        if time.monotonic() >= deadline:
            raise ControllerError("Starting pose did not settle or agree with base/flange FK. "
                                  "GetPose={}, base/flange FK={}; no lift target was sent.".format(pose, calculated))
        previous = pose
        time.sleep(ROBOT_HOME["poll_interval_s"])


def inspect_pose(dashboard):
    """Compare current pose readings to controller FK without changing state."""
    print("Pose inspection only; frames, enable state, gripper, and motion are unchanged.", flush=True)
    for sample in range(ROBOT_HOME["inspect_pose_samples"]):
        mode, alarms = status(dashboard)
        print("  Sample {}: mode {}, alarms {}".format(sample + 1, mode, alarms), flush=True)
        if mode not in (4, 5) or any(alarms):
            raise ControllerError("Pose inspection needs an idle controller without alarms; no recovery was attempted")
        joints = read_coordinates(dashboard, "GetAngle()")
        print("  Measured joints (degrees): {}".format(joints), flush=True)
        pose = read_coordinates(dashboard, "GetPose()")
        print("  GetPose() in currently selected frames: {}".format(pose), flush=True)
        base_pose = base_flange_pose(dashboard, joints)
        print("  Controller FK, User 0 / Tool 0: {}".format(base_pose), flush=True)
        print("  GetPose minus base/flange FK XYZ (mm): {}".format(
            [round(pose[i] - base_pose[i], 3) for i in range(3)]), flush=True)
        if sample + 1 < ROBOT_HOME["inspect_pose_samples"]:
            time.sleep(ROBOT_HOME["poll_interval_s"])


def wait_target(dashboard, target, timeout, initial_pose=None):
    deadline = time.monotonic() + timeout
    stable = 0
    while True:
        mode, alarms = status(dashboard)
        require_no_alarms(alarms)
        if mode not in (5, 7, 8):
            raise ControllerError("Motion interrupted: mode {}".format(mode))
        query = "GetAngle()" if initial_pose is None else "GetPose()"
        measured = read_coordinates(dashboard, query)
        if initial_pose is not None:
            delta = [measured[i] - initial_pose[i] for i in range(3)]
            reasons = []
            if abs(delta[0]) > 2 or abs(delta[1]) > 2:
                reasons.append("lateral displacement exceeded 2 mm")
            if delta[2] < -0.5:
                reasons.append("Z decreased by more than 0.5 mm")
            if measured[2] > target[2] + 0.5:
                reasons.append("Z exceeded the requested endpoint by more than 0.5 mm")
            if reasons:
                raise ControllerError(
                    "Lift deviated from the requested base +Z path: {}. "
                    "Start pose={}, target pose={}, measured pose={}, XYZ delta (mm)={}".format(
                        "; ".join(reasons), initial_pose, target, measured,
                        [round(value, 3) for value in delta]))
            errors = [abs(actual - goal) for actual, goal in zip(measured[:3], target[:3])]
            errors += [abs((actual - goal + 180) % 360 - 180)
                       for actual, goal in zip(measured[3:], target[3:])]
        else:
            errors = [abs(actual - goal) for actual, goal in zip(measured, target)]
        reached = all(error <= 0.5 for error in errors)
        stable = stable + 1 if mode == 5 and reached else 0
        if stable >= ROBOT_HOME["stable_samples"]:
            return
        if time.monotonic() >= deadline:
            raise ControllerError("Timed out waiting for measured coordinates to reach {}".format(target))
        time.sleep(ROBOT_HOME["poll_interval_s"])


def move_arm(dashboard, motion, targets, timeout):
    try:
        for stage, target in enumerate(targets, 1):
            mode, alarms = status(dashboard)
            require_no_alarms(alarms)
            if mode != 5:
                raise ControllerError("Controller is not idle before stage {}".format(stage))
            print("  Stage {}: {} degrees".format(stage, target), flush=True)
            command = "JointMovJ({},SpeedJ=100,AccJ=10)".format(
                ",".join(str(value) for value in target))
            motion.command(command)
            wait_target(dashboard, target, timeout)
    except BaseException:
        # Also attempt a stop when command acceptance is uncertain after a timeout.
        try:
            dashboard.command("ResetRobot()")
        except Exception as error:
            print("Stop request failed: {}. Use the physical emergency stop if needed.".format(error),
                  file=sys.stderr, flush=True)
        raise


def lift_arm(dashboard, motion, lift_mm, timeout, speed):
    try:
        mode, alarms = status(dashboard)
        require_no_alarms(alarms)
        if mode != 5:
            raise ControllerError("Controller is not idle before lift")
        # V3 firmware uses the selected global frames with parameter-free GetPose().
        # Check both frame selection replies before trusting any Cartesian reading.
        dashboard.command("User(0)")
        dashboard.command("Tool(0)")
        initial_pose = stable_base_pose(dashboard)
        target = initial_pose[:]
        target[2] += lift_mm
        print("  Start flange pose (XYZ mm, Rx/Ry/Rz degrees): {}".format(initial_pose), flush=True)
        print("  Requested flange pose: {}".format(target), flush=True)
        dashboard.command("SpeedFactor({})".format(min(speed, 5)))
        print("Lifting {} mm along base +Z, with a {}% global speed cap; gripper unchanged.".format(
            lift_mm, min(speed, 5)), flush=True)
        command = "MovL({},User=0,Tool=0,SpeedL=10,AccL=5)".format(
            ",".join("{:.6f}".format(value) for value in target))
        print("  Motion command: {}".format(command), flush=True)
        motion.command(command)
        wait_target(dashboard, target, timeout, initial_pose=initial_pose)
    except BaseException:
        try:
            dashboard.command("ResetRobot()")
        except Exception as error:
            print("Stop request failed: {}. Use the physical emergency stop if needed.".format(error),
                  file=sys.stderr, flush=True)
        raise


def running_clients(proc=Path("/proc")):
    names = {"launch_nodes.py", "run_control.py", "run_inference.py"}
    found = []
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            arguments = (entry / "cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            continue
        except PermissionError as error:
            raise ControllerError("Cannot check active controllers: {}".format(error))
        if any(Path(os.fsdecode(argument)).name in names for argument in arguments if argument):
            found.append(entry.name)
    return found


def main(argv=None, channel_factory=Channel):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "--move enables the selected arms and moves them one at a time through the existing "
        "Xtrainer initial poses. This is not a planned recovery path: remove surface contact "
        "and ensure the entire path is clear first. Grippers are not commanded. "
        "Stop all other robot clients. TCP/IP control and network access must already work. "
        "--lift-mm is a short base +Z withdrawal for one arm. --base-z-up confirms that "
        "this direction points away from the surface. Verify overhead and arm clearance. "
        "The lowered global speed cap remains after a movement command."))
    parser.add_argument("--arm", choices=("left", "right", "both"), default=ROBOT_HOME["arm"])
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--inspect-pose", action="store_true",
                         help="read pose/joints and calculate base/flange FK; no state changes or motion")
    actions.add_argument("--move", action="store_true", help="execute real robot motion")
    actions.add_argument("--recover", action="store_true",
                         help="stop previous execution and enable the arm without homing or gripper commands")
    actions.add_argument("--lift-mm", type=float, metavar="1..50",
                         help="lift one arm along base +Z by this distance; no gripper commands")
    parser.add_argument("--base-z-up", action="store_true",
                        help="confirm that base +Z points upward, away from the contacted surface")
    parser.add_argument("--clear-errors", action="store_true", help="clear alarms after resolving their cause")
    parser.add_argument("--power-on", action="store_true", help="power on an arm if its mode is 3")
    parser.add_argument("--speed", type=int, choices=range(1, 21), default=ROBOT_HOME["speed_percent"], metavar="1..20",
                        help="global speed cap in percent (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=ROBOT_HOME["stage_timeout_s"], help="seconds to wait for each stage (default: %(default)s)")
    args = parser.parse_args(argv)
    if args.arm not in ("left", "right", "both"):
        parser.error("ROBOT_HOME arm must be left, right, or both")
    if type(args.speed) is not int or not 1 <= args.speed <= 20:
        parser.error("--speed must be between 1 and 20")
    for key in ("inspect_pose_samples", "stable_samples"):
        if type(ROBOT_HOME[key]) is not int or ROBOT_HOME[key] < 1:
            parser.error("ROBOT_HOME {} must be a positive integer".format(key))
    for key in ("poll_interval_s", "pose_settle_timeout_s", "power_on_timeout_s",
                "reset_timeout_s", "enable_timeout_s", "clear_errors_settle_s"):
        value = ROBOT_HOME[key]
        minimum_ok = value >= 0 if key == "clear_errors_settle_s" else value > 0
        if not minimum_ok or not math.isfinite(value):
            parser.error("Invalid ROBOT_HOME timing: {}".format(key))
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        parser.error("--timeout must be positive and finite")
    lift_requested = args.lift_mm is not None
    if lift_requested:
        if not math.isfinite(args.lift_mm) or not 1 <= args.lift_mm <= 50:
            parser.error("--lift-mm must be finite and between 1 and 50")
        if args.arm == "both" or not args.base_z_up:
            parser.error("--lift-mm requires --arm left/right and --base-z-up after checking the mounting")
    elif args.base_z_up:
        parser.error("--base-z-up requires --lift-mm")
    change_state = args.move or args.recover or lift_requested
    if (args.clear_errors or args.power_on) and not change_state:
        parser.error("--clear-errors and --power-on require --move, --recover, or --lift-mm")
    selected = list(ARMS) if args.arm == "both" else [args.arm]
    try:
        if change_state:
            clients = running_clients()
            if clients:
                raise ControllerError("Stop robot clients first; active PIDs: " + ", ".join(clients))
        with ExitStack() as stack:
            dashboards = {}
            for name in selected:
                ip, targets = ARMS[name]
                dashboard = channel_factory(ip, ROBOT_HOME["dashboard_port"])
                stack.callback(dashboard.close)
                dashboards[name] = dashboard
                mode, alarms = status(dashboard)
                print("{} ({}): mode {} ({}), alarms {}".format(
                    name, ip, mode, MODES.get(mode, "other"), alarms), flush=True)
                for code in alarms[0]:
                    if code in ALARM_DESCRIPTIONS:
                        print("  Alarm {}: {}".format(code, ALARM_DESCRIPTIONS[code]), flush=True)
                print("  Xtrainer initial joints: {} degrees".format(targets[-1]), flush=True)
                if change_state:
                    check_preflight(mode, alarms, args)
                    if lift_requested and any(code not in (-2, 117) for group in alarms for code in group):
                        raise ControllerError("Lift recovery only accepts a collision alarm; resolve other alarms separately")
            if not change_state:
                if args.inspect_pose:
                    for name in selected:
                        print("Inspecting {} arm:".format(name), flush=True)
                        inspect_pose(dashboards[name])
                print("Status only. No robot state was changed.")
                return 0
            if args.recover:
                for name in selected:
                    prepare(dashboards[name], args, home_motion=False)
                    print("{}: mode 5, no alarms. Recovery complete; no target or gripper commands sent.".format(name),
                          flush=True)
                return 0
            motions = {}
            for name in selected:
                motions[name] = channel_factory(ARMS[name][0], ROBOT_HOME["motion_port"])
                stack.callback(motions[name].close)
            for name in selected:
                prepare(dashboards[name], args, home_motion=not lift_requested)
            if lift_requested:
                name = selected[0]
                lift_arm(dashboards[name], motions[name], args.lift_mm, args.timeout, args.speed)
                print("Lift complete. No home targets or gripper commands were sent.")
                return 0
            for name in selected:
                print("Moving {} arm at {}% global speed cap.".format(name, args.speed), flush=True)
                move_arm(dashboards[name], motions[name], ARMS[name][1], args.timeout)
            print("Selected arms reached the Xtrainer initial pose.")
            return 0
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except (ControllerError, OSError, ValueError) as error:
        print("Operation refused or interrupted: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
