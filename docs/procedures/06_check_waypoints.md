# Check the taught waypoints and the carton wrist rotation

At the end each taught pose has been reached on the real robot with the other arm at home, and the carton label reads in the wrist sweep from every starting face.

## Before you start

- Complete [teach waypoints](05_teach_waypoints.md). `config/waypoints.local.yaml` holds your real poses, 12 verified `joint_limits_rad` pairs and `rotation_direction`; keep `commissioned: false`.
- Grippers empty for steps 1–7. Both arm paths clear, emergency stop within reach.
- Stop `recording/run_control.py` and every other motion client. If you positioned arms by teleoperation, first lock the leaders and disable following on both arms.
- Two terminals, each prepared as in [install](01_install.md#every-new-terminal).

## Steps

1. Preview the wrist sweep without hardware. This also validates the waypoint file.

   ```bash
   python3 setup/check_wrist_rotation.py --dry-run --fake-read-at 180
   ```

   Expect: `Preflight passed for ... commands`, four JSON lines (0, 90, 180, 270) with a read at 180, and `Sweep complete; 1 orientations read`.

2. Set the check defaults in `WAYPOINT_DEFAULTS` in `config/settings.py`: `speed_rad_s` (default 0.1, maximum 0.25) and, to keep a history, `report_file = REPO_ROOT / "cycle_logs" / "waypoint_checks.jsonl"`.

   Expect: no other change is needed. See [waypoint check settings](../reference/hardware.md#waypoint-check-settings) before changing the gripper values.

3. Terminal 1: start the robot server, or reuse the one already running.

   **Both grippers open and close at startup. Keep hands clear.**

   ```bash
   python3 robot/launch_nodes.py
   ```

   Expect: `Starting robot server on port 6001`. Leave it running.

4. Terminal 2: open the waypoint menu.

   ```bash
   python3 setup/check_waypoints.py
   ```

   Expect: the defaults, then a numbered list: `home_left`, `scan_left`, `drop_bin0_left`, `drop_bin1_left`, `drop_receiving_left`, the same for the right arm, and `q`.

5. Type a number or name, for example `scan_left`, and press Enter. Read the displayed joints and inspect the whole path.

   **The selected arm moves after you type `MOVE`. Keep the emergency stop within reach.**

   Type `MOVE` (uppercase) and press Enter. Each via point needs its own `MOVE`.

   Expect: a JSON line with `target_rad`, `observed_rad` and `max_error_rad` no greater than 0.025, then the menu again. Check the real tool position, not only the numbers.

6. Visit every pose of the same arm, then select `home_left` (or `home_right`) and `MOVE` before choosing a pose of the other arm.

   Expect: a pose of the other arm is blocked with `... arm must be home before moving ...` until the active arm is home.

7. Type `q` at the menu to finish.

   Expect: the program exits where the arm is. It does not release the grippers or move home.

8. Wrist check, left arm with a carton: start teleoperation with empty grippers, grasp the carton at its normal width with the label on `top`, and move the left arm to `scan_left`. Lock the leaders, disable following on both arms, stop `recording/run_control.py`, and stop any `setup/check_scanner.py`. Keep Terminal 1 running.

   Expect: the arm is still, holding the carton at the taught scan pose.

9. Run the wrist check with the gripper commands that match the current jaws: left holding (`0`), right open (`1`). See [gripper commands](../reference/hardware.md#gripper-commands-in-the-checks) first.

   **The left wrist turns after each `MOVE`. Keep the emergency stop within reach.**

   ```bash
   python3 setup/check_wrist_rotation.py --live --arm left --grippers 0 1 --label-face top --expect-token DEST-A-S138683 --report cycle_logs/wrist_checks.jsonl
   ```

   Type `MOVE` at each of the four prompts and watch grip, label visibility, clearance and cable slack.

   Expect: four JSON lines (0, 90, 180, 270); a read shows `barcode` and `bin_index`, `null` means no read. `Sweep complete; N orientations read`, exit status 0 if at least one read matched.

10. Recover the carton by hand under operator control on a checked path. The check leaves the wrist at 270° and does not release, unwind or go home. Do not restart teleoperation while a parcel is held.

    Expect: carton released, arm back at `scan_left`.

11. Repeat steps 8–10 with the label starting on `bottom`, `front` and `rear`, changing `--label-face` each time.

    Expect: each starting face reads at one or more positions.

When every path, the wrist sweep and the routes are checked, set `commissioned: true` in `config/waypoints.local.yaml`, then continue with [run cycles](10_run_cycles.md).
See [waypoint and wrist checks](../reference/hardware.md#waypoint-and-wrist-checks) for interlocks, tolerances and the report file.

## If something goes wrong

- `Teach local waypoints first` or `unrecorded` -> teach the pose ([teach waypoints](05_teach_waypoints.md)).
- `Set rotation_direction for left to 1 or -1` -> add `rotation_direction` to the waypoint file.
- Preflight rejects a path -> nothing moved; fix the pose, route or verified limits. Never widen limits just to pass.
- `Manually position the holding arm at scan_left` -> the arm is more than 0.025 rad from `scan_left`; reposition and retry.
- Both arms away from home -> every menu move is blocked; quit and home with [home and recover](home_and_recover.md).
- A fault during motion, or a restart request for `robot/launch_nodes.py` -> stop, then follow [home and recover](home_and_recover.md). Use the physical emergency stop if needed; `Ctrl+C` only requests a network stop.
