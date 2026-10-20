"""Editable defaults for this folder.

Sections are named after their source files. CLI options override these defaults.
Paths built from __file__ are relative to this config; other paths preserve their
existing meaning. Hardware calibration and credentials remain in
scripts/dobot_config/dobot_settings.ini. Restart programs after editing.
Protocol constants, array indices, and mathematical constants remain in code.
"""

from pathlib import Path
from experiments.experiments_config import CONTROL

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
# Each project contains fresh pick-to-scan demonstrations for one medium.
PREPARE_ACT_DATASETS = {
    "root_dir": str(DATASETS_DIR),
    "home_tolerance_rad": 0.12,
    "idle_tolerance_rad": 0.12,
    "gripper_tolerance": 0.08,
    "rate_tolerance_fraction": 0.10,
    "projects": {
        medium: {"schema_version": 3, "medium": medium, "episode_len": 500,
                 "train_ratio": 0.8, "camera_names": ["top", "left_wrist", "right_wrist"],
                 "control_period_ms": CONTROL["control_period_ms"]}
        for medium in ("envelope", "poly_mailer", "carton")
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

# 5_camera_read.py
SCRIPT_5_CAMERA_READ = {
    "flip_top_right": True,
    "flip_left": False,
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
    "COMPRESS": True,
    "root_dir": str(DATASETS_DIR),
    "jpeg_quality": 50,
    "video_frame_period_s": CONTROL["control_period_ms"] / 1000,
    "episode_index": '0',
    "hdf5_cache_bytes": 2097152,
}

# Shared parcel dataset recipes and ACT / Diffusion Policy training defaults.
ROBOMIMIC = {
    "recipes": {medium: {"medium": medium} for medium in ("envelope", "poly_mailer", "carton")},
    "train_fraction": 0.8,
    "seed": 0,
    "image_size": [128, 128],  # Shared resize for both algorithms; HWC uint8 RGB.
    "cameras": ["top", "left_wrist", "right_wrist"],
    "batch_size": 8,
    "epochs": 1000,
    "steps_per_epoch": 100,
    "validation_steps": 10,
    "action_chunk": 16,
    "observation_horizon": 2,
    "action_horizon": 8,
    "learning_rate": 0.0001,
    "visual_feature_dimension": 64,
    "save_every_epochs": 50,
    "smoke_epochs": 1,
    "smoke_steps": 2,
    "smoke_batch_size": 2,
    "smoke_act_hidden_dim": 64,
    "smoke_act_feedforward_dim": 128,
    "smoke_act_layers": 1,
    "smoke_unet_down_dims": [32, 64, 128],
    "smoke_diffusion_steps": 10,
}

# review_episodes.py: offline playback and review decisions.
REVIEW_EPISODES = {
    "preview_camera_size": [240, 320],  # Height, width in pixels per camera.
    "playback_speed": 1.0,
    "fallback_period_ms": CONTROL["control_period_ms"],
    "window_name": "Episode review: a accept, r reject, s skip, p replay, space pause, q quit",
}
