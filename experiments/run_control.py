from pathlib import Path as _ConfigPath
import sys as _config_sys
_config_sys.path.insert(0, str(_ConfigPath(__file__).resolve().parent))
from experiments_config import RUN_CONTROL, CONTROL

import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
import cv2
import time
from dataclasses import dataclass
import numpy as np
import tyro
import threading
import datetime
from pathlib import Path
import requests
from typing import Optional
from barcode_scanning.recording import RecordingSession


@dataclass
class Args:
    medium: str
    label_face: str
    robot_port: int = RUN_CONTROL["robot_port"]
    hostname: str = RUN_CONTROL["hostname"]
    show_img: bool = RUN_CONTROL["show_img"]
    save_data_path: str = RUN_CONTROL["save_data_path"]
    project_name: Optional[str] = RUN_CONTROL["project_name"]
    dry_run: bool = False



# Thread button: [lock or nor, servo or not, record or not]
# 0: lock, 1: unlock
# 0: stop servo, 1: servo
# 0: stop recording, 1: recording
what_to_do = np.array(([0, 0, 0], [0, 0, 0]))
dt_time = np.array([20240507161455], dtype=object)
using_sensor_protection = RUN_CONTROL["using_sensor_protection"]
is_falling = np.array([0])
recording_lock = threading.Lock()

def button_monitor_realtime(agent):
    # servo
    last_keys_status = np.array(([0, 0, 0], [0, 0, 0]))
    start_press_status = np.array(([0, 0], [0, 0]))  # start press
    keys_press_count = np.array(([0, 0, 0], [0, 0, 0]))

    while not is_falling[0]:
        # time.sleep(0.010)
        now_keys = agent.get_keys()
        dev_keys = now_keys - last_keys_status
        # button a
        for i in range(2):
            if dev_keys[i, 0] == -1:  # button a: start
                tic = time.time()
                start_press_status[i, 0] = 1
            if dev_keys[i, 0] == 1 and start_press_status[i, 0]:  # button a: end
                start_press_status[i, 0] = 0
                toc = time.time()
                if toc-tic < RUN_CONTROL["short_press_s"]:
                    keys_press_count[i, 0] += 1
                    # print(i, keys_press_count[i, 0], "short press", toc-tic)
                    if keys_press_count[i, 0] % 2 == 1:
                        what_to_do[i, 0] = 1
                        # log_write(__file__, "ButtonA: ["+str(i)+"] unlock")
                        print("ButtonA: [" + str(i) + "] unlock", what_to_do)
                    else:
                        what_to_do[i, 0] = 0
                        # log_write(__file__, "ButtonA: [" + str(i) + "] lock")
                        print("ButtonA: [" + str(i) + "] lock", what_to_do)

                elif toc-tic > RUN_CONTROL["long_press_s"]:
                    keys_press_count[i, 1] += 1
                    # print(i, keys_press_count[i, 1], "long press", toc-tic)
                    if keys_press_count[i, 1] % 2 == 1:
                        what_to_do[i, 1] = 1
                        # log_write(__file__, "ButtonA: [" + str(i) + "] servo")
                        print("ButtonA: [" + str(i) + "] servo")
                    else:
                        what_to_do[i, 1] = 0
                        # log_write(__file__, "ButtonA: [" + str(i) + "] stop servo")
                        print("ButtonA: [" + str(i) + "] stop servo")

        # button B
        # more than one start servo
        for i in range(2):
            if dev_keys[i, 1] == -1:  # B button pressed
                start_press_status[i, 1] = 1
            if dev_keys[i, 1] == 1:
                start_press_status[i, 1] = 0
                with recording_lock:
                    if not what_to_do[0, 2]:
                        if keys_press_count[0, 1] % 2 == 1 or keys_press_count[1, 1] % 2 == 1:
                            what_to_do[0, 2] = 1
                            # log_write(__file__, "ButtonB: [" + str(i) + "] recording")
                            # new recording
                            now_time = datetime.datetime.now()
                            dt_time[0] = int(now_time.strftime("%Y%m%d%H%M%S%f"))
                            keys_press_count[0, 2] += 1
                    else:
                        what_to_do[0, 2] = 0
                        keys_press_count[0, 2] += 1
                        # log_write(__file__, "ButtonB: [" + str(i) + "] stop recording")

        # status fall
        if using_sensor_protection:
            for i in range(2):
                if now_keys[i, 2] and what_to_do[i, 0]:  # button a: lock
                    agent.set_torque(2, True)
                    is_falling[0] = 1

        last_keys_status = now_keys


