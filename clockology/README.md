# Star Fighter — Clockology watch faces

Custom Apple Watch faces for [Clockology](https://apps.apple.com/us/app/clockology/id1456386228),
generated from source. A cockpit-HUD read on the game's theme: starfield backdrop,
targeting dial, and readouts labelled as ship systems.

| | |
|---|---|
| ![Star Fighter HUD](dist/previews/StarFighterHUD-Green-45mm.jpg) | ![Star Fighter Analog](dist/previews/StarFighterAnalog-Green-45mm.jpg) |
| **Star Fighter HUD** — digital, with a radar sweep on the second hand | **Star Fighter Analog** — swept fighter hands over a targeting reticle |

Three colourways — **Green** (default), **Amber**, **Ice** — built for four watch
sizes. Everything in `dist/` is ready to install.

## Installing a face

1. Pick the file in [`dist/`](dist) matching your design, colourway and watch size —
   e.g. `StarFighterHUD-Green-45mm.clock`. Sizes map to watch models as:

   | File suffix | Models | Canvas |
   |---|---|---|
   | `41mm` | Series 7/8/9 41mm | 352 × 430 |
   | `45mm` | Series 7/8/9 45mm | 396 × 484 |
   | `46mm-s10` | Series 10/11 46mm | 416 × 496 |
   | `49mm-ultra` | Ultra / Ultra 2 / Ultra 3 | 410 × 502 |

   Other sizes (`40mm`, `42mm-s10`, `44mm`) can be built on demand — see below.

2. Get the file onto your iPhone: AirDrop it, email it, or drop it in iCloud Drive.
3. Open it and choose **Clockology** from the share sheet. It lands in the app's
   *Designs* list.
4. In Clockology, open the design and tap **Sync to Watch**.

The Clockology watch app must be running on the watch to display the face — it is a
third-party app, not a real watchOS face, so it cannot be set as your default face and
does not show on the wrist-raise until you open Clockology.

## What's on each face

**Star Fighter HUD** (digital)

- Hours and minutes, large and centred
- Weekday and date beneath
- `HULL` — live heart rate
- `TEMP` — current temperature (needs Weather enabled in Clockology)
- Battery indicator at the bottom
- A translucent radar wedge rotating once a minute on the second hand

**Star Fighter Analog**

- Swept fighter-blade hour and minute hands
- A second hand carrying a small delta fighter at its tip
- Weekday and date at the top
- Heart rate with a heart icon, battery indicator opposite
- An Activity move ring around the dial, **hidden by default** — unhide it in the
  layer list if you want it

## Building from source

Requires Python 3.10+ and Pillow.

```bash
pip install Pillow
cd clockology
python3 build.py                              # defaults: 2 designs x 3 colourways x 4 sizes
python3 build.py --all                        # every supported size
python3 build.py --sizes 45mm --variants ice  # just one
python3 build.py --seed 42                    # reroll the starfield
```

Output goes to `dist/`, with a JPEG preview of each face in `dist/previews/`.

Layout is driven by two tables in `clocklib/face.py` — `ANALOG_POS` and `HUD_POS` —
which hold the `(x, y, scale)` of every readout. The layer graph and the preview
renderer both read those tables, so a preview always reflects the real composition.
Colourways live in `VARIANTS` and only repaint three accent slots of the palette.

Artwork in `clocklib/art.py` is drawn procedurally at 4× and resampled down, so any
canvas size comes out crisp; nothing is a fixed-resolution bitmap.

### Inspecting a face

```bash
python3 inspect_clock.py dist/StarFighterHUD-Green-45mm.clock
python3 inspect_clock.py some.clock --layers          # full layer options
python3 inspect_clock.py some.clock --extract out/    # pull out the PNGs
```

This works on any `.clock` file, including ones exported from the Clockology app.

## The `.clock` file format

Worth writing down, because it is not documented anywhere and the common guess is wrong.

A `.clock` file is **not** a zip archive. It is an Apple **binary property list**
containing an `NSKeyedArchiver` object graph. The graph uses only `NSDictionary`,
`NSArray`, strings, numbers, booleans and raw data — no custom classes — so it can be
written from plain Python with `plistlib`. That is all `clocklib/archive.py` does.

The root object:

```
faceSetting         title, uniqueID, filterCategories, faceColors, lastUpdateDate, faceLayers
mediaAssets         [ { filename, assetData } ]   — PNG bytes, one per image layer
thumbnailImageData  JPEG bytes, rendered at 2x the canvas
syncModePreference  ""
```

Each entry in `faceLayers` carries a fixed key set — `layerType`, `customName`,
`layerOptions`, `desiredThemeColorIndex`, `horizontalPosition`, `verticalPosition`,
`scale`, `alpha`, `angleOffset`, `filenameForImage`, `isHidden`. Note that the numeric
fields are **strings** (`"1.0"`, `"-0.46"`); only `desiredThemeColorIndex` is a real
integer.

Conventions worth knowing:

- **Layer order is bottom to top.** The first element of `faceLayers` is the backdrop.
- **Positions are normalised from the centre**: horizontal runs −1 (left) to +1 (right),
  vertical runs −1 (bottom) to **+1 (top)** — y is positive *upwards*.
- **Image assets are always full canvas size**, whatever the layer is. A hand is drawn
  pointing at 12 o'clock across the whole canvas, with its pivot set by `imageXPos` /
  `imageYPos` (`0.5`, `0.5` for centre).
- **`desiredThemeColorIndex` indexes into `faceColors`.** An `ImageTexture` with
  `tinted: true` is recoloured by it, so greyscale artwork recolours for free — that is
  how one set of PNGs serves all three colourways.

Layer types seen in the wild: `ColorTexture`, `ImageTexture`, `GradientTexture`,
`VideoTexture`, `TextLabel`, `DateTimeLabel`, `HealthLabel`, `WeatherLabel`,
`HourHand`, `MinuteHand`, `SecondHand`, `ActivityRing`, `BatteryIndicator`, `Icon`,
`MoonPhase`, `Utility`.

## Known caveats

These faces were built and verified offline; they have not been opened on a physical
watch. The archive structure is sound — it round-trips byte-identically against faces
exported by Clockology itself, and `build.py` re-reads and validates every file it
writes. What could still need a nudge:

- **Text sizing.** Clockology's `scale` has no published reference size; the values here
  were calibrated from real faces, so a label may want resizing. Drag it in the app if so.
- **`Icon` and `BatteryIndicator` dimensions** are estimates for the same reason.
- **The weather readout** needs Weather permission granted to Clockology, otherwise it
  renders blank.

All of this is adjustable directly in the app — nothing requires a rebuild.

## Credit

Format details were reverse-engineered by reading the `.clock` files published in
[GoldenChaos/FacePorts](https://github.com/GoldenChaos/FacePorts). The artwork here is
generated from scratch and shares nothing with that project.
