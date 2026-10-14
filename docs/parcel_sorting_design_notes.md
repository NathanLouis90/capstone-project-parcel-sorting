# Parcel and mail sorting: working design notes

Updated: 2026-10-14. These notes retain user decisions and implementation findings for future work. They are a working reference, not a fixed specification. Explicit user updates take precedence over the proposal and over these notes.

## User-confirmed direction — 2026-10-14

- Policy A is one unified policy across envelopes, poly mailers and cartons. For mailers/cartons, only the left arm picks from receiving, presents the label, places at staging and returns home. The right arm remains home with its gripper closed.
- Envelope A uses both arms sequentially. The left arm slides an edge toward the right arm and returns fully home. After a short pause, the right arm tilts, grasps the edge, presents the label, places at staging with an overhanging edge and returns home.
- Policy B is one right-arm policy across all media and both bins. Destination is a constant one-hot observation: `[1, 0]` for bin 0 and `[0, 1]` for bin 1. The left arm stays home with its gripper closed.
- Main ACT and Diffusion Policy experiments use robomimic-r2d2 with the same loader, normalization and frozen train/validation split. Medium-specific A policies are only the O6 ablation. Separate B-bin policies are only the specialist baseline and the vendor ACT option.
- Recording remains one stage/bin per project, with `--demonstrated-bin 0` or `1` for B. Projects are combined during offline conversion. The recorder CLI is unchanged.
- Scanner output never enters policy observations. A supervisor supplies B's destination. Its design below is documented, not implemented.

## Demonstration rules

Every demonstration starts and ends with both arms at home and both grippers closed. An unused arm stays home, closed and unsynchronized. Envelope A must finish the left slide and left-arm return, pause briefly, and only then move the right arm; both arms must never move simultaneously. Stage envelopes with an edge overhanging so B never needs a slide.

Labels must agree with the demonstrated B destination: DEST-A for bin 0, DEST-B for bin 1 (the configured full tokens are `DEST-A-S138683` and `DEST-B-S828608`). When barcode capture is disabled, the recorder cannot verify label agreement. Collect roughly equal B-bin-0 and B-bin-1 episode counts for every medium. Discard searching or wiggling at the scanner and any failed, interrupted or wrong-bin demonstration.

Review episodes before conversion and explicitly mark them accepted or rejected. Home, idle-arm, rate and inference-limit violations are advisory warnings for review; the configured length limit and provenance checks remain hard failures.

## Supervisor design (not yet implemented)

At startup, load A and B, home both arms and start the scanner reader as the scanner's only owner. For each parcel:

1. Create a new cycle ID, flush scanner input and open a scan window.
2. Run unified A. Ignore right-arm commands for mailers/cartons and keep that arm home and closed. Envelope A drives both arms; check safety for both.
3. End A after parcel release at staging and approximately 1 s with both arms near home. Use a maximum-step timeout as backup, not proof of success.
4. Close the scan window. The first valid token wins; ignore later reads. If no valid token was accepted, log a no-read and stop the cycle. Never guess a bin.
5. Move both arms home and close both grippers to exactly match the B training start state.
6. Reset B's action queue, temporal aggregation and other episode state.
7. Run B with the fixed destination one-hot at every step; keep the left arm home and closed.
8. End B using release and home dwell with a timeout backup. Log cycle ID, medium, destination, stage durations and outcome.

## Current implementation verification — 2026-10-14

The vendor converter writes 14-D `/observations/qpos` and `/action`, padded JPEG byte rows under `/observations/images/{top,left_wrist,right_wrist}`, and constant B destination vectors. Robomimic conversion decodes BGR JPEGs to RGB uint8 HWC and resizes all cameras identically. Repeated cycle IDs stay in the same stratified split.

