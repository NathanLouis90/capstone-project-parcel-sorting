# Hardware and media

| Item | Dimensions | Candidate label faces | Purchase reference |
| --- | --- | --- | --- |
| Poly mailer, fixed bubble-wrap filling | 130 × 190 mm | Top, bottom | [Shopee](https://sg.shp.ee/KEAi1vGk) |
| Carton, exterior | 150 × 75 × 45 mm | Top, bottom, front, rear | [Lazada](https://s.lazada.sg/s.6ELRP?c=d&t=p-i1DjcEO-s2CK0KWD) |
| DL envelope | 110 × 220 mm | Top, bottom | [Lazada](https://s.lazada.sg/s.6ELkQ?c=d&t=p-i3XhIlx-sNuvvNZ) |
| USB HID presentation scanner | See the purchased scanner listing | Not applicable | [Shopee](https://sg.shp.ee/M8FZszsv) |
| Label stock | 100 × 150 mm | Cut an 80 × 40 mm layout for cartons | Not specified |

Carton front and rear are the long 150 × 45 mm faces, not the 75 × 45 mm ends.
An end-on grasp aligns the wrist roll with the long axis, exposing the four
candidate faces in 90° steps. Keep approximately 25 mm at each end clear for
the fingertips. Apply the label centrally on its assigned face.

Mailer and envelope labels use the full stock. Barcode dimensions remain
0.25 mm per module and 20 mm bar height, approximately 52 mm wide for the
configured destination tokens. Print PDFs at actual size without scaling.

From the repository root with `Xtrainer` activated, generate the two layouts:

```bash
python3 barcode_scanning/make_labels.py --size 100x150
python3 barcode_scanning/make_labels.py --size carton
```

`--size 100x150` selects the full 100 × 150 mm envelope/mailer layout.
`--size carton` selects the compact 80 × 40 mm carton layout. Both commands
write PDFs for both destinations under `barcode_scanning/labels/`; they need no
hardware. See [scanner and labels](barcodes.md#generate-printable-labels) for
output-folder, combined-sheet, and crop-mark options. Example PDFs are in
`barcode_scanning/label_examples/`. Purchase references come from the supplied reimplementation specification.
Verify the physical items before updating dimensions.

Move receiving beneath the top camera and remove the intermediate platform.
Teach scan, bin, and receiving-return joint waypoints for each holding arm.
Check stationary reads at every candidate face and cable slack throughout the
carton's 270° sweep before enabling a live cycle.
