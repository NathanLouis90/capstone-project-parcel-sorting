"""Check that supervisor faults prefer a verified controlled stop without hardware."""

import numpy as np
import pytest

from parcel_sorting.hardware.robots import dashboard_rpc
from parcel_sorting.runtime import hardware_runtime
from parcel_sorting.runtime.hardware_runtime import LiveRuntime

CLEAR = [[], [], [], [], [], [], []]


class FakeStopRobot:
    def __init__(self, modes=(5, 5), alarms=(CLEAR, CLEAR), drift=0.0, controlled_error=None):
        self.calls, self.modes, self.alarms = [], modes, alarms
        self.drift, self.controlled_error = drift, controlled_error
        self.joints = np.zeros(14)

    def controlled_stop(self):
        self.calls.append('controlled_stop')
        if self.controlled_error:
            raise self.controlled_error

    def emergency_stop(self):
        self.calls.append('emergency_stop')

    def get_controller_status(self):
        return {arm: dict(mode=mode, alarms=alarms)
                for arm, mode, alarms in zip(('left', 'right'), self.modes, self.alarms)}

    def get_joint_state(self):
        self.joints[12] += self.drift
        return self.joints.copy()


@pytest.fixture
def runtime(monkeypatch):
    elapsed = [0.0]
    monkeypatch.setattr(hardware_runtime.time, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(hardware_runtime.time, 'sleep',
                        lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))

    def make(robot):
        live = LiveRuntime.__new__(LiveRuntime)
        live.stop_robot = robot
        return live
    return make


def test_idle_still_arms_keep_power_after_controlled_stop(runtime):
    robot = FakeStopRobot()
    assert runtime(robot).stop() == 'controlled stop confirmed'
    assert robot.calls == ['controlled_stop']


@pytest.mark.parametrize('robot', [
    FakeStopRobot(controlled_error=RuntimeError('Controlled stop failed: right: timeout')),
    FakeStopRobot(drift=0.01),
    FakeStopRobot(modes=(5, 7)),
    FakeStopRobot(alarms=(CLEAR, [[117], [], [], [], [], [], []])),
], ids=['request-failed', 'still-moving', 'still-running', 'new-alarm'])
def test_unconfirmed_controlled_stop_falls_back_to_emergency_stop(runtime, robot):
    result = runtime(robot).stop()
    assert result.startswith('controlled stop not confirmed')
    assert robot.calls == ['controlled_stop', 'emergency_stop']


def test_failed_emergency_fallback_is_reported(runtime):
    class NoStop(FakeStopRobot):
        def emergency_stop(self):
            super().emergency_stop()
            raise RuntimeError('Stop acknowledgement failed')

    robot = NoStop(drift=0.01)
    with pytest.raises(RuntimeError, match='Stop acknowledgement failed'):
        runtime(robot).stop()
    assert robot.calls == ['controlled_stop', 'emergency_stop']


def test_controlled_stop_requests_reset_on_both_controllers_even_after_a_failure():
    sent = []

    class Dashboard:
        def __init__(self, arm, fail):
            self.arm, self.fail = arm, fail

        def sendRecvMsg(self, command):
            sent.append((self.arm, command))
            if self.fail:
                raise OSError('timed out')
            return '0,{},ResetRobot();'

    with pytest.raises(RuntimeError, match='left: timed out'):
        dashboard_rpc.controlled_stop(dict(left=Dashboard('left', True), right=Dashboard('right', False)))
    assert sent == [('left', 'ResetRobot()'), ('right', 'ResetRobot()')]
