"""Check homing arm selection and speed limits without opening robot connections."""

import pytest

from parcel_sorting.hardware import robot_home


@pytest.fixture
def fake_controllers(monkeypatch):
    commands = []
    measured = {}

    class FakeChannel:
        def __init__(self, ip, port):
            self.ip, self.port = ip, port

        def close(self):
            pass

        def command(self, command):
            commands.append((self.ip, self.port, command))
            if command == "RobotMode()":
                return "5"
            if command == "GetErrorID()":
                return "[[], [], [], [], [], [], []]"
            if command.startswith("JointMovJ("):
                measured[self.ip] = command[len("JointMovJ("):].split(",")[:6]
            if command == "GetAngle()":
                return ",".join(measured[self.ip])
            return ""

    monkeypatch.setattr(robot_home, "running_clients", lambda: [])
    monkeypatch.setattr(robot_home, "wait_target", lambda *args, **kwargs: None)
    monkeypatch.setattr(robot_home.time, "sleep", lambda seconds: None)
    return FakeChannel, commands


@pytest.mark.parametrize("speed", [40, 45, 50])
def test_both_arms_receive_requested_homing_speed(fake_controllers, speed):
    factory, commands = fake_controllers
    assert robot_home.main(["--move", "--arm", "both", "--speed", str(speed)], factory) == 0
    for ip, targets in robot_home.ARMS.values():
        assert (ip, robot_home.ROBOT_HOME["dashboard_port"],
                "SpeedFactor({})".format(speed)) in commands
    moves = [(ip, command) for ip, port, command in commands
             if port == robot_home.ROBOT_HOME["motion_port"]]
    expected = [(ip, "JointMovJ({},SpeedJ=100,AccJ=10)".format(
        ",".join(str(value) for value in target)))
        for stage in range(2) for ip, targets in robot_home.ARMS.values()
        for target in [targets[stage]]]
    assert moves == expected
    first_measurement = next(index for index, entry in enumerate(commands) if entry[2] == "GetAngle()")
    assert sum(entry[2].startswith("JointMovJ(") for entry in commands[:first_measurement]) == 2


def test_default_homing_still_selects_both_arms_at_ten_percent(fake_controllers):
    factory, commands = fake_controllers
    assert robot_home.main(["--move"], factory) == 0
    assert [ip for ip, port, command in commands if command == "SpeedFactor(10)"] == [
        values[0] for values in robot_home.ARMS.values()]


@pytest.mark.parametrize("speed", ["0", "-1", "51", "100", "40.5"])
def test_invalid_speed_is_rejected_before_connecting(speed):
    def refuse_connection(*args):
        pytest.fail("Invalid arguments must not open a controller connection")

    with pytest.raises(SystemExit) as error:
        robot_home.main(["--move", "--speed", speed], refuse_connection)
    assert error.value.code == 2


def test_invalid_configured_speed_is_also_rejected(monkeypatch):
    monkeypatch.setitem(robot_home.ROBOT_HOME, "speed_percent", 51)

    def refuse_connection(*args):
        pytest.fail("Invalid configuration must not open a controller connection")

    with pytest.raises(SystemExit) as error:
        robot_home.main(["--move"], refuse_connection)
    assert error.value.code == 2


def test_fifty_percent_request_keeps_lift_at_five_percent(fake_controllers, monkeypatch):
    factory, commands = fake_controllers
    monkeypatch.setattr(robot_home, "stable_base_pose", lambda dashboard: [0, 0, 100, 0, 0, 0])
    assert robot_home.main([
        "--arm", "right", "--lift-mm", "10", "--base-z-up", "--speed", "50",
    ], factory) == 0
    speeds = [command for ip, port, command in commands if command.startswith("SpeedFactor(")]
    assert speeds == ["SpeedFactor(5)"]


