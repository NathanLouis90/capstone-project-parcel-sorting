"""Validated joint streams shared by learned actions and scripted motion."""
import json
from pathlib import Path
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import yaml
from experiments.experiments_config import CONTROL, RUN_INFERENCE, SUPERVISOR
from experiments.inference_safety import validate_action
from experiments.handoff import home_action
from scripts.control_timing import wait_period


class VirtualClock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def sleep(self, seconds): self.value += max(0, seconds)


class SimulatedEnv:
    def __init__(self, action=None, verbose=False):
        self.action = home_action() if action is None else np.asarray(action).copy()
        self.verbose, self.commands, self.stopped = verbose, [], False

    def get_obs(self): return {'joint_positions': self.action.copy()}

    def step(self, joints, flags):
        if self.stopped: raise RuntimeError('Environment is stopped')
        self.action = np.asarray(joints).copy()
        self.commands.append(self.action.copy())
        if self.verbose: print(json.dumps({'joints_rad': self.action.tolist()}))
        return self.get_obs()

    def stop(self): self.stopped = True


class MotionLoop:
    def __init__(self, env, waypoints, config=SUPERVISOR, clock=time.monotonic,
                 sleep=time.sleep, stop=None, health=None):
        self.env, self.waypoints, self.config = env, waypoints, config
        self.clock, self.sleep = clock, sleep
        self.stop_callback = stop or getattr(env, 'stop', lambda: None)
        self.health = health or (lambda: None)
        self.last_action = np.asarray(env.get_obs()['joint_positions']).copy()
        self.last_action[[6, 13]] = 1
        self.halted, self.overruns = False, 0

    def observe(self):
        self.health()
        obs = self.env.get_obs()
        action = np.asarray(obs['joint_positions'], dtype=float).copy()
        if action.shape != (14,) or not np.isfinite(action).all():
            raise ValueError('Invalid robot joint feedback')
        # The current driver reports a constant gripper value. Track commands;
        # this is not evidence of a grasp and never determines physical success.
        action[[6, 13]] = self.last_action[[6, 13]]
        obs['joint_positions'] = action
        return obs

    def command(self, action):
        if self.halted: raise RuntimeError('Motion is halted')
        start = self.clock()
        observed = self.observe()['joint_positions']
        action = np.asarray(action, dtype=float).copy()
        validate_action(action, observed)
        if np.any((action[[6, 13]] < 0) | (action[[6, 13]] > 1)):
            raise ValueError('Gripper command outside 0..1')
        limits = np.asarray(self.waypoints['joint_limits_rad'])
        joint_values = np.concatenate([action[:6], action[7:13]])
        if limits.shape != (12, 2) or np.any(joint_values < limits[:, 0]) or np.any(joint_values > limits[:, 1]):
            raise ValueError('Command exceeds taught joint/cable limits')
        validate_action(action, self.last_action)
        obs = self.env.step(action, np.ones(2, dtype=int))
        self.last_action = action
        if self.clock() - start > CONTROL['control_period_ms'] / 1000:
            self.overruns += 1
        wait_period(CONTROL['control_period_ms'], start, clock=self.clock, sleep=self.sleep)
        self.health()
        obs['joint_positions'] = np.asarray(obs['joint_positions']).copy()
        obs['joint_positions'][[6, 13]] = action[[6, 13]]
        return obs

    def halt(self):
        self.halted = True
        self.stop_callback()

    def hold(self, seconds, poll=None):
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            if poll is not None:
                value = poll()
                if value is not None: return value
            self.command(self.last_action)
        return None if poll is None else poll()

    def move(self, target, poll=None):
        target = np.asarray(target, dtype=float)
        start = self.observe()['joint_positions']
        joints = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
        delta = np.max(np.abs(target[joints] - start[joints]))
        period = CONTROL['control_period_ms'] / 1000
        steps = max(1, int(np.ceil(delta / (self.config['joint_speed_rad_s'] * period))))
        if steps * period > self.config['motion_timeout_s']:
            raise ValueError('Scripted motion would exceed timeout')
        for fraction in np.linspace(0, 1, steps + 1)[1:]:
            if poll is not None:
                value = poll()
                if value is not None: return value
            self.command(start + fraction * (target - start))
        deadline = self.clock() + self.config['motion_timeout_s']
        while np.max(np.abs(self.observe()['joint_positions'][joints] - target[joints])) > 0.025:
            if self.clock() >= deadline: raise TimeoutError('Robot did not reach scripted target')
            self.command(target)
        return None if poll is None else poll()

    def pose(self, name, arm, gripper=None):
        target = self.last_action.copy()
        offset = 0 if arm == 'left' else 7
        target[offset:offset + 6] = self.waypoints['poses'][name]
        if gripper is not None: target[offset + 6] = gripper
        return self.move(target)

    def route(self, name, arm, gripper=None):
        for point in self.waypoints.get('routes', {}).get(name, []):
            self.pose(point, arm)
        self.pose(name, arm, gripper)

    def home(self, arm):
        offset = 0 if arm == 'left' else 7
        for point in self.waypoints.get('routes', {}).get('home_' + arm, []):
            self.pose(point, arm)
        target = self.last_action.copy()
        target[offset:offset + 7] = home_action()[offset:offset + 7]
        self.move(target)


def load_waypoints(path, live=False):
    value = yaml.safe_load(Path(path).read_text())
    if value.get('units') != 'radians': raise ValueError('Waypoint units must be radians')
    if live and not value.get('commissioned', False):
        raise ValueError('Teach and commission all paths before live operation')
    poses = value.get('poses', {})
    required = ['{}_{}'.format(name, arm) for arm in ('left', 'right')
                for name in ('scan', 'drop_bin0', 'drop_bin1', 'drop_receiving')]
    for name in required:
        pose = np.asarray(poses.get(name), dtype=float)
        if pose.shape != (6,) or not np.isfinite(pose).all():
            raise ValueError('Teach six finite joint angles for ' + name)
    limits = np.asarray(value.get('joint_limits_rad'), dtype=float)
    if limits.shape != (12, 2) or not np.isfinite(limits).all() or np.any(limits[:, 0] >= limits[:, 1]):
        raise ValueError('Set 12 joint/cable limit pairs in radians')
    for name, pose in poses.items():
        if name.endswith(('_left', '_right')):
            side = 0 if name.endswith('_left') else 6
            pose = np.asarray(pose, dtype=float)
            if pose.shape != (6,) or not np.isfinite(pose).all() or np.any(pose < limits[side:side+6, 0]) or np.any(pose > limits[side:side+6, 1]):
                raise ValueError('Waypoint outside joint/cable limits: ' + name)
    return value


def simulation_waypoints():
    home = home_action()
    poses = {}
    for arm, offset in (('left', 0), ('right', 7)):
        for i, name in enumerate(('scan', 'drop_bin0', 'drop_bin1', 'drop_receiving')):
            target = home[offset:offset + 6].copy(); target[0] += .08 * (i + 1)
            poses[name + '_' + arm] = target.tolist()
    return dict(units='radians', commissioned=False, poses=poses, routes={},
                joint_limits_rad=[[-2*np.pi, 2*np.pi] for _ in range(12)])


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', required=True)
    args=parser.parse_args()
    clock=VirtualClock(); points=simulation_waypoints()
    motion=MotionLoop(SimulatedEnv(verbose=True),points,clock=clock,sleep=clock.sleep)
    motion.pose('scan_left','left')
    motion.route('drop_bin0_left','left')
    motion.home('left')
    print('Validated {} simulated commands'.format(len(motion.env.commands)))


if __name__ == '__main__': main()
