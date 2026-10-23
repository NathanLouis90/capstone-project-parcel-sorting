# Run the robot checks

**Yes: the `--live` commands below move the real robot.** Start the follower
server in Terminal 1, then run one check in Terminal 2. The waypoint check
commands the selected arm to the saved pose; you do not have to guide it there
with a leader during the check.

Choose the check you need:

| What you want to do | Script | What moves |
| --- | --- | --- |
| Send the robot to a taught pose and inspect clearance | `check_waypoint.py` | The selected arm follows saved via points, then reaches the requested pose. |
| Check whether wrist rotation exposes a carton label | `check_wrist_rotation.py` | Starting at the taught scan pose, the selected wrist visits offsets 0°, 90°, 180°, and 270°. |
| Pick a parcel, scan it, and place it in bin 0 or bin 1 | `check_full_cycle.py` | The trained policy picks and approaches the scanner; the supervisor rotates, places, and returns home. |

The waypoint and wrist scripts ask you to type `MOVE` before each step.
The full-cycle script starts the cycle after initialization without that prompt.
`--dry-run`, `--list`, and pytest do **not** move the robot.

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

1. In Terminal 2, list your saved targets. This command only lists poses:

   ```bash
   python3 tests/check_waypoint.py --live --list
   ```

2. Determine both arms' current jaw command values. `0` means open, `1` means
   closed, and partial widths use values between them. The driver cannot reliably
   measure these settings, so you must supply them. The examples below assume
   both jaw commands are `1`. Replace `--grippers 1 1` with the actual left and
   right values; for example, use `--grippers 0 0` if both are open. Each motion
   command resends the supplied jaw settings.

3. To move the left arm to its saved scanner pose, run:

   ```bash
   python3 tests/check_waypoint.py --live --name scan_left \
     --grippers 1 1 --report cycle_logs/waypoint_checks.jsonl
   ```

4. Wait for the preflight result and displayed target joints. The robot has not
   moved to the target yet. Inspect the full path, then type uppercase `MOVE`
   and press Enter. **The selected arm now moves.** If the route has via points,
   repeat this confirmation at each point and at the final target.

5. Watch the entire movement. At arrival, inspect the physical pose and the
   printed `target_rad`, `observed_rad`, and `max_error_rad`. The script requires
   joint error no greater than `0.025` radians per joint. Check the actual tool
   location as well as the numbers.

6. The script exits with the arm at the requested pose. It does not open the
   gripper or return home. The other arm keeps its starting commanded joints.

7. To check a bin pose from this new starting position, run the next command
   separately and confirm its path before typing `MOVE`:

   ```bash
   python3 tests/check_waypoint.py --live --name drop_bin0_left \
     --grippers 1 1 --report cycle_logs/waypoint_checks.jsonl
   ```

   Use `drop_bin1_left` to check bin 1, `drop_receiving_left` to check the
   receiving-return pose, or a taught name ending in `_right` to move the right
   arm. Every command starts from the robot's current posture. Do not paste a
   sequence of destination commands and assume every transition is clear.

Default joint speed is `0.1` radians/s. Add `--speed 0.05` for a slower check.
The report appends each reached target and measured joint angles. Check all
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

These commands need no server, scanner, cameras, or trained model. They use the
local waypoint file if present, otherwise explicitly marked synthetic poses.
They do not establish physical clearance.

```bash
python3 tests/check_waypoint.py --dry-run --name drop_bin0_left
python3 tests/check_wrist_rotation.py --dry-run --fake-read-at 180
python3 tests/check_full_cycle.py --medium poly_mailer --dry-run \
  --fake-token DEST-B-S828608 --csv /tmp/poly-mailer-cycle.csv
```

Use `--fake-no-read` for a wrist no-read check. Omit `--fake-token` for a
full-cycle no-read check. Both return status `2` when no barcode is read.
Synthetic files are rejected by live checks and full cycles.

To run the small mocked regression module without moving the robot:

```bash
python3 -m pytest tests/ -q
```

Pytest runs software guards only; it does not execute the live scripts.