def test_next_stage_waits_for_both_arms_to_settle(fake_controllers):
    factory, commands = fake_controllers
    right_ip = robot_home.ARMS["right"][0]
    right_polls = []

    class DelayedRight(factory):
        def command(self, command):
            moves = sum(entry[2].startswith("JointMovJ(") for entry in commands)
            if command.startswith("JointMovJ(") and moves == 2:
                assert len(right_polls) >= 2 + robot_home.ROBOT_HOME["stable_samples"]
            result = super().command(command)
            if self.ip == right_ip and command == "RobotMode()" and moves == 2:
                right_polls.append(command)
                if len(right_polls) <= 2:
                    return "7"
            return result

    assert robot_home.main(["--move", "--arm", "both"], DelayedRight) == 0


@pytest.mark.parametrize("arm", ["left", "right"])
@pytest.mark.parametrize("error_type,exit_code", [(OSError, 1), (KeyboardInterrupt, 130)])
def test_command_failure_or_interrupt_stops_both_arms(fake_controllers, arm, error_type, exit_code):
    factory, commands = fake_controllers
    failed_ip = robot_home.ARMS[arm][0]

    class FailedCommand(factory):
        def command(self, command):
            result = super().command(command)
            if self.ip == failed_ip and command.startswith("JointMovJ("):
                raise error_type("Injected command failure")
            return result

    assert robot_home.main(["--move", "--arm", "both"], FailedCommand) == exit_code
    last_move = max(index for index, entry in enumerate(commands) if entry[2].startswith("JointMovJ("))
    stops = [ip for ip, port, command in commands[last_move + 1:] if command == "ResetRobot()"]
    assert stops == [values[0] for values in robot_home.ARMS.values()]


def test_fault_on_right_is_checked_while_left_is_still_moving(fake_controllers):
    factory, commands = fake_controllers
    left_ip = robot_home.ARMS["left"][0]

    class RightFault(factory):
        def command(self, command):
            result = super().command(command)
            if command == "RobotMode()" and any(entry[2].startswith("JointMovJ(") for entry in commands):
                return "7" if self.ip == left_ip else "9"
            return result

    assert robot_home.main(["--move", "--arm", "both"], RightFault) == 1
    assert sum(entry[2].startswith("JointMovJ(") for entry in commands) == 2
    assert [entry[2] for entry in commands[-2:]] == ["ResetRobot()", "ResetRobot()"]


def test_group_timeout_stops_both_arms(fake_controllers, monkeypatch):
    factory, commands = fake_controllers
    elapsed = [0.0]
    monkeypatch.setattr(robot_home.time, "monotonic", lambda: elapsed[0])

    def advance(seconds):
        elapsed[0] += seconds

    monkeypatch.setattr(robot_home.time, "sleep", advance)

    class NeverSettled(factory):
        def command(self, command):
            result = super().command(command)
            if command == "RobotMode()" and any(entry[2].startswith("JointMovJ(") for entry in commands):
                return "7"
            return result

    assert robot_home.main(["--move", "--arm", "both", "--timeout", "0.5"], NeverSettled) == 1
    assert sum(entry[2].startswith("JointMovJ(") for entry in commands) == 2
    assert [entry[2] for entry in commands[-2:]] == ["ResetRobot()", "ResetRobot()"]


def test_peer_stop_is_attempted_even_if_first_stop_fails(fake_controllers):
    factory, commands = fake_controllers
    left_ip = robot_home.ARMS["left"][0]

    class StopFailure(factory):
        def command(self, command):
            result = super().command(command)
            moving = any(entry[2].startswith("JointMovJ(") for entry in commands)
            if command.startswith("JointMovJ("):
                raise OSError("Injected motion failure")
            if self.ip == left_ip and command == "ResetRobot()" and moving:
                raise OSError("Injected stop failure")
            return result

    assert robot_home.main(["--move", "--arm", "both"], StopFailure) == 1
    assert [entry[2] for entry in commands[-2:]] == ["ResetRobot()", "ResetRobot()"]


@pytest.mark.parametrize("arm", ["left", "right"])
def test_single_arm_selection_still_moves_only_that_arm(fake_controllers, arm):
    factory, commands = fake_controllers
    assert robot_home.main(["--move", "--arm", arm], factory) == 0
    assert {ip for ip, port, command in commands} == {robot_home.ARMS[arm][0]}


