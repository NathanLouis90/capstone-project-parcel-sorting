# Recording reference

How the recorder, leader controls and episode layout behave. For the steps, see [record episodes](../procedures/07_record_episodes.md).

## What an episode contains

An episode is a synchronized sequence of three camera images, robot observations, and demonstrated control targets for both arms. It covers picking up one parcel and carrying it to the scan pose. Release and return-home motion are outside the episode. Starting the recorder opens teleoperation; green starts and stops individual episodes within that process.

Each episode is a folder `datasets/<project>/collect_data/<episode_id>/` containing `topImg/`, `leftImg/`, `rightImg/`, `observation/` and `episode_metadata.json`. The folder name is a timestamp. The metadata uses schema 3 and records medium, label face, episode and cycle IDs, start and end times, frame count, completion, control overruns, the control period, and review status. See [episode files](datasets.md#episode-files).

The recorder does not open the barcode scanner or store decoded barcodes. A scan observed during teleoperation is not a training label or a policy input. The recorded images and arm targets teach only the carry motion; the runtime supervisor opens its own scanner window after handoff (see [runtime](runtime.md)).

## Dataset names and label faces

The default project is `<medium>_<label_face>`. For example, `--medium poly_mailer --label-face bottom` writes to `poly_mailer_bottom`. Defaults:

- `envelope_top`, `envelope_bottom`
- `poly_mailer_top`, `poly_mailer_bottom`
- `carton_top`, `carton_bottom`, `carton_front`, `carton_rear`

`--project-name` overrides the default. The training menu finds any project folder automatically; `tools/curate_datasets.py` accepts only names listed in `DATASETS["projects"]` in `config/settings.py`.

The label face describes where the label starts in receiving. It is metadata, not a policy observation. Projects registered with a face require matching metadata during curation. Changing face means restarting the recorder with the new `--label-face`, which repeats startup homing.

## Leader controls

| Control | Effect |
| --- | --- |
| Yellow, short press (under 0.5 s) | Toggle the leader lock. Unlocked, the leader can be moved by hand. |
| Yellow, long press (over 1 s, about 2 s in practice) and release | Toggle follower synchronization for that arm. Enabling it first aligns the follower to the leader ("dynamic approach"). |
| Green press and release | Start an episode; the next press stops it. |

Unlocking the leader and enabling synchronization are separate controls. The thresholds are `short_press_s` and `long_press_s` in `RUN_CONTROL` in `config/settings.py`. The status light (robot digital outputs) shows green while recording, yellow while following without recording, and red after a safety stop.

`robot/launch_nodes.py` provides the shared follower and gripper server; its startup cycles both grippers. `recording/run_control.py` connects the leaders, the cameras and that server, and homes both followers at startup. `--medium` records provenance; it does not stop either arm from being used.

While following, the recorder checks each commanded pose against the workspace ranges in `RUN_CONTROL` (`x_range_left`, `x_range_right`, `y_range`, `z_range_left`, `z_range_right`) and the J3 joint limits. A violation turns the light red and stops the recorder. Each loop that exceeds the 40 ms control period prints a warning and increments `control_overruns` in the episode metadata.

## Arm roles and saved actions

| Medium | Arms used in the demonstration | Holding arm at the scan pose |
| --- | --- | --- |
| Envelope | Both: the left slides the envelope to an edge, the right grasps; the left returns home before the scan hold | Right |
| Poly mailer | Right only; the left follower stays home | Right |
| Carton | Left only; the right follower stays home | Left |

These roles match `MEDIA` in `config/settings.py` (`holding_arm`, `active_arms`). At runtime an inactive arm is held at home, and loading refuses a checkpoint whose training data contradicts `active_arms`: an active arm that never moved, or a parked arm that did. Poly-mailer recordings must therefore keep the left arm still. See [runtime](runtime.md).

At least one follower must be synchronized for frames to be saved. With both disabled, an active episode stays open but receives no new frames.

The recorder saves both leaders' targets as actions, including the leader of an unsynchronized follower. If that leader differs from the stationary follower, the saved action does not describe the motion actually executed. Keep the unused leader locked and aligned with its follower at home; keeping the follower home alone is not enough.

## Scan poses and label schedules

Both arms use the same physical scanner, but `scan_left` and `scan_right` are different six-joint postures. Cartons end at `scan_left`; envelopes and poly mailers share `scan_right`. A waypoint defines the arm posture, not the jaw opening. A consistent endpoint gives the policy a repeatable target and lets the supervisor detect the end of pick-and-carry. Waypoints are described in [hardware](hardware.md).

| Medium | Label schedule (50 accepted per medium) | Carry | Runtime backup scan |
| --- | --- | --- | --- |
| Envelope | Alternate 25 top and 25 bottom | Top labels: one demonstrated 180° right J6 roll after lifting, same direction every time. Bottom labels: no roll. | One 180° J6 roll |
| Poly mailer | Alternate 25 top and 25 bottom | Right-arm corner grasp, clear of label and contents | One 180° J6 roll |
| Carton | Cycle top, bottom, front, rear; 12–13 per face | Presented as grasped, no demonstrated roll | Up to three 90° J6 rolls |

Spread demonstrations across receiving positions and yaw. Carton front and rear are the long 150 × 45 mm faces. Poly-mailer bubble-wrap filling stays fixed so grasps stay comparable.

## Gripper width and handoff

Normalized gripper commands follow the recordings: `open_gripper_command` (1.0) opens the jaws, as at the start of every demonstration and at home; `closed_gripper_command` (0.0) closes them on a held parcel. Wrist-camera frames confirm this convention.

A securely held parcel can need a partial jaw opening, and waypoints store no gripper value. `handoff_pose_ok()` in `parcel_sorting/safety/handoff.py` requires the holding arm's command within `gripper_tolerance` (0.08) of closed and the idle arm's within the same tolerance of open. A valid partial grasp whose command stays above 0.08 can therefore fail the handoff and time out; the review end check uses the same test and warns. Do not squeeze a carton harder to satisfy it; the limitation is in the handoff logic.

The driver reports constant gripper values, so recording substitutes the leader command values. None of these values proves jaw width, contact force or grasp success.

## Recorder options

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Required: `envelope`, `poly_mailer` or `carton`. Recorded as metadata. |
| `--label-face bottom` | Required starting label face: `top`/`bottom` for flat media, plus `front`/`rear` for cartons. Sets the default project suffix. |
| `--show-img` | Show the three camera views to check the scene and label placement. |
| `--project-name NAME` | Use another project name instead of `<medium>_<label_face>`. |
| `--save-data-path PATH` | Parent folder for projects; default `datasets/`. `<project>/collect_data/` is added beneath it. |
| `--hostname 127.0.0.1` | Host running `robot/launch_nodes.py`, not a follower controller's IP. |
| `--robot-port 6001` | Server port; must match the server. |
| `--dry-run` | Write one metadata-only episode without hardware, then exit. |

Defaults live in `LAUNCH_NODES` and `RUN_CONTROL` in `config/settings.py`; command-line options override them.

## Metadata-only dry runs

`--dry-run` opens no hardware, waits for no buttons and writes no image or observation frames. It creates `<save-data-path>/<project>/collect_data/dry_<timestamp>/episode_metadata.json` with a frame count of 1 and prints `Metadata-only dry run; not a training episode`. The episode counter may call it complete because it reads metadata only; review acceptance and training refuse it because the frame files are missing. Point `--save-data-path` at a scratch folder so it never mixes with real recordings.
