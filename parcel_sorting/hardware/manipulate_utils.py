from config.settings import MANIPULATE_UTILS

import numpy as np
import time
import configparser
from parcel_sorting.hardware.agents.dobot_agent import DobotRobotConfig
import os
from pathlib import Path
from dataclasses import dataclass

from parcel_sorting.utils import wait_period, log_write


def set_light(env, which_color, which_status):
    print("light change")
    if which_color == "red":
        env.set_do_status([3, 0])
        env.set_do_status([2, 0])
        env.set_do_status([1, which_status])
    elif which_color == "yellow":
        env.set_do_status([3, 0])
        env.set_do_status([2, which_status])
        env.set_do_status([1, 0])
    elif which_color == "green":
        env.set_do_status([3, which_status])
        env.set_do_status([2, 0])
        env.set_do_status([1, 0])
    return which_color

def load_ini_data_camera():
    camera_dict = {"top": None, "left": None, "right": None}
    ini_file_path = MANIPULATE_UTILS["hardware_settings_path"]
    ini_file = configparser.ConfigParser()
    ini_file.read(ini_file_path)
    for _cam in camera_dict.keys():
        camera_dict[_cam] = ini_file.get("CAMERA", _cam)
    return camera_dict

def load_ini_data_hands():
    ini_file_path = MANIPULATE_UTILS["hardware_settings_path"]
    ini_file = configparser.ConfigParser()
    ini_file.read(ini_file_path)

    hands_dict = {"HAND_LEFT": None, "HAND_RIGHT": None}
    for _hand in hands_dict.keys():
        hands_dict[_hand] = DobotRobotConfig(
            joint_ids=[int(i) for i in ini_file.get(_hand, "joint_ids").split(",")],
            append_id=int(ini_file.get(_hand, "append_id")),
            port=ini_file.get(_hand, "port"),
            joint_offsets=[float(i) for i in ini_file.get(_hand, "joint_offsets").split(",")],
            joint_signs=[int(i) for i in ini_file.get(_hand, "joint_signs").split(",")],
            gripper_config=[int(i) for i in ini_file.get(_hand, "gripper_config").split(",")],
            start_joints=[float(i) for i in ini_file.get(_hand, "start_joints").split(",")],
            baud_rate=int(ini_file.get(_hand, "baud_rate")),
            using_sensor=int(ini_file.get(_hand, "using_sensor")))
    return ini_file, hands_dict


@dataclass
class GripperConfig:
    id_name: int
    pos: tuple
    port: str


def load_ini_data_gripper():
    ini_file_path = MANIPULATE_UTILS["hardware_settings_path"]
    ini_file = configparser.ConfigParser()
    ini_file.read(ini_file_path)

    gripper_dict = {"GRIPPER_LEFT": None, "GRIPPER_RIGHT": None}
    for _gripper in gripper_dict.keys():
        gripper_dict[_gripper] = GripperConfig(id_name=int(ini_file.get(_gripper, "id")),
                                               pos=list([int(i) for i in ini_file.get(_gripper, "pos").split(",")]),
                                               port=ini_file.get(_gripper, "port"))
    return ini_file, gripper_dict

