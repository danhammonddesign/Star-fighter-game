"""Read and write Clockology `.clock` files.

A `.clock` file is not a zip archive: it is an Apple *binary property list*
holding an `NSKeyedArchiver` graph. The graph only ever uses `NSDictionary`,
`NSArray`, strings, numbers, booleans and raw data, so it can be produced
without any Objective-C runtime.

Top level shape::

    {
      "faceSetting":        {...},   # title, colors, layers
      "mediaAssets":        [{"filename": ..., "assetData": <png bytes>}],
      "thumbnailImageData": <jpeg bytes>,
      "syncModePreference": "",
    }
"""

from __future__ import annotations

import plistlib
from plistlib import UID

NS_DICTIONARY = {"$classname": "NSDictionary", "$classes": ["NSDictionary", "NSObject"]}
NS_ARRAY = {"$classname": "NSArray", "$classes": ["NSArray", "NSObject"]}


def encode(root) -> bytes:
    """Serialise a plain Python graph into NSKeyedArchiver binary plist bytes."""
    objects = ["$null"]
    primitives: dict[tuple, int] = {}
    classes: dict[str, int] = {}

    def add_class(template):
        name = template["$classname"]
        if name not in classes:
            classes[name] = len(objects)
            objects.append(template)
        return UID(classes[name])

    def add(value) -> UID:
        # bool must be tested before int: isinstance(True, int) is True.
        if isinstance(value, (bool, int, float, str, bytes)):
            key = (type(value).__name__, value)
            if key not in primitives:
                primitives[key] = len(objects)
                objects.append(value)
            return UID(primitives[key])

        if isinstance(value, dict):
            index = len(objects)
            objects.append(None)  # reserve, so children get higher UIDs
            keys = [add(k) for k in value]
            vals = [add(v) for v in value.values()]
            objects[index] = {"NS.keys": keys, "NS.objects": vals, "$class": add_class(NS_DICTIONARY)}
            return UID(index)

        if isinstance(value, (list, tuple)):
            index = len(objects)
            objects.append(None)
            items = [add(v) for v in value]
            objects[index] = {"NS.objects": items, "$class": add_class(NS_ARRAY)}
            return UID(index)

        raise TypeError(f"cannot archive {type(value).__name__}")

    root_uid = add(root)
    archive = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": root_uid},
        "$objects": objects,
    }
    return plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)


def decode(data: bytes):
    """Inverse of `encode`, used by the round-trip self-check and for inspection."""
    archive = plistlib.loads(data)
    objects = archive["$objects"]

    def resolve(value):
        if isinstance(value, UID):
            return resolve(objects[value.data])
        if isinstance(value, dict):
            if "NS.keys" in value:
                return {resolve(k): resolve(v) for k, v in zip(value["NS.keys"], value["NS.objects"])}
            if "NS.objects" in value:
                return [resolve(v) for v in value["NS.objects"]]
        return value

    return resolve(archive["$top"]["root"])