# Thread: camera
npy_list = np.array([np.zeros(480*640*3), np.zeros(480*640*3), np.zeros(480*640*3)])
npy_len_list = np.array([0, 0, 0])
img_list = np.array([np.zeros((480, 640, 3)), np.zeros((480, 640, 3)), np.zeros((480, 640, 3))])


def run_thread_cam(rs_cam, which_cam):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), RUN_CONTROL["jpeg_quality"]]
    while 1:
        image_cam, _ = rs_cam.read()
        image_cam = image_cam[:, :, ::-1]
        img_list[which_cam] = image_cam
        _, image_ = cv2.imencode('.jpg', image_cam, encode_param)
        npy_list[which_cam][:len(image_)] = image_
        npy_len_list[which_cam] = len(image_)



from experiments.kinematics import claw_width, forward_kinematics

def calculate_vel_pos(action, last_action, total_time, r_type):
    """
    Calculate the velocity for forward kinematics
    """
    claw_left = claw_width(action[6])
    claw_right = claw_width(action[13])

    positions = {}
    vel = {}

    for side in ['left', 'right']:
        for paw in ['left', 'right']:
            coef = 1 if paw == 'left' else -1
            claw = claw_left if side == 'left' else claw_right
            claw *= coef

            current_fk = forward_kinematics(*action[0:6] if side == 'left' else action[7:13], claw, r_type)
            last_fk = forward_kinematics(*last_action[0:6] if side == 'left' else last_action[7:13], claw, r_type)

            positions[f'{side}_{paw}'] = current_fk
            vel[f'{side}_{paw}'] = (current_fk - last_fk) / total_time

    return positions, vel

# Check that the positions is within a safe zone
def is_within_safe_position(position, x_range, y_range, z_min):
    return x_range[0] <= position[0] <= x_range[1] and \
           y_range[0] <= position[1] <= y_range[1] and \
           position[2] > z_min


def check_pose_protection(positions, vel, what_to_do):
    protect_err = False
    warnings = []

    delta_left_left = vel['left_left']
    delta_left_right = vel['left_right']
    delta_right_left = vel['right_left']
    delta_right_right = vel['right_right']

    positions_mm = {key: value * 1000 for key, value in positions.items()}
    # Define a safe zone
    # left arm (jaw tip position) limit:  290>x>-450  -750<Y<-160  z>44;
    # right arm (jaw tip position) limit:  450>x>-290  -750<Y<-160  z>42;
    x_range_left = RUN_CONTROL["x_range_left"]
    x_range_right = RUN_CONTROL["x_range_right"]
    y_range = RUN_CONTROL["y_range"]
    z_range_left = RUN_CONTROL["z_range_left"]
    z_range_right = RUN_CONTROL["z_range_right"]

    if what_to_do[0, 1]:  # The left hand is in sync
        # Z direction speed limit -1 m/s
        if delta_left_left[2] < RUN_CONTROL["minimum_z_velocity_m_s"] or delta_left_right[2] < RUN_CONTROL["minimum_z_velocity_m_s"]:
            warnings.append("[Warn]:The left robot speed of the TCP is moving too fast!")
            warnings.append(f"delta_left_left: {delta_left_left[2]}")
            protect_err = True
        # Left arm working space limitation
        positions_to_check = ['left_left', 'left_right']
        x_ranges = [x_range_left, x_range_left]
        z_ranges = [z_range_left, z_range_left]
        if not all(is_within_safe_position(positions_mm[pos], x_range, y_range, z_range)
                   for pos, x_range, z_range in zip(positions_to_check, x_ranges, z_ranges)):
            warnings.append("[Warn]:The left arm is out of the safe zone!")
            protect_err = True

    if what_to_do[1, 1]:  # The right hand is in sync
        # Z direction speed limit -1 m/s
        if delta_right_left[2] < RUN_CONTROL["minimum_z_velocity_m_s"] or delta_right_right[2] < RUN_CONTROL["minimum_z_velocity_m_s"]:
            warnings.append("[Warn]:The right robot speed of the TCP is moving too fast!")
            warnings.append(f"delta_right_left: {delta_right_left[2]}")
            protect_err = True
        # Right arm working space limitation
        positions_to_check = ['right_left', 'right_right']
        x_ranges = [x_range_right, x_range_right]
        z_ranges = [z_range_right, z_range_right]
        if not all(is_within_safe_position(positions_mm[pos], x_range, y_range, z_range)
                   for pos, x_range, z_range in zip(positions_to_check, x_ranges, z_ranges)):
            warnings.append("[Warn]:The right arm is out of the safe zone!")
            protect_err = True

    for warning in warnings:
        print(warning)

    return protect_err

