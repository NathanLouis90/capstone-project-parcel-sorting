"""Editable defaults for check_waypoint.py. Restart the program after editing.

The waypoint tool controls the real robot. Values here send no commands until
the operator selects a waypoint and confirms MOVE. Gripper values are position
commands, not measured contact force. Only the selected arm receives commands.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WAYPOINT_DEFAULTS = {
    # Joint speed in radians/second. For example, change 0.1 to 0.2.
    # The maximum remains SUPERVISOR['joint_speed_rad_s'] (currently 0.25).
    "speed_rad_s": 0.1,
    # Use "open", "closed", or a number from 0.0 (open) to 1.0 (closed).
    "left_gripper": "closed",
    "right_gripper": "closed",
    "waypoint_file": REPO_ROOT / "experiments" / "waypoints.local.yaml",
    # None disables reports. To save waypoint history, use a filename such as
    # REPO_ROOT / "waypoint_reports" / "waypoint_checks.jsonl".
    "report_file": None,
}
