# Prepare the workspace and parcels

At the end the board, bins, scanner and receiving area sit at their measured positions and every parcel carries a correctly placed label.

## Before you start

- Complete [hardware setup](02_hardware_setup.md) and [labels and scanner](03_labels_and_scanner.md).
- Both followers at their home pose (see [home and recover](home_and_recover.md) if they are not).
- Robot server and recorder stopped while you work inside the arm reach.
- A tape measure; all positions below are in millimetres, tolerance ±10 mm.

## Steps

1. Mark the layout origin on the bench: X/Y halfway between the two arm bases (robot at home), Z = 0 on the EVA board surface.

   Expect: X and Y axes drawn or noted. See [workspace layout](../reference/hardware.md#workspace-layout-and-coordinate-frame).

2. Place the 700 × 700 mm EVA board centred at X 0, Y 50, then place each item by its centre:

   | Item | X | Y |
   | --- | ---: | ---: |
   | Bin 0 | -190 | -270 |
   | Bin 1 | 190 | -270 |
   | Barcode scanner | -30 | 80 |
   | Receiving area | -30 | 150 |

   Expect: every centre within ±10 mm.

3. Point the top camera at the receiving area and check it with the preview; stop the preview with `Ctrl+C`.

   ```bash
   python3 setup/4_check_cameras.py
   ```

   Expect: the receiving area is fully visible in the first (top) image.

4. For poly mailers only, fix the elevated flip platform at a measured position and height where all cameras see it. Write down its position and height.

   Expect: it does not move when pressed; it is clear of envelope and carton paths.

5. Prepare the parcels: 130 × 190 mm poly mailers with fixed bubble-wrap filling, 110 × 220 mm DL envelopes, and 150 × 75 × 45 mm cartons.

   Expect: measured sizes match. If not, see [parcel dimensions](../reference/hardware.md#parcel-dimensions-and-label-faces) before changing `MEDIA` in `config/settings.py`.

6. Apply one 100 × 150 mm label to each parcel, with the barcode at roughly the centre of the chosen face: top or bottom for envelopes and poly mailers; top, bottom, front or rear for cartons.

   Expect: label flat, barcode fully visible and clear of the gripper fingertips.

7. Place one parcel at a time in the receiving area.

   Expect: only one parcel in the receiving zone.

After teaching waypoints, check stationary scans on every label face, and wrist cable slack, grip and clearance through the full 270° carton sweep ([check waypoints](06_check_waypoints.md)).
Continue with [teach waypoints](05_teach_waypoints.md).

## If something goes wrong

- An item cannot sit at its centre within ±10 mm -> record the actual position; taught waypoints follow the real fixtures, not the table.
- Top camera cannot see the whole receiving area -> move the camera, not the receiving area.
- Platform in an arm's path -> move it, measure again, and keep it fixed for all recordings and cycles.
- Label wrinkles on a mailer -> use the fixed filling and smooth the surface before applying.
