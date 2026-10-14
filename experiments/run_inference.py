"""Run one explicitly selected vendor ACT task on the robot."""
import argparse
from pathlib import Path
import sys
import time
import threading
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from experiments.experiments_config import CONTROL, RUN_INFERENCE
from experiments.inference_safety import validate_action, resolve_episode_length, prepare_vendor_action
from scripts.control_timing import wait_period
from scripts.scripts_config import MANIPULATE_UTILS, PREPARE_ACT_DATASETS


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-name', required=True)
    parser.add_argument('--checkpoint-dir', required=True, type=Path)
    parser.add_argument('--model-name', default=RUN_INFERENCE['model_name'])
    parser.add_argument('--episode-len', type=int)
    parser.add_argument('--robot-port', type=int, default=RUN_INFERENCE['robot_port'])
    parser.add_argument('--hostname', default=RUN_INFERENCE['hostname'])
    parser.add_argument('--show-img', action='store_true')
    return parser.parse_args(argv)


def main(args):
    # Reject invalid requests and load the checkpoint before opening any hardware.
    from ModelTrain.constants import TASK_CONFIGS
    episode_len = resolve_episode_length(args.task_name, args.episode_len, TASK_CONFIGS)
    project = PREPARE_ACT_DATASETS['projects'].get(args.task_name)
    if project is None:
        raise ValueError('Register parcel task metadata in PREPARE_ACT_DATASETS before deployment')
    checkpoint_dir = args.checkpoint_dir.expanduser().resolve()
    if not (checkpoint_dir / args.model_name).is_file():
        raise ValueError('Missing checkpoint: {}'.format(checkpoint_dir / args.model_name))
    sys.path.insert(0, str(REPO_ROOT / 'ModelTrain'))
    from ModelTrain.module.model_module import Imitate_Model
    model = Imitate_Model(ckpt_dir=str(checkpoint_dir), ckpt_name=args.model_name)
    model.loadModel()
    # B and mailer/carton A have one active arm. Envelope A uses both arms.
    active = np.array([1, 1] if project['policy_stage'] == 'A' and project['medium'] == 'envelope'
                      else [1, 0] if project['policy_stage'] == 'A' else [0, 1])
    import cv2
    from dobot_control.env import RobotEnv
    from dobot_control.robots.robot_node import ZMQClientRobot
    from dobot_control.cameras.realsense_camera import RealSenseCamera
    from scripts.manipulate_utils import load_ini_data_camera
    images, cameras, threads = {}, [], []
    running = threading.Event()
    running.set()

    def read_camera(camera, name):
        while running.is_set():
            frame, _ = camera.read()
            images[name] = frame[:, :, ::-1]

    overruns, steps = 0, 0
    try:
        identities = load_ini_data_camera()
        for name, identity, flip in (('top', identities['top'], RUN_INFERENCE['flip_top_right']),
                                    ('left_wrist', identities['left'], RUN_INFERENCE['flip_left']),
                                    ('right_wrist', identities['right'], RUN_INFERENCE['flip_top_right'])):
            camera = RealSenseCamera(flip=flip, device_id=identity)
            cameras.append(camera)
            thread = threading.Thread(target=read_camera, args=(camera, name), daemon=True)
            thread.start()
            threads.append(thread)
        time.sleep(RUN_INFERENCE['camera_startup_s'])
        if len(images) != 3:
            raise RuntimeError('All three cameras must supply images before startup')
        env = RobotEnv(ZMQClientRobot(port=args.robot_port, host=args.hostname))
        home = np.concatenate([np.deg2rad(MANIPULATE_UTILS['stage2_left_deg']),
                               np.deg2rad(MANIPULATE_UTILS['stage2_right_deg'])])
        home[[6, 13]] = RUN_INFERENCE['closed_gripper_command']
        current = np.asarray(env.get_obs()['joint_positions'])
        # Require explicit operator homing via robot_home.py before policy execution.
        joint_indices = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
        if np.abs(current[joint_indices] - home[joint_indices]).max() > PREPARE_ACT_DATASETS['home_tolerance_rad']:
            raise ValueError('Both arms must be at home before inference; use robot_home.py')
        validate_action(home, current)
        obs = env.step(home, np.array([1, 1]))
        obs['joint_positions'][[6, 13]] = RUN_INFERENCE['starting_gripper_observation']
        previous = np.asarray(obs['joint_positions']).copy()
        for t in range(episode_len):
            start = time.monotonic()
            if not all(thread.is_alive() for thread in threads):
                raise RuntimeError('Camera thread stopped')
            observation = {'qpos': previous.copy(), 'images': dict(images)}
            if args.show_img:
                cv2.imshow('Inference', np.hstack([images[k] for k in ('left_wrist', 'right_wrist', 'top')]))
                if cv2.waitKey(1) & 0xff == ord('q'):
                    break
            # Vendor loader appends two base-action dimensions; robots have 14 DoF.
            action = prepare_vendor_action(model.predict(observation, t))
            for offset, enabled in zip((0, 7), active):
                if not enabled:
                    action[offset:offset + 7] = home[offset:offset + 7]
            validate_action(action, previous)
            obs = env.step(action, active)
            previous = np.asarray(obs['joint_positions']).copy()
            previous[[6, 13]] = action[[6, 13]]
            steps += 1
            elapsed = time.monotonic() - start
            if elapsed > CONTROL['control_period_ms'] / 1000:
                overruns += 1
                print('[Warn]: inference control period overrun: {:.1f} ms'.format(elapsed * 1000))
            wait_period(CONTROL['control_period_ms'], start, clock=time.monotonic)
        print('Rollout ended; physical success requires operator evaluation.')
    finally:
        running.clear()
        for thread in threads:
            thread.join(timeout=RUN_INFERENCE['settle_s'])
        cv2.destroyAllWindows()
        print('Inference: {} steps, {} control overruns'.format(steps, overruns))


if __name__ == '__main__':
    main(parse_args())
