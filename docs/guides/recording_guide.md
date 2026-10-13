# Recording demonstrations

Policy A picks up a parcel, presents it at the reading station, stages it, and retracts. Policy B reacquires the staged parcel and places it in bin 0 or 1. Scanner capture is optional; the standard workflow below uses manually labelled B destinations.

For scanner setup and optional scan-paired A/B recordings, see the [barcode scanning guide](barcode_scanning_guide.md). For dataset conversion and ACT training, see the [ACT guide](act_training.md).

## 1. Environment and settings

Run commands from the repository root:

```bash
conda activate Xtrainer
cd /path/to/capstone-project-parcel-sorting
```

Use the existing Python 3.8 environment: vendor training modules are supplied as Python 3.8 bytecode, and `requirements.txt` is not a complete environment lockfile.

On a fresh checkout, copy `scripts/dobot_config/dobot_settings.example.ini` to `scripts/dobot_config/dobot_settings.ini` only if the actual file is absent. Configure devices and calibrate using the Dobot manuals. The example contains placeholders, not working calibration. Do not overwrite existing working settings.

Defaults live in [experiments/experiments_config.py](../../experiments/experiments_config.py), under `RUN_CONTROL`. CLI arguments override them for that run.

| Argument | What to set |
| --- | --- |
| `--project-name` | Recording folder name; use separate projects for A, B bin 0 and B bin 1 |
| `--policy-stage` | `A` or `B`; omitting it uses legacy recording without A/B metadata |
| `--medium` | `envelope` (including DL envelopes), `poly_mailer`, or `carton` |
| `--demonstrated-bin` | `0` or `1` for B; omit for A |
| `--show-img` | Show camera previews |
| `--no-capture-barcode` | Record without scanner capture, which is the default |
| `--source-episode` | Optional path to a completed A episode to preserve A/B pairing |

Recording a new project does not require registering it for ACT yet. Register the exact folder name in `PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py` before preparing/training it.

## 2. Start the robot and recorder

