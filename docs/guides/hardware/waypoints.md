# Teach and commission joint waypoints

Pose values are six joint angles in **radians**, separately for each arm.
Two physical bin locations must be reachable by both arms; each arm has its
own joint target for the same location. No direct Cartesian move bypasses
the validated 25 Hz stream.

Use the controller's manual drag mode to position a follower, stop moving,
and disable drag before capturing. The capture tool reads feedback only; it
does not enable drag, release a gripper or command motion.

```bash
python3 experiments/teach_waypoints.py --name scan_left
python3 experiments/teach_waypoints.py --name scan_right
python3 experiments/teach_waypoints.py --name drop_bin0_left
```

Also teach `drop_bin0_right`, `drop_bin1_left`, `drop_bin1_right`,
`drop_receiving_left`, and `drop_receiving_right`. Receiving returns must release
a few centimetres above its surface, with the parcel clear of the scanner and
bin rims. Existing poses require `--overwrite` to replace them.

The local YAML/JSON file defaults to `experiments/waypoints.local.yaml` and is
ignored by Git. It contains `units: radians`, a `poses` map, a `routes` map, a
`rotation_direction` map (`left`/`right`: `1` or `-1`), and 12 `joint_limits_rad`
min/max pairs: left J1–J6 followed by right J1–J6. Set these to verified robot
and cable limits; the tool does not invent live limits.

Teach optional via points with names ending `_left` or `_right`. A route named
`drop_bin0_left` lists via poses executed before that endpoint. A route named
`home_left` lists via poses before home. Use corresponding names for the other
arm and receiving returns. Paths must be clear from every possible final scan
rotation; a scan sweep can stop between nominal face angles. Via points may
be needed to lift away before unwinding J6 or crossing a bin rim.

Keep `commissioned: false` until all paths, rotations, release heights, FK
positions/orientations and limits have been checked on the revised hardware.
Then set it to `true` explicitly. Capturing any pose resets it to `false`.
Taught pose/FK checks do not model parcel-body collisions or prove a grasp.

For software checks only:

```bash
python3 experiments/teach_waypoints.py --dry-run --output /tmp/example-waypoints.yaml
python3 experiments/scripted_motion.py --dry-run
```

Synthetic waypoints are marked uncommissioned and live runs refuse them.
