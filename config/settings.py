"""Editable settings for the parcel-sorting cell.

Edit a value, then restart the program that uses it. Command-line options
override these defaults. Sections are grouped by workflow stage and named after
the program or module that reads them.

Local files in this folder (ignored by Git):
- dobot_settings.ini: camera serials, USB ports and leader calibration.
- waypoints.local.yaml: taught poses, routes and verified joint limits.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent
DATASETS_DIR = REPO_ROOT / "datasets"
HARDWARE_SETTINGS_PATH = str(CONFIG_DIR / "dobot_settings.ini")
WAYPOINT_FILE = str(CONFIG_DIR / "waypoints.local.yaml")


# ---------------------------------------------------------------------------
# Robot server, control timing and media
# ---------------------------------------------------------------------------

# robot/launch_nodes.py
LAUNCH_NODES = {
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "left_robot_ip": "192.168.5.1",
    "right_robot_ip": "192.168.5.2",
    "robot_number": 2,
}

CONTROL = {"control_period_ms": 40}

# Shared command and alignment bounds for demonstrations and learned rollouts.
# Absolute targets can lead measured feedback; that gap is not a command step.
MOTION_LIMITS = {
    "max_joint_increment_rad": 0.17,
    "tracking_tolerance_rad": 0.6,
    "initial_approach_max_rad": 0.6,
    "approach_step_rad": 0.01,
    "approach_period_ms": 50,
}

# Supervisor faults first request ResetRobot() and require both arms idle,
# alarm-free, and still; otherwise they request EmergencyStop().
CONTROLLED_STOP = {
    "timeout_s": 2.0,
    "poll_interval_s": 0.1,
    "still_samples": 3,
    "still_tolerance_rad": 0.002,
}

MEDIA = {
    "envelope": {"dimensions_mm": [110, 220], "label_faces": ["top", "bottom"], "holding_arm": "right", "active_arms": [1, 1], "rotation_deg": 180, "max_rotations": 1},
    "poly_mailer": {"dimensions_mm": [130, 190], "label_faces": ["top", "bottom"], "holding_arm": "right", "active_arms": [0, 1], "rotation_deg": 180, "max_rotations": 1},
    "carton": {"dimensions_mm": [150, 75, 45], "label_faces": ["top", "bottom", "front", "rear"], "holding_arm": "left", "active_arms": [1, 0], "rotation_deg": 90, "max_rotations": 3},
}

# Arm homing stages (degrees, gripper last) and hardware approach limits used by
# parcel_sorting/hardware/manipulate_utils.py.
MANIPULATE_UTILS = {
    "stage1_left_deg": [-90, 30, -110, 20, 90, 90, 0],
    "stage1_right_deg": [90, -30, 110, -20, -90, -90, 0],
    "stage2_left_deg": [-90, 0, -90, 0, 90, 90, 0],
    "stage2_right_deg": [90, 0, 90, 0, -90, -90, 0],
    "hardware_settings_path": HARDWARE_SETTINGS_PATH,
    'home_step_rad': 0.01,
    'home_max_steps': 100,
    'approach_step_rad': MOTION_LIMITS['approach_step_rad'],
    'approach_period_ms': MOTION_LIMITS['approach_period_ms'],
    'servo_max_delta_rad': MOTION_LIMITS['max_joint_increment_rad'],
    'obs_max_delta_rad': MOTION_LIMITS['tracking_tolerance_rad'],
    'obs_report_delta_rad': 0.5,
    'pose_max_delta_rad': MOTION_LIMITS['initial_approach_max_rad'],
}

# parcel_sorting/utils.py: hardware logs and video encoding.
UTILS = {
    "log_dir": str(REPO_ROOT / "logs") + "/",
    "video_codec": 'mp4v',
    "hardware_settings_path": HARDWARE_SETTINGS_PATH,
}

# robot/robot_home.py
ROBOT_HOME = {
    # Joint targets are in degrees. Workspace bounds in RUNTIME are in millimeters.
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
    # --open-gripper: servo speed 0..100, and the 0..255 position error allowed
    # when confirming the jaws opened.
    "gripper_speed": 100,
    "gripper_open_timeout_s": 2.0,
    "gripper_open_tolerance": 15,
    # Collision, displacement, speed, and coordinate tolerance limits remain
    # in parcel_sorting/hardware/robot_home.py. Motion still requires an explicit CLI action.
}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# setup/1_find_ports.py
FIND_PORTS = {
    "baud_rate_list": [2000000, 1000000],
    "hardware_settings_path": HARDWARE_SETTINGS_PATH,
    "minimum_ports": 4,
}

# setup/2_get_offsets.py
GET_OFFSETS = {
    "gripper_ids": {"HAND_LEFT": [8], "HAND_RIGHT": [18]},
    "gripper_open_offset_deg": 0.2,
    "gripper_close_offset_deg": 30,
    "hardware_settings_path": HARDWARE_SETTINGS_PATH,
}

# setup/3_leader_buttons.py
LEADER_BUTTONS = {
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

# setup/4_check_cameras.py
CHECK_CAMERAS = {
    "flip_top_right": True,
    "flip_left": False,
}

# setup/make_labels.py
# Label dimensions use the unit stated in each size entry. Layout distances are
# in inches or PDF points as indicated by their names; font sizes are in points.
MAKE_LABELS = {
    "outdir": str(REPO_ROOT / "output" / "labels"),
    "default_size": "100x150",
    "combined": False,
    "crop_marks": True,
    "destinations": [
        {
            "token": "DEST-A-S138683",
            "bin": 0,
            "name": "DESTINATION A",
            "lines": [
                "SIT @ Dover Campus",
                "10 Dover Drive",
                "Singapore 138683",
            ],
        },
        {
            "token": "DEST-B-S828608",
            "bin": 1,
            "name": "DESTINATION B",
            "lines": [
                "SIT @ Punggol Campus",
                "1 Punggol Coast Road",
                "Singapore 828608",
            ],
        },
    ],
    "sizes": {
        "3x4": (3.0, 4.0, "inch"),
        "2x3": (2.0, 3.0, "inch"),
        "100x150": (100.0, 150.0, "mm"),  # standard label for every parcel
    },
    "barcode_options": {
        "module_width": 0.25,
        "module_height": 20.0,
        "quiet_zone": 3.0,
        "font_size": 0,
        "text_distance": 0.0,
        "write_text": False,
        "dpi": 600,
    },
    "layout": {
        "reference_width_in": 100.0 / 25.4,
        "reference_height_in": 150.0 / 25.4,
        "margin_in": 0.20,
        "crop_line_width_pt": 0.5,
        "crop_dash_pt": (2, 2),
        "crop_inset_pt": 2,
        "payload_font": "Courier-Bold",
        "payload_font_size_pt": 12,
        "payload_gap_in": 0.17,
        "banner_height_in": 0.45,
        "banner_font": "Helvetica-Bold",
        "banner_font_size_pt": 20,
        "banner_baseline_offset_pt": 7,
        "address_line_spacing_in": 0.20,
        "address_baseline_offset_pt": 4,
        "address_heading_font": "Helvetica-Bold",
        "address_heading_size_pt": 12,
        "address_font": "Helvetica",
        "address_font_size_pt": 11,
        "footer_font": "Helvetica",
        "footer_font_size_pt": 8,
        "footer_margin_fraction": 0.4,
    },
    "footer_template": "Code 128  |  bin {bin}  |  RSE4018",
    "label_title_template": "RSE4018 {name}",
    "combined_title": "RSE4018 destination labels",
    "barcode_filename_template": "bc_{token}",
    "label_filename_template": "label_{size}_{token}.pdf",
    "combined_filename_template": "labels_{size}_combined.pdf",
}

# parcel_sorting/scanning/scanner_reader.py (setup/check_scanner.py)
# This identity is a candidate from /proc/bus/input/devices. Confirm with a hand
# scan before using recording integration. Never substitute the normal keyboard.
SCANNER_READER = {
    "device_path": "/dev/input/by-id/usb-Megahunt_HID_Keyboard_D-2TYYGQMH-event-kbd",
    "device_name": "Megahunt HID Keyboard",
    "vendor_id": 0x0461,
    "product_id": 0x4D82,
    "exclusive_capture": True,
    "normalize_case": True,  # Destination tokens are uppercase; retain raw text in events.
    "keyboard_layout": "us",  # Configure the scanner to emit a US keyboard layout.
    "terminator_keys": ["KEY_ENTER", "KEY_KPENTER"],
    "scan_window_s": 10.0,
    "partial_timeout_s": 0.5,
    "max_length": 64,
    "poll_interval_s": 0.05,
}

# setup/check_waypoints.py. The waypoint tool controls the real robot. Values
# here send no commands until the operator selects a waypoint and confirms MOVE.
# Gripper values are position commands, not measured contact force. Only the
# selected arm receives commands.
WAYPOINT_DEFAULTS = {
    # Joint speed in radians/second. For example, change 0.1 to 0.2.
    # The maximum remains SUPERVISOR['joint_speed_rad_s'] (currently 0.25).
    "speed_rad_s": 0.1,
    # Use "open", "closed", or a number from 1.0 (open) to 0.0 (closed),
    # the same convention as RUNTIME open/closed_gripper_command.
    "left_gripper": "closed",
    "right_gripper": "closed",
    "waypoint_file": Path(WAYPOINT_FILE),
    # None disables reports. To save waypoint history, use a filename such as
    # REPO_ROOT / "cycle_logs" / "waypoint_checks.jsonl".
    "report_file": None,
}


# ---------------------------------------------------------------------------
# Recording and datasets
# ---------------------------------------------------------------------------

# recording/run_control.py
RUN_CONTROL = {
    "using_sensor_protection": False,
    "robot_port": 6001,
    "hostname": "127.0.0.1",
    "show_img": False,
    "project_name": None,
    # "x_range_left": (-450, 290), # original
    "x_range_left": (-490, 340),
    # "x_range_right": (-290, 450), # original
    "x_range_right": (-340, 450),
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

# parcel_sorting/data/recording.py
RECORDING = {
    "metadata_filename": "episode_metadata.json",
}

# Episode format shared by review and training-data preparation.
EPISODE_FORMAT = {
    "MIRROR_STATE_MULTIPLY": [1, 1, 1, 1, 1, 1, 1],
    "jpeg_quality": 50,
}

# Recording projects, episode checks and handoff tolerances. Each project folder
# under datasets/ holds pick-to-scan demonstrations for one medium. Projects are
# named <medium>_<label_face> by default; the training menu discovers any
# folder automatically. tools/curate_datasets.py only accepts the names below.
DATASETS = {
    "root_dir": str(DATASETS_DIR),
    "home_tolerance_rad": 0.12,
    "idle_tolerance_rad": 0.12,
    "gripper_tolerance": 0.08,
    "rate_tolerance_fraction": 0.10,
    "projects": {
        medium: {"schema_version": 3, "medium": medium, "episode_len": 500,
                 "train_ratio": 0.8, "camera_names": ["top", "left_wrist", "right_wrist"],
                 "control_period_ms": CONTROL["control_period_ms"]}
        for medium in MEDIA
    },
}
DATASETS["projects"].update({
    "{}_{}".format(medium, face): dict(
        DATASETS["projects"][medium], label_face=face)
    for medium, settings in MEDIA.items()
    for face in settings["label_faces"]
})
DATASETS["projects"].update({
    "poly_mailer_{}_extra".format(face): dict(
        DATASETS["projects"]["poly_mailer_{}".format(face)])
    for face in MEDIA["poly_mailer"]["label_faces"]
})

# tools/count_episodes.py
COUNT_EPISODES = {
    "root_dir": str(DATASETS_DIR),
}

# recording/review_episodes.py: offline playback and review decisions.
REVIEW_EPISODES = {
    "preview_camera_size": [240, 320],  # Height, width in pixels per camera.
    "playback_speed": 1.0,
    "fallback_period_ms": CONTROL["control_period_ms"],
    "window_name": "Episode review: a accept, r reject, s skip, p replay, space pause, q quit",
}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

# Shared parcel dataset recipes and ACT / Diffusion Policy training defaults.
ROBOMIMIC = {
    "recipes": {medium: {"medium": medium} for medium in MEDIA},
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


# ---------------------------------------------------------------------------
# Evaluation cycles
# ---------------------------------------------------------------------------

SUPERVISOR = {
    "waypoint_file": WAYPOINT_FILE,
    "position_tolerance_m": 0.025,
    "orientation_tolerance_rad": 0.15,
    "velocity_threshold_rad_s": 0.15,
    "settle_s": 0.5,
    "policy_timeout_s": 20.0,
    "policy_step_timeout_s": 1.0,
    "scan_dwell_s": 1.0,
    "joint_speed_rad_s": 0.25,
    "motion_timeout_s": 40.0,
    "tracking_tolerance_rad": MOTION_LIMITS["tracking_tolerance_rad"],
    "policy_approach_max_rad": MOTION_LIMITS["initial_approach_max_rad"],
    "policy_approach_speed_rad_s": MOTION_LIMITS["approach_step_rad"] * 1000 / MOTION_LIMITS["approach_period_ms"],
    "waypoint_home_tolerance_rad": 0.025,
    "cycle_csv": str(REPO_ROOT / "cycle_logs" / "cycles.csv"),
}

# Shared cycle safety limits and runtime camera orientation.
RUNTIME = {
    # Normalized gripper commands, confirmed from wrist-camera recordings:
    # 1.0 opens the jaws (start/home), 0.0 closes them on a held parcel.
    "open_gripper_command": 1.0,
    "closed_gripper_command": 0.0,
    "robot_types": ["Nova 2", "Nova 2"],
    'max_joint_increment_rad': MOTION_LIMITS['max_joint_increment_rad'],
    'left_j3_min_rad': -2.6,
    'right_j3_max_rad': 2.6,
    'left_j4_min_rad': -0.6,
    'right_j4_max_rad': 0.6,
    'left_x_min_mm': -410,
    'left_x_max_mm': 210,
    'right_x_max_mm': 410,
    # Was -210. Right-arm mailer demonstrations reach x=-369 mm with the left arm
    # at home; the operator confirmed that reach is clear. Includes ~10 mm margin.
    'right_x_min_mm': -380,
    'y_min_mm': -740,
    'y_max_mm': -210,
    'z_min_mm': 42,
    "flip_top_right": True,
    "flip_left": False,
}
