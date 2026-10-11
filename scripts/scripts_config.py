"""Editable defaults for this folder.

Sections are named after their source files. CLI options override these defaults.
Paths built from __file__ are relative to this config; other paths preserve their
existing meaning. Hardware calibration and credentials remain in
scripts/dobot_config/dobot_settings.ini. Restart programs after editing.
Protocol constants, array indices, and mathematical constants remain in code.
"""

from pathlib import Path

# All dataset defaults are rooted inside this repository.
DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"

# count_episodes.py
COUNT_EPISODES = {
    "root_dir": str(DATASETS_DIR),
}

# prepare_act_datasets.py
# ModelTrain/constants.py also reads these project settings, so validation and
# training use the same paths, episode lengths, split, and camera inputs.
# For another recording project, add an entry with its folder name as the key.
# Use medium="carton" for cartons; bin_index=None does not check a bin.
PREPARE_ACT_DATASETS = {
    "root_dir": str(DATASETS_DIR),
    "projects": {
        "first_set_poly_mailer_A": {
            "policy_stage": "A",
            "medium": "poly_mailer",
            "bin_index": None,
            "episode_len": 400,
            "train_ratio": 0.8,
            "camera_names": ["top", "left_wrist", "right_wrist"],
        },
        "first_set_poly_mailer_B_bin_0": {
            "policy_stage": "B",
            "medium": "poly_mailer",
            "bin_index": 0,
            "episode_len": 400,
            "train_ratio": 0.8,
            "camera_names": ["top", "left_wrist", "right_wrist"],
        },
        "first_set_poly_mailer_B_bin_1": {
            "policy_stage": "B",
            "medium": "poly_mailer",
            "bin_index": 1,
            "episode_len": 400,
            "train_ratio": 0.8,
            "camera_names": ["top", "left_wrist", "right_wrist"],
        },
    },
}

# 1_find_port.py
SCRIPT_1_FIND_PORT = {
    "baud_rate_list": [2000000, 1000000],
    "hardware_settings_path": str(Path(__file__).resolve().parent / "dobot_config" / "dobot_settings.ini"),
    "minimum_ports": 4,
}

# 2_get_offset.py
SCRIPT_2_GET_OFFSET = {
    "gripper_ids": {"HAND_LEFT": [8], "HAND_RIGHT": [18]},
    "gripper_open_offset_deg": 0.2,
    "gripper_close_offset_deg": 30,
    "hardware_settings_path": str(Path(__file__).resolve().parent / "dobot_config" / "dobot_settings.ini"),
}

# 3_just_buttonA.py
SCRIPT_3_JUST_BUTTONA = {
    "using_sensor_protection": False,
    "agent": "dobot",
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "max_step_delta": 0.08,
    "show_img": False,
    "log_dir": "~/bc_data",
    "save_data_path": str(DATASETS_DIR),
    'short_press_s': 0.5,
    'long_press_s': 1,
    'loop_period_ms': 35,
}

# 4_collect2train_data.py
SCRIPT_4_COLLECT2TRAIN_DATA = {
    "root_dir": str(DATASETS_DIR),
    "dataset_name": "first_test",
}

# 5_camera_read.py
SCRIPT_5_CAMERA_READ = {
    "flip_top_right": True,
    "flip_left": False,
}

# 6_dataset_count.py
SCRIPT_6_DATASET_COUNT = {
    "dataset_name": "dataset_package_test",
    "root_dir": str(DATASETS_DIR),
}

# function_util.py
FUNCTION_UTIL = {
    "log_dir": str(Path(__file__).resolve().parent / "logs") + "/",
    "video_codec": 'mp4v',
    "hardware_settings_path": str(Path(__file__).resolve().parent / "dobot_config" / "dobot_settings.ini"),
}

# manipulate_utils.py
MANIPULATE_UTILS = {
    "stage1_left_deg": [-90, 30, -110, 20, 90, 90, 0],
    "stage1_right_deg": [90, -30, 110, -20, -90, -90, 0],
    "stage2_left_deg": [-90, 0, -90, 0, 90, 90, 0],
    "stage2_right_deg": [90, 0, 90, 0, -90, -90, 0],
    "hardware_settings_path": str(Path(__file__).resolve().parent / "dobot_config" / "dobot_settings.ini"),
    'home_step_rad': 0.01,
    'home_max_steps': 100,
    'approach_step_rad': 0.01,
    'approach_period_ms': 50,
    'servo_max_delta_rad': 0.9,
    'obs_max_delta_rad': 0.6,
    'obs_report_delta_rad': 0.5,
    'pose_max_delta_rad': 0.6,
}

# script_collect2train.py
SCRIPT_COLLECT2TRAIN = {
    "MIRROR_STATE_MULTIPLY": [1, 1, 1, 1, 1, 1, 1],
    "MIRROR_BASE_MULTIPLY": [1, 1],
    "COMPRESS": True,
    "root_dir": str(DATASETS_DIR),
    "dataset_name": "dataset_package_test",
    "date_collect": "20241010",
    "jpeg_quality": 50,
    "video_frame_period_s": 0.02,
    "episode_index": '0',
    "hdf5_cache_bytes": 2097152,
}
