# Scanner and labels

The scanner is a dedicated USB HID device. Check its identity before using
exclusive capture; never substitute the normal keyboard. Configure a US keyboard
layout and continuous/presentation scanning if the device supports it.

```bash
python3 barcode_scanning/scanner_reader.py --help
python3 barcode_scanning/scanner_reader.py --simulate DEST-A-S138683
python3 barcode_scanning/make_labels.py --size 100x150
python3 barcode_scanning/make_labels.py --size carton
```

Destination mapping remains `DEST-A-S138683` to bin 0 (Dover) and
`DEST-B-S828608` to bin 1 (Punggol). These tokens name destinations. Print at
actual size. See [hardware](../hardware.md) for face definitions and dimensions.

Only the cycle supervisor owns the scanner during runtime. Recording does not
open it. Each scan window is armed for a fresh cycle after handoff; stale,
unknown, partial and unmapped input cannot choose a bin. Stop at the first
accepted read. Scanner/device failures are faults; an exhausted valid sweep
without a token is a no-read and follows the taught receiving-return path.

Before live operation, confirm each face reads while held still at the scan
pose. Check all four carton faces with paused 90° wrist steps and sufficient
cable slack. A failed read never changes a policy observation.
