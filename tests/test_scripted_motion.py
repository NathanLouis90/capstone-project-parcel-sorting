import numpy as np
import pytest
import yaml
from experiments.scripted_motion import MotionLoop, SimulatedEnv, VirtualClock, simulation_waypoints, load_waypoints
from experiments.handoff import home_action


def setup():
    clock=VirtualClock(); env=SimulatedEnv()
    return MotionLoop(env,simulation_waypoints(),clock=clock,sleep=clock.sleep), clock


def test_interpolation_and_25hz_pacing():
    motion, clock=setup()
    motion.pose('drop_receiving_left','left')
    assert clock() == pytest.approx(len(motion.env.commands)*.04)
    states=np.vstack([home_action(),motion.env.commands])
    assert np.max(np.abs(np.diff(states,axis=0))) <= .0100001


def test_invalid_stream_never_reaches_environment():
    motion,_=setup(); target=home_action(); target[0]=np.nan
    with pytest.raises(ValueError): motion.command(target)
    assert not motion.env.commands


def test_cable_limit_blocks_sweep():
    motion,_=setup(); motion.waypoints['joint_limits_rad'][5]=[1,1.6]
    target=home_action(); target[5]=1.7
    with pytest.raises(ValueError, match='joint/cable'): motion.move(target)
    assert all(command[5] <= 1.6 for command in motion.env.commands)


def test_halt_prevents_further_commands():
    motion,_=setup(); motion.halt()
    with pytest.raises(RuntimeError,match='halted'): motion.command(home_action())
    assert motion.env.stopped


def test_live_rejects_simulation_points(tmp_path):
    p=tmp_path/'points.yaml'; p.write_text(yaml.safe_dump(simulation_waypoints()))
    load_waypoints(p)
    with pytest.raises(ValueError,match='commission'): load_waypoints(p,live=True)


def test_home_keeps_released_gripper_open_during_retreat():
    motion,_=setup()
    motion.pose('drop_receiving_left','left',gripper=0)
    first=len(motion.env.commands)
    motion.home('left')
    assert all(command[6]==0 for command in motion.env.commands[first:])


def test_feedback_divergence_prevents_next_command():
    motion,_=setup()
    motion.env.action[0]+=.2
    with pytest.raises(ValueError,match='feedback diverged'):
        motion.command(motion.last_action)
    assert not motion.env.commands
