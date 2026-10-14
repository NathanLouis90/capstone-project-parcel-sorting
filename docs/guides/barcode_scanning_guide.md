# Barcode scanning

This guide covers the dedicated USB HID scanner, destination labels, standalone testing, and optional barcode capture during a demonstration. For robot startup, Policy A/B recording arguments and button steps, see the [recording guide](recording_guide.md).

Scanner capture is disabled by default in demonstrations. Standalone capture commands no robot hardware and does not automatically attach scans to a recording or autonomous policy.

## 1. Files and settings

- `barcode_scanning/scanner_reader.py`: standalone capture and reusable reader thread. It commands no robot hardware.
- `barcode_scanning/barcode_scanning_config.py`: destination mapping, scanner identity, suffix keys, timeouts, and metadata filename.
- `barcode_scanning/recording.py`: paired recording metadata and offline episode inspection.
- `experiments/run_control.py`: existing teleoperation recorder with optional `--policy-stage A/B` integration.
- `scripts/script_collect2train.py`: conversion preserves metadata and adds B destination observations.

All examples run from the repository root:

```bash
conda activate Xtrainer
cd /path/to/capstone-project-parcel-sorting
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

Before using the robot examples below, complete hardware setup and start the server using the [recording guide](recording_guide.md). Run only one recorder, using the commands below, then follow the guide's synchronization steps. Stop the standalone reader before starting a recorder with `--capture-barcode`: only one process can own the scanner. Place parcel labels away from the grasp region, keep other readable labels out of view, and keep scanner/camera/bin positions consistent.

## 3. Optional barcode capture during Policy A

In terminal 2, from the repository root:

```bash
python3 experiments/run_control.py \
  --show-img \
  --project-name barcode_test_A \
  --policy-stage A \
  --capture-barcode \
  --medium carton \
  --scan-window-s 30
