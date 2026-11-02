#!/usr/bin/env python3
"""Render complete manuscript tables for the website using Poppler only.

Run from any directory: python3 tools/export_tables.py
Only website assets and their provenance are written. A changed source PDF
requires checking the table locations and updating SOURCE_SHA256 and TABLES.
"""

import argparse
import hashlib
import json
import math
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "a285a1b38a82f9cdac151f45c5c49b32a2d830425fd38b1bec68426e4093e735"
# Rectangles are [left, top, right, bottom], measured in PDF points (1/72 inch)
# from the top-left corner of the 612 x 792 pt page. Include caption/footnotes.
TABLES = (
    ("table-ii", "Table II: Simulation Accuracy across Reconstruction Backbones", 5,
     [54.0, 44.0, 558.0, 289.15]),
    ("table-iv", "Table IV: Physical-Robot Evaluation", 6,
     [309.0, 168.0, 562.0, 388.0]),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path):
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG header: {path}")
    return list(struct.unpack(">II", header[16:24]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path,
                        default=ROOT.parent / "HEVFM/paper/root.pdf")
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    if args.dpi < 300:
        parser.error("Use at least 300 dpi to preserve readable table footnotes.")
    source_hash = sha256(args.pdf)
    if source_hash != SOURCE_SHA256:
        parser.error("The PDF changed. Recheck the table coordinates before updating SOURCE_SHA256.")

    version = subprocess.run(["pdftoppm", "-v"], capture_output=True,
                             text=True, check=True)
    renderer = (version.stderr or version.stdout).splitlines()[0]
    output = ROOT / "docs/assets/images"
    output.mkdir(parents=True, exist_ok=True)
    provenance = {
        "source_pdf": "HEVFM/paper/root.pdf",
        "source_pdf_sha256": source_hash,
        "source_page_size_pt": [612, 792],
        "renderer": renderer,
        "dpi": args.dpi,
        "coordinate_system": "top-left origin; point rectangles are [left, top, right, bottom]; pages are 1-based",
        "pixel_rounding": "floor left/top, ceil right/bottom; crop width/height are differences",
        "processing": "Direct PDF rendering and rectangular crop only; no text, numbers, captions, or footnotes are redrawn.",
        "reproduce": "python3 tools/export_tables.py",
        "tables": [],
    }
    scale = args.dpi / 72
    for slug, title, page, rectangle in TABLES:
        left, top, right, bottom = rectangle
        x, y = math.floor(left * scale), math.floor(top * scale)
        width = math.ceil(right * scale) - x
        height = math.ceil(bottom * scale) - y
        prefix = output / slug
        subprocess.run([
            "pdftoppm", "-f", str(page), "-l", str(page), "-singlefile",
            "-r", str(args.dpi), "-x", str(x), "-y", str(y),
            "-W", str(width), "-H", str(height), "-png",
            str(args.pdf), str(prefix),
        ], check=True)
        path = prefix.with_suffix(".png")
        dimensions = png_dimensions(path)
        if dimensions != [width, height]:
            raise RuntimeError(f"Unexpected dimensions for {path}: {dimensions}")
        provenance["tables"].append({
            "id": slug,
            "title": title,
            "source_page": page,
            "crop_rectangle_pt": rectangle,
            "crop_rectangle_px": {"x": x, "y": y, "width": width, "height": height},
            "output": str(path.relative_to(ROOT)),
            "dimensions_px": dimensions,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "included": ["table label", "caption", "all data cells", "all footnotes"],
        })
        print(f"{path.relative_to(ROOT)}: {width} x {height} px")
    (ROOT / "tools/table-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
