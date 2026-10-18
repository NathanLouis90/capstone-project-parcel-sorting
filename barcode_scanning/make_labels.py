#!/usr/bin/env python3
"""
make_labels.py  --  RSE4018 destination label generator

Generates two labels, one per destination building. The barcode payload
is a short destination token; the full address is printed above it.
The barcode is centred on the label, so that the symbol coincides with
the centre of the item face when the label is applied centred.

Payload -> bin mapping is configured in barcode_scanning_config.py and consumed by the supervisor
script, so no label_manifest.csv is required.

Usage:
    python make_labels.py                      # configured size, writes barcode_scanning/labels/
    python make_labels.py --size carton        # 80 x 40 mm, cut from stock
    python make_labels.py --combined           # all destinations on one page

Deps (Python 3.8):
    pip install python-barcode "reportlab<4"
    # reportlab 4.1+ calls md5(usedforsecurity=...) which py3.8 lacks
"""

import argparse
import os

from barcode import Code128
from barcode.writer import ImageWriter
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Support direct execution and package imports without extra dependencies.
if __package__:
    from .barcode_scanning_config import MAKE_LABELS
else:
    from barcode_scanning_config import MAKE_LABELS

DESTINATIONS = MAKE_LABELS["destinations"]
BARCODE_OPTS = MAKE_LABELS["barcode_options"]
LAYOUT = MAKE_LABELS["layout"]
_UNITS = {"inch": inch, "mm": mm}
SIZES = {
    name: (width * _UNITS[unit], height * _UNITS[unit])
    for name, (width, height, unit) in MAKE_LABELS["sizes"].items()
}


def render_barcode_png(token, path):
    stem = os.path.splitext(path)[0]
    Code128(token, writer=ImageWriter()).save(stem, options=BARCODE_OPTS)
    return stem + ".png"


