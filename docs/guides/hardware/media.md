# Prepare hardware and parcel media

Read the [hardware README](README.md#parcel-dimensions-and-label-faces) for
specifications, face definitions, purchase references, and scan geometry.

## 1. Prepare the workspace

1. Complete the repository [device and environment setup](../../../README.md#software-setup).
2. Mark the shared layout X/Y origin between the arm bases with the robot home,
   and use the EVA board surface as Z = 0.
3. Place the 700 × 700 mm board and fixtures at the centres in the
   [workspace layout table](README.md#workspace-layout-and-coordinate-frame).
   Check placement against the ±10 mm tolerance.
4. Position the top camera over receiving. For mailer demonstrations, install
   the elevated flip platform at a fixed, measured position and height, visible
   to the cameras. Verify both arms' platform clearance; keep the platform clear
   of envelope and carton paths when it is not used.
5. Keep one parcel in the receiving zone at a time.
6. Prepare 130 × 190 mm mailers with fixed bubble-wrap filling, 110 × 220 mm DL
   envelopes, and 150 × 75 × 45 mm cartons. Verify the actual items before
   changing configured dimensions.

## 2. Generate and fit labels

Prepare [one terminal](../../terminal_commands.md) with `Xtrainer` activated.
Generate the two layouts:

```bash
python3 barcode_scanning/make_labels.py --size 100x150
python3 barcode_scanning/make_labels.py --size carton
```

1. Find the PDFs under `barcode_scanning/labels/`.
2. Print at actual size without scaling, on stock large enough for the PDF.
3. Use the full layout for mailers/envelopes and cut the 80 × 40 mm carton layout.
4. Apply each label centrally on its assigned face, clear of the fingertips.
5. For cartons, use the long 150 × 45 mm sides as front and rear, and leave
   approximately 25 mm at each end clear for grasping.
6. Follow [scanner and label checks](barcodes.md#generate-printable-labels) for
   custom output folders, combined sheets, crop marks, and physical reads.

## 3. Check scan and drop geometry

1. Teach [scan, bin, and receiving-return waypoints](waypoints.md) for both arms.
2. Check stationary reads on every candidate face.
3. Check wrist cable slack, grasp retention, and tool/parcel clearance through
   the carton's complete 270° sweep before enabling a live cycle.
4. Continue with [recording by medium](../recording/media.md).
