# Record each parcel medium

Complete the [shared recording procedure](protocol.md) first. Keep the server
running in Terminal 1. Run the chosen recorder in Terminal 2. Each startup homes
both followers; clear both paths and start with no parcel held.

For terms, arm assignments, and scan rotations, read the [recording README](README.md).

## Envelopes

```bash
python3 experiments/run_control.py --medium envelope --label-face bottom --show-img
```

1. Alternate top and bottom labels; collect 25 accepted episodes per face.
2. Enable both followers for the slide and grasp.
3. Use the left arm to slide the envelope to an overhanging edge.
4. Pinch the short edge with the right gripper, keeping fingertips within about
   30 mm of the edge. Return the left arm home after its assistance.
5. For a top-facing label, roll right J6 180° immediately after lifting. Use the
   same roll direction in each demonstration. For a bottom-facing label, carry
   without that flip. Arrive with the label facing down.
6. End at `scan_right`, hold still for about one second, and stop recording
   before release or homing.

## Poly mailers

```bash
python3 experiments/run_control.py --medium poly_mailer --label-face bottom --show-img
```

1. Keep bubble-wrap filling fixed. Alternate top and bottom labels; collect 25
   accepted episodes per face.
2. Keep the elevated platform at a fixed, measured position and height, visible
   to the cameras. Check platform clearance along both arms' paths before
   recording. Enable both followers when demonstrating left-arm assistance.
3. For a top-facing label, use the left arm to position and flip the mailer on
   the elevated platform until the label faces down. Include the complete
   positioning and flipping sequence in the recorded episode. For a bottom-facing
   label, skip the flip.
4. Use the right gripper to grasp a corner margin, clear of the label and
   contents. Use a repeatable grasp with enough material to avoid slipping or
   tearing. Carry with the label facing down; do not add another carry flip
   after the platform flip.
5. Release any left-arm contact and return the left follower home. If its
   following is disabled, keep its leader locked and aligned with that home pose.
6. End at `scan_right`, holding the mailer securely with the right arm and the
   left arm home. Hold still for about one second, then stop recording before
   release or homing. Check the right-arm scan and drop paths using this grasp.

The former left-arm `poly_mailer_bottom` collection is archived outside the
active dataset root under `archived_datasets/`. Fresh recordings reuse
`datasets/poly_mailer_bottom/collect_data/`. Do not mix the old left-arm pickup
episodes into the new right-arm workflow or reuse a model trained on them.

## Cartons

```bash
python3 experiments/run_control.py --medium carton --label-face bottom --show-img
```

1. Cycle through top, bottom, front, and rear labels; collect 12–13 accepted
   episodes per face for 50 total. Use the long 150 × 45 mm sides as front/rear.
2. Keep the right follower home with its gripper closed. If its following is
   disabled, keep its leader locked and aligned with it.
3. Approach along the long axis at 20° or less. Pinch within about 25 mm of the end.
4. Hold securely at the required jaw opening; do not force the jaws fully closed.
5. Present the carton as grasped. Do not add a demonstration wrist roll.
6. End at `scan_left`, hold still for about one second, and stop recording
   before release or homing.

## Change faces and check recordings

1. For top-face flat parcels, replace `--label-face bottom` with `--label-face top`.
   For cartons, select `top`, `bottom`, `front`, or `rear` to match the actual label.
2. Stop the episode, release safely, return home, and disable following on both
   arms before restarting the recorder with another face.
3. Clear both paths before restarting; startup homes both followers.
4. Confirm the assigned face in the images when [reviewing each episode](../datasets/preparation.md).
5. Verify stationary scanner reads and wrist cable slack before collecting the
   next set. Use [recorder options](README.md#recorder-options) for custom outputs.
