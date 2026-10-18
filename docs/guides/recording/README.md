# Record pick-to-scan demonstrations

## Before recording

Run from the repository root in Python 3.8 `Xtrainer`. Complete the README's
hardware setup. Position receiving beneath the top camera, remove the
intermediate platform, teach the scan poses, and verify scanner reads while
holding each medium still above it. Check wrist cable slack for the complete sweep.

Use [terminal setup](../../terminal_commands.md) in each terminal. Server startup
cycles the grippers, and recorder startup homes both followers. Keep both paths
clear and remain within reach of the emergency stop.

For initial scan-pose setup, follow the [three-terminal waypoint walkthrough](../hardware/waypoints.md#use-three-terminals).
Use [instructions by medium](media.md) for grasp, flip and label schedules.

## Demonstration protocol

Record 50 fresh accepted demonstrations for each medium. Vary position and yaw
throughout the receiving zone. Keep mailer filling fixed. Place the label near
the centre of its assigned face and clear of the fingertips.

1. Start with both arms home and grippers closed. Scanner capture stays off.
2. Start moving within about 0.5 seconds of starting the recording.
3. Grasp, lift and carry to the holding arm's taught scan pose.
4. Hold still for about one second, then stop recording while still holding.
5. Release and return home outside the recording.

A short yellow button press (under 0.5 seconds) toggles leader lock. Hold yellow
for about two seconds and release to toggle follower synchronization. A green
button press/release starts recording; the next stops it.
Support leaders before unlocking them. Disable synchronization before resetting
parcels by hand. Stop helper programs before starting the recorder.

## Terminal 1: start the robot server

```bash
python3 experiments/launch_nodes.py
```

This command takes no arguments in this example. It starts the shared follower
and gripper server using `LAUNCH_NODES` in `experiments/experiments_config.py`.
Leave it running while recording.

## Terminal 2: start the recorder

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face top --show-img
```

| Argument | Meaning |
| --- | --- |
| `--medium poly_mailer` | Required parcel type: `envelope`, `poly_mailer`, or `carton`. Records metadata; it does not limit teleoperation to one arm. |
| `--label-face top` | Required starting label face. Use `top`/`bottom` for flat media, or `top`/`bottom`/`front`/`rear` for cartons. This is metadata, not a policy input. |
| `--show-img` | Open camera previews so you can check the scene and label placement. |
| `--project-name poly_mailer_session2` | Optional collection name. Without this option, the project name equals the medium. Register custom names in `scripts/scripts_config.py` before preparation. |
| `--save-data-path datasets` | Optional parent directory for projects; defaults to the repository's `datasets/`. The project and `collect_data/` folders are added beneath it. |
| `--hostname 127.0.0.1` | Optional server host. This is the PC running `launch_nodes.py`, not a follower's controller IP. |
| `--robot-port 6001` | Optional server port; it must match Terminal 1's configuration. |

Keep the recorder running while capturing episodes with the green button.
When the assigned label face changes, stop recording, disable following on both
arms, stop the recorder, and restart it with the new `--label-face`. Startup
homes both followers again, so clear both paths before restarting. Do not move
parcels by hand while following remains enabled.

Raw episodes live under `datasets/<project>/collect_data/<episode_id>/` with
camera folders, observation pickles and `episode_metadata.json` (schema 3).
Metadata records medium, label face, IDs, timing, completion and review status.
It contains no scanner observations. Never load untrusted observation pickles.

## Check metadata without hardware

No server or leader arms are needed for this separate check:

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom \
  --dry-run --save-data-path /tmp/parcel-recording-check
```

`--medium` and `--label-face` have the meanings above. `--dry-run` bypasses all
hardware initialization and writes a metadata-only example, with no usable
training frames. `--save-data-path /tmp/parcel-recording-check` redirects that
output away from real datasets. With the default project name, the episode is
under `/tmp/parcel-recording-check/poly_mailer/collect_data/dry_<timestamp>/`.
The program prints the created path and exits; it does not wait for buttons.

Follow [review and preparation](../datasets/preparation.md) before training.
