# Run parcel cycles

The robot picks a parcel, scans it, places it in the mapped bin (or back at receiving), returns home, and logs one row per attempt.

## Before you start

- Waypoints are taught, checked, and marked `commissioned: true` in `config/waypoints.local.yaml` ([teach](05_teach_waypoints.md), [check](06_check_waypoints.md)).
- A trained checkpoint exists for the medium ([train models](09_train_models.md)). The examples use `ckpt/act_poly_mailer_v1.1/best.pth`.
- Two terminals are open, each prepared with:
  ```bash
  conda activate Xtrainer
  cd ~/dobot_xtrainer
  ```
- The recorder, leader control, waypoint checks, and standalone scanner readers are stopped. The cycle opens its own scanner reader.
- Grippers are empty, both arm paths are clear, and the emergency stop is within reach.

Steps 1 to 3 need no robot, cameras, or scanner.

## Steps

1. Check that the checkpoint loads and predicts.
   ```bash
   python3 evaluation/check_checkpoint.py --medium poly_mailer --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --steps 3
   ```
   Expect: `ACT rollout settings: {...}` (ACT only), three JSON lines `{"step": 0, "policy_type": "ACT", ...}` to `"step": 2`, then `Checkpoint stepped without hardware; predictions were not sent to a robot`.

2. Simulate a cycle that reads the bin 0 label.
   ```bash
   python3 evaluation/run_cycle.py --medium poly_mailer --dry-run --fake-token DEST-A-S138683 --csv /tmp/poly-mailer-cycle.csv
   echo "exit status $?"
   ```
   Expect: a `Motion limits:` line, one JSON row with `"outcome": "success"`, `"bin": 0`, `"rotations_to_read": 0`, `"dry_run": true`, then `exit status 0`.

3. Simulate a parcel whose label is never read, with its one retry.
   ```bash
   python3 evaluation/run_cycle.py --medium poly_mailer --dry-run --retry-once --csv /tmp/poly-mailer-no-read.csv
   echo "exit status $?"
   ```
   Expect: `Retry failed. Stop and wait for the operator.`, two rows with `"outcome": "no_read"` (the second row's `retry_of` is the first row's `cycle_id`), then `exit status 2`.

4. Stop the robot server in Terminal 1 with Ctrl+C if it is running, then home both arms from Terminal 2.
   **Both arms move. Keep the emergency stop within reach.**
   ```bash
   python3 robot/robot_home.py --move
   ```
   Expect: `Moving both arms together at 10% global speed cap.`, then `Selected arms reached the Xtrainer initial pose.`

5. Start the robot server in Terminal 1 and leave it running.
   ```bash
   python3 robot/launch_nodes.py
   ```
   Expect: `Starting robot server on port 6001`. The grippers cycle during startup.

6. Place the labelled poly mailer in the receiving area as in the recordings, start any video recording, then run one live cycle in Terminal 2. Set `--label-face` to the face the label starts on (`top` or `bottom`).
   **The right arm starts moving as soon as the model has loaded; there is no start prompt. Keep the emergency stop within reach.**
   ```bash
   python3 evaluation/run_cycle.py --medium poly_mailer --live --checkpoint ckpt/act_poly_mailer_v1.1/best.pth --label-face top
   ```
   Expect: `ACT rollout settings: {...}` and `Motion limits: {...}`, then the arm picks, scans, places, returns home, and both grippers open. The terminal shows `Record outcome: [s] success, [g] grasp_fail, [d] drop, [w] wrong_bin`.

7. Inspect where the parcel ended up and press one key: `s` success, `g` grasp failure, `d` dropped, `w` wrong bin.
   If the label was not read, the arm returns the parcel to receiving and asks for a cause instead: `t` tilted in grip, `l` label occluded, or Enter for unknown.
   Expect: the attempt's JSON row is printed. A success exits with status 0.

8. After a failed attempt, the terminal shows `Place the same parcel at receiving. [r] retry once, any other key stops`. Reset the same parcel at receiving, then press `r` to retry once, or any other key to stop.
   Expect: a second row whose `retry_of` is the first `cycle_id`. If the retry also fails, the terminal shows `Retry failed. Stop and wait for the operator.` Stop and inspect; do not restart the program to get another retry.

9. Press any key at `Cycle stopped. Inspect the parcel and robot before recovery.` (shown after any non-success), then check the log.
   ```bash
   tail -n 3 cycle_logs/cycles.csv
   ```
   Expect: the newest rows, one per attempt, with `dry_run` set to `False`. Add `--csv PATH` in step 6 to keep runs in a separate file.

See [runtime reference](../reference/runtime.md#cycle-log-columns) for the log columns.

## If something goes wrong

- `Both arms must start at home; home explicitly before a cycle`: repeat steps 4 and 5.
- `Restart robot/launch_nodes.py to load controller status/stop support`: stop all clients, restart the server with empty grippers (step 5).
- `Teach and commission all paths before live operation`: finish [teaching](05_teach_waypoints.md) and [checking](06_check_waypoints.md) waypoints.
- `"outcome": "fault"` with `controlled stop confirmed` in `fault_detail`: both arms are enabled and holding position. Exit, stop the server, clear the paths, and [home](home_and_recover.md). With `emergency stop requested` instead, power-cycle both controllers first, then follow [home and recover](home_and_recover.md). The program never releases the parcel or homes after a fault.
- `Pick-to-scan handoff timeout`: the arm did not settle at its scan pose within 20 s. See [handoff check](../reference/runtime.md#handoff-check).
- `Cycle CSV columns differ; select a new log file`: pass a new `--csv` path.