# robot init move
def robot_pose_init(env):
    # go to the first point
    reset_joints_left = np.deg2rad(MANIPULATE_UTILS["stage1_left_deg"])  #
    reset_joints_right = np.deg2rad(MANIPULATE_UTILS["stage1_right_deg"])
    reset_joints = np.concatenate([reset_joints_left, reset_joints_right])
    print("Initial pose stage 1: reading robot joints...", flush=True)
    curr_joints = env.get_obs()["joint_positions"]
    max_delta = (np.abs(curr_joints - reset_joints)).max()
    steps = min(int(max_delta / MANIPULATE_UTILS["home_step_rad"]), MANIPULATE_UTILS["home_max_steps"])
    print(f"Initial pose stage 1: {steps} steps", flush=True)
    for step_index, jnt in enumerate(np.linspace(curr_joints, reset_joints, steps), start=1):
        if step_index == 1 or step_index % 10 == 0:
            print(f"Initial pose stage 1: step {step_index}/{steps}", flush=True)
        env.step(jnt, [1, 1])

    # go to the second point
    reset_joints_left = np.deg2rad(MANIPULATE_UTILS["stage2_left_deg"])  #
    reset_joints_right = np.deg2rad(MANIPULATE_UTILS["stage2_right_deg"])
    reset_joints = np.concatenate([reset_joints_left, reset_joints_right])
    print("Initial pose stage 2: reading robot joints...", flush=True)
    curr_joints = env.get_obs()["joint_positions"]
    max_delta = (np.abs(curr_joints - reset_joints)).max()
    steps = min(int(max_delta / MANIPULATE_UTILS["home_step_rad"]), MANIPULATE_UTILS["home_max_steps"])
    print(f"Initial pose stage 2: {steps} steps", flush=True)
    for step_index, jnt in enumerate(np.linspace(curr_joints, reset_joints, steps), start=1):
        if step_index == 1 or step_index % 10 == 0:
            print(f"Initial pose stage 2: step {step_index}/{steps}", flush=True)
        env.step(jnt, [1, 1])


# main hand pose dev check
def obs_action_check(env, agent):
    from parcel_sorting.safety.inference_safety import validate_joint_gap
    obs = env.get_obs()
    joints = obs["joint_positions"]
    action = agent.act(obs)
    try:
        validate_joint_gap(action, joints, MANIPULATE_UTILS["obs_max_delta_rad"],
                           "Leader target exceeds measured tracking limit")
    except ValueError as error:
        print(str(error))
        return 0, 0
    return 1, action


# nova2 dev joint check
def servo_action_check(action, last_action, flag_in, step_len=MANIPULATE_UTILS["servo_max_delta_rad"]):
    from parcel_sorting.safety.inference_safety import prepare_recording_action
    try:
        return 1, prepare_recording_action(action, last_action, step_len)
    except ValueError as error:
        print("Servo action rejected: {}".format(error))
        return 0, action


# pose check between main hand and the follower
def pose_check(env, agent, flag_in):
    start_pos = agent.act(env.get_obs())
    obs = env.get_obs()
    joints = obs["joint_positions"]
    err_pose_check, action_return = servo_action_check(start_pos, joints, flag_in, MANIPULATE_UTILS["pose_max_delta_rad"])
    if err_pose_check:
        return 1, action_return
    else:
        return 0, action_return


def dynamic_approach(env, agent, flag_in):
    err1, action1 = pose_check(env, agent, flag_in)
    assert err1 != 0, set_light(env, "red", 1)
    obs = env.get_obs()
    joints = obs["joint_positions"]
    # log_write(__file__, "joints: " + str(joints))
    # log_write(__file__, "action1: " + str(action1))
    joints[6] = action1[6]
    joints[13] = action1[13]
    if flag_in[0] and not flag_in[1]:
        abs_deltas = max(np.abs(action1[:6] - joints[:6]))
    elif not flag_in[0] and flag_in[1]:
        abs_deltas = max(np.abs(action1[7:13] - joints[7:13]))
    else:
        abs_deltas = max(np.abs(action1 - joints))
    # log_write(__file__,  "abs_deltas: " + str(abs_deltas))
    steps = int(abs_deltas / MANIPULATE_UTILS["approach_step_rad"])
    # log_write(__file__, "steps: " + str(steps))

    for jnt in np.linspace(joints, action1, steps):
        env.step(jnt, flag_in)
        tic = time.time()
        wait_period(MANIPULATE_UTILS["approach_period_ms"], tic)

        # log_write(__file__, "flag_in: " + str(flag_in))
        # log_write(__file__, "jnt: " + str(jnt))
    # time.sleep(0.05)
    err1, action1 = pose_check(env, agent, flag_in)
    assert err1 != 0, set_light(env, "red", 1)
    return action1
