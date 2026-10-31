# Runtime

This page describes how parcel cycles run: the cycle supervisor, the safety checks applied to every command, the handoff and scan logic, fault handling, and the cycle log. For the steps, see [Run parcel cycles](../procedures/10_run_cycles.md) and [Evaluate the poly-mailer models](../procedures/11_evaluate_poly_mailer.md).

## Programs

| Program | Purpose | Hardware |
| --- | --- | --- |
| `evaluation/run_cycle.py` | Runs one pick, scan, and place cycle, plus at most one retry, and appends a row per attempt to the cycle log. | `--live` connects to `robot/launch_nodes.py`, the three cameras, and the scanner. `--dry-run` opens nothing. |
| `evaluation/check_checkpoint.py` | Loads a robomimic ACT or DP checkpoint on the CPU and prints `--steps` predictions (default 3) for home joint positions and black images. | None. It sends no robot commands. |

The supervisor code is in `parcel_sorting/runtime/cycle.py`, with the motion loop in `parcel_sorting/runtime/scripted_motion.py` and the live hardware connection in `parcel_sorting/runtime/hardware_runtime.py`. The pure checks are in `parcel_sorting/safety/` (`handoff.py`, `inference_safety.py`, `kinematics.py`), and the policy wrapper is in `parcel_sorting/policies/robomimic_policy.py`.

A checkpoint check only shows that a model loads and predicts. It does not show grasping, scanning, or sorting performance.

## Holding arm and policy arms

The operator chooses `--medium`. `MEDIA` in `config/settings.py` then sets the holding arm, which arms the policy controls, and how the parcel is rotated at the scanner:

| Medium | `active_arms` (left, right) | Holding arm at scan and drop | Backup rotation |
| --- | --- | --- | --- |
| `envelope` | both | right | at most one 180° turn of J6 |
| `poly_mailer` | right only | right | at most one 180° turn of J6 |
| `carton` | left only | left | at most three 90° turns of J6 |

The cycle does not detect the parcel type or the holding arm from cameras or sensors. An inactive arm is held at home: its policy output is replaced by the home joints with an open gripper. The policy is fed the inputs that arm had during training.

When it loads, the policy compares these roles with the checkpoint's training data:

- If an active arm never moved in training (joint standard deviation below 0.01 rad), the checkpoint is refused.
- If a parked arm did move in training, the checkpoint is also refused.

A checkpoint is also refused when any of these is true:

- It was trained for another medium.
- It does not use exactly `qpos` plus the `top`, `left_wrist` and `right_wrist` cameras.
- It does not produce 14 actions.
- It lacks normalization statistics.

A live cycle also refuses a smoke-run checkpoint (experiment name ending in `_smoke`).

## Cycle sequence

