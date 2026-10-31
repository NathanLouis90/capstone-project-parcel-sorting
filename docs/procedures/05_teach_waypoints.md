# Teach the scan, drop and receiving-return waypoints

At the end `config/waypoints.local.yaml` holds the eight required poses for both arms, ready for checking.

## Before you start

- Complete [hardware setup](02_hardware_setup.md) and [workspace preparation](04_workspace.md). Keep existing calibration.
- Both grippers empty, both arm paths clear, emergency stop within reach. Server startup cycles both grippers; recorder startup moves both followers home.
- If a server and recorder are already running, reuse them. Never start a second one, and never restart either while a parcel is held.
- Three terminals, each prepared as in [install](01_install.md#every-new-terminal).

## Steps

1. Terminal 1: start the robot server and leave it running.

   **Both grippers open and close at startup. Keep hands clear.**

   ```bash
   python3 robot/launch_nodes.py
   ```

   Expect: `Starting robot server on port 6001`.

2. Terminal 2: start leader control.

   **Both followers move to their home pose. Keep the emergency stop within reach.**

   ```bash
   python3 recording/run_control.py --medium poly_mailer --label-face bottom --project-name waypoint_setup --show-img
   ```

   Expect: `Ok, let's start`. Do not press the green button while teaching; it starts recording.

3. Position the left follower over the scanner with the left leader: keep the leader near the follower posture, long-press yellow (about 2 s) and wait for alignment, short-press yellow to unlock, move slowly to the pose, short-press yellow to lock.

   Expect: the follower holds still within scanner range, with room to turn the wrist. The right follower stays home.

4. Long-press yellow on every leader whose following is enabled, then wait about one second.

   Expect: `ButtonA: [0] stop servo` (left) or `ButtonA: [1] stop servo` (right) for each arm you had enabled.

5. Terminal 3: save the pose.

   ```bash
   python3 setup/teach_waypoints.py --name scan_left
   ```

   Expect: `Saved scan_left; review limits and routes before commissioning`.

6. Return the left follower home under teleoperation, then repeat steps 3–5 for each remaining pose, one posture per command:

   | Posture to reach | Terminal 3 command |
   | --- | --- |
   | Right arm over the scanner | `python3 setup/teach_waypoints.py --name scan_right` |
   | Left arm over bin 0, at release height | `python3 setup/teach_waypoints.py --name drop_bin0_left` |
   | Left arm over bin 1, at release height | `python3 setup/teach_waypoints.py --name drop_bin1_left` |
   | Right arm over bin 0, at release height | `python3 setup/teach_waypoints.py --name drop_bin0_right` |
   | Right arm over bin 1, at release height | `python3 setup/teach_waypoints.py --name drop_bin1_right` |
   | Left arm a few centimetres above receiving | `python3 setup/teach_waypoints.py --name drop_receiving_left` |
   | Right arm a few centimetres above receiving | `python3 setup/teach_waypoints.py --name drop_receiving_right` |

   Expect: a `Saved ...` line each time. Return the used arm home before switching arms.

7. Optional: hold a parcel at its normal grasp width while teaching to check scanner range and clearance. Release it under teleoperation before stopping.

   Expect: grippers empty before you continue.

8. List the saved poses (this opens no device).

   ```bash
   python3 setup/check_waypoints.py --list
   ```

   Expect: all eight scan, drop and receiving poses show angles; none shows `unrecorded`.

9. To replace a pose, reposition deliberately and save it again with `--overwrite`.

   ```bash
   python3 setup/teach_waypoints.py --name scan_left --overwrite
   ```

   Expect: `Saved scan_left; ...`. Every save sets `commissioned: false`.

10. Edit `config/waypoints.local.yaml`: set `joint_limits_rad` (12 verified min/max pairs, left J1–J6 then right J1–J6, including wrist cable limits) and `rotation_direction` (`left` and `right`, each `1` or `-1`). Keep `commissioned: false`.

    Expect: the hardware-free preview in [check waypoints](06_check_waypoints.md) step 1 passes.

11. Stop Terminal 2 and then Terminal 1 with `Ctrl+C` when finished, or keep Terminal 1 running for the next procedure.

Continue with [check waypoints](06_check_waypoints.md). Add intermediate poses and `routes`, then set `commissioned: true`, only after those checks.
See [waypoints](../reference/hardware.md#waypoint-names-and-arm-selection) and [waypoint file and commissioning](../reference/hardware.md#waypoint-file-and-commissioning).

## If something goes wrong

- `Stop moving the follower before capture` -> disable following on both arms (step 4), wait for the follower to settle, retry.
- Connection timeout in Terminal 3 -> Terminal 1 is not running, or its host/port differ from `LAUNCH_NODES` in `config/settings.py`.
- `Pose exists; use --overwrite to replace it` -> reposition first, then use step 9.
- `Name must end in _left or _right` -> use one of the names in step 6.
- Teleoperation stops with a red table light -> stop and rerun Terminal 2 with empty grippers and clear paths.