def draw_label(c, dest, png_path, w, h, x0=0.0, y0=0.0, crop_marks=MAKE_LABELS["crop_marks"]):
    """Draw one label with lower-left corner at (x0, y0).

    Layout is anchored on the barcode: the symbol is centred on the label
    both horizontally and vertically. Text blocks are placed around it.
    """
    s = min(w / (LAYOUT["reference_width_in"] * inch), h / (LAYOUT["reference_height_in"] * inch))
    margin = LAYOUT["margin_in"] * inch * s
    cx = x0 + w / 2.0
    cy = y0 + h / 2.0

    if crop_marks:
        c.setLineWidth(LAYOUT["crop_line_width_pt"])
        c.setDash(*LAYOUT["crop_dash_pt"])
        inset = LAYOUT["crop_inset_pt"]
        c.rect(x0 + inset, y0 + inset, w - 2 * inset, h - 2 * inset)
        c.setDash()

    # --- Barcode, centred, at its NATIVE module width -------------------
    img = ImageReader(png_path)
    iw, ih = img.getSize()
    dpi = BARCODE_OPTS["dpi"]
    bc_w = iw * 72.0 / dpi                 # points, true physical size
    bc_h = ih * 72.0 / dpi
    max_w = w - 2 * margin
    if bc_w > max_w:
        k = max_w / bc_w
        bc_w, bc_h = bc_w * k, bc_h * k
        print("  WARNING: %s barcode scaled to %.3f (module %.3f mm)"
              % (dest["token"], k, BARCODE_OPTS["module_width"] * k))
    bc_y = cy - bc_h / 2.0
    if w <= 81 * mm and h <= 41 * mm:
        if bc_w > w - 4 * mm:
            raise ValueError('Carton barcode must fit at native module width')
        c.drawImage(img, cx - bc_w / 2, bc_y, width=bc_w, height=bc_h, mask='auto')
        c.setFont('Courier-Bold', 6)
        c.drawCentredString(cx, bc_y - 3 * mm, dest['token'])
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(cx, y0 + h - 4 * mm, 'BIN {}'.format(dest['bin']))
        return
    c.drawImage(img, cx - bc_w / 2.0, bc_y, width=bc_w, height=bc_h,
                preserveAspectRatio=True, anchor='c', mask='auto')

    # --- Human-readable payload, directly under the symbol --------------
    c.setFillGray(0.0)
    c.setFont(LAYOUT["payload_font"], LAYOUT["payload_font_size_pt"] * s)
    c.drawCentredString(cx, bc_y - LAYOUT["payload_gap_in"] * inch * s, dest["token"])

    # --- Destination banner, top ---------------------------------------
    banner_h = LAYOUT["banner_height_in"] * inch * s
    banner_y = y0 + h - margin - banner_h
    c.rect(x0 + margin, banner_y, w - 2 * margin, banner_h, fill=1, stroke=0)
    c.setFillGray(1.0)
    c.setFont(LAYOUT["banner_font"], LAYOUT["banner_font_size_pt"] * s)
    c.drawCentredString(cx, banner_y + banner_h / 2 - LAYOUT["banner_baseline_offset_pt"] * s, dest["name"])
    c.setFillGray(0.0)

    # --- Address block, between banner and barcode ----------------------
    n = len(dest["lines"])
    step = LAYOUT["address_line_spacing_in"] * inch * s
    gap_top = banner_y
    gap_bot = bc_y + bc_h
    y = (gap_top + gap_bot) / 2.0 + (n - 1) * step / 2.0 - LAYOUT["address_baseline_offset_pt"] * s
    for i, line in enumerate(dest["lines"]):
        c.setFont(LAYOUT["address_heading_font"] if i == 0 else LAYOUT["address_font"],
                  (LAYOUT["address_heading_size_pt"] if i == 0 else LAYOUT["address_font_size_pt"]) * s)
        c.drawCentredString(cx, y, line)
        y -= step

    # --- Footer ---------------------------------------------------------
    c.setFont(LAYOUT["footer_font"], LAYOUT["footer_font_size_pt"] * s)
    c.drawCentredString(cx, y0 + margin * LAYOUT["footer_margin_fraction"],
                        MAKE_LABELS["footer_template"].format(bin=dest["bin"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=MAKE_LABELS["outdir"])
    ap.add_argument("--size", default=MAKE_LABELS["default_size"], choices=sorted(SIZES),
                    help="label size preset (default: %(default)s)")
    ap.add_argument("--combined", action="store_true", default=MAKE_LABELS["combined"],
                    help="also write all labels side by side on one page")
    ap.add_argument("--no-crop-marks", action="store_true",
                    default=not MAKE_LABELS["crop_marks"])
    args = ap.parse_args()

    w, h = SIZES[args.size]
    os.makedirs(args.outdir, exist_ok=True)
    marks = not args.no_crop_marks

    pngs = []
    for dest in DESTINATIONS:
        png = render_barcode_png(dest["token"],
                                 os.path.join(args.outdir, MAKE_LABELS["barcode_filename_template"].format(token=dest["token"])))
        pngs.append(png)
        pdf = os.path.join(args.outdir,
                           MAKE_LABELS["label_filename_template"].format(size=args.size, token=dest["token"]))
        c = canvas.Canvas(pdf, pagesize=(w, h))
        c.setTitle(MAKE_LABELS["label_title_template"].format(name=dest["name"]))
        draw_label(c, dest, png, w, h, crop_marks=marks)
        c.showPage()
        c.save()
        print("wrote %s  (payload %r -> bin %d)" % (pdf, dest["token"], dest["bin"]))

    if args.combined:
        pdf = os.path.join(args.outdir, MAKE_LABELS["combined_filename_template"].format(size=args.size))
        c = canvas.Canvas(pdf, pagesize=(len(DESTINATIONS) * w, h))
        c.setTitle(MAKE_LABELS["combined_title"])
        for i, dest in enumerate(DESTINATIONS):
            draw_label(c, dest, pngs[i], w, h, x0=i * w, crop_marks=marks)
        c.showPage()
        c.save()
        print("wrote %s" % pdf)

    print("\nSupervisor mapping:")
    for d in DESTINATIONS:
        print("    %-16s -> bin %d" % (d["token"], d["bin"]))


if __name__ == "__main__":
    main()