Follow the six-step [quick startup](../../README.md#quick-startup), using one of the commands below for step 6. Run only one recorder at a time. Keep camera placement, reading station, staging surface and bin assignments fixed. Resolve controller alarms and use the required TCP/IP mode before starting.

The server and recorder are the steady recording processes. Port finding runs once and exits. Calibration runs only when needed. Stop `3_just_buttonA.py` before the recorder because both open the leaders and control their torque locks. Stop any `5_camera_read.py` preview before the recorder because both open cameras.

Server startup enables followers and cycles grippers. Recorder startup moves both followers, even when you intend to synchronize only one. Keep both startup paths clear. Recording off does not mean teleoperation off; recorder exit and the yellow/green buttons are not emergency stops.

### Policy A

Leave the server running in terminal 1. In terminal 2:

```bash
python3 experiments/run_control.py --show-img \
  --project-name second_set_poly_mailer_A \
  --policy-stage A --medium poly_mailer --no-capture-barcode
```

### Policy B, bin 0

Stop the previous recorder after recording and synchronization are off, then start:

```bash
python3 experiments/run_control.py --show-img \
  --project-name second_set_poly_mailer_B_bin_0 \
  --policy-stage B --medium poly_mailer --demonstrated-bin 0 \
  --no-capture-barcode
```

### Policy B, bin 1

```bash
python3 experiments/run_control.py --show-img \
  --project-name second_set_poly_mailer_B_bin_1 \
  --policy-stage B --medium poly_mailer --demonstrated-bin 1 \
  --no-capture-barcode
```

Change the project names for another collection set and use `--medium carton` or `--medium envelope` for those media. A has no required barcode/bin. B needs a configured destination, supplied manually above or inherited from a valid source A episode.

## 3. Synchronize and record

The yellow **A** and green **B** button names are separate from policy names A/B.

For each required arm, one at a time:

1. Support the leader handle. Short-press yellow **A** for less than 0.5 seconds to unlock, position it at its calibrated initial posture, then short-press again to lock.
2. Hold yellow **A** for more than 2 seconds and release to enable synchronization. Wait for alignment to finish. The code accepts holds above 1 second; above 2 seconds follows the vendor guide.
3. Support the leader and short-press yellow **A** to unlock for teleoperation. Squeeze its trigger to close the follower gripper; release it to open.
4. Synchronize only the arm needed for the task; leave the unused arm unsynchronized. Press each arm's yellow button separately.

At least one arm must be synchronized to record. Both arm states/actions and all three cameras are recorded even when only one arm is synchronized; this does not configure one-arm inference.

For each episode:

1. Place the parcel at the agreed starting location and restore the required starting arm configuration.
2. Press and release green **B** to start. Confirm the recording message and numbered observation files.
3. Demonstrate the selected policy: **A** picks up, presents with a sensible dwell, stages, releases and retracts; **B** grasps from staging, places in the specified bin, releases and retracts. Scanner acceptance is optional for A. B's bin argument labels the intended placement, not the measured destination.
4. Press and release green **B** again to stop. Wait for `Saved episode metadata: ...` and saving to finish before the next episode.
5. Before exiting or manually resetting the workspace, disable synchronization with another long yellow **A** press, support/lock the leaders, and confirm the followers are stationary. Exit with **Ctrl+C** after recording stops.

Interrupting an active recording marks it incomplete. Review physical success: a saved episode is not proof of successful manipulation or correct-bin placement.

## 4. Optional A/B pairing

For ordinary separate A/B datasets, `--source-episode` is optional. To preserve the relationship between a completed A and its B demonstration, add the exact A episode directory to the B command:

```bash
--source-episode datasets/second_set_poly_mailer_A/collect_data/A_EPISODE_ID
```

Replace `A_EPISODE_ID` with the recorded directory name. Keep the parcel in its actual staged pose; do not improve the staging before collecting the paired B episode. Without a source, B is standalone with its own cycle ID. If A captured a barcode, B's supplied bin must match that scan.

Manually supplied destinations are stored as `destination.source = "manual"`; the recorder does not fabricate a scan. A new A recording starts a new cycle and clears previous scans.

## 5. Check and prepare episodes

Episodes are saved under the configured dataset root, normally:

```text
datasets/<project>/collect_data/<episode_id>/
    episode_metadata.json
    observation/*.pkl
    topImg/*.jpg
    leftImg/*.jpg
    rightImg/*.jpg
```

Episode IDs include microseconds. Metadata records policy stage, medium, cycle ID, destination provenance, frame count and completion status; task success remains `unreviewed`.

Count episodes and inspect a specific recording:

```bash
python3 scripts/count_episodes.py
python3 -m barcode_scanning.recording --inspect-episode \
  datasets/second_set_poly_mailer_A/collect_data/A_EPISODE_ID
```

An unscanned A has null barcode/bin values. A manually labelled B has its selected bin. Inspection checks metadata and matching frame filenames, not physical success or every image's contents.

After registering the project in `scripts/scripts_config.py`:

```bash
# Validate only
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A
# Validate and create HDF5 training files plus review videos
python3 scripts/prepare_act_datasets.py --dataset-name second_set_poly_mailer_A --convert
```

Finish collecting each set before conversion. Existing HDF5 outputs are refused, and mismatched raw frames are preserved. Review the videos and exclude interrupted, failed or wrong-bin demonstrations. Repeat for both B projects; see the [ACT guide](act_training.md) for training and combining sets.

## 6. Collection consistency and current limits

Balance bins 0 and 1 for each medium. Vary parcel poses within the intended range while keeping cameras, staging, bins and policy starting configurations consistent. Preserve A/B metadata when copying episodes, and keep destination mappings fixed for paired recordings.

The current baseline trains separate A, B bin 0 and B bin 1 tasks. B conversion preserves a constant `/observations/destination` vector per timestep: `[1, 0]` for bin 0 and `[0, 1]` for bin 1. The vendor ACT loader does not consume it automatically. A shared destination-conditioned B model and autonomous A/B handoff require further work. Existing inference commands both arms.