ESTOP = "[[116], [], [], [], [], [], []]"
CLEAR = "[[], [], [], [], [], [], []]"


@pytest.fixture
def estopped_controllers(monkeypatch):
    """Controllers left in mode 3 with alarm 116 by a software EmergencyStop()."""
    commands = []
    state = {}

    class EstoppedChannel:
        reset_by_power_on = True

        def __init__(self, ip, port):
            self.ip, self.port = ip, port
            state.setdefault(ip, {"mode": 3, "alarms": ESTOP})

        def close(self):
            pass

        def command(self, command):
            commands.append((self.ip, self.port, command))
            arm = state[self.ip]
            if command == "RobotMode()":
                return str(arm["mode"])
            if command == "GetErrorID()":
                return arm["alarms"]
            if command == "PowerOn()" and self.reset_by_power_on:
                arm.update(mode=4, alarms=CLEAR)
            if command == "EnableRobot()" and arm["alarms"] == CLEAR:
                arm["mode"] = 5
            return ""

    monkeypatch.setattr(robot_home, "running_clients", lambda: [])
    monkeypatch.setattr(robot_home.time, "sleep", lambda seconds: None)
    return EstoppedChannel, commands


def test_software_estop_reset_powers_on_before_reset_and_enable(estopped_controllers):
    factory, commands = estopped_controllers
    assert robot_home.main(["--recover", "--power-on", "--software-estop-reset"], factory) == 0
    for ip, targets in robot_home.ARMS.values():
        sent = [command for address, port, command in commands
                if address == ip and command not in ("RobotMode()", "GetErrorID()")]
        assert sent == ["PowerOn()", "ResetRobot()", "EnableRobot()"]
    assert not any(port == robot_home.ROBOT_HOME["motion_port"] for ip, port, command in commands)


def test_estop_alarm_without_confirmation_sends_nothing(estopped_controllers, capsys):
    factory, commands = estopped_controllers
    assert robot_home.main(["--recover", "--clear-errors", "--power-on"], factory) == 1
    assert "--software-estop-reset" in capsys.readouterr().err
    assert {command for ip, port, command in commands} <= {"RobotMode()", "GetErrorID()", "ClearError()"}