1. **Start check.** Both arms must be within 0.12 rad of home on every joint. Otherwise the cycle stops with `Both arms must start at home; home explicitly before a cycle`. It never homes on its own.
2. **Warmup.** The policy predicts once on the current observation, then resets. No robot command is sent, and the cycle timer starts after warmup.
3. **Pick (`t_pick_s`).** Every 40 ms (`CONTROL["control_period_ms"]`) the supervisor reads the joints and camera frames, asks the policy for an action, validates it, and sends it. This continues until the [handoff check](#handoff-check) passes, or until `policy_timeout_s` (20 s) runs out with `Pick-to-scan handoff timeout`. A single prediction that takes longer than `policy_step_timeout_s` (1 s) is a fault.
4. **Scan (`t_scan_s`).** Learned actions stop. A fresh scanner window is opened for this cycle's ID. The arm holds still for `scan_dwell_s` (1 s). If no accepted read arrives, it turns J6 by the medium's rotation angle, then holds again, up to the medium's rotation limit. The turn direction comes from `rotation_direction` in the waypoint file (default `1`).
5. **Place (`t_place_s`).** A read follows the route to `drop_bin<bin>_<arm>`, for example `drop_bin0_right`. No read follows `drop_receiving_<arm>`. At the drop pose the holding gripper opens, the arm holds for 0.5 s, returns home through any `home_<arm>` route, and then both grippers are commanded open.
6. **Outcome.** The operator enters the physical outcome. On a no-read, the operator enters the cause instead. The row is then appended to the log.

Releases and homing are scripted moves at up to `joint_speed_rad_s` (0.25 rad/s). Each move must arrive within 0.025 rad per joint before `motion_timeout_s` (40 s).

## Initial approach

Training actions are absolute joint targets, not increments. The first policy target can be further from the current pose than one command step allows. In that case the supervisor approaches it in small validated steps at `policy_approach_speed_rad_s` (0.2 rad/s, the same 0.01 rad per 50 ms rate used when teaching). It then resets the policy, so that no ACT chunk, ensemble, or Diffusion Policy history from before the approach carries over.

- The whole first target is checked before any approach command: it must be within `initial_approach_max_rad` (0.6 rad) of the measured joints, and pass the joint, workspace, gripper, and taught-limit checks.
- Every intermediate command is checked again.
- The approach counts toward `t_pick_s` and the 20 s timeout.
- Only the first target gets an approach. A later jump larger than one command step is a fault.

`tools/check_rollout_compatibility.py --checkpoint PATH` compares the recordings behind a checkpoint with these bounds without opening hardware. See [curate datasets](../procedures/curate_datasets.md).

## Motion validation

Every command, whether learned or scripted, goes through the same loop. Gripper channels are excluded from joint checks. A failed check raises a fault before the command is sent.

| Check | Limit | Setting |
| --- | --- | --- |
| Values | 14 finite numbers; grippers within 0..1 | |
| Command step: change from the previous command, per joint | 0.17 rad | `MOTION_LIMITS["max_joint_increment_rad"]` (`RUNTIME["max_joint_increment_rad"]`) |
| Tracking: measured joints versus the previous command | 0.6 rad | `MOTION_LIMITS["tracking_tolerance_rad"]` (`SUPERVISOR["tracking_tolerance_rad"]`) |
| Tracking: new target versus measured joints | 0.6 rad | same |
| J3/J4 limits | left J3 between -2.6 and 0 rad, left J4 above -0.6 rad, right J3 between 0 and 2.6 rad, right J4 below 0.6 rad | `RUNTIME` `left_j3_min_rad`, `left_j4_min_rad`, `right_j3_max_rad`, `right_j4_max_rad` |
| Workspace box for both jaw tips (forward kinematics, full jaw span) | left x -410 to 210 mm, right x -380 to 410 mm, y -740 to -210 mm, z above 42 mm | `RUNTIME` `*_x_*_mm`, `y_*_mm`, `z_min_mm` |
| Taught joint and cable limits | 12 min/max pairs from `joint_limits_rad` in the waypoint file | `config/waypoints.local.yaml` |
| Controller health, before and after each command (live only) | both controllers in mode 5, 7 or 8 with no alarms | |
| Camera frames (live only, each policy step) | all three frames younger than 0.5 s | |

The tracking gap is a position error between a target and the lagging feedback. It is not an allowed instantaneous movement and not a measured speed.

A command that takes longer than one 40 ms period is counted in `control_overruns`; it is not a fault.

The current driver reports a constant gripper value. The loop therefore tracks the last gripper command in its place. That value is not evidence of a grasp.

These checks constrain commands. They do not check parcel clearance, contact force, or grasp retention. Commissioned routes and physical trials are still needed.

## Handoff check

The pick phase ends when all of the following hold on the same reading, and keep holding for `settle_s` (0.5 s):

| Condition | Limit | Setting |
| --- | --- | --- |
| Holding-arm flange position versus the taught `scan_<arm>` pose (forward kinematics) | 0.025 m | `SUPERVISOR["position_tolerance_m"]` |
| Holding-arm flange orientation versus the scan pose | 0.15 rad | `SUPERVISOR["orientation_tolerance_rad"]` |
| Other arm at home, per joint | 0.12 rad | `DATASETS["idle_tolerance_rad"]` |
| Holding gripper command closed (0.0) | within 0.08 | `DATASETS["gripper_tolerance"]`, `RUNTIME["closed_gripper_command"]` |
| Other gripper command open (1.0) | within 0.08 | `RUNTIME["open_gripper_command"]` |
| Fastest joint speed (both arms) | 0.15 rad/s | `SUPERVISOR["velocity_threshold_rad_s"]` |

Gripper commands are normalized: 1.0 opens the jaws and 0.0 closes them. The gripper condition uses the tracked command, not a measured jaw width. A grasp commanded at partial width (for example 0.3) does not pass, even if it holds the parcel securely. Likewise, a closed command does not prove the parcel is held.

If the demonstrations end away from the taught scan pose, the policy settles there too. Every attempt then ends with `Pick-to-scan handoff timeout`, and the arm stops where it settled.

## Scanning and destinations

- The scanner window is opened only after the handoff succeeds, and accepts only events tagged with the current cycle ID.
- Only a complete, known token in the destination mapping (`MAKE_LABELS["destinations"]` in `config/settings.py`) selects a bin: `DEST-A-S138683` is bin 0 (Dover) and `DEST-B-S828608` is bin 1 (Punggol).
- Stale, partial, unknown, or unmapped reads never select a destination.
- A scanner device failure is a fault.
- Finishing the rotation sweep without an accepted read is `no_read`, and the parcel goes back to receiving. The cycle never guesses a bin.
- Barcode data is never a policy input.

A live cycle opens its own scanner reader. A second reader such as `setup/check_scanner.py` competes for the device, so keep any other reader stopped.

## Waypoints

A live cycle loads `config/waypoints.local.yaml` (`SUPERVISOR["waypoint_file"]`, overridable with `--waypoints`). It requires:

- `units: radians`
- `commissioned: true`
- no `simulation_only` flag
- six finite joints for `scan`, `drop_bin0`, `drop_bin1` and `drop_receiving` on both arms
- 12 valid `joint_limits_rad` pairs, with every pose inside them
- routes that list only same-arm poses

A dry run uses the same file without requiring `commissioned: true`. If the file is missing, it uses built-in synthetic poses marked `simulation_only`, which a live run refuses. See [hardware reference](hardware.md) for waypoint names and routes.

## Outcomes and retries

| Key | Outcome |
| --- | --- |
| `s` | `success` |
| `g` | `grasp_fail` |
| `d` | `drop` |
| `w` | `wrong_bin` |

After a no-read, the operator enters a cause instead:

| Key | `no_read_cause` |
| --- | --- |
| `t` | `tilted_in_grip` |
| `l` | `label_occluded` |
| Enter or `u` | `unknown` |

Physical outcomes are always entered by the operator. A gripper command or a completed path does not prove success.

After any final outcome other than `success` or `fault`, the live program offers one retry. The operator resets the same parcel and presses `r`. The retry writes a new row whose `retry_of` holds the first attempt's `cycle_id`. If the retry also fails, the program prints `Retry failed. Stop and wait for the operator.` A fault never offers a retry.

The program does not identify parcels. Restarting it resets the retry count, so it cannot enforce the one-retry rule across restarts.

The exit status is 0 when the last attempt is `success`, and 2 otherwise. A live run that does not end in success waits at `Cycle stopped. Inspect the parcel and robot before recovery.` until a key is pressed. Homing is always manual.

## Faults and controlled stop

Any exception or Ctrl+C during a cycle is a fault:

- tracking, step, limit, or workspace check failures
- timeouts
- controller alarms or a mode change
- camera or scanner failure
- an invalid outcome

The supervisor then stops sending commands and does not release the parcel, run a recovery path, or home.

1. It asks the server for a controlled stop: `ResetRobot()` on both controllers, which stops the arms and clears the planned command queue.
2. It confirms the stop using `CONTROLLED_STOP` in `config/settings.py`. Within `timeout_s` (2 s), polling every `poll_interval_s` (0.1 s):
   - both arms must report mode 4 or 5 with no alarms;
   - the joints must change by no more than `still_tolerance_rad` (0.002 rad) for `still_samples` (3) consecutive readings.
3. If confirmed, `fault_detail` ends with `controlled stop confirmed`. Both arms stay powered and enabled, holding position. `robot/robot_home.py --move` can home them once the server is stopped.
4. If the request fails, an alarm appears, or the arms do not settle in time, it asks for `EmergencyStop()` on both controllers. `fault_detail` then ends with `controlled stop not confirmed (...); emergency stop requested`. This powers both arms off with alarm 116. On this installation, clearing that alarm has required power-cycling the controllers. See [home and recover](../procedures/home_and_recover.md).

Status and stop requests go through `robot/launch_nodes.py`, which owns each controller's single dashboard connection (port 29999). Stops use a separate request socket, but they still depend on a responsive server and controller connection. A live cycle refuses to start against a server that lacks the status and stop interface: `Restart robot/launch_nodes.py to load controller status/stop support`. Network stop requests do not replace the physical emergency stop.

## Cycle log columns

Rows are appended to `SUPERVISOR["cycle_csv"]` (`cycle_logs/cycles.csv`) or to `--csv PATH`, under a file lock. A file with a different header is refused with `Cycle CSV columns differ; select a new log file`. The same row is printed as JSON.

| Column | Meaning |
| --- | --- |
| `cycle_id` | Random ID for this attempt. |
| `retry_of` | `cycle_id` of the original attempt, or blank. |
| `medium` | `envelope`, `poly_mailer` or `carton`. |
| `policy_type` | `ACT` or `DP`. A dry run without a checkpoint reports `ACT` for its simulated policy. |
| `label_face` | Value of `--label-face`, or blank. |
| `rotations_to_read` | Backup rotations completed. `0` with a token means a read during the initial stationary window. |
| `token`, `bin` | Accepted barcode and its bin index, or blank. |
| `outcome` | `success`, `grasp_fail`, `drop`, `wrong_bin`, `no_read` or `fault`. |
| `no_read_cause` | `tilted_in_grip`, `label_occluded`, `unknown`, or blank. |
| `fault_detail` | Fault message and which stop was used. |
| `t_pick_s`, `t_scan_s`, `t_place_s`, `t_total_s` | Phase and total durations in seconds, from the end of warmup. Operator decision time is excluded. |
| `dry_run` | `True` for simulated cycles. |
| `control_overruns` | Commands that took longer than one control period. |

Calculate success rates from physical trials only. Keep simulated rows and retries separate from first attempts.

## Command-line options

`evaluation/run_cycle.py`:

| Option | Meaning |
| --- | --- |
| `--medium {envelope,poly_mailer,carton}` | Required. Selects the workflow, holding arm, and rotations, and must match the checkpoint. |
| `--live` or `--dry-run` | Exactly one is required. `--live` opens hardware and moves the robot. `--dry-run` simulates the robot, clock, and scanner. |
| `--policy NAME` | Policy type from `POLICY_LOADERS` in `parcel_sorting/policies/interface.py`; default `robomimic`. See [extending the system](architecture.md#extending-the-system). |
| `--checkpoint PATH` | For `robomimic`: an ACT or DP `.pth` file. Required with `--live`. With `--dry-run` it loads the real model; without it a simulated policy moves straight to the scan pose. |
| `--waypoints PATH` | Waypoint file (default `config/waypoints.local.yaml`). |
| `--csv PATH` | Cycle log (default `cycle_logs/cycles.csv`). Dry runs append to it too. |
| `--label-face FACE` | The label's known starting face, for evaluation records only. `top`/`bottom` for flat media, `top`/`bottom`/`front`/`rear` for cartons. Omit it if unknown. It never reaches the policy. |
| `--fake-token TOKEN` | Dry run only. Simulated scan. An unmapped token never selects a bin; omitting it gives a no-read. |
| `--fake-read-after N` | Dry run only. The fake read appears after N rotations (default 0). |
| `--fake-outcome {success,grasp_fail,drop,wrong_bin}` | Dry run only. The simulated operator outcome (default `success`). |
| `--retry-once` | Dry run only. Simulates the operator accepting the one retry. |
| `--act-temporal-ensemble`, `--no-act-temporal-ensemble`, `--act-ensemble-coefficient VALUE`, `--act-query-frequency STEPS` | See [ACT rollout options](#act-rollout-options). |

`--fake-token` and `--retry-once` are refused with `--live`. `--fake-read-after` and `--fake-outcome` have no effect on a live run.

`evaluation/check_checkpoint.py` takes `--checkpoint PATH` and `--medium` (both required), `--steps N` (number of predictions, default 3; not parcel cycles), and the same ACT rollout options. It has no `--dry-run` flag because it never opens hardware.

## ACT rollout options

An ACT checkpoint stores its temporal ensembling and replan settings. These options change them in memory for one run; the file on disk is unchanged:

- `--act-temporal-ensemble` / `--no-act-temporal-ensemble` turns blending of overlapping chunks on or off.
- `--act-ensemble-coefficient VALUE` sets the weighting: positive favours older predictions, negative favours newer ones, zero averages.
- `--act-query-frequency STEPS` sets the replan interval when ensembling is off; `0` executes a full chunk.

The effective settings print as `ACT rollout settings: {...}` before hardware opens. These options require an ACT `--checkpoint`; a DP checkpoint refuses them with `ACT rollout options require an ACT checkpoint`. They do not relax any motion check or fault stop. See [ACT rollout](act_rollout.md) for weighting, timing, and recovery behaviour.

## Dry runs

A cycle dry run uses a virtual clock and a simulated robot that reaches every command exactly. Without `--checkpoint`, it also uses a simulated policy. It needs no server, cameras, scanner, or trained model. Each attempt is still appended to `--csv`, with `dry_run` set to `True`. Simulated rows are not evaluation data. See [commands reference](commands.md#dry-run-effects) for other programs.

## Limitations

- **Handoff gripper check:** the check is not a grasp detector. A partial-width grasp is rejected, and a closed command is accepted whether or not a parcel is held. See [handoff check](#handoff-check).
- **No timing or scan overrides:** the cycle has no command-line override for the rollout timeout or the scan window. It has no trial-start prompt and no stop after the first scan; it always continues to placement. Timing starts after model warmup, not at the first robot motion.
- **Gripper state:** the tracked gripper commands start open (1.0) and the actual jaw state is not measured. A completed cycle commands both grippers open; a fault leaves them as they were.
- **Recovery is manual:** after a fault or a non-success, nothing is released or homed automatically.
- **Software checks only:** they cover joint, workspace, and cable limits. They do not detect collisions with the parcel, scanner, bin rims, or the other arm.
