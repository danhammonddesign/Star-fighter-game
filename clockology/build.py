#!/usr/bin/env python3
"""Build the Star Fighter Clockology watch faces.

    python3 build.py                     # default designs, variants and sizes
    python3 build.py --all               # every watch size
    python3 build.py --sizes 45mm --variants ice

Output lands in `dist/`: one `.clock` file per design/variant/size, plus a PNG
preview of each so the faces can be eyeballed without a watch.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from clocklib import face
from clocklib.archive import decode, encode

DIST = Path(__file__).resolve().parent / "dist"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--designs", nargs="+", default=list(face.DESIGNS), choices=list(face.DESIGNS))
    parser.add_argument("--variants", nargs="+", default=list(face.VARIANTS), choices=list(face.VARIANTS))
    parser.add_argument("--sizes", nargs="+", default=list(face.DEFAULT_SIZES), choices=list(face.CANVASES))
    parser.add_argument("--all", action="store_true", help="build every supported watch size")
    parser.add_argument("--seed", type=int, default=7, help="starfield random seed")
    parser.add_argument("--out", type=Path, default=DIST)
    return parser.parse_args(argv)


def verify(payload: bytes, graph: dict) -> None:
    """Re-read what we just wrote and confirm the graph survives the round trip."""
    restored = decode(payload)
    assert restored == graph, "archive did not round-trip"
    setting = restored["faceSetting"]
    names = {asset["filename"] for asset in restored["mediaAssets"]}
    for layer in setting["faceLayers"]:
        referenced = layer["filenameForImage"]
        assert not referenced or referenced in names, f"missing asset {referenced}"
        index = layer["desiredThemeColorIndex"]
        assert 0 <= index < len(setting["faceColors"]), f"colour index {index} out of range"


def main(argv=None) -> int:
    args = parse_args(argv)
    sizes = list(face.CANVASES) if args.all else args.sizes
    out = args.out
    (out / "previews").mkdir(parents=True, exist_ok=True)

    built = 0
    for design in args.designs:
        for variant in args.variants:
            for size in sizes:
                graph = face.build_face(design, size, variant, seed=args.seed)
                payload = encode(graph)
                verify(payload, graph)

                title = face.DESIGNS[design][0].replace(" ", "")
                stem = f"{title}-{variant.title()}-{size}"
                (out / f"{stem}.clock").write_bytes(payload)
                (out / "previews" / f"{stem}.jpg").write_bytes(
                    _preview(graph["thumbnailImageData"])
                )
                built += 1
                print(f"  {stem}.clock  {len(payload) / 1024:7.1f} KB  "
                      f"{len(graph['faceSetting']['faceLayers'])} layers  "
                      f"{len(graph['mediaAssets'])} assets")

    print(f"\nBuilt {built} face(s) into {out}")
    return 0


def _preview(thumbnail: bytes) -> bytes:
    """Halve the embedded 2x thumbnail back to canvas size for the repo previews."""
    from PIL import Image
    image = Image.open(io.BytesIO(thumbnail))
    image = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


if __name__ == "__main__":
    sys.exit(main())