Recorded first-frame gripper observations in all five local projects were `[0.99114583, 0.97942708]`. Commands near 1 close the grippers: the driver maps commands directly to servo positions, whose maximum is documented as closed. The legacy `claw_width()` formula increases width toward 1 and is inconsistent with that command convention. Inference therefore checks both extremes of the jaw span conservatively; geometry still requires calibration. The robot's joint-state getter uses a placeholder gripper value, so first-frame observations come from configuration matched to recordings.

Nova 2/5 forward kinematics was available in the recorder and is now shared without hardware imports. Inference validates commanded jaw-tip positions before every policy command, rejects nonfinite outputs and both signs of excessive joint increments, and parks the task's unused arm. Both loops use the shared 40 ms period. The recorder velocity denominator includes the wait, preserving meters-per-second units; overruns use the actual longer interval.

Recursive Python 3.8 bytecode inspection of `ModelTrain/module/*.pyc` found no `DT` or `FPS` references. No editable vendor source referenced them either. They remain unchanged at `DT=0.02` and `FPS=50`; opaque bytecode behavior is not otherwise inferred from this inspection.

The bundled robomimic fork required repairs for list-based validation datasets, training-stat normalization during validation, observation normalization API mismatches, raw-image rollout processing, unnecessary eager CLIP downloads and CUDA-only ACT model construction. ACT's robomimic branch backend is included with upstream license and revision. No vendor bytecode was edited. CPU smoke runs use synthetic data and reduced models; they verify integration, not learned parcel sorting or deployment readiness.

## Proposal context, subject to change

Historical: the settled design dated 2026-10-14 supersedes this section wherever they conflict.

Source: `docs/RSE4018_Proposal_2302637_AdielFirqin.pdf`, submitted 14 September 2026.

The proposal describes Policy A placing the item at a staging point and retracting after barcode presentation. Policy B then reacquires the item from staging. Both policies begin from a fixed home configuration. Two destination bins use a one-hot destination signal held constant throughout each Policy B episode. The media are a thin envelope, filled poly mailer, and small rigid carton. ACT and Diffusion Policy comparisons and a unified Policy A ablation are proposed; these are not confirmed implementation commitments.

The proposal mentions serial scanner integration. Actual reported scanner behaviour suggests USB HID keyboard mode, so serial availability must be verified rather than assumed. The staging step and exact policy handoff remain open to revision.

## Current code and device evidence

Historical: the settled design dated 2026-10-14 supersedes this section wherever they conflict.

- `barcode_scanning/make_labels.py` generates Code 128 PNGs and PDF labels. It does not capture scanner input, run policies, or implement a supervisor.
- `barcode_scanning/barcode_scanning_config.py`, section `MAKE_LABELS`, contains destination mappings and label settings.
- Current mappings: `DEST-A-S138683` maps to bin 0 (SIT Dover); `DEST-B-S828608` maps to bin 1 (SIT Punggol). These are destination tokens shared by items going to the same bin, not unique parcel identifiers.
- `experiments/run_inference.py` supplies joint state (`qpos`) and camera images to one model. No explicit destination input or A/B orchestration was found in the inspected runtime.
- `ModelTrain/detr/models/detr_vae.py` hardcodes a 14-dimensional state in its model builder. Destination conditioning requires corresponding dataset, loader, model, and inference changes, followed by training.
- Several vendor training/inference modules are present only as `.pyc` files, including `ModelTrain/module/model_module.pyc`; editable `.py` sources are absent. Their internals were not verified.
- `/proc/bus/input/devices` lists `Megahunt HID Keyboard`, vendor `0461`, product `4d82`, with handler `event3`. This is a candidate scanner, not a confirmed identity. The ordinary HP keyboard is listed separately.
- This agent environment could not access `/dev/input/event3` or enumerate `/dev/input/by-id` and `/dev/serial/by-id`. No live scanner capture or device grab was performed.

## Suggested integration, not yet implemented

Historical: the settled design dated 2026-10-14 supersedes this section wherever they conflict.

