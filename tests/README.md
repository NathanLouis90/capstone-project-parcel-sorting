# Run the robot checks

**The waypoint tool controls the real robot.** The wrist and full-cycle checks
also control real hardware when run with `--live`. Start the follower
server in Terminal 1, then run one check in Terminal 2. The waypoint check
commands the selected arm to the saved pose; you do not have to guide it there
with a leader during the check.

Choose the check you need:

| What you want to do | Script | What moves |
| --- | --- | --- |
| Select taught poses repeatedly and inspect clearance | `check_waypoint.py` | One selected arm follows saved via points; the other must remain home. |
| Check whether wrist rotation exposes a carton label | `check_wrist_rotation.py` | Starting at the taught scan pose, the selected wrist visits offsets 0°, 90°, 180°, and 270°. |
| Pick a parcel, scan it, and place it in bin 0 or bin 1 | `check_full_cycle.py` | The trained policy picks and approaches the scanner; the supervisor rotates, places, and returns home. |

The waypoint and wrist scripts ask you to type `MOVE` before each step.
The full-cycle script starts the cycle after initialization without that prompt.
`--dry-run` and `--list` do **not** move the robot.

## 1. Prepare the saved poses

You need your actual taught file at `experiments/waypoints.local.yaml`.
If you have not taught the poses yet, follow the
[waypoint teaching instructions](../docs/guides/hardware/waypoints.md#use-three-terminals)
first. That procedure uses the leaders to position the followers and
`teach_waypoints.py` to save each pose. Saving a pose does not test motion to it.
Do not substitute the synthetic waypoints from a dry run.

Before a live check, open the local waypoint file and confirm:

1. The pose you want to visit exists, such as `scan_left` or `drop_bin0_left`.
2. `joint_limits_rad` contains 12 verified min/max pairs: left J1–J6, then right
   J1–J6, including wrist cable limits.
3. Any required intermediate poses are taught and listed in the destination's
   `routes` entry. Without via points, the script interpolates directly in joint
   space from the current posture to the target. The tool path is not necessarily
   a straight line.
4. For the wrist check, `rotation_direction` contains `left: 1` or `left: -1`
   for the verified direction. Use the corresponding right-arm entry when testing
   the right arm.

Keep `commissioned: false` while checking the installation. The waypoint and
wrist checks allow this setting and do not require unused poses to be taught.
The full cycle requires all scan, bin, and receiving-return poses for both arms,
verified routes, and `commissioned: true`.

## 2. Open two terminals

Run this setup in **both** terminals:

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

### Terminal 1: start the follower server

Start with empty grippers and clear arm paths. Server startup cycles the
grippers. Run:

```bash
python3 experiments/launch_nodes.py
```

Wait for `Starting robot server on port 6001`, then leave this terminal running.
If this server is already running, reuse it. Do not start a second instance.
Do not restart the server while holding a parcel.

After updating server code, restart it once with empty grippers and all motion
clients stopped. The checks request controller status and emergency stops
through the launcher's existing dashboard connections. Port 29999 accepts one
client; a separate controller connection can close with
`Controller closed the connection`. If a check asks you to restart
`launch_nodes.py`, the running server predates this status/stop interface.

### Terminal 2: run one check

Stop `run_control.py` and any other motion client before starting a check.
If you used teleoperation to position the arms, first lock the leaders and
disable following on **both** arms, then stop the recorder. Keep Terminal 1
running. See the [teaching instructions](../docs/guides/hardware/waypoints.md#terminal-2-start-leader-control)
for the yellow-button sequence.

The wrist and waypoint checks need neither a trained model nor cameras.
Keep immediate access to the emergency stop while inspecting movement.
Software checks cannot detect collisions with the parcel, scanner, bin rims,
or other arm.

## 3. Move to a waypoint

Perform this first with **no parcel held**.

1. In Terminal 2, start the menu without arguments:

   ```bash
   python3 tests/check_waypoint.py
   ```

2. Configure defaults in [waypoint_config.py](waypoint_config.py) before starting
   the tool. Under `WAYPOINT_DEFAULTS`, set `speed_rad_s`, `left_gripper`, and
   `right_gripper`. For example, set `speed_rad_s` to `0.2` for a faster check.
   Gripper values can be `"open"`, `"closed"`, or a number from `0.0` (open) to
   `1.0` (closed). These are position commands, not grip force. The driver cannot
   reliably measure the jaw command, so match the configured positions to the
   intended hold. Only the selected arm receives its gripper command after MOVE.
3. The same config contains `waypoint_file` and `report_file`. Reports are off
   when `report_file` is `None`. To save history, set it to a filename such as
   `REPO_ROOT / "waypoint_reports" / "waypoint_checks.jsonl"`. A report records
   waypoint choices, measured angles, and outcomes; it does not run a parcel-
   sorting cycle. Relative paths resolve from the repository root.

4. The numbered menu shows `home_left`, `home_right`, both arms' scan, bin, and
   receiving-return targets, and any additional taught poses. Angles are shown
   in degrees; missing or null poses show `unrecorded`. Select a number or exact
   waypoint name, such as `scan_left`. Unrecorded choices send no commands.
5. Wait for preflight and the displayed target joints. Inspect the full path,
   then type uppercase `MOVE` and press Enter. **The selected arm now moves.**
   Each via point and final target requires its own `MOVE`. Press Enter to
   cancel the selection, or type `q` to quit at a confirmation prompt.

6. Watch the entire movement. At arrival, inspect the physical pose and the
   printed `target_rad`, `observed_rad`, and `max_error_rad`. The script requires
   joint error no greater than `0.025` radians per joint. Check the actual tool
   location as well as the numbers.

7. The menu returns after the move. You can select another target for that same
   arm. Before switching arms, select that arm's `home_left` or `home_right`
   entry and confirm its path. Home uses the configured Xtrainer final home
   joints and any taught `home_left`/`home_right` via-point route.

8. Type `q` at the menu to exit at the current pose. Quitting does not release
   the grippers or move either arm home. During motion, Ctrl+C requests a stop;
   use the physical emergency stop when needed.

The menu displays the configured defaults and has waypoint selections plus `q`.
There is no settings submenu or real/simulation selector. Defaults are loaded
at startup; restart after editing the config. Opening the menu or editing the
config sends no movement or gripper commands. MOVE remains required.

The idle arm must be within `SUPERVISOR["waypoint_home_tolerance_rad"]` of its
configured home joints (default `0.025` radians per joint, about 1.43 degrees).
This check uses measured joint feedback before each selection and before every
motion command. Only the selected follower receives movement/gripper commands.
For example, `scan_left`, then `drop_bin0_left`, is allowed while the right arm
is home. Selecting `scan_right` is blocked until `home_left` completes. If both
arms start away from home, all menu moves are blocked; quit and recover manually.

Blocked selections, failed preflight, and cancelled moves return to the menu.
A controller/communication fault or failure during movement stops the session;
movement failures request both controllers' stop. Do not resume until the cause
has been resolved. Successful, cancelled, and blocked recorded selections append
individual entries to the report file.

For a single check that exits afterward, the existing `--name` form remains
available and enforces the same idle-arm interlock:

```bash
python3 tests/check_waypoint.py --name drop_bin0_left
```

Use `drop_bin1_left` for bin 1, `drop_receiving_left` for the receiving return,
or a taught name ending in `_right` for the right arm. Every selection starts
from the robot's current posture. Check the path for each transition.

Default joint speed is `0.1` radians/s. Set a different `speed_rad_s` in the config
when needed; the maximum is `0.25` radians/s. When enabled, the report appends each
reached target and measured joint angles. Check all
required approaches and retreats, including paths from possible final scan
angles. Reaching a destination once does not validate other starting postures.

## 4. Rotate a carton through four scan orientations

This script rotates the wrist automatically after each confirmation. It does
**not** pick up the carton or move from home to the scanner first.

1. Complete the empty-arm waypoint checks above.
2. Using the [teleoperation procedure](../docs/guides/hardware/waypoints.md), grasp
   the carton at its normal width and position the holding arm at its taught
   `scan_left` pose. Start teleoperation with empty grippers: its startup homes
   both arms. Once the carton is held, do not restart teleoperation or the server.
3. Lock the leaders, disable following on both arms, and stop the recorder.
   Leave Terminal 1 running. The arm must already match the taught scan pose
   within `0.025` radians per joint; otherwise the wrist script refuses to start.
4. Stop any standalone `scanner_reader.py` process. The wrist check opens its
   own scanner reader.
5. In Terminal 2, run this command with your actual current jaw settings and the
   token printed on your carton:

   ```bash
   python3 tests/check_wrist_rotation.py --live --arm left \
     --grippers 1 1 --label-face top --expect-token DEST-A-S138683 \
     --report cycle_logs/wrist_checks.jsonl
   ```

6. Type `MOVE` and press Enter at each prompt. The script checks the starting
   orientation, then physically turns J6 in three 90° steps. Offsets are measured
   from the starting wrist angle, using your configured rotation direction.
   It pauses at 0°, 90°, 180°, and 270° and accepts fresh scans after settling.
7. At each position, inspect carton retention, label visibility, arm clearance,
   and cable slack. Read the printed `scan` result: a decoded read includes
   `barcode` and `bin_index`; `null` means no read at that orientation.
8. After the fourth position, the script exits and leaves the wrist at its 270°
   offset. It does not release the carton, unwind, or return home. Recover under
   operator control using a checked path. Do not restart teleoperation with a
   parcel held; its startup homes the arms. Use the physical setup's supported
   recovery procedure before another trial.
9. Reset safely to the taught scan pose. Repeat with the label initially on
   `bottom`, `front`, and `rear`, changing `--label-face` for each trial. That flag
   records the starting face; it does not change the motion or choose a turn.

One label may read at only one orientation. Verify a successful read for each
starting face across the four trials. The script continues through the entire
sweep after a read so you can inspect all four positions. Exit status `0` means
at least one mapped read, with all reads matching `--expect-token` if supplied.
No read or a mismatched token returns status `2`.

The default stationary scan window is three seconds. Add `--dwell 5` for five
seconds. For the right arm, use `--arm right` and start at `scan_right`. Use
`--device /dev/input/eventN` only for the dedicated scanner when necessary;
configured scanner identity checks still apply.

## 5. Run a full poly-mailer cycle

Use this after commissioning and after training a model for the selected medium.
This check uses the normal three cameras and the physical scanner.

1. Finish all path and wrist checks, then set `commissioned: true` in the local
   waypoint file. Resolve the documented
   [partial-gripper handoff limitation](../docs/guides/recording/README.md#gripper-width-and-handoff)
   before relying on automatic cycles with partial-width grasps.
2. With no parcel held, stop the server in Terminal 1 and stop all motion clients.
   Check the complete homing path, then run in Terminal 2:

   ```bash
   python3 experiments/robot_home.py --move
   ```

   This command physically homes both arms. If an alarm or obstruction prevents
   safe homing, follow the [recovery guide](../docs/guides/hardware/homing.md)
   rather than repeatedly restarting.
3. Restart `python3 experiments/launch_nodes.py` in Terminal 1 with empty
   grippers. Leave it running. Keep the recorder and standalone scanner readers
   stopped.
4. Place the labeled poly mailer in the receiving area. Keep both arms at home.
   For a top-facing label, use the same fixed elevated platform as training.
   Use a checkpoint trained for left-arm platform flipping and right-arm corner
   pickup, and commission the right-arm scan/drop paths with that grasp.
5. In Terminal 2, replace `/path/to/model.pth` with your actual trained robomimic
   ACT or DP checkpoint and run:

   ```bash
   python3 tests/check_full_cycle.py --medium poly_mailer --live \
     --backend robomimic --checkpoint /path/to/model.pth --label-face top
   ```

   For vendor ACT, use `--backend vendor --checkpoint /path/to/checkpoint_directory`
   instead. The directory must contain the required model, saved configuration,
   and dataset statistics. Set `--label-face` to the actual starting label face.
6. After initialization, the robot runs the cycle automatically. There is no
   `MOVE` prompt. It picks the parcel, reaches the scan pose, reads or rotates
   as needed, releases into the mapped destination, and returns home.
   `DEST-A-S138683` selects bin 0; `DEST-B-S828608` selects bin 1. An unread parcel
   returns to receiving rather than a guessed bin.
7. Inspect the actual outcome when prompted. Enter `s` for success, `g` for grasp
   failure, `d` for a drop, or `w` for the wrong bin. On no read, record the cause.
   If offered a retry, reset the parcel safely before selecting it.
8. Inspect the printed result and `cycle_logs/cycles.csv`. On a runtime fault,
   the supervisor requests an emergency stop and does not release or home.
   Inspect and follow the recovery guide before another attempt.

**Do not start a separate barcode script during this evaluation.**
`check_full_cycle.py` delegates to `experiments/run_cycle.py`, which starts its
own scanner reader. Prediction-only checkpoint checks do not test physical
barcode scanning. See the [evaluation guide](../docs/guides/runtime/evaluation.md)
for the complete outcome and retry procedure.

## Stop a waypoint or wrist check

At a stationary `MOVE` prompt, enter `q` or any answer other than `MOVE` to finish
without another move. During motion, use the physical emergency stop when
needed. Ctrl+C or a runtime fault requests a network emergency stop; this is
not a substitute for the physical stop. Neither check automatically releases
or returns home after cancellation or a fault.

If preflight rejects a path, the check sends no motion commands. Correct the
pose, route, or verified limits before retrying; do not widen limits simply to
make the check pass. If the waypoint file is missing, teach actual poses first.

## Optional: preview without moving hardware

The wrist and full-cycle preview commands need no server, scanner, cameras, or
trained model. They use the local waypoint file if present, otherwise explicitly
marked synthetic poses.
They do not establish physical clearance.

```bash
python3 tests/check_wrist_rotation.py --dry-run --fake-read-at 180
python3 tests/check_full_cycle.py --medium poly_mailer --dry-run \
  --fake-token DEST-B-S828608 --csv /tmp/poly-mailer-cycle.csv
```

Use `--fake-no-read` for a wrist no-read check. Omit `--fake-token` for a
full-cycle no-read check. Both return status `2` when no barcode is read.
Synthetic files are rejected by live checks and full cycles.
