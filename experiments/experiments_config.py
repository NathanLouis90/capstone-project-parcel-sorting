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

# launch_nodes.py
LAUNCH_NODES = {
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "left_robot_ip": "192.168.5.1",
    "right_robot_ip": "192.168.5.2",
    "robot_number": 2,
}

CONTROL = {"control_period_ms": 40}

# run_control.py
RUN_CONTROL = {
    "using_sensor_protection": False,
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "show_img": False,
    "project_name": "preliminary",
    # Recording metadata defaults. CLI options override these values.
    "medium": None,
    "label_face": None,
    "x_range_left": (-450, 290),
    "x_range_right": (-290, 450),
    "y_range": (-750, -160),
    "z_range_left": 44,
    "z_range_right": 42,
    "save_data_path": str(DATASETS_DIR),
    "left_robot_ip": "192.168.5.1",
    "right_robot_ip": "192.168.5.2",
    "short_press_s": 0.5,
    "long_press_s": 1,
    "jpeg_quality": 50,
    "initial_control_period_s": CONTROL["control_period_ms"] / 1000,
    'camera_startup_s': 2,
    'minimum_z_velocity_m_s': -1,
    "flip_top_right": True,
    "flip_left": False,
    "version_url_template": 'http://{robot_ip}:22000/settings/version',
    "controller_type_url_template": 'http://{robot_ip}:22000/properties/controllerType',
}

# run_inference.py
RUN_INFERENCE = {
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "show_img": True,
    "model_name": 'policy_last.ckpt',
    # First observed frame in the existing recordings; commands near 1 close the grippers.
    "starting_gripper_observation": [0.99114583, 0.97942708],
    "closed_gripper_command": 1.0,
    "robot_types": ["Nova 2", "Nova 2"],
    "safe_joints_left_deg": [-90, 30, -110, 20, 90, 90, 0],
    "safe_joints_right_deg": [90, -30, 110, -20, -90, -90, 0],
    "photo_joints_left_deg": [-90, 0, -90, 0, 90, 90, 57],
    "photo_joints_right_deg": [90, 0, 90, 0, -90, -90, 57],
    'interpolation_step_rad': 0.001,
    'initial_max_steps': 150,
    'approach_max_steps': 100,
    'camera_startup_s': 2,
    'settle_s': 1,
    'max_joint_increment_rad': 0.17,
    'left_j3_min_rad': -2.6,
    'right_j3_max_rad': 2.6,
    'left_j4_min_rad': -0.6,
    'right_j4_max_rad': 0.6,
    'left_x_min_mm': -410,
    'left_x_max_mm': 210,
    'right_x_max_mm': 410,
    'right_x_min_mm': -210,
    'y_min_mm': -700,
    'y_max_mm': -210,
    'z_min_mm': 42,
    "flip_top_right": True,
    "flip_left": False,
}

# robot_home.py
ROBOT_HOME = {
    # Joint targets are in degrees. Workspace bounds above are in millimeters.
    "ARMS": {
        "left": ("192.168.5.1", ((-90, 30, -110, 20, 90, 90), (-90, 0, -90, 0, 90, 90))),
        "right": ("192.168.5.2", ((90, -30, 110, -20, -90, -90), (90, 0, 90, 0, -90, -90))),
    },
    "socket_timeout_s": 5,
    "pose_settle_timeout_s": 5,
    "dashboard_port": 29999,
    "motion_port": 30003,
    "speed_percent": 10,
    "stage_timeout_s": 300,
    "arm": "both",
    "poll_interval_s": 0.2,
    "clear_errors_settle_s": 0.5,
    "power_on_timeout_s": 30,
    "reset_timeout_s": 15,
    "enable_timeout_s": 15,
    "inspect_pose_samples": 3,
    "stable_samples": 3,
    # Collision, displacement, speed, and coordinate tolerance limits remain
    # in robot_home.py. Motion still requires an explicit CLI action.
}