Use a device-specific scanner reader that runs independently of GUI focus. If supported by the scanner, USB serial mode is an option; otherwise Linux evdev can read its keyboard events. For HID mode, exclusively grab only the confirmed scanner device while capture is active so decoded text does not also enter other applications. Decode key events correctly, including shift state and configured keyboard layout, and frame complete scans using the configured terminator. Avoid blocking the robot control loop while waiting for input.

A supervisor should own each item cycle, select the Policy A model from a known medium selection, arm a scan window, validate the complete token against the configured mapping, and associate the accepted scan with the active cycle. Reject unknown or conflicting tokens. Deduplicate repeated scans within a cycle, but allow the same destination on successive items. A destination barcode alone cannot prove unique item identity.

With staging retained, start Policy B only after both a valid destination and a successful staging/retraction handoff. Convert bin 0 to `[1, 0]` and bin 1 to `[0, 1]`, freeze that signal for the episode, and reset model action buffers and episode state at policy transitions. Stop or use an explicitly designed recovery path on scan timeout or failed handoff; do not choose a default bin.

Store paired A/B episode IDs, medium, raw barcode, destination index, scan timing, mapping version, and per-stage outcomes in dataset metadata. Supply destination conditioning consistently during Policy B training and inference. Balance each medium across destinations, vary item poses, and test destination use with controlled destination swaps to detect visual shortcuts.

Open issues include scanner identity/mode/terminator, input permissions and stable device selection, presentation geometry and scan dwell, stage completion detection, medium selection, staging consistency, stale scans from nearby labels, reconnect handling, recovery behaviour, and access to editable training/inference sources.


## Implementation update: scanner and recording support

Historical: the settled design dated 2026-10-14 supersedes this section wherever they conflict.

On 2026-10-10, `barcode_scanning/scanner_reader.py` and `recording.py` were implemented. Scanner capture uses a dedicated Linux HID input device with exclusive access, exact destination lookup, monotonic scan windows, partial-frame rejection, and single accepted destination per cycle. Live device identity/access remains to be confirmed on the host.

`run_control.py` now accepts `--policy-stage A/B`, medium, scan-window settings, and an explicit source A episode / demonstrated bin for B. A scans are saved in atomic episode metadata; B inherits the source destination and cycle. The first B-button release now starts recording, and timestamp folders include microseconds. Conversion retains provenance and writes B's `/observations/destination`. Policy loaders/models and autonomous A/B supervision still need implementation. See the [recording guide](guides/recording_guide.md) for current commands and teleoperation steps, and the [barcode scanning guide](guides/barcode_scanning_guide.md) for scanner setup and scan-paired episodes. Earlier findings above describe the pre-integration state.


## Revised collection direction: scanner-independent demonstrations

Historical: the settled design dated 2026-10-14 supersedes this section wherever they conflict.

The user clarified that demonstrations can focus on manipulation without running scanner capture. The reader now captures continuously by default until Ctrl+C; `--once --window N` retains a bounded test. Rejected raw tokens and reasons are shown, `--debug` prints key decoding, case normalization defaults on, and keypad digits are supported.

A/B recording now defaults to scanner capture disabled. A records acquisition, presentation, staging and retraction without requiring a barcode. B requires a configured `--demonstrated-bin`, stored explicitly as a manual destination; optional `--source-episode` maintains pairing with unscanned A. An A scan can still be collected with `--capture-barcode`, and scanner-paired B must agree with that scan. Conversion accepts unscanned A and manually labelled B, preserving B's constant destination observation. No scan is fabricated for manually labelled episodes.

The scanner is needed for automatic destination resolution during inference, but model conditioning support and autonomous supervision remain pending. Standalone capture does not itself send events to the recorder or policy. Keep only one scanner owner. Find-port and calibration tools are one-time setup tasks; stop just-button-A and camera preview helpers before the recorder to avoid shared-device conflicts.
