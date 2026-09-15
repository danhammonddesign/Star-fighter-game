#!/usr/bin/env python3
"""Dump the contents of any Clockology `.clock` file.

    python3 inspect_clock.py path/to/Face.clock            # summary
    python3 inspect_clock.py path/to/Face.clock --layers    # every layer option
    python3 inspect_clock.py path/to/Face.clock --extract out/   # pull the images out

Useful for checking a face this repo produced, or for reading one exported from
the Clockology app to see how it was put together.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clocklib.archive import decode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--layers", action="store_true", help="print full layerOptions for each layer")
    parser.add_argument("--extract", type=Path, metavar="DIR", help="write mediaAssets and thumbnail to DIR")
    args = parser.parse_args(argv)

    graph = decode(args.path.read_bytes())
    setting = graph["faceSetting"]

    print(f"title       {setting['title']}")
    print(f"uniqueID    {setting['uniqueID']}")
    print(f"categories  {', '.join(setting['filterCategories'])}")
    print(f"colors      {len(setting['faceColors'])}: {' '.join(setting['faceColors'])}")
    print(f"assets      {len(graph['mediaAssets'])}")
    print(f"thumbnail   {len(graph['thumbnailImageData'])} bytes")
    print(f"layers      {len(setting['faceLayers'])} (listed bottom to top)\n")

    for index, layer in enumerate(setting["faceLayers"]):
        flag = "hidden" if layer["isHidden"] else "      "
        print(f"{index:>3}  {flag}  {layer['layerType']:<17} "
              f"pos=({layer['horizontalPosition']}, {layer['verticalPosition']}) "
              f"scale={layer['scale']} color={layer['desiredThemeColorIndex']}  {layer['customName']}")
        if args.layers:
            print(json.dumps(layer["layerOptions"], indent=6, sort_keys=True))

    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=True)
        for asset in graph["mediaAssets"]:
            (args.extract / asset["filename"]).write_bytes(asset["assetData"])
        (args.extract / "thumbnail.jpg").write_bytes(graph["thumbnailImageData"])
        print(f"\nextracted {len(graph['mediaAssets']) + 1} file(s) to {args.extract}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
