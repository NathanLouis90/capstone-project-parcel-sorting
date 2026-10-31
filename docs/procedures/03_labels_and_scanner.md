# Print the destination labels and check the scanner

At the end you have printed labels for both destinations and a scanner that reads them as bin 0 and bin 1.

## Before you start

- Complete [software installation](01_install.md). No robot server is needed.
- Connect the dedicated USB barcode scanner.
- Stop any other scanner reader and any running cycle (`evaluation/run_cycle.py`); only one program may own the scanner.
- Prepare one terminal (see [install](01_install.md#every-new-terminal)).

## Steps

1. Generate the full-size labels for envelopes and poly mailers.

   ```bash
   python3 setup/make_labels.py --size 100x150
   ```

   Expect: `wrote .../output/labels/label_100x150_DEST-A-S138683.pdf  (payload 'DEST-A-S138683' -> bin 0)`, the same for `DEST-B-S828608` -> bin 1, and the supervisor mapping.

2. Generate the carton labels.

   ```bash
   python3 setup/make_labels.py --size carton
   ```

   Expect: `label_carton_DEST-A-S138683.pdf` and `label_carton_DEST-B-S828608.pdf` in `output/labels/`.

3. Print the PDFs from `output/labels/` at actual size (no scaling, no "fit to page").

   Expect: each barcode is about 52 mm wide. Compare with the samples in [label_examples](../label_examples/).

4. Check the token-to-bin mapping without the scanner.

   ```bash
   python3 setup/check_scanner.py --simulate DEST-A-S138683
   python3 setup/check_scanner.py --simulate DEST-B-S828608
   ```

   Expect: `"reason": "accepted"` with `"bin_index": 0`, then `"bin_index": 1`.

5. List the input devices and find the scanner.

   ```bash
   python3 setup/check_scanner.py --list-devices
   ```

   Expect: one JSON line per device. The scanner's name, vendor and product match `SCANNER_READER` in `config/settings.py`. **Never use the normal keyboard as the scanner.**

6. Set the scanner to a US keyboard layout and presentation (continuous) mode, using its manual, if it supports this.

   Expect: scanning a label into a text editor types `DEST-A-S138683` followed by Enter.

7. Read one label through the program.

   ```bash
   python3 setup/check_scanner.py --once --window 10
   ```

   Expect: `Capturing scanner exclusively: ...`, `Scan window open for 10 seconds`; present a label and see `"barcode": "DEST-A-S138683", "bin_index": 0` (or bin 1 for `DEST-B-S828608`). Exit status 0.

8. Read both labels on every face you will use, holding each still under the scanner.

   ```bash
   python3 setup/check_scanner.py --continuous
   ```

   Expect: one accepted read per presentation. Stop with `Ctrl+C`.

Continue with [workspace preparation](04_workspace.md).
See [scanner and destinations](../reference/hardware.md#scanner-and-destination-mapping) and [label layouts](../reference/hardware.md#label-layouts-and-outputs) for options and behaviour.

## If something goes wrong

- `--simulate` exits with status 2 -> the token is not in `MAKE_LABELS["destinations"]` in `config/settings.py`; check its spelling.
- `Input devices exist but cannot be opened` -> give your user read access to `/dev/input` (for example `sudo usermod -aG input $USER`, then log in again).
- Scanner not found or identity mismatch -> compare `--list-devices` with `SCANNER_READER`; add `--device /dev/input/eventN` with the scanner's path only, the identity check still applies.
- Wrong or garbled characters -> set the scanner to a US keyboard layout; add `--debug` to see each key event.
- No read within 10 seconds -> reprint at actual size, flatten the label, and present it closer and still.
- Device busy -> stop the other reader or the running cycle first.