def check_joint_safety(action):
    protect_err = False
    if not (action[2] < 0):
        print("[Warn]:The J3 joints of the robotic arm are out of the safe position! ")
        print(action)
        protect_err = True
    if not (action[9] > 0):
        print("[Warn]:The J3 joints of the robotic arm are out of the safe position! ")
        print(action)
        protect_err = True
    return protect_err

def get_firmware_version_satisfied(robot_ip):
    try:
        response = requests.post(RUN_CONTROL["version_url_template"].format(robot_ip=robot_ip))
        if response.status_code == 200:
            rt_version = response.text.split("{")[1].split("\n\t")[3].split(":")[1].split("\"")[1].split("-")[0].split(".")
            rt_num = "".join(rt_version)
            return 1, int(rt_num)
        else:
            print("Failed to retrieve the version webpage")
            return 0, 0
    except Exception as e:
        print(e)
        return 0, 0

def get_robot_type(robot_ip):
    response = requests.post(RUN_CONTROL["controller_type_url_template"].format(robot_ip=robot_ip))
    if response.status_code == 200:
        print("The type of robot is:", eval(response.text)["name"])
        return eval(response.text)["name"]
    else:
        print("Failed to obtain the type of robot")
        return None

def check_firmware_version():
    left_version = get_firmware_version_satisfied(RUN_CONTROL["left_robot_ip"])
    right_version = get_firmware_version_satisfied(RUN_CONTROL["right_robot_ip"])
    if left_version[1] < 3581 or left_version[1]>=4000:
        print("[ERROR]Left hand error[192.168.5.1]:firmware version requires V3 and must >=3.5.8.1 (found: %s),please check and update"%left_version[1])
        return False
    if right_version[1] < 3581 or right_version[1]>=4000:
        print("[ERROR]Right hand error[192.168.5.1]:firmware version requires V3 and must >=3.5.8.1 (found: {%s}),please check and update"% right_version[1])
        return False
    return True

