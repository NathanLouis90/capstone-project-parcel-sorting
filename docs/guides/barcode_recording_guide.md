# Barcode capture and paired Policy A/B recordings

This guide uses staging: Policy A picks, scans, sets the item down, and retracts. Policy B picks it up from staging and places it into the scanned destination bin. There are three intended A models (envelope, poly mailer, carton) and one shared destination-conditioned B model.

Implemented here: indefinite standalone scanner capture, optional timed scan acceptance during A recording, raw episode metadata, optional A/B pairing, and destination-preserving conversion. Scanner capture is disabled by default during demonstrations; B can use a manually supplied destination label. Autonomous A/B orchestration and destination-conditioned model training/inference are not implemented by this change.

## 1. Files and settings

- `barcode_scanning/scanner_reader.py`: standalone capture and reusable reader thread. It commands no robot hardware.
- `barcode_scanning/barcode_scanning_config.py`: destination mapping, scanner identity, suffix keys, timeouts, and metadata filename.
- `barcode_scanning/recording.py`: paired recording metadata and offline episode inspection.
- `experiments/run_control.py`: existing teleoperation recorder with optional `--policy-stage A/B` integration.
- `scripts/script_collect2train.py`: conversion preserves metadata and adds B destination observations.

All examples run from the repository root:

```bash
conda activate Xtrainer
cd /home/adiel/dobot_xtrainer
```

Install the Linux scanner dependency in this environment:

```bash
python3 -m pip install "evdev==1.6.1"
```

The pin supports the repository's Python 3.8 environment. Source installation may need a C compiler and Linux input headers. See [evdev 1.6.1](https://pypi.org/project/evdev/1.6.1/).

The reader supports USB HID keyboard mode, not serial mode. Configure the scanner to use a US keyboard layout and an Enter suffix. Only complete configured destination tokens are accepted. Case normalization is enabled by default (lowercase scanner output matches the uppercase tokens); raw text is retained. Set `normalize_case` to `False` for case-sensitive matching. Arbitrary prefixes, suffixes, or other tokens are not treated as destinations. Do not change the scanner to serial mode for these commands.

Current destinations are `DEST-A-S138683` (bin 0) and `DEST-B-S828608` (bin 1). Labels can be regenerated with `python3 barcode_scanning/make_labels.py`.

## 2. Test the reader alone, without robot movement

### 2.1 Test lookup without a scanner

```bash
python3 barcode_scanning/scanner_reader.py --simulate DEST-A-S138683
python3 barcode_scanning/scanner_reader.py --simulate DEST-B-S828608
python3 barcode_scanning/scanner_reader.py --simulate UNKNOWN
```

The first two report `accepted` and bins 0/1. The last reports `unknown or empty barcode; waiting` and exits with status 2. Simulation tests text lookup; it does not test USB capture, event decoding, or physical scan quality.

### 2.2 Identify the scanner

```bash
python3 barcode_scanning/scanner_reader.py --list-devices
```

Each accessible device prints its path, name, decimal vendor/product IDs, physical connection, and unique identifier. Compare the list with the scanner connected and disconnected if its identity is unclear. Never configure the ordinary keyboard as the scanner.

The current config contains a candidate observed on this PC:

```python
"device_name": "Megahunt HID Keyboard",
"vendor_id": 0x0461,
"product_id": 0x4D82,
```

The host currently has the stable link `/dev/input/by-id/usb-Megahunt_HID_Keyboard_D-2TYYGQMH-event-kbd`, and the config now uses it. Confirm this is the scanner by a hand scan. On another PC, update the identity and path, or use `None` to discover by name/vendor/product. A temporary `--device /dev/input/eventN` override still checks identity. Event numbers can change after reconnecting.

If no devices are accessible, run on the host PC rather than an environment that hides `/dev/input`. Access to the confirmed scanner node is required. Ask the workstation administrator for a device-specific access rule, or grant a temporary ACL to that node after identification:

```bash
sudo setfacl -m u:"$USER":rw /dev/input/by-id/usb-Megahunt_HID_Keyboard_D-2TYYGQMH-event-kbd
```

