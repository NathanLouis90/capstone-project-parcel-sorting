# Check the scanner and print labels

Prepare [one terminal](../../terminal_commands.md) with `Xtrainer` activated.
These standalone checks need no robot server. Read the
[hardware README](README.md#scanner-and-destination-mapping) for token mapping,
scanner behavior, and command options.

## Test the barcode mapping without a scanner

```bash
python3 barcode_scanning/scanner_reader.py --simulate DEST-A-S138683
```

Check that a mapped bin-0 result prints and the command exits with status 0.
Use `DEST-B-S828608` to check bin 1. An unknown token should produce no destination
and exit status 2. Test the physical scanner separately below.

## Check the physical scanner

1. List connected input devices:

```bash
python3 barcode_scanning/scanner_reader.py --list-devices
```

2. Identify the dedicated scanner. Check its name/vendor/product in
   `SCANNER_READER` in `barcode_scanning/barcode_scanning_config.py`.
   **Never select the normal keyboard for exclusive capture.**
3. Configure a US keyboard layout and continuous/presentation scanning if the
   device supports it.
4. Stop other scanner readers, then run:

```bash
python3 barcode_scanning/scanner_reader.py --once --window 10
```

5. Present a mapped label within the 10-second window. Check the decoded token
   and destination. If needed, use `--device /dev/input/eventN` with the actual
   scanner path; keep its configured identity checks intact.
6. Add `--debug` when investigating key-event decoding. Use `--continuous` for
   repeated reads and Ctrl+C to stop that reader.
7. Verify each face reads while the parcel is held still at its taught scan pose.
   For cartons, check all four faces with paused 90° wrist steps and adequate
   cable slack.
8. Stop this standalone reader before starting the cycle supervisor.

## Generate printable labels

Generate the full and compact layouts:

```bash
python3 barcode_scanning/make_labels.py --size 100x150
python3 barcode_scanning/make_labels.py --size carton
```

To use a separate output folder and add a combined sheet, run:

```bash
python3 barcode_scanning/make_labels.py --size carton \
  --outdir /tmp/carton-labels --combined
```

1. Inspect the PDFs and barcode PNGs in the selected folder. Expect
   `label_carton_DEST-A-S138683.pdf`, `label_carton_DEST-B-S828608.pdf`, and
   `labels_carton_combined.pdf` for the combined carton example.
2. Choose a different folder if you need to retain earlier generated files;
   rerunning the same size in the same folder replaces them.
3. Add `--no-crop-marks` only if you do not need cutting guides.
4. Print at actual size without scaling. Use stock large enough for the PDF,
   especially for combined sheets.
5. Fit labels using the [parcel preparation steps](media.md).