def _run_control(args, recording_session=None):
    global BimanualAgent, save_frame, RobotEnv, ZMQClientRobot, mismatch_data_write, wait_period, log_write, mk_dir, robot_pose_init, pose_check, dynamic_approach, obs_action_check, servo_action_check, load_ini_data_hands, set_light, load_ini_data_camera, DobotAgent, RealSenseCamera
    from dobot_control.agents.agent import BimanualAgent
    from scripts.format_obs import save_frame
    from dobot_control.env import RobotEnv
    from dobot_control.robots.robot_node import ZMQClientRobot
    from scripts.function_util import mismatch_data_write, wait_period, log_write, mk_dir
    from scripts.manipulate_utils import robot_pose_init, pose_check, dynamic_approach, obs_action_check, servo_action_check, load_ini_data_hands, set_light, load_ini_data_camera
    from dobot_control.agents.dobot_agent import DobotAgent
    from dobot_control.cameras.realsense_camera import RealSenseCamera
    # create dataset file path
    save_dir = str(Path(args.save_data_path).expanduser() / args.project_name / "collect_data")
    mk_dir(save_dir)

    # camera init
    camera_dict = load_ini_data_camera()
    rs1 = RealSenseCamera(flip=RUN_CONTROL["flip_top_right"], device_id=camera_dict["top"])
    rs2 = RealSenseCamera(flip=RUN_CONTROL["flip_left"], device_id=camera_dict["left"])
    rs3 = RealSenseCamera(flip=RUN_CONTROL["flip_top_right"], device_id=camera_dict["right"])
    thread_cam_top = threading.Thread(target=run_thread_cam, args=(rs1, 0), daemon=True)
    thread_cam_left = threading.Thread(target=run_thread_cam, args=(rs2, 1), daemon=True)
    thread_cam_right = threading.Thread(target=run_thread_cam, args=(rs3, 2), daemon=True)
    thread_cam_top.start()
    thread_cam_left.start()
    thread_cam_right.start()
    show_canvas = np.zeros((480, 640*3, 3), dtype=np.uint8)
    time.sleep(RUN_CONTROL["camera_startup_s"])
    print("camera thread init success...")

    # agent init
    _, hands_dict = load_ini_data_hands()
    left_agent = DobotAgent(which_hand="LEFT", dobot_config=hands_dict["HAND_LEFT"])
    right_agent = DobotAgent(which_hand="RIGHT", dobot_config=hands_dict["HAND_RIGHT"])
    agent = BimanualAgent(left_agent, right_agent)

    # pose init
    print("Waiting to connect the robot...")
    robot_client = ZMQClientRobot(port=args.robot_port, host=args.hostname)
    print("If the robot fails to initialize successfully after 5 seconds,please check that the robot network is connected correctly and make sure TCP/IP mode is turned!")
    if check_firmware_version()==False:
        return
    robot_type = get_robot_type(RUN_CONTROL["left_robot_ip"])
    env = RobotEnv(robot_client)
    for output_index in (1, 2, 3):
        print(f"Setting robot output {output_index}/3...", flush=True)
        env.set_do_status([output_index, 0])
    print("Starting robot initial pose...", flush=True)
    robot_pose_init(env)
    start_servo = False
    curr_light = "dark"
    print("robot init success....")

    # button status init
    last_status = np.array(([0, 0, 0], [0, 0, 0]))  # init lock
    thread_button = threading.Thread(target=button_monitor_realtime, args=(agent, ), daemon=True)
    thread_button.start()
    print("button thread init success...")

    print("-------------------------Ok, let's start------------------------")
    idx = 0
    safe_limit = 0
    total_time = RUN_CONTROL["initial_control_period_s"]

    last_recording = False
    while 1:
        tic = time.monotonic()
        with recording_lock:
            recording = bool(what_to_do[0, 2])
            episode_timestamp = dt_time[0]
        if recording_session is not None:
            if recording and not last_recording:
                recording_session.start(Path(save_dir) / str(episode_timestamp))
            elif last_recording and not recording:
                recording_session.stop()
        last_recording = recording

        assert thread_cam_top.is_alive(), "Error: please check the top camera!"
        assert thread_cam_left.is_alive(), "Error: please check the left camera!"
        assert thread_cam_right.is_alive(), "Error: please check the right camera!"
        assert not is_falling, "sensor   detection!"

        action = agent.act({})
        print(action)
        dev_what_to_do = what_to_do.copy()-last_status
        last_status = what_to_do.copy()
        # button A: short press event. lock and unlock
        for i in range(2):
            if dev_what_to_do[i, 0] != 0:
                agent.set_torque(i, not what_to_do[i, 0])

        # button A: long press event. servo or not
        if dev_what_to_do[0, 1] == 1 or dev_what_to_do[1, 1] == 1:
            # pose check between main hand and the follower
            print("dynamic approach")
            for i in range(2):
                if what_to_do[i, 1]:
                    agent.set_torque(i, True)
            flag_in = np.array([what_to_do[0, 1], what_to_do[1, 1]])
            last_action = dynamic_approach(env, agent, flag_in)
            for i in range(2):
                if what_to_do[i, 0]:
                    if what_to_do[i, 1]:
                        agent.set_torque(i, False)
            start_servo = True
            obs = env.get_obs()
            if curr_light != "green":
                curr_light = set_light(env, "yellow", 1)

        if dev_what_to_do[0, 1] == -1 or dev_what_to_do[1, 1] == -1:
            flag_in = np.array([what_to_do[0, 1], what_to_do[1, 1]])
            if what_to_do[0, 1] == 0 and what_to_do[1, 1] == 0:
                set_light(env, "green", 0)

        if (what_to_do[0, 1] or what_to_do[1, 1]) and start_servo:
            action = agent.act({})
            err3, action = servo_action_check(action, last_action, flag_in)
            assert err3 != 0, set_light(env, "red", 1)

            # ×××××××××××××××××××××××××××××Security protection×××××××××××××××××××××××××××××××××××××××××××
            # [Note]: Modify the protection parameters in this section carefully !
            protect_err = [False, False]
            if (safe_limit < 1):
                safe_limit = safe_limit + 1
            else:
                positions, vel = calculate_vel_pos(action, last_action, total_time, robot_type)
                protect_err[0] = check_pose_protection(positions, vel, what_to_do)
                protect_err[1] = check_joint_safety(action)
            if any(protect_err):
                set_light(env, "red", 1)
                time.sleep(1)
                exit()
            # ×××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××××

            # button B: recording or not
            if dev_what_to_do[0, 2] == 1:
                curr_light = set_light(env, "green", 1)
            elif dev_what_to_do[0, 2] == -1:
                curr_light = set_light(env, "yellow", 1)
            if recording:
                idx += 1
                left_dir = save_dir + f"/{episode_timestamp}/leftImg/"
                right_dir = save_dir + f"/{episode_timestamp}/rightImg/"
                top_dir = save_dir + f"/{episode_timestamp}/topImg/"
                mk_dir(right_dir)
                mk_dir(top_dir)
                if mk_dir(left_dir):
                    idx = 0
                cv2.imwrite(top_dir + f"{idx}.jpg", img_list[0])
                cv2.imwrite(left_dir + f"{idx}.jpg", img_list[1])
                cv2.imwrite(right_dir + f"{idx}.jpg", img_list[2])

                obs_dir = save_dir + f"/{episode_timestamp}/observation/"
                mk_dir(obs_dir)
                save_frame(obs_dir, idx, obs, action)
                if recording_session is not None:
                    recording_session.record_frame()

            obs = env.step(action, flag_in)
            obs["joint_positions"][6] = action[6]
            obs["joint_positions"][13] = action[13]
            last_action = action
        else:
            start_servo = False
            safe_limit = 0

        # img show
        if args.show_img:
            show_canvas[:, :640] = np.asarray(img_list[0], dtype="uint8")
            show_canvas[:, 640:640 * 2] = np.asarray(img_list[1], dtype="uint8")
            show_canvas[:, 640 * 2:640 * 3] = np.asarray(img_list[2], dtype="uint8")
            cv2.imshow("0", show_canvas)
            key = cv2.waitKey(1) & 0xFF

        elapsed = time.monotonic() - tic
        if elapsed > CONTROL["control_period_ms"] / 1000:
            print("[Warn]: recording control period overrun: {:.1f} ms".format(elapsed * 1000))
            if recording_session is not None and recording_session.active:
                recording_session.metadata["control_overruns"] += 1
        wait_period(CONTROL["control_period_ms"], tic, clock=time.monotonic)
        # Include pacing in the previous sample interval used by FK velocity checks.
        total_time = time.monotonic() - tic
        print("total time: ", total_time)



def main(args):
    args.project_name = args.project_name or args.medium
    session = RecordingSession(args.medium, args.label_face)
    if args.dry_run:
        episode = Path(args.save_data_path) / args.project_name / 'collect_data' / ('dry_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))
        session.start(episode)
        session.record_frame()
        session.stop()
        print('Metadata-only dry run; not a training episode: {}'.format(episode))
        return
    try:
        _run_control(args, session)
    finally:
        session.stop(complete=False)


if __name__ == '__main__':
    main(tyro.cli(Args))