The stable link above points to the current scanner event node. This example is not a blanket permission change for all keyboards. Temporary node ACLs may need renewal after reconnecting. Linux event reading and exclusive capture are documented in the [evdev tutorial](https://python-evdev.readthedocs.io/en/stable/tutorial.html).

### 2.3 Capture one actual scan

```bash
python3 barcode_scanning/scanner_reader.py --once --window 20
```

It prints the exclusively captured device and opens a 20-second window. Scan one generated label by hand. Expect a JSON event with `barcode`, `bin_index`, `timestamp` (Unix seconds), `cycle_id`, and `received_monotonic`.

Click another application while the reader is waiting and scan again in a fresh test. Text should reach the reader without being typed into that application. Your normal keyboard remains available. The reader exits after one accepted scan or timeout and releases exclusive capture.

For repeated testing:

```bash
python3 barcode_scanning/scanner_reader.py
```

Running without flags captures indefinitely, without a scan-window deadline or rearming gaps. Every complete recognised barcode prints an event. Unknown barcodes print a rejection with the decoded raw text and reason. Ctrl+C exits. A scan timeout exits with status 2 in single-window mode. A disconnected scanner ends capture with an error; restart after reconnecting.

Only one process can exclusively own the scanner. You may leave the standalone reader running alongside normal scanner-independent A/B recordings. Stop it before using `--capture-barcode`, because that A recorder starts its own reader thread. Standalone output is not automatically attached to recordings or passed to an autonomous policy.

If a scan is rejected, inspect the printed `raw_barcode` and `reason`. To see individual scanner keys and decoded characters, run:

```bash
python3 barcode_scanning/scanner_reader.py --debug
```

A lowercase token should now match. An unmapped token requires checking the label/configuration. An unsupported-key or partial-frame rejection requires checking the scanner keyboard layout, prefixes/suffixes, and character timing. Do not guess a destination from an unknown token.

## 3. Robot setup before collecting demonstrations

1. Prepare the receiving area, scanner, staging surface, and labelled bins. Keep camera placement and physical bin assignment fixed. Place labels clear of the grasp region and keep other readable labels out of the scanner's view.
2. Resolve controller alarms and use the required TCP/IP control mode. Stop other robot command clients. Support the leaders and keep their buttons released during startup.
3. Find leader and follower-gripper serial ports before starting the server:

   ```bash
   PYTHONPATH=. python3 scripts/1_find_port.py
   ```

   This probes devices and rewrites `scripts/dobot_config/dobot_settings.ini`. It does not identify the keyboard-mode scanner. Do not run it concurrently with the robot server or recorder.
4. Run offset calibration only when required, with the leaders positioned according to the platform calibration procedure:

   ```bash
   PYTHONPATH=. python3 scripts/2_get_offset.py
   ```

   It rewrites calibration; it is not a routine dataset-directory setup step.
5. Optionally preview cameras:

   ```bash
   PYTHONPATH=. python3 scripts/5_camera_read.py
   ```

   Stop this preview before recording. Confirm all three views cover the task.
6. In terminal 1, start the robot server:

   ```bash
   python3 experiments/launch_nodes.py
   ```

   This is not a passive connection check: it enables followers, sets motion parameters, and cycles grippers. Keep the workspace clear. The server's existing initialization sets a 20% global speed factor.

The recorder also automatically moves both followers through their initial poses before teleoperation starts. Those startup paths must be clear. Recording off does not mean teleoperation off, and exiting the recorder is not an emergency-stop command.

## Preferred workflow: record manipulation without scanner capture

The scanner is not required to record or train Policy A's manipulation trajectory. Demonstrate pickup, presentation at the reading station with a sensible dwell, staging, release, and retraction. A successful read is useful feedback when checking the presentation geometry, but it is not a required A model input.

Policy B still needs a destination label during collection and training. Select the bin before that B recording, then demonstrate placement into that bin. Balance both bins for every medium. A manually supplied bin is stored as `destination.source = "manual"`, not as a fabricated scan.

After the robot setup above, start scanner-independent A recording:

```bash
python3 experiments/run_control.py --show-img --project-name parcel_sorting --policy-stage A --medium carton
```

Follow the leader synchronization steps in section 4.1 below. Press/release B to start; demonstrate pickup, scanner presentation, staging and retraction; press/release B to stop. A's metadata has no barcode and no destination requirement. Inspect it with the offline episode command in section 4.3; `barcode` and `bin_index` will be null for unscanned A.

Stop the A recorder after recording has stopped. Leave the parcel in its actual staging pose. Start B and specify the intended bin:

```bash
python3 experiments/run_control.py --show-img --project-name parcel_sorting --policy-stage B --medium carton --demonstrated-bin 0
```

Use `--demonstrated-bin 1` for a bin-1 demonstration. An optional `--source-episode datasets/parcel_sorting/collect_data/A_EPISODE_ID` preserves the A/B cycle pairing even when A did not scan. Without it, B is a standalone demonstration with its own cycle ID. If you reference an A episode that did scan, its scanned bin must match the supplied bin.

Synchronize leaders again, press/release B, grasp the staged item, place it into the selected bin, release and retract, then stop with B. Review the actual placement: the bin flag is an operator label, not a measurement of which bin was used. A and B metadata and conversion work without any scanner process.

If you want scanner text suppressed across other applications all day, run the standalone reader in a separate terminal:

```bash
python3 barcode_scanning/scanner_reader.py
```

This can coexist with the commands above, but not with `--capture-barcode`. The scanner reader consumes only its dedicated device; teleoperation and recording use their own inputs.

Do not keep all setup scripts running as separate services. `1_find_port.py` runs once and exits. `2_get_offset.py` is calibration only. Stop `3_just_buttonA.py` before `run_control.py`: both open the leaders and control their torque locks. Stop the camera preview before the recorder: both open cameras. The steady recording processes are the robot server and recorder, plus an optional standalone reader.

## 4. Optional scanner-paired Policy A recording

In terminal 2, from the repository root:

```bash
python3 experiments/run_control.py \
  --show-img \
  --project-name barcode_test \
  --policy-stage A \
  --capture-barcode \
  --medium carton \
  --scan-window-s 30
```

The recorder confirms scanner access before camera/robot startup. If capture fails, resolve that error before restarting. The server in terminal 1 stays running.

### 4.1 Enable teleoperation

For each required arm, one at a time:

1. Support its leader handle. A short yellow A press under 0.5 seconds toggles its torque lock.
2. Unlock, position near its calibrated starting configuration, and lock again.
3. Hold yellow A longer than one second and release to enable synchronization. Wait for the dynamic alignment movement to finish.
4. Support and unlock the leader for teleoperation.
5. Repeat for the other arm if needed. Avoid simultaneous A presses because their existing timing variable is shared.

Squeeze the trigger to close the follower gripper; release it to open. Green B controls one global recording state. At least one arm must be synchronized to start recording. The first B release now starts recording; the next stops it. Confirm terminal messages and frames rather than relying only on the lamp.

### 4.2 Demonstrate A

1. Prepare one carton at the receiving area with a verified label. Start the followers from the agreed home configuration.
2. Press and release green B. Confirm `Recording A: ...`, an open scan window, and numbered observation files.
3. Teleoperate the approach, grasp, and lift.
4. Present the barcode at the scanner. Hold the parcel stable until the terminal says, for example:

   ```text
   BARCODE ACCEPTED: DEST-A-S138683 -> bin 0
   ```

5. If the 30-second window expires before a successful read, hold the parcel securely, focus the camera preview, press the normal keyboard's `s` key, and present the barcode again. This opens a new window in the same cycle. A partial/invalid frame must finish with Enter before the next scan can be accepted.
6. Once a destination is accepted, it is fixed. Another barcode cannot replace it within that recording. If it was the wrong parcel, stop and discard the episode rather than reusing it.
7. Move to staging, lower and release the parcel, and retract both arms to home.
8. Press and release B to stop. Confirm `Saved episode metadata: ...` and that observation-file messages stop.
9. Disable synchronization, support/lock the leaders, and confirm the followers are stationary. Leave the parcel at its actual staging pose if collecting the paired B episode next.
10. Exit terminal 2's recorder with Ctrl+C after the recording is stopped. The server remains running. Exiting or interrupting the recorder while recording is active marks that episode incomplete.

Each recording goes to:

```text
 datasets/barcode_test/collect_data/<episode_id>/
     episode_metadata.json
     observation/*.pkl
     topImg/*.jpg
     leftImg/*.jpg
     rightImg/*.jpg
```

The episode ID includes microseconds to prevent rapid start/stop folder collisions. The metadata records stage, medium, cycle ID, scan window(s), accepted token/bin/time, frame count, and completion state. Task success remains `unreviewed`: scan acceptance does not prove grasp or staging success.

### 4.3 Check that one recording

Copy the exact episode directory printed by the recorder. Replace `A_EPISODE_ID` below:

```bash
python3 -m barcode_scanning.recording --inspect-episode \
  datasets/barcode_test/collect_data/A_EPISODE_ID
```

Expect stage A, medium carton, the correct barcode/bin, and a nonzero matching frame count. This checks metadata and matching filenames, not physical success or every image's contents. Review the images/video to confirm the parcel was picked, scanned, released at staging, and the arms retracted.

For a short conversion test, choose an unused output index:

```bash
python3 scripts/script_collect2train.py \
  --root_dir /home/adiel/dobot_xtrainer/datasets \
  --dataset_name barcode_test \
  --date_collect A_EPISODE_ID \
  --idx 0
```

Do not reuse an existing index: the converter's existing output behaviour overwrites that HDF5 path. Its existing mismatch cleanup can remove unmatched raw files, so inspect frame matching first. New A/B metadata is validated before conversion. Old recordings without metadata remain convertible.

## 5. Optional scanner-paired Policy B episode

Proceed only if A physically staged the parcel successfully. Do not manually improve its staged pose. A's accepted barcode provides the destination; B does not rescan the label or require scanner capture.

After stopping terminal 2's A recorder, start B with A's exact source directory. This example assumes its accepted destination was bin 0:

```bash
python3 experiments/run_control.py \
  --show-img \
  --project-name barcode_test \
  --policy-stage B \
  --medium carton \
  --source-episode datasets/barcode_test/collect_data/A_EPISODE_ID \
  --demonstrated-bin 0
```

Use `--demonstrated-bin 1` for a source scanned to bin 1. A source with missing scans, interruption, wrong medium, mapping mismatch, zero recorded frames, or scanner failure is refused before recorder robot/camera startup. The bin argument must match A's scan. It records your intended placement, not an automatic measurement of actual placement.

1. Start from the same agreed home configuration. Re-enable teleoperation one arm at a time as described above.
2. Confirm the terminal's fixed B destination.
3. Press/release B and confirm recording starts.
4. Teleoperate to the staged parcel, grasp, lift, and transport it to the reported bin.
5. Lower it into that bin, release, and retract to home.
6. Press/release B to stop. Disable synchronization and confirm the followers stop before manual resets.
7. Inspect the new B episode with `python3 -m barcode_scanning.recording --inspect-episode ...`. Confirm its cycle ID matches A and its source episode identifies A.
8. Review actual placement. A wrong-bin demonstration must be excluded even if its metadata says the intended bin was correct.
9. Convert B with the same converter command but B's episode ID and a new unused index, for example `--idx 1`.

Both manually labelled and scanner-paired B HDF5 files contain `/observations/destination`, a constant float32 vector per timestep: `[1, 0]` for bin 0 and `[0, 1]` for bin 1. Raw metadata is retained in HDF5 attributes. The current vendor model/loader does not automatically consume this new dataset; conditioning support and retraining are still needed.

## 6. Collect the training set

Repeat paired A/B cycles for `--medium envelope`, `--medium poly_mailer`, and `--medium carton`. Balance both destinations for each medium. Vary item poses within the intended operating range, while keeping cameras, scanner, staging area, bins, and policy starting configuration consistent.

Do not change the destination mapping between paired episodes. Keep A/B metadata with the images/actions when copying datasets. Review failures and exclude accidental, interrupted, unknown-destination, and wrong-bin episodes from successful imitation examples.

One Policy A recording contains both arms and all cameras even when only one arm is synchronized. A new A recording starts a new cycle and clears old scans. B takes its destination explicitly from the selected completed A episode; ensure that episode belongs to the parcel still on staging.

## 7. What inference will require next

The implemented reader can also be embedded in a future supervisor. That supervisor must select the A model, open a scan window, verify A's staging/retraction, then start B with the fixed destination. It must reset policy action queues at transitions and handle scan/staging failures. It must also detect or receive confirmation of stage completion; an elapsed duration alone is not proof.

This guide does not claim the existing `run_inference.py` can perform this sequence yet. Destination-conditioned model inputs, training, checkpoint selection, and the autonomous supervisor remain separate work.

## 8. Hardware-free verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Tests cover exact lookup, timed acceptance, stale events, invalid/partial frames, repeated cycles, keyboard decoding, wrong-device rejection, device cleanup, A/B pairing, interruption, scanner failure, B's constant HDF5 condition, and the first B-button recording toggle. Passing these tests does not replace a physical scanner test or a reviewed teleoperation trial.
