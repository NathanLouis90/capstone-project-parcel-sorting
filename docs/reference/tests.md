# Tests

The regression suite in `tests/` checks safety logic, cycle behaviour, homing commands, and training bookkeeping without any hardware. It runs in about 10 seconds on the robot PC.

## Running the suite

From the repository root, after the [terminal preparation](commands.md#terminal-preparation):

```bash
python3 -m pytest
```

Expect a line such as `115 passed`. `pytest.ini` limits collection to `tests/` and skips `third_party`, `robomimic-r2d2`, `datasets`, `ckpt` and `archived_datasets`. No extra environment variables are needed, because the repository is installed with `pip install -e .`.

To run one file or one test:

```bash
python3 -m pytest tests/test_motion_limits.py
python3 -m pytest tests/test_motion_limits.py -k initial_approach
```

Run the suite after changing anything in `config/settings.py`, `parcel_sorting/safety/`, `parcel_sorting/runtime/`, `parcel_sorting/policies/`, `parcel_sorting/hardware/robot_home.py` or `parcel_sorting/training/`.

## Rules for tests

- **No hardware.** Tests never open a robot, camera, leader, gripper, or scanner, and never start `robot/launch_nodes.py`.
- **Fakes stand in for devices.** Controllers, grippers, and stop requests are fakes. Motion runs on the simulated environment and virtual clock from `parcel_sorting/runtime/scripted_motion.py`, and scans come from the cycle's `FakeScanner`.
- **Synthetic data only.** Recordings, HDF5 datasets, checkpoints, and training logs are small synthetic files built in pytest's `tmp_path`. Tests never read `datasets/` or `ckpt/`.
- **Naming.** Files are named `tests/test_*.py`, and test functions `test_*`.
- **Add coverage with behaviour changes.** Changes to safety limits, metadata, conversion, or checkpoint handling need a regression test.

Checks that need the real robot are not tests: `setup/check_waypoints.py`, `setup/check_wrist_rotation.py`, `setup/check_scanner.py`, and the numbered `setup/1_` to `setup/4_` helpers. They are run by hand as procedures; see [check waypoints](../procedures/06_check_waypoints.md) and [hardware setup](../procedures/02_hardware_setup.md).

## What each file covers

| File | Covers |
| --- | --- |
| `test_motion_limits.py` | **Shared bounds:** recording and rollout use the same 0.17 rad command-step bound, and the recording helper's wrap correction still enforces it.<br>**Gaps:** feedback lag is checked separately from command steps; later command jumps and feedback divergence fault with joint details naming the arm and joint (grippers excluded).<br>**Initial approach:** uses only small paced steps; skipped for a small first target; rejects a large or unsafe first target before any movement, and checks taught cable limits, gripper range, and the rollout deadline.<br>**Cycle:** resets policy history after the approach; faults without sending an out-of-bounds first target.<br>**Workspace faults:** name the arm, axis, and overshoot.<br>**Rollout audit:** `tools/check_rollout_compatibility.py` separates lag from command steps, reports recordings to fix, and finds the dataset saved in a checkpoint. |
| `test_gripper_convention.py` | 1.0 opens and 0.0 closes, matching the recordings. Home has both grippers open. Handoff needs a closed holding gripper and an open idle gripper. A simulated cycle opens the holding gripper at the drop and ends with both grippers open. |
| `test_controlled_stop.py` | **Confirmed stop:** a fault first requests `ResetRobot()` on both controllers, even if one request fails; idle, still arms keep power.<br>**Fallback:** an unconfirmed stop requests `EmergencyStop()`, and a failed emergency fallback is reported. Uses a fake stop client in place of the server. |
| `test_idle_arm_inputs.py` | **Parked arm:** gets its training inputs, including the gripper.<br>**Refusals:** a checkpoint is refused when an arm that never moved in training would be commanded, or when an arm that moved would be parked.<br>**Roles:** both arms are active when both moved; mailer recordings are right-arm only. |
| `test_act_temporal_ensemble.py` | **Replanning and ensembling:** ACT replan offsets within a chunk, ensemble weight order (including zero predictions), expiry and bounded memory of old predictions, reset between episodes, and refusal of non-finite predictions or a changed batch shape.<br>**Native ACT:** observes new state at every step and clears warmup history.<br>**Settings:** old-checkpoint defaults, in-memory rollout overrides, command-line defaults that leave saved settings alone, and temporal settings saved into checkpoint config and reports.<br>**Joint input noise:** applies only in training mode, reaches new ACT configs, and rejects negative values. |
| `test_robot_home.py` | **Speed and arms:** `robot/robot_home.py` sends the requested speed to both arms (default both arms at 10%), rejects invalid speeds before connecting, keeps lifts at 5%, and moves only the selected arm when one is chosen.<br>**Stages and faults:** each stage waits for both arms to settle; command failures, interrupts, peer faults, and group timeouts stop both arms, and the peer stop is attempted even if the first fails.<br>**Software emergency-stop reset:** powers on before reset and enable, sends nothing without confirmation, never enables after a persistent stop, refuses extra alarms and invalid flag combinations, and does not suggest retrying after a power-on failure alarm.<br>**`--open-gripper`:** opens both grippers before any arm changes state, blocks motion if a gripper does not open, needs `--move` or `--recover`, and grippers are never commanded without it. |
| `test_checkpoint_names.py` | **Short paths:** `best.pth` and `latest.pth` are relative links that follow the right checkpoints and survive renaming the model folder.<br>**Refusals:** missing, external, or regular-file targets.<br>**After failures:** completed saves are still published if training later fails. |
| `test_hyperparameter_defaults.py` | **Separate defaults:** the training menu keeps ACT and DP hyperparameter defaults separately; older flat preferences seed both, and each editor changes only its own algorithm while keeping the shared split.<br>**Editor:** the DP editor shows its advanced fields and saves on back; field validation is independent per algorithm.<br>**Generated jobs:** use each algorithm's saved defaults; paired training shares one split. |
| `test_training_reports.py` | **Metrics:** the epoch-log parser keeps finite scalars only; full reports use the saved hyperparameters and all metrics, and sparse old reports get no invented training curves.<br>**After a run:** metrics and reports are kept after success or failure; DP comparisons reuse the exact data snapshot and split.<br>**Configuration:** the full-configuration table keeps every saved value and marks inactive ones, and reports read the configuration captured by the trainer rather than later menu edits.<br>**Learning-rate graph:** appears only when recorded rates change, and is never invented from missing history. |
