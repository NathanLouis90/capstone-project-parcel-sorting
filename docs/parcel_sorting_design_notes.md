# Parcel and mail sorting: working design notes

Updated: 2026-10-10. These notes retain user decisions and implementation findings for future work. They are a working reference, not a fixed specification. Explicit user updates take precedence over the proposal and over these notes.

## User-confirmed direction

- Policy A acquires an item and presents its barcode to the scanner.
- The intended initial design has three specialist Policy A models: thin envelope, filled poly mailer, and rigid carton.
- One unified Policy B uses the resolved destination to place items in the correct bin across all three media.
- The connected scanner currently types decoded barcode text into whichever application has keyboard focus.
- Dataset defaults in scripts and experiments point to the repository's `datasets/` folder, which Git ignores.

## Proposal context, subject to change

Source: `docs/RSE4018_Proposal_2302637_AdielFirqin.pdf`, submitted 14 September 2026.

The proposal describes Policy A placing the item at a staging point and retracting after barcode presentation. Policy B then reacquires the item from staging. Both policies begin from a fixed home configuration. Two destination bins use a one-hot destination signal held constant throughout each Policy B episode. The media are a thin envelope, filled poly mailer, and small rigid carton. ACT and Diffusion Policy comparisons and a unified Policy A ablation are proposed; these are not confirmed implementation commitments.

The proposal mentions serial scanner integration. Actual reported scanner behaviour suggests USB HID keyboard mode, so serial availability must be verified rather than assumed. The staging step and exact policy handoff remain open to revision.

## Current code and device evidence

- `barcode_scanning/make_labels.py` generates Code 128 PNGs and PDF labels. It does not capture scanner input, run policies, or implement a supervisor.
- `barcode_scanning/barcode_scanning_config.py`, section `MAKE_LABELS`, contains destination mappings and label settings.
- Current mappings: `DEST-A-S138683` maps to bin 0 (SIT Dover); `DEST-B-S828608` maps to bin 1 (SIT Punggol). These are destination tokens shared by items going to the same bin, not unique parcel identifiers.
- `experiments/run_inference.py` supplies joint state (`qpos`) and camera images to one model. No explicit destination input or A/B orchestration was found in the inspected runtime.
- `ModelTrain/detr/models/detr_vae.py` hardcodes a 14-dimensional state in its model builder. Destination conditioning requires corresponding dataset, loader, model, and inference changes, followed by training.
- Several vendor training/inference modules are present only as `.pyc` files, including `ModelTrain/module/model_module.pyc`; editable `.py` sources are absent. Their internals were not verified.
- `/proc/bus/input/devices` lists `Megahunt HID Keyboard`, vendor `0461`, product `4d82`, with handler `event3`. This is a candidate scanner, not a confirmed identity. The ordinary HP keyboard is listed separately.
- This agent environment could not access `/dev/input/event3` or enumerate `/dev/input/by-id` and `/dev/serial/by-id`. No live scanner capture or device grab was performed.

## Suggested integration, not yet implemented

Use a device-specific scanner reader that runs independently of GUI focus. If supported by the scanner, USB serial mode is an option; otherwise Linux evdev can read its keyboard events. For HID mode, exclusively grab only the confirmed scanner device while capture is active so decoded text does not also enter other applications. Decode key events correctly, including shift state and configured keyboard layout, and frame complete scans using the configured terminator. Avoid blocking the robot control loop while waiting for input.

A supervisor should own each item cycle, select the Policy A model from a known medium selection, arm a scan window, validate the complete token against the configured mapping, and associate the accepted scan with the active cycle. Reject unknown or conflicting tokens. Deduplicate repeated scans within a cycle, but allow the same destination on successive items. A destination barcode alone cannot prove unique item identity.

With staging retained, start Policy B only after both a valid destination and a successful staging/retraction handoff. Convert bin 0 to `[1, 0]` and bin 1 to `[0, 1]`, freeze that signal for the episode, and reset model action buffers and episode state at policy transitions. Stop or use an explicitly designed recovery path on scan timeout or failed handoff; do not choose a default bin.

Store paired A/B episode IDs, medium, raw barcode, destination index, scan timing, mapping version, and per-stage outcomes in dataset metadata. Supply destination conditioning consistently during Policy B training and inference. Balance each medium across destinations, vary item poses, and test destination use with controlled destination swaps to detect visual shortcuts.

Open issues include scanner identity/mode/terminator, input permissions and stable device selection, presentation geometry and scan dwell, stage completion detection, medium selection, staging consistency, stale scans from nearby labels, reconnect handling, recovery behaviour, and access to editable training/inference sources.


## Implementation update: scanner and recording support

On 2026-10-10, `barcode_scanning/scanner_reader.py` and `recording.py` were implemented. Scanner capture uses a dedicated Linux HID input device with exclusive access, exact destination lookup, monotonic scan windows, partial-frame rejection, and single accepted destination per cycle. Live device identity/access remains to be confirmed on the host.

`run_control.py` now accepts `--policy-stage A/B`, medium, scan-window settings, and an explicit source A episode / demonstrated bin for B. A scans are saved in atomic episode metadata; B inherits the source destination and cycle. The first B-button release now starts recording, and timestamp folders include microseconds. Conversion retains provenance and writes B's `/observations/destination`. Policy loaders/models and autonomous A/B supervision still need implementation. See the [recording guide](guides/recording_guide.md) for current commands and teleoperation steps, and the [barcode scanning guide](guides/barcode_scanning_guide.md) for scanner setup and scan-paired episodes. Earlier findings above describe the pre-integration state.


## Revised collection direction: scanner-independent demonstrations

The user clarified that demonstrations can focus on manipulation without running scanner capture. The reader now captures continuously by default until Ctrl+C; `--once --window N` retains a bounded test. Rejected raw tokens and reasons are shown, `--debug` prints key decoding, case normalization defaults on, and keypad digits are supported.

A/B recording now defaults to scanner capture disabled. A records acquisition, presentation, staging and retraction without requiring a barcode. B requires a configured `--demonstrated-bin`, stored explicitly as a manual destination; optional `--source-episode` maintains pairing with unscanned A. An A scan can still be collected with `--capture-barcode`, and scanner-paired B must agree with that scan. Conversion accepts unscanned A and manually labelled B, preserving B's constant destination observation. No scan is fabricated for manually labelled episodes.

The scanner is needed for automatic destination resolution during inference, but model conditioning support and autonomous supervision remain pending. Standalone capture does not itself send events to the recorder or policy. Keep only one scanner owner. Find-port and calibration tools are one-time setup tasks; stop just-button-A and camera preview helpers before the recorder to avoid shared-device conflicts.