```

The recorder confirms scanner access before camera/robot startup. If capture fails, resolve that error before restarting. The server in terminal 1 stays running.

Use the [recording guide's synchronization steps](recording_guide.md#3-synchronize-and-record), then follow the scan-specific sequence below. The example uses carton projects; choose `poly_mailer` or `envelope` and matching project names for other media.

### Present, scan and stage

1. Prepare one carton at the receiving area with a verified label. Start the followers from the agreed home configuration.
2. Press and release green B. Confirm `Recording A: ...`, an open scan window, and numbered observation files.
3. Teleoperate the approach, grasp, and lift.
4. Present the barcode at the scanner. Hold the parcel stable until the terminal says, for example:

   ```text
   BARCODE ACCEPTED: DEST-A-S138683 -> bin 0
   ```

5. If the 30-second window expires before a successful read, hold the parcel securely, focus the camera preview, press the normal keyboard's `s` key, and present the barcode again. This opens a new window in the same cycle. A partial/invalid frame must finish with Enter before the next scan can be accepted.
6. Once a destination is accepted, it is fixed. Another barcode cannot replace it within that recording. If it was the wrong parcel, stop and discard the episode rather than reusing it.
7. Move to staging, lower and release the parcel, and retract the active arms to home.
8. Press and release B to stop. Confirm `Saved episode metadata: ...` and that observation-file messages stop.
9. Disable synchronization, support/lock the leaders, and confirm the followers are stationary. Leave the parcel at its actual staging pose if collecting the paired B episode next.
10. Exit terminal 2's recorder with Ctrl+C after the recording is stopped. The server remains running. Exiting or interrupting the recorder while recording is active marks that episode incomplete.

Each recording goes to:

```text
 datasets/barcode_test_A/collect_data/<episode_id>/
     episode_metadata.json
     observation/*.pkl
     topImg/*.jpg
     leftImg/*.jpg
     rightImg/*.jpg
```

The episode ID includes microseconds to prevent rapid start/stop folder collisions. The metadata records stage, medium, cycle ID, scan window(s), accepted token/bin/time, frame count, and completion state. Task success remains `unreviewed`: scan acceptance does not prove grasp or staging success.

### Check the scan and recording

Inspect the exact A episode directory printed by the recorder:

```bash
python3 -m barcode_scanning.recording --inspect-episode \
  datasets/barcode_test_A/collect_data/A_EPISODE_ID
```

Expect stage A, medium carton, the accepted barcode/bin, and a nonzero matching frame count. Inspection does not prove physical grasping or staging success; review the images and conversion videos.

Record A and each B bin in separate projects; combine them for unified A and conditioned B training with robomimic. Separate B-bin models are the vendor ACT baseline. Register their names in `scripts/scripts_config.py`, then validate and convert as described in the [recording guide](recording_guide.md#5-check-and-prepare-episodes). Existing HDF5 files are refused; mismatched raw frames are preserved.

## 4. Pair B with a scanned A

Proceed only if A physically staged the parcel successfully. Do not manually improve its staged pose. A's accepted barcode provides the destination; B does not rescan the label or require scanner capture.

After stopping terminal 2's A recorder, start B with A's exact source directory. This example assumes its accepted destination was bin 0:

```bash
python3 experiments/run_control.py \
  --show-img \
  --project-name barcode_test_B_bin_0 \
  --policy-stage B \
  --medium carton \
  --source-episode datasets/barcode_test_A/collect_data/A_EPISODE_ID \
  --demonstrated-bin 0
```

For a source scanned to bin 1, use `--demonstrated-bin 1` and a separate project such as `barcode_test_B_bin_1`. A source with missing scans, interruption, wrong medium, mapping mismatch, zero recorded frames, or scanner failure is refused before recorder robot/camera startup. The bin argument must match A's scan. It records your intended placement, not an automatic measurement of actual placement.

1. Start from the same agreed home configuration. Re-enable teleoperation one arm at a time using the [recording guide](recording_guide.md#3-synchronize-and-record).
2. Confirm the terminal's fixed B destination.
3. Press/release B and confirm recording starts.
4. Teleoperate to the staged parcel, grasp, lift, and transport it to the reported bin.
5. Lower it into that bin, release, and retract to home.
6. Press/release B to stop. Disable synchronization and confirm the followers stop before manual resets.
7. Inspect the new B episode with `python3 -m barcode_scanning.recording --inspect-episode ...`. Confirm its cycle ID matches A and its source episode identifies A.
8. Review actual placement. A wrong-bin demonstration must be excluded even if its metadata says the intended bin was correct.
9. Register and prepare each separate project using the [recording guide](recording_guide.md#5-check-and-prepare-episodes). Review converted videos before training.

Both manually labelled and scanner-paired B HDF5 files contain `/observations/destination`, a constant float32 vector per timestep: `[1, 0]` for bin 0 and `[0, 1]` for bin 1. Raw metadata is retained in HDF5 attributes. The vendor ACT loader ignores this observation and therefore requires separate B-bin baselines. The main robomimic ACT/DP path consumes destination as a low-dimensional input and combines both B bins; see the [training guide](diffusion_policy_training.md).

## 5. Collection consistency and inference limits

Keep destination mappings fixed between paired episodes and preserve metadata when copying recordings. Balance both bins for each medium and exclude interrupted, failed-scan and wrong-bin episodes from successful paired examples. A new A recording clears old scans; select the source episode belonging to the parcel actually on staging.

The reader can be embedded in a future supervisor, but standalone capture does not run policies. A supervisor must select A, open a scan window, verify staging/retraction and the destination, then start B. It must reset policy action queues at transitions and handle failures; elapsed time alone does not prove stage completion. Destination-conditioned training and offline checking use robomimic-r2d2. The vendor inference entry point requires explicit task/checkpoint selection; robomimic robot deployment and autonomous A/B handoff are not implemented.

## 6. Hardware-free verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Tests cover token lookup, scan timing, stale/partial/invalid input, keyboard decoding, wrong-device rejection, device cleanup, A/B pairing, interruption, scanner failure, B destination metadata, and the first green-B recording toggle. Passing tests does not replace a physical scanner test or reviewed demonstration.
