# Record pick-to-scan demonstrations

Read [recording concepts and command options](README.md) when you need an
explanation. Use [medium-specific steps](media.md) for each grasp and label face.

## 1. Prepare the workspace

1. Complete the repository [hardware setup](../../../README.md#software-setup).
2. Prepare [each terminal](../../terminal_commands.md).
3. Place receiving beneath the top camera. For mailers, install the elevated
   flip platform at a fixed, measured pose and check both arms' clearance. Keep
   the platform out of envelope and carton paths when it is not used.
4. Teach the [scan waypoints](../hardware/waypoints.md#use-three-terminals).
5. Verify stationary scanner reads, tool clearance, and wrist cable slack through
   the full scan sweep. Stop standalone scanner capture before recording.
6. Stop calibration helpers. Start with no parcel held, both follower paths clear,
   and immediate emergency-stop access. Server startup cycles the grippers;
   recorder startup homes both followers.

## 2. Start the server in Terminal 1

```bash
python3 experiments/launch_nodes.py
```

Leave this process running throughout the recording session.

## 3. Start the recorder in Terminal 2

For bottom-face mailers, run:

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom --show-img
```

Wait for `Ok, let's start`. Check all three camera views. Expect recordings under
`datasets/poly_mailer_bottom/collect_data/`. Use the corresponding command in
[recording by medium](media.md) for another parcel type or face.

## 4. Enable following

1. Keep the leaders near their followers' starting postures.
2. Hold the relevant yellow button for about two seconds, then release it.
3. Wait for alignment to finish.
4. Support the leader and short-press yellow for under 0.5 seconds to unlock it.
5. Enable both arms when demonstrating the envelope slide or the mailer
   platform flip followed by right-arm pickup.
6. Keep an unused follower home. If its following is disabled, keep its leader
   locked and aligned with that follower; see the [recording limitation](README.md#synchronization-and-saved-actions).

Keep at least one arm following while recording. Do not reposition parcels by
hand while following remains enabled.

## 5. Record each demonstration

1. Prepare one parcel with its label centred on the assigned face, clear of the
   fingertips. Keep mailer filling fixed.
2. Start with both followers home and grippers closed without a parcel.
3. Press and release green to start the episode.
4. Start moving within about 0.5 seconds.
5. Follow the [grasp and carry steps](media.md) for the selected medium.
6. Finish at the taught scan pose, holding the parcel securely at its required
   grasp width. Return the assisting or unused arm home.
7. Hold still for about one second, then press and release green again to stop.
8. Release the parcel and return home outside the recording.
9. Disable following before resetting the next parcel by hand.

Collect 50 fresh accepted demonstrations per medium across varied receiving
positions and yaw. Follow the face schedule in [recording by medium](media.md).
Do not squeeze a carton further to satisfy a software gripper check; review the
[current handoff limitation](README.md#gripper-width-and-handoff).

## 6. Change the label face or finish

1. Stop the active episode with green.
2. Release any held parcel safely under teleoperation and return both arms home.
3. Lock the leaders and disable following on both arms.
4. Stop Terminal 2 with Ctrl+C.
5. To change faces, restart the recorder with the correct `--label-face` after
   clearing both paths. Keep Terminal 1 running between recording sessions.
6. Follow [review and preparation](../datasets/preparation.md) before training.

Never load untrusted observation pickles.

## Check metadata without hardware

Run this as a separate check; no server or leader arms are needed:

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom \
  --dry-run --save-data-path /tmp/parcel-recording-check
```

Check the printed path under
`/tmp/parcel-recording-check/poly_mailer_bottom/collect_data/dry_<timestamp>/`.
Do not use this metadata-only output as training data.
