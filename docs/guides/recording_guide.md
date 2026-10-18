# Record pick-to-scan demonstrations

## Before recording

Run from the repository root in Python 3.8 `Xtrainer`. Complete the README's
hardware setup. Position receiving beneath the top camera, remove the
intermediate platform, teach the scan poses, and verify scanner reads while
holding each medium still above it. Check wrist cable slack for the complete sweep.

Start the server in a separate terminal: `python3 experiments/launch_nodes.py`.
The recorder's startup can move both arms and cycle the grippers. Keep both
paths clear and remain within reach of the emergency stop.

## Demonstration protocol

Record 50 fresh accepted demonstrations for each medium. Vary position and yaw
throughout the receiving zone. Keep mailer filling fixed. Place the label near
the centre of its assigned face and clear of the fingertips.

1. Start with both arms home and grippers closed. Scanner capture stays off.
2. Start moving within about 0.5 seconds of starting the recording.
3. Grasp, lift and carry to the holding arm's taught scan pose.
4. Hold still for about one second, then stop recording while still holding.
5. Release and return home outside the recording.

A short yellow button press toggles leader lock. A long press toggles follower
synchronization. A green button press/release starts recording; the next stops it.
Support leaders before unlocking them. Disable synchronization before resetting
parcels by hand. Stop helper programs before starting the recorder.

## Commands and metadata

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face top --show-img
```

`--medium` and `--label-face` are required. The project defaults to the medium.
Use `--project-name NAME` for another collection and register that exact name in
`scripts/scripts_config.py` before preparation. Face choices are `top`/`bottom`
for flat media and `top`/`bottom`/`front`/`rear` for cartons.

Raw episodes live under `datasets/<project>/collect_data/<episode_id>/` with
camera folders, observation pickles and `episode_metadata.json` (schema 3).
Metadata records medium, label face, IDs, timing, completion and review status.
It contains no scanner observations. Never load untrusted observation pickles.

A metadata-only check opens no hardware and creates no usable training frames:

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom \
  --dry-run --save-data-path /tmp/parcel-recording-check
```

Follow [review and preparation](dataset_preparation.md) before training.