def test_persistent_estop_after_power_on_never_enables(estopped_controllers, monkeypatch, capsys):
    factory, commands = estopped_controllers
    elapsed = [0.0]
    monkeypatch.setattr(robot_home.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(robot_home.time, "sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))

    class ButtonStillPressed(factory):
        reset_by_power_on = False

    assert robot_home.main(["--move", "--power-on", "--software-estop-reset"], ButtonStillPressed) == 1
    assert "Alarm 116 remained after PowerOn()" in capsys.readouterr().err
    sent = [command for ip, port, command in commands]
    assert sent.count("PowerOn()") == 1
    assert "EnableRobot()" not in sent and not any(c.startswith("JointMovJ(") for c in sent)


@pytest.mark.parametrize("alarms", ["[[116, 22], [], [], [], [], [], []]", "[[116], [], [], [], [], [], [8]]"])
def test_estop_reset_refuses_additional_alarms(estopped_controllers, alarms):
    factory, commands = estopped_controllers

    class ExtraAlarm(factory):
        def __init__(self, ip, port):
            super().__init__(ip, port)

        def command(self, command):
            result = super().command(command)
            return alarms if command == "GetErrorID()" else result

    assert robot_home.main(["--recover", "--power-on", "--software-estop-reset"], ExtraAlarm) == 1
    assert "PowerOn()" not in [command for ip, port, command in commands]


@pytest.mark.parametrize("argv", [
    ["--recover", "--software-estop-reset"],
    ["--software-estop-reset", "--power-on"],
    ["--arm", "right", "--lift-mm", "10", "--base-z-up", "--power-on", "--software-estop-reset"],
])
def test_estop_reset_flag_combinations_are_rejected_before_connecting(argv):
    def refuse_connection(*args):
        pytest.fail("Invalid arguments must not open a controller connection")

    with pytest.raises(SystemExit) as error:
        robot_home.main(argv, refuse_connection)
    assert error.value.code == 2


def test_power_on_failure_alarm_stops_without_suggesting_retry(estopped_controllers, capsys):
    factory, commands = estopped_controllers

    class PowerOnFails(factory):
        reset_by_power_on = False

        def command(self, command):
            result = super().command(command)
            if command == "PowerOn()":
                type(self).failed = True
            if command == "GetErrorID()" and getattr(type(self), "failed", False):
                return "[[116, 1009], [], [], [], [], [], []]"
            return result

    assert robot_home.main(["--recover", "--power-on", "--software-estop-reset"], PowerOnFails) == 1
    error = capsys.readouterr().err
    assert "1009: power-on failure" in error and "Do not repeat PowerOn()" in error
    assert "--software-estop-reset" not in error
    sent = [command for ip, port, command in commands]
    assert sent.count("PowerOn()") == 1 and "EnableRobot()" not in sent


class FakeGripper:
    def __init__(self, name, events, reached=True):
        self.name, self.events, self.reached, self.position = name, events, reached, 0

    def move(self, position, speed, force):
        self.events.append(("gripper", self.name, position))
        if self.reached:
            self.position = position

    def get_current_position(self):
        return self.position

    def disconnect(self):
        self.events.append(("disconnect", self.name))


def gripper_test_factory(fake_controllers, reached=True):
    channel_factory, commands = fake_controllers
    events = []

    class RecordingChannel(channel_factory):
        def command(self, command):
            events.append(("controller", self.ip, command))
            return super().command(command)

    return RecordingChannel, (lambda name: FakeGripper(name, events, reached)), events


def test_open_gripper_opens_both_before_any_arm_state_change(fake_controllers):
    channels, grippers, events = gripper_test_factory(fake_controllers)
    assert robot_home.main(["--move", "--open-gripper"], channels, grippers) == 0
    opens = [index for index, event in enumerate(events) if event[0] == "gripper"]
    assert [events[index][1:] for index in opens] == [
        ("left", robot_home.GRIPPER_OPEN_POSITION), ("right", robot_home.GRIPPER_OPEN_POSITION)]
    assert robot_home.GRIPPER_OPEN_POSITION == 255
    first_state_change = next(index for index, event in enumerate(events)
                              if event[0] == "controller" and event[2].startswith("ResetRobot("))
    assert max(opens) < first_state_change
    assert any(event[0] == "controller" and event[2].startswith("JointMovJ(") for event in events)


def test_gripper_that_does_not_open_prevents_arm_motion(fake_controllers, capsys):
    channels, grippers, events = gripper_test_factory(fake_controllers, reached=False)
    assert robot_home.main(["--move", "--arm", "right", "--open-gripper"], channels, grippers) == 1
    assert "Gripper did not open: right" in capsys.readouterr().err
    assert not any(event[0] == "controller" and event[2].startswith(("ResetRobot(", "EnableRobot(", "JointMovJ("))
                   for event in events)
    assert ("disconnect", "right") in events


def test_homing_without_the_flag_never_commands_grippers(fake_controllers):
    channels, grippers, events = gripper_test_factory(fake_controllers)
    assert robot_home.main(["--move"], channels, grippers) == 0
    assert not any(event[0] == "gripper" for event in events)


@pytest.mark.parametrize("argv", [["--open-gripper"], ["--inspect-pose", "--open-gripper"],
                                  ["--lift-mm", "10", "--arm", "right", "--base-z-up", "--open-gripper"]])
def test_open_gripper_requires_move_or_recover(argv):
    def refuse(*args):
        pytest.fail("Invalid arguments must not connect")

    with pytest.raises(SystemExit) as error:
        robot_home.main(argv, refuse, refuse)
    assert error.value.code == 2
