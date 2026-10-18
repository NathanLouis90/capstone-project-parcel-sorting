"""Editable settings for barcode_scanning.

Each section is named after its source file. CLI arguments override defaults.
Label dimensions use the unit stated in each size entry. Layout distances are
in inches or PDF points as indicated by their names; font sizes are in points.
Restart the generator after editing this file.
"""

from pathlib import Path

# make_labels.py
MAKE_LABELS = {
    "outdir": str(Path(__file__).resolve().parent / "labels"),
    "default_size": "100x150",
    "combined": False,
    "crop_marks": True,
    "destinations": [
        {
            "token": "DEST-A-S138683",
            "bin": 0,
            "name": "DESTINATION A",
            "lines": [
                "SIT @ Dover Campus",
                "10 Dover Drive",
                "Singapore 138683",
            ],
        },
        {
            "token": "DEST-B-S828608",
            "bin": 1,
            "name": "DESTINATION B",
            "lines": [
                "SIT @ Punggol Campus",
                "1 Punggol Coast Road",
                "Singapore 828608",
            ],
        },
    ],
    "sizes": {
        "3x4": (3.0, 4.0, "inch"),
        "2x3": (2.0, 3.0, "inch"),
        "100x150": (100.0, 150.0, "mm"),
        "carton": (80.0, 40.0, "mm"),
    },
    "barcode_options": {
        "module_width": 0.25,
        "module_height": 20.0,
        "quiet_zone": 3.0,
        "font_size": 0,
        "text_distance": 0.0,
        "write_text": False,
        "dpi": 600,
    },
    "layout": {
        "reference_width_in": 100.0 / 25.4,
        "reference_height_in": 150.0 / 25.4,
        "margin_in": 0.20,
        "crop_line_width_pt": 0.5,
        "crop_dash_pt": (2, 2),
        "crop_inset_pt": 2,
        "payload_font": "Courier-Bold",
        "payload_font_size_pt": 12,
        "payload_gap_in": 0.17,
        "banner_height_in": 0.45,
        "banner_font": "Helvetica-Bold",
        "banner_font_size_pt": 20,
        "banner_baseline_offset_pt": 7,
        "address_line_spacing_in": 0.20,
        "address_baseline_offset_pt": 4,
        "address_heading_font": "Helvetica-Bold",
        "address_heading_size_pt": 12,
        "address_font": "Helvetica",
        "address_font_size_pt": 11,
        "footer_font": "Helvetica",
        "footer_font_size_pt": 8,
        "footer_margin_fraction": 0.4,
    },
    "footer_template": "Code 128  |  bin {bin}  |  RSE4018",
    "label_title_template": "RSE4018 {name}",
    "combined_title": "RSE4018 destination labels",
    "barcode_filename_template": "bc_{token}",
    "label_filename_template": "label_{size}_{token}.pdf",
    "combined_filename_template": "labels_{size}_combined.pdf",
}

# scanner_reader.py
# This identity is a candidate from /proc/bus/input/devices. Confirm with a hand
# scan before using recording integration. Never substitute the normal keyboard.
SCANNER_READER = {
    "device_path": "/dev/input/by-id/usb-Megahunt_HID_Keyboard_D-2TYYGQMH-event-kbd",
    "device_name": "Megahunt HID Keyboard",
    "vendor_id": 0x0461,
    "product_id": 0x4D82,
    "exclusive_capture": True,
    "normalize_case": True,  # Destination tokens are uppercase; retain raw text in events.
    "keyboard_layout": "us",  # Configure the scanner to emit a US keyboard layout.
    "terminator_keys": ["KEY_ENTER", "KEY_KPENTER"],
    "scan_window_s": 10.0,
    "partial_timeout_s": 0.5,
    "max_length": 64,
    "poll_interval_s": 0.05,
}

# recording.py
RECORDING = {
    "metadata_filename": "episode_metadata.json",
}
