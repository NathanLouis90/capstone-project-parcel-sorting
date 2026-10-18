"""Hardware-free checks for the terminal homing command."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "robot_home", Path(__file__).resolve().parents[1] / "experiments" / "robot_home.py")
home = importlib.util.module_from_spec(spec)
spec.loader.exec_module(home)
EMPTY_ALARMS = [[], [], [], [], [], [], []]


class FakeController:
    def __init__(self, name, events, mode=4, alarms=None):
        self.name = name
        self.events = events
        self.mode = mode
        self.alarms = EMPTY_ALARMS if alarms is None else alarms
        self.angles = [0] * 6
        self.pose = [50, -350, 100, 180, 0, 90]
        self.lift_delta = None
        self.fault_on_move = False
        self.fail_clear = False
        self.enabled_mode = 5
        self.user = 7
        self.tool = 1
        self.rejected_commands = set()
        self.fk_offset = 0

    def command(self, command):
        self.events.append((self.name, command))
        if command in self.rejected_commands:
            raise home.ControllerError("Command rejected: " + command)
        if command == "RobotMode()":
            return str(self.mode)
        if command == "GetErrorID()":
            return json.dumps(self.alarms)
        if command == "GetAngle()":
            return ",".join(str(value) for value in self.angles)
        if command.startswith("GetPose(") and command != "GetPose()":
            raise home.ControllerError("V3 test controller rejects parameterized GetPose")
        if command == "GetPose()":
            return ",".join(str(value) for value in self.pose)
        if command.startswith("PositiveSolution("):
            calculated = self.pose[:]
            calculated[2] += self.fk_offset
            return ",".join(str(value) for value in calculated)
        if command == "User(0)":
            self.user = 0
        elif command == "Tool(0)":
            self.tool = 0
        if command == "ClearError()" and not self.fail_clear:
            self.alarms = EMPTY_ALARMS
            self.mode = 4
        elif command == "PowerOn()":
            self.mode = 4
        elif command == "EnableRobot()":
            self.mode = self.enabled_mode
        elif command.startswith("JointMovJ("):
            self.angles = [float(value) for value in command[10:].split(",")[:6]]
            if self.fault_on_move:
                self.alarms = [[117], [], [], [], [], [], []]
                self.mode = 9
        elif command.startswith("MovL("):
            target = [float(value) for value in command[5:].split(",")[:6]]
            if self.lift_delta is not None:
                target[2] = self.pose[2] + self.lift_delta
            self.pose = target
            if self.fault_on_move:
                self.alarms = [[-2], [], [], [], [], [], []]
                self.mode = 9
        return ""

    def close(self):
        pass


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.arms = {name: FakeController(name, self.events) for name in home.ARMS}
        self.clients = patch.object(home, "running_clients", return_value=[])
        self.sleep = patch.object(home.time, "sleep")
        self.clients.start()
        self.sleep.start()
        self.addCleanup(self.clients.stop)
        self.addCleanup(self.sleep.stop)

    def run_cli(self, arguments):
        def factory(ip, port):
            self.events.append((ip, port))
            return self.arms["left" if ip.endswith(".1") else "right"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return home.main(arguments, factory)

    def moves(self):
        return [(arm, command) for arm, command in self.events
                if isinstance(command, str) and command.startswith("JointMovJ(")]

    def test_default_is_read_only_even_with_alarms(self):
        self.arms["left"].mode = 9
        self.arms["left"].alarms = [[117], [], [], [], [], [], []]
        self.assertEqual(self.run_cli([]), 0)
        self.assertTrue(all(command in (29999, "RobotMode()", "GetErrorID()")
                            for _, command in self.events))

    def test_configured_arm_and_cli_override_remain_read_only(self):
        with patch.dict(home.ROBOT_HOME, {"arm": "left"}):
            self.assertEqual(self.run_cli([]), 0)
            self.assertNotIn(("right", "RobotMode()"), self.events)
            self.events.clear()
            self.assertEqual(self.run_cli(["--arm", "right"]), 0)
            self.assertNotIn(("left", "RobotMode()"), self.events)
            self.assertIn(("right", "RobotMode()"), self.events)
        self.assertFalse(self.moves())

    def test_invalid_config_blocks_before_connecting(self):
        for changes in ({"arm": "missing"}, {"speed_percent": 21},
                        {"stable_samples": 0}, {"inspect_pose_samples": 0},
                        {"poll_interval_s": 0}, {"power_on_timeout_s": float("nan")}):
            with self.subTest(changes=changes), patch.dict(home.ROBOT_HOME, changes):
                with self.assertRaises(SystemExit) as error:
                    self.run_cli(["--move"])
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(self.events, [])

    def test_alarm_on_second_arm_prevents_all_mutations(self):
        self.arms["right"].alarms = [[116, 165], [], [], [], [], [], []]
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertFalse(self.moves())
        self.assertNotIn(("left", "EnableRobot()"), self.events)

    def test_power_on_requires_explicit_flag(self):
        self.arms["left"].mode = 3
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertNotIn(("left", "PowerOn()"), self.events)
        self.assertEqual(self.run_cli(["--arm", "left", "--power-on", "--move"]), 0)
        self.assertIn(("left", "PowerOn()"), self.events)

    def test_failed_alarm_clear_never_enables_or_moves(self):
        arm = self.arms["left"]
        arm.alarms = [[117], [], [], [], [], [], []]
        arm.fail_clear = True
        self.assertEqual(self.run_cli(["--arm", "left", "--move", "--clear-errors"]), 1)
        self.assertFalse(self.moves())
        self.assertNotIn(("left", "EnableRobot()"), self.events)

    def test_sequential_stages_wait_for_measured_completion(self):
        self.assertEqual(self.run_cli(["--move"]), 0)
        self.assertEqual([arm for arm, _ in self.moves()], ["left", "left", "right", "right"])
        move_indices = [index for index, (_, command) in enumerate(self.events)
                        if isinstance(command, str) and command.startswith("JointMovJ(")]
        for index in move_indices:
            arm = self.events[index][0]
            self.assertEqual(self.events[index + 1:index + 10],
                             [(arm, command) for _ in range(3)
                              for command in ("RobotMode()", "GetErrorID()", "GetAngle()")])

    def test_collision_stops_and_prevents_further_motion(self):
        self.arms["left"].fault_on_move = True
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertEqual(len(self.moves()), 1)
        self.assertIn(("left", "ResetRobot()"), self.events)

    def test_accepted_move_without_reaching_target_times_out_and_stops(self):
        arm = self.arms["left"]
        original = arm.command
        def command(value):
            result = original(value)
            if value.startswith("JointMovJ("):
                arm.angles = [0] * 6
            return result
        arm.command = command
        with patch.object(home.time, "monotonic", side_effect=[0, 0, 0, 100]):
            self.assertEqual(self.run_cli(["--arm", "left", "--move", "--timeout", "1"]), 1)
        self.assertEqual(len(self.moves()), 1)
        self.assertIn(("left", "ResetRobot()"), self.events)

    def test_collision_recovery_clears_stops_enables_without_targets(self):
        arm = self.arms["right"]
        arm.mode = 9
        arm.alarms = [[-2], [], [], [], [], [], []]
        self.assertEqual(self.run_cli(["--arm", "right", "--recover", "--clear-errors"]), 0)
        self.assertFalse(self.moves())
        self.assertNotIn(("192.168.5.2", 30003), self.events)
        commands = [command for name, command in self.events if name == "right"]
        self.assertLess(commands.index("ClearError()"), commands.index("ResetRobot()"))
        self.assertLess(commands.index("ResetRobot()"), commands.index("EnableRobot()"))
        self.assertFalse(any(command.startswith("SpeedFactor(") for command in commands))
        self.assertEqual(arm.mode, 5)

    def test_recovery_requires_explicit_alarm_clear(self):
        self.arms["right"].mode = 9
        self.arms["right"].alarms = [[-2], [], [], [], [], [], []]
        self.assertEqual(self.run_cli(["--arm", "right", "--recover"]), 1)
        self.assertNotIn(("right", "ClearError()"), self.events)

    def test_recovery_refuses_persistent_collision(self):
        arm = self.arms["right"]
        arm.mode = 9
        arm.alarms = [[-2], [], [], [], [], [], []]
        arm.fail_clear = True
        self.assertEqual(self.run_cli(["--arm", "right", "--recover", "--clear-errors"]), 1)
        self.assertNotIn(("right", "EnableRobot()"), self.events)
        self.assertFalse(self.moves())

    def test_recovery_honors_local_client_guard(self):
        home.running_clients.return_value = ["1234"]
        self.assertEqual(self.run_cli(["--recover", "--clear-errors"]), 1)
        self.assertEqual(self.events, [])

    def test_lift_uses_base_z_and_preserves_other_coordinates_and_gripper(self):
        arm = self.arms["right"]
        initial = arm.pose[:]
        arm.mode = 9
        arm.alarms = [[-2], [], [], [], [], [], []]
        args = ["--arm", "right", "--lift-mm", "10", "--base-z-up", "--clear-errors"]
        self.assertEqual(self.run_cli(args), 0)
        self.assertEqual(arm.pose, initial[:2] + [initial[2] + 10] + initial[3:])
        targets = [command for name, command in self.events
                   if name == "right" and command.startswith("MovL(")]
        self.assertEqual(targets, ["MovL(50.000000,-350.000000,110.000000,180.000000,0.000000,90.000000,User=0,Tool=0,SpeedL=10,AccL=5)"])
        self.assertFalse(self.moves())
        self.assertFalse(any(name == "left" for name, _ in self.events))
        allowed = {"RobotMode()", "GetErrorID()", "ClearError()", "ResetRobot()", "EnableRobot()",
                   "User(0)", "Tool(0)", "GetPose()", "GetAngle()", "SpeedFactor(5)", targets[0]}
        self.assertTrue(all(command in allowed or command.startswith("PositiveSolution(")
                            for name, command in self.events if name == "right"))
        commands = [command for name, command in self.events if name == "right"]
        self.assertLess(commands.index("User(0)"), commands.index("GetPose()"))
        self.assertLess(commands.index("Tool(0)"), commands.index("GetPose()"))
        self.assertNotIn("GetPose(0,0)", commands)

    def test_lift_refuses_to_move_if_frame_selection_is_rejected(self):
        for rejected in ("User(0)", "Tool(0)"):
            with self.subTest(command=rejected):
                self.events.clear()
                self.arms["right"].rejected_commands = {rejected}
                self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 1)
                self.assertNotIn(("right", "GetPose()"), self.events)
                self.assertFalse(any(isinstance(command, str) and command.startswith("MovL(")
                                     for _, command in self.events))

    def test_lift_requires_single_arm_and_verified_direction_and_valid_distance(self):
        for args in (["--lift-mm", "10", "--base-z-up"],
                     ["--arm", "right", "--lift-mm", "10"],
                     ["--arm", "right", "--lift-mm", "nan", "--base-z-up"],
                     ["--arm", "right", "--lift-mm", "-10", "--base-z-up"],
                     ["--arm", "right", "--lift-mm", "51", "--base-z-up"]):
            with self.assertRaises(SystemExit) as error:
                self.run_cli(args)
            self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.events, [])

    def test_lift_refuses_non_collision_alarms(self):
        self.arms["right"].mode = 9
        self.arms["right"].alarms = [[116, 165], [], [], [], [], [], []]
        self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up",
                                       "--clear-errors"]), 1)
        self.assertNotIn(("right", "ClearError()"), self.events)

    def test_lift_stops_if_collision_returns(self):
        self.arms["right"].fault_on_move = True
        self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 1)
        self.assertEqual(self.events[-1], ("right", "ResetRobot()"))

    def test_lift_stops_if_measured_z_decreases(self):
        self.arms["right"].lift_delta = -1
        self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 1)
        self.assertEqual(self.events[-1], ("right", "ResetRobot()"))

    def test_pose_inspection_has_no_state_changes_or_motion_connection(self):
        self.arms["right"].mode = 5
        self.assertEqual(self.run_cli(["--arm", "right", "--inspect-pose"]), 0)
        self.assertEqual(self.arms["right"].user, 7)
        self.assertEqual(self.arms["right"].tool, 1)
        allowed = {"RobotMode()", "GetErrorID()", "GetAngle()", "GetPose()"}
        self.assertTrue(all(command in allowed or command.startswith("PositiveSolution(")
                            for name, command in self.events if name == "right"))
        self.assertNotIn(("192.168.5.2", 30003), self.events)

    def test_pose_inspection_does_not_clear_active_alarms(self):
        self.arms["right"].mode = 9
        self.arms["right"].alarms = [[-2], [], [], [], [], [], []]
        self.assertEqual(self.run_cli(["--arm", "right", "--inspect-pose"]), 1)
        self.assertNotIn(("right", "ClearError()"), self.events)

    def test_path_violation_reports_measured_evidence(self):
        self.arms["right"].mode = 5
        with contextlib.redirect_stdout(io.StringIO()), patch.object(home.time, "monotonic", return_value=0):
            with self.assertRaisesRegex(home.ControllerError, r"Z decreased.*Start pose=.*measured pose=.*XYZ delta"):
                home.wait_target(self.arms["right"], [50, -350, 110, 180, 0, 90], 1,
                                 initial_pose=[50, -350, 101, 180, 0, 90])

    def test_lift_invalid_pose_never_sends_motion(self):
        self.arms["right"].pose = [float("nan")] * 6
        self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 1)
        self.assertFalse(any(isinstance(command, str) and command.startswith("MovL(")
                             for _, command in self.events))

    def test_lift_blocks_before_motion_if_pose_does_not_match_base_frame(self):
        self.arms["right"].fk_offset = 197
        with patch.object(home.time, "monotonic", side_effect=[0, 0, 0, 100]):
            self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 1)
        self.assertFalse(any(isinstance(command, str) and command.startswith("MovL(")
                             for _, command in self.events))

    def test_lift_waits_for_frame_readings_to_settle_before_motion(self):
        arm = self.arms["right"]
        original = arm.command
        pose_reads = []
        def command(value):
            result = original(value)
            if value == "GetPose()":
                pose_reads.append(result)
                if len(pose_reads) == 1:
                    return "50,-350,297,180,0,90"
            return result
        arm.command = command
        self.assertEqual(self.run_cli(["--arm", "right", "--lift-mm", "10", "--base-z-up"]), 0)
        target_index = next(index for index, (_, command) in enumerate(self.events)
                            if isinstance(command, str) and command.startswith("MovL("))
        pose_count_before = sum(command == "GetPose()" for _, command in self.events[:target_index])
        self.assertGreaterEqual(pose_count_before, 5)
        self.assertEqual(arm.pose[2], 110)

    def test_uncertain_motion_acceptance_requests_stop(self):
        arm = self.arms["left"]
        original = arm.command
        def command(value):
            result = original(value)
            if value.startswith("JointMovJ("):
                raise TimeoutError("Motion reply timed out")
            return result
        arm.command = command
        self.assertEqual(self.run_cli(["--arm", "left", "--move"]), 1)
        self.assertEqual(len(self.moves()), 1)
        self.assertIn(("left", "ResetRobot()"), self.events)

    def test_ctrl_c_during_motion_requests_stop(self):
        arm = self.arms["left"]
        original = arm.command
        def command(value):
            result = original(value)
            if value == "GetAngle()":
                raise KeyboardInterrupt()
            return result
        arm.command = command
        self.assertEqual(self.run_cli(["--arm", "left", "--move"]), 130)
        self.assertIn(("left", "ResetRobot()"), self.events)

    def test_mode_change_blocks_motion(self):
        self.arms["left"].mode = 7
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertFalse(self.moves())

    def test_local_controller_blocks_before_connecting(self):
        home.running_clients.return_value = ["1234"]
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertEqual(self.events, [])

    def test_alarm_shape_is_checked(self):
        self.arms["left"].alarms = [False]
        self.assertEqual(self.run_cli(["--move"]), 1)
        self.assertFalse(self.moves())

    def test_partial_multiline_reply(self):
        chunks = [b"0,{[\n[117],", b"[],[],[],[],[],[]]\n},GetErrorID();"]
        class FakeSocket:
            def sendall(self, data):
                pass
            def recv(self, size):
                return chunks.pop(0)
        channel = home.Channel.__new__(home.Channel)
        channel.socket = FakeSocket()
        channel.buffer = b""
        self.assertEqual(json.loads(channel.command("GetErrorID()")),
                         [[117], [], [], [], [], [], []])

    def test_rejected_or_wrong_command_reply(self):
        for reply in ("-2,{},EnableRobot();", "0,{},GetAngle();", "invalid"):
            with self.assertRaises(home.ControllerError):
                home.parse_reply(reply, "EnableRobot()")

    def test_proc_scan_matches_script_arguments(self):
        self.clients.stop()
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            for pid, command in (("101", b"python3\0/home/adiel/dobot_xtrainer/experiments/launch_nodes.py\0"),
                                 ("102", b"bash\0-c\0pgrep run_control.py\0"),
                                 ("103", b"python3\0run_control.py\0")):
                (proc / pid).mkdir()
                (proc / pid / "cmdline").write_bytes(command)
            self.assertEqual(sorted(home.running_clients(proc)), ["101", "103"])


if __name__ == "__main__":
    unittest.main()
