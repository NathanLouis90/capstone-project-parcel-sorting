# Hardware and media

| Item | Dimensions | Candidate label faces |
| --- | --- | --- |
| Poly mailer, fixed bubble-wrap filling | 130 × 190 mm | Top, bottom |
| Carton, exterior | 150 × 75 × 45 mm | Top, bottom, front, rear |
| DL envelope | 110 × 220 mm | Top, bottom |
| USB HID presentation scanner | See the purchased scanner listing | Not applicable |
| Label stock | 100 × 150 mm | Cut an 80 × 40 mm layout for cartons |

Carton front and rear are the long 150 × 45 mm faces, not the 75 × 45 mm ends.
An end-on grasp aligns the wrist roll with the long axis, exposing the four
candidate faces in 90° steps. Keep approximately 25 mm at each end clear for
the fingertips. Apply the label centrally on its assigned face.

Mailer and envelope labels use the full stock. Barcode dimensions remain
0.25 mm per module and 20 mm bar height, approximately 52 mm wide for the
configured destination tokens. Print PDFs at actual size without scaling.

Run `python3 barcode_scanning/make_labels.py --size 100x150` or
`python3 barcode_scanning/make_labels.py --size carton`. Example PDFs are in
`barcode_scanning/label_examples/`. Purchase links remain the embedded links
in the supplied reimplementation specification; verify the physical items
before updating dimensions.

Move receiving beneath the top camera and remove the intermediate platform.
Teach scan, bin, and receiving-return joint waypoints for each holding arm.
Check stationary reads at every candidate face and cable slack throughout the
carton's 270° sweep before enabling a live cycle.
