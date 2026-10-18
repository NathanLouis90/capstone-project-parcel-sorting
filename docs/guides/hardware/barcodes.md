# Scanner and labels

Run from the repository root with `Xtrainer` activated. These standalone checks
need no robot server. See [terminal setup](../../terminal_commands.md).

The scanner is a dedicated USB HID device. Check its identity before using
exclusive capture; never substitute the normal keyboard. Configure a US keyboard
layout and continuous/presentation scanning if the device supports it.

## Test the barcode mapping without a scanner

```bash
python3 barcode_scanning/scanner_reader.py --simulate DEST-A-S138683
```

`--simulate` feeds the following token as text, without opening an input device.
This example prints a mapped bin-0 result and exits with status 0. An unknown
token produces no destination and exit status 2. This does not verify a physical
label or scanner. `--help` prints all scanner options and exits.

| Token | Destination |
| --- | --- |
| `DEST-A-S138683` | Bin 0, Dover |
| `DEST-B-S828608` | Bin 1, Punggol |

## Check the physical scanner

```bash
python3 barcode_scanning/scanner_reader.py --list-devices
python3 barcode_scanning/scanner_reader.py --once --window 10
```

Run the first command to identify devices, then check the scanner identity in
`SCANNER_READER` in `barcode_scanning/barcode_scanning_config.py` before capture.

| Argument | Meaning |
| --- | --- |
| `--list-devices` | Print input device paths and identities without starting exclusive capture. |
| `--once` | Capture one valid mapped barcode, then exit. |
| `--window 10` | Allow up to 10 seconds for the one-shot read. This value is in seconds. |
| `--device /dev/input/eventN` | Optional: replace `eventN` with the actual scanner path from the listing. Configured name/vendor/product must still match. |
| `--debug` | Optional: print scanner key events and decoded characters while troubleshooting. |
| `--continuous` | Optional: keep reading until stopped with `Ctrl+C`; this is also the default when `--once` is omitted. |

Capture grabs the scanner exclusively. Stop this reader before starting the
cycle supervisor; only one process should own the scanner at a time.

## Generate printable labels

```bash
python3 barcode_scanning/make_labels.py --size 100x150
python3 barcode_scanning/make_labels.py --size carton
```

| Argument | Meaning |
| --- | --- |
| `--size 100x150` | Generate full 100 × 150 mm layouts for envelopes and poly mailers. |
| `--size carton` | Select the preset for compact 80 × 40 mm carton-face layouts. |
| `--outdir barcode_scanning/labels` | Optional output folder; this is the default. Each run writes labels for both destinations. |
| `--combined` | Optional: also create one PDF with both destination labels side by side. |
| `--no-crop-marks` | Optional: omit the cutting guides from the PDFs. |

To choose a separate output folder and include the combined sheet:

```bash
python3 barcode_scanning/make_labels.py --size carton \
  --outdir /tmp/carton-labels --combined
```

This writes the compact labels and combined sheet to `/tmp/carton-labels/`.
Output names include
`label_carton_DEST-A-S138683.pdf`, `label_carton_DEST-B-S828608.pdf`, and, with
`--combined`, `labels_carton_combined.pdf`. Barcode PNGs are also generated.
Rerunning with the same size and output folder replaces those generated files.

Print at actual size without scaling. Use a page or label stock large enough
for the chosen PDF, especially combined sheets. See [hardware](media.md) for
face definitions and dimensions.

Only the cycle supervisor owns the scanner during runtime. Recording does not
open it. Each scan window is armed for a fresh cycle after handoff; stale,
unknown, partial and unmapped input cannot choose a bin. Stop at the first
accepted read. Scanner/device failures are faults; an exhausted valid sweep
without a token is a no-read and follows the taught receiving-return path.

Before live operation, confirm each face reads while held still at the scan
pose. Check all four carton faces with paused 90° wrist steps and sufficient
cable slack. A failed read never changes a policy observation.
