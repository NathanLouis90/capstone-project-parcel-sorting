# Recording: meaning and behavior

Use the [recording procedure](protocol.md) for terminal startup, buttons, episode
capture, and shutdown. Use [recording by medium](media.md) for grasp and face
schedules. This README explains those procedures and their limits.

## What an episode contains

An episode is a synchronized sequence of three camera images, robot observations,
and demonstrated control targets for both arms. It covers picking one parcel and
carrying it to the scanner. Release and return-home motion are outside the
training episode. Starting the recorder opens teleoperation; green starts and
stops individual episodes within that process.

The raw folder is `datasets/<project>/collect_data/<episode_id>/`. It contains
`topImg/`, `leftImg/`, `rightImg/`, `observation/`, and
`episode_metadata.json`. The metadata uses schema 3 and records medium, label
face, episode/cycle IDs, timing, frame count, completion, control overruns, and
review status. Observation pickles are trusted local data, not safe inputs from
unknown sources.

The recorder does not open the barcode scanner or store decoded scanner results.
A scanner read observed during teleoperation does not become a training label or
a policy input. Recorded images and arm targets teach the carry motion. The
runtime supervisor starts its own scanner window after handoff.

## Dataset names and face metadata

The default project is `<medium>_<label_face>`. For example,
`--medium poly_mailer --label-face bottom` selects `poly_mailer_bottom`. The
registered default projects are:

- `envelope_top` and `envelope_bottom`;
- `poly_mailer_top` and `poly_mailer_bottom`;
- `carton_top`, `carton_bottom`, `carton_front`, and `carton_rear`.

`--project-name` overrides that default. Custom project settings belong in
`PREPARE_ACT_DATASETS["projects"]` in `scripts/scripts_config.py` before
preparation or vendor training. Existing medium-only collections remain usable;
changing the default name does not move or rename recordings.

The face describes where the label starts in receiving. It is metadata, not a
policy observation. Face-specific projects require matching metadata during
preparation and curation. A change of face requires restarting the recorder with
the new argument, which also repeats startup homing.

## Leader controls

A short yellow press under 0.5 seconds toggles the leader lock. Holding yellow
for about two seconds and releasing toggles follower synchronization. The
configured long-press threshold is greater than one second. A green press/release
starts recording; the next stops it. Unlocking the leader permits hand motion;
enabling synchronization makes its follower track that motion. They are separate
controls.

`launch_nodes.py` provides the shared follower/gripper server. Startup cycles
grippers. `run_control.py` connects leaders, cameras, and that server, and homes
both followers at startup. `--medium` supplies provenance; it does not prevent
either arm from being used during teleoperation.

## Synchronization and saved actions

One follower can remain unsynchronized while the other works. At least one
follower must be enabled for frame saving. With both disabled, an active episode
can remain open but receives no new frames.

The current recorder still saves both leaders' action targets, including targets
for an unsynchronized follower. If that leader differs from the stationary
follower, the training action does not describe the motion actually executed.
Keeping the unused follower home alone does not resolve this mismatch; the
inactive leader must also remain locked and aligned. Recording a follower-based
hold target for disabled arms would require a code change and is not implemented
by these documentation changes.

Envelope pickup uses both arms: the left slides/assists, the right grasps and
carries, and the left returns home before the final scan hold. For mailers and
cartons, the right follower remains home. The current automatic holding-arm
assignment is explained in the [runtime README](../runtime/README.md#holding-arm-selection).

## Scan poses and label schedules

Both arms use the same physical scanner, but `scan_left` and `scan_right` contain
different six-joint configurations. `scan_left` is shared by mailers and cartons;
`scan_right` is used for envelopes. A waypoint defines the arm posture, not the
jaw opening. A consistent endpoint gives the learned policy a repeatable target
and lets the supervisor recognize the end of pick-and-carry.

| Medium | Holding arm | Label schedule | Runtime backup scan |
| --- | --- | --- | --- |
| Envelope | Right; left assists the initial slide | Alternate 25 top and 25 bottom | One 180° J6 roll |
| Poly mailer | Left | Alternate 25 top and 25 bottom | One 180° J6 roll |
| Carton | Left | Cycle top, bottom, front, rear; 12–13 per face | Up to three 90° J6 rolls |

The target collection has 50 accepted demonstrations per medium, distributed
across receiving positions and yaw. Flat-media top labels use a demonstrated
180° carry flip to arrive label-down; bottom labels do not need that carry flip.
The roll direction stays consistent. Cartons arrive as grasped; the supervisor
performs the candidate-face sweep. Carton front/rear are the long 150 × 45 mm
faces. Mailer bubble-wrap filling stays fixed to keep grasp behavior comparable.

## Gripper width and handoff

A securely held parcel can require a partial jaw opening. Cartons and mailers do
not need identical physical widths, and waypoint capture saves no gripper value.

There is a separate implementation limit: `handoff_pose_ok()` currently requires
both normalized gripper commands within `gripper_tolerance` (default 0.08) of
`closed_gripper_command` (1.0). A valid partial-width grasp can therefore fail
handoff and time out. Dataset end checks use the same criterion and can warn.

The driver reports constant gripper values; recording substitutes leader command
values, and the motion loop tracks sent commands. None of those values proves
actual jaw width, contact force, or grasp success. The appropriate change for
partial grasps belongs in the handoff logic; it is not a reason to squeeze a
carton further. These docs do not change that logic.

## Recorder options

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Required parcel type: `envelope`, `poly_mailer`, or `carton`. Records metadata; it does not limit teleoperation to one arm. |
| `--label-face bottom` | Required starting label face. Use `top`/`bottom` for flat media, or `top`/`bottom`/`front`/`rear` for cartons. This sets the default project's suffix and records metadata; it is not a policy input. |
| `--show-img` | Open camera previews so you can check the scene and label placement. |
| `--project-name poly_mailer_session2` | Optional collection name overriding the default `<medium>_<label_face>`, such as `poly_mailer_bottom`. Register custom names in `scripts/scripts_config.py` before preparation. |
| `--save-data-path datasets` | Optional parent directory for projects; defaults to the repository's `datasets/`. The project and `collect_data/` folders are added beneath it. |
| `--hostname 127.0.0.1` | Optional server host. This is the PC running `launch_nodes.py`, not a follower's controller IP. |
| `--robot-port 6001` | Optional server port; it must match Terminal 1's configuration. |

`LAUNCH_NODES` and `RUN_CONTROL` in `experiments/experiments_config.py` contain
server and recorder defaults. CLI options override them. A custom server host is
the PC running the server, not the IP address of an individual follower controller.

## Metadata-only dry runs

`--dry-run` bypasses hardware and writes one metadata-only example, then exits.
It does not wait for buttons or create usable image/observation frames. With
`--save-data-path /tmp/parcel-recording-check`, the default mailer-bottom path is
`/tmp/parcel-recording-check/poly_mailer_bottom/collect_data/dry_<timestamp>/`.
The dry run sets a metadata frame count of 1 despite creating no actual frame
files. The metadata-based counter can therefore call it complete; preparation
refuses it because the image and observation files are missing.

Continue with [dataset concepts](../datasets/README.md) for completion, review,
image playback, and conversion.
