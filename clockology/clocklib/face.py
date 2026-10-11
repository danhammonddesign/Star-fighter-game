"""The Star Fighter face designs, expressed as Clockology layer graphs.

Positions are normalised to the centre of the canvas: horizontal runs -1 (left)
to +1 (right), vertical runs -1 (bottom) to +1 (top). Layers are drawn in array
order, so the first entry is the bottom of the stack.
"""

from __future__ import annotations

import io
import uuid

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import art

# Canvas sizes are the native pixel dimensions Clockology uses per watch model.
CANVASES = {
    "40mm": (324, 394),
    "41mm": (352, 430),
    "42mm-s10": (374, 446),
    "44mm": (368, 448),
    "45mm": (396, 484),
    "46mm-s10": (416, 496),
    "49mm-ultra": (410, 502),
}

DEFAULT_SIZES = ("41mm", "45mm", "46mm-s10", "49mm-ultra")

BASE_COLORS = [
    "#E9F6FFFF",  # 0  instrument white
    "#04070CFF",  # 1  space black, the backdrop
    "#3DFF9AFF",  # 2  primary HUD accent
    "#00D9FFFF",  # 3  secondary scanner accent
    "#FF3355FF",  # 4  alert red
    "#FFC24BFF",  # 5  amber
    "#6F8496FF",  # 6  slate, for chrome and framing
    "#9BFFC9FF",  # 7  pale accent
    "#14202BFF",  # 8  panel dark
    "#FF7A00FF",  # 9  ion orange
    "#B980FFFF",  # 10 plasma violet
    "#FFFFFFFF",  # 11 white
]

TRON_COLORS = [
    "#EAF9FFFF",  # 0  white-blue, for the clock
    "#000000FF",  # 1  black, the grid void
    "#00E5FFFF",  # 2  cyan, the player's light ribbon
    "#2E6BFFFF",  # 3  electric blue, the rival's
    "#7FE9FFFF",  # 4  pale cyan
    "#0A1A2AFF",  # 5  navy panel
    "#4A7FA8FF",  # 6  steel, for chrome and framing
    "#00A0C8FF",  # 7  dim cyan
    "#001018FF",  # 8  near black
    "#66B0FFFF",  # 9  sky blue
    "#B8ECFFFF",  # 10 ice
    "#FFFFFFFF",  # 11 white
]

# Arcade values: maze blue, pellet peach, and the four ghost colours.
PACMAN_COLORS = [
    "#FFFFFFFF",  # 0  white, the score font
    "#000000FF",  # 1  black, the board
    "#2121DEFF",  # 2  maze blue
    "#FFB8AEFF",  # 3  pellet peach
    "#FFFF00FF",  # 4  hero yellow
    "#FF0000FF",  # 5  Blinky
    "#FFB8FFFF",  # 6  Pinky, and the chamber gate
    "#00FFFFFF",  # 7  Inky
    "#FFB852FF",  # 8  Clyde
    "#2121FFFF",  # 9  frightened blue
    "#DEDEDEFF",  # 10 light grey
    "#FFCC00FF",  # 11 amber
]

PALETTES = {"starfighter": BASE_COLORS, "tron": TRON_COLORS, "pacman": PACMAN_COLORS}

# Each variant only repaints the three accent slots of its base palette.
VARIANTS = {
    "green": {},
    "amber": {2: "#FFB13DFF", 3: "#FF7A00FF", 7: "#FFE4B0FF"},
    "ice": {2: "#7FE9FFFF", 3: "#2E9BFFFF", 7: "#D6F4FFFF"},
    "blue": {},
    "arcade": {},
}


def palette_for(design: str, variant: str) -> list[str]:
    colors = list(PALETTES[DESIGNS[design]["palette"]])
    for index, value in VARIANTS[variant].items():
        colors[index] = value
    return colors


# Readout placement, shared by the layer graph and the preview renderer so the
# two can never drift apart. Values are (x, y, scale) in normalised centre coords.
ANALOG_POS = {
    "date": (0.0, 0.52, 0.3125),
    "hull": (-0.40, -0.46, 0.2625),
    "hull_icon": (-0.40, -0.30, 0.45),
    "battery": (0.40, -0.46, 1.3),
}

HUD_POS = {
    "callsign": (0.0, 0.62, 0.16),
    "time": (0.0, 0.06, 0.82),
    "date": (0.0, -0.22, 0.2125),
    "hull_label": (-0.42, -0.42, 0.13),
    "hull": (-0.42, -0.56, 0.2125),
    "temp_label": (0.42, -0.42, 0.13),
    "temp": (0.42, -0.56, 0.2125),
    "battery": (0.0, -0.80, 1.2),
}

TRON_POS = {
    "label": (0.0, 0.60, 0.15),
    "time": (0.0, 0.10, 0.86),
    "date": (0.0, -0.13, 0.2125),
    "battery": (0.0, -0.62, 1.2),
    "hull": (0.0, -0.78, 0.19),
}

# The clock sits in the chamber the ghosts start from; the date rides the top
# band above the board, where the arcade puts the score line.
PACMAN_POS = {
    "time": (0.0, -0.04, 0.58),
    "date": (0.0, 0.93, 0.17),
    "battery": (0.0, -0.93, 1.0),
}

# Clockology text scale of 1.0 renders at roughly this fraction of canvas height.
TEXT_SCALE_TO_HEIGHT = 0.19


def _num(value) -> str:
    return f"{float(value)}"


def _layer(layer_type, name, options, *, color=0, x=0.0, y=0.0,
           scale=1.0, alpha=1.0, angle=0.0, image="", hidden=False) -> dict:
    return {
        "layerType": layer_type,
        "customName": name,
        "layerOptions": options,
        "desiredThemeColorIndex": color,
        "horizontalPosition": _num(x),
        "verticalPosition": _num(y),
        "scale": _num(scale),
        "alpha": _num(alpha),
        "angleOffset": _num(angle),
        "filenameForImage": image,
        "isHidden": hidden,
    }


def _place(entry) -> dict:
    x, y, scale = entry
    return {"x": x, "y": y, "scale": scale}


def _texture_options(*, tinted: bool, transparent: bool) -> dict:
    return {
        "backgroundType": "FaceBackgroundTypeFilled",
        "filename": "",
        "tinted": tinted,
        "anglePerSec": 0.0,
        "hasTransparency": transparent,
    }


def _text_options(format_type, *, custom_text="", justification="Centered",
                  kerning=0.0, outline_width=0.0, outline_color=0, effect="None",
                  font="") -> dict:
    """Layer options for a text layer.

    `font` names a font that must already be installed on the *watch* — a font
    cannot be embedded in a .clock file. Left empty, Clockology uses its default.
    """
    return {
        "formatType": format_type,
        "customText": custom_text,
        "shouldShowCustomText": bool(custom_text),
        "justificationType": justification,
        "fontType": "NumberTextTypeSystem",
        "customFont": font,
        "casingType": "Uppercased",
        "kerning": _num(kerning),
        "effectType": effect,
        "outlineWidth": _num(outline_width),
        "desiredThemeColorIndexForOutline": str(outline_color),
        "angle": "45.0",
        "radius": "50.0",
    }


def _hand_options(kind: str) -> dict:
    options = {
        "handType": {
            "HourHand": "HourHandTypeImageGallery",
            "MinuteHand": "MinuteHandImageGallery",
            "SecondHand": "SecondHandGallery",
        }[kind],
        "handImage": "",
        "imageScale": "1.0",
        "imageXPos": "0.5",
        "imageYPos": "0.5",
        "animateClockwise": True,
        "outlineWidth": "0.0",
        "effectsStrength": "0.0",
        "desiredThemeColorIndexForOutline": "0",
        "desiredThemeColorIndexForHighlights": "0",
        "desiredThemeColorIndexForMoreHighlights": "0",
    }
    if kind == "HourHand":
        options["use24HourRotation"] = False
    if kind == "MinuteHand":
        options["handAnimation"] = "MinuteHandMovementSmooth"
    if kind == "SecondHand":
        options["handAnimation"] = "SecondHandMovementSmooth"
        options["physicsFieldType"] = "None"
        options["physicFieldStrength"] = "0.0"
    return options


class AssetLibrary:
    """Renders each artwork once per canvas and hands out Clockology filenames."""

    def __init__(self, width: int, height: int, seed: int):
        self.width, self.height, self.seed = width, height, seed
        self.clock_font = ""
        self.video_scale = 1.0
        self._images: dict[str, Image.Image] = {}
        self._files: dict[str, str] = {}
        self.assets: list[dict] = []

    def image(self, key: str) -> Image.Image:
        if key not in self._images:
            builder = getattr(art, key)
            kwargs = {"seed": self.seed} if key == "starfield" else {}
            self._images[key] = builder(self.width, self.height, **kwargs)
        return self._images[key]

    def add_raw(self, filename: str, data: bytes) -> str:
        """Register an asset that isn't drawn by `art`, such as the light cycle movie."""
        self._files[filename] = filename
        self.assets.append({"filename": filename, "assetData": data})
        return filename

    def put_image(self, key: str, image: Image.Image) -> None:
        self._images[key] = image

    def filename(self, key: str) -> str:
        if key not in self._files:
            image = self.image(key)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            name = f"{uuid.uuid4()}.png".upper().replace(".PNG", ".png")
            self._files[key] = name
            self.assets.append({"filename": name, "assetData": buffer.getvalue()})
        return self._files[key]


def _chrome_layers(lib: AssetLibrary) -> list[dict]:
    """Backdrop and HUD framing shared by both designs."""
    return [
        _layer("ColorTexture", "Space: Void", _texture_options(tinted=False, transparent=False), color=1),
        _layer("ImageTexture", "Space: Starfield", _texture_options(tinted=False, transparent=True),
               color=0, image=lib.filename("starfield")),
    ]


def analog_layers(lib: AssetLibrary) -> list[dict]:
    layers = _chrome_layers(lib)
    layers += [
        _layer("ImageTexture", "HUD: Tick Dial", _texture_options(tinted=True, transparent=True),
               color=2, image=lib.filename("hud_ring")),
        _layer("ImageTexture", "HUD: Corner Brackets", _texture_options(tinted=True, transparent=True),
               color=6, image=lib.filename("hud_frame")),
        _layer("ImageTexture", "HUD: Targeting Reticle", _texture_options(tinted=True, transparent=True),
               color=3, alpha=0.7, image=lib.filename("reticle")),

        _layer("DateTimeLabel", "Readout: Date", _text_options("DADD", kerning=2.0),
               color=2, **_place(ANALOG_POS["date"])),
        _layer("HealthLabel", "Readout: Hull (Heart Rate)", _text_options("HeartRate", kerning=2.0),
               color=4, **_place(ANALOG_POS["hull"])),
        _layer("Icon", "Readout: Hull Icon", {"iconType": "heart", "thickness": 4},
               color=4, **_place(ANALOG_POS["hull_icon"])),
        _layer("BatteryIndicator", "Readout: Shields (Battery)", {
            "indicatorType": "normal",
            "autoBatteryColor": False,
            "desiredThemeColorIndexForBatteryLevel": "2",
            "desiredThemeColorIndexForOutline": "6",
            "innerPadding": "0.0",
            "outlineWidth": "1.0",
        }, color=2, **_place(ANALOG_POS["battery"])),
        _layer("ActivityRing", "Readout: Fuel (Move Ring)", {
            "activityRingType": "Move",
            "desiredThemeColorIndexForStart": "9",
            "desiredThemeColorIndexForEnd": "9",
            "ringWidth": "9.0",
            "backgroundAlpha": "0.22",
        }, color=9, y=0.0, scale=1.86, hidden=True),

        _layer("HourHand", "Hands: Hour", _hand_options("HourHand"),
               color=0, image=lib.filename("hand_hour")),
        _layer("MinuteHand", "Hands: Minute", _hand_options("MinuteHand"),
               color=0, image=lib.filename("hand_minute")),
        _layer("SecondHand", "Hands: Second Fighter", _hand_options("SecondHand"),
               color=4, image=lib.filename("hand_second")),
        _layer("ImageTexture", "Hands: Centre Cap", _texture_options(tinted=True, transparent=True),
               color=0, image=lib.filename("center_cap")),
    ]
    return layers


def hud_layers(lib: AssetLibrary) -> list[dict]:
    layers = _chrome_layers(lib)
    layers += [
        _layer("SecondHand", "Scanner: Radar Sweep", _hand_options("SecondHand"),
               color=2, alpha=0.55, image=lib.filename("radar_sweep")),
        _layer("ImageTexture", "HUD: Tick Dial", _texture_options(tinted=True, transparent=True),
               color=2, image=lib.filename("hud_ring")),
        _layer("ImageTexture", "HUD: Corner Brackets", _texture_options(tinted=True, transparent=True),
               color=6, image=lib.filename("hud_frame")),

        _layer("TextLabel", "Readout: Callsign", _text_options("HHMM", custom_text="STAR FIGHTER", kerning=6.0),
               color=6, **_place(HUD_POS["callsign"])),
        _layer("DateTimeLabel", "Readout: Time", _text_options("HHMM", kerning=1.0),
               color=0, **_place(HUD_POS["time"])),
        _layer("DateTimeLabel", "Readout: Date", _text_options("DADD", kerning=3.0),
               color=2, **_place(HUD_POS["date"])),

        _layer("TextLabel", "Label: Hull", _text_options("HHMM", custom_text="HULL", kerning=3.0,),
               color=6, **_place(HUD_POS["hull_label"])),
        _layer("HealthLabel", "Readout: Hull (Heart Rate)", _text_options("HeartRate", kerning=1.0),
               color=4, **_place(HUD_POS["hull"])),
        _layer("TextLabel", "Label: Temp", _text_options("HHMM", custom_text="TEMP", kerning=3.0),
               color=6, **_place(HUD_POS["temp_label"])),
        _layer("WeatherLabel", "Readout: Temperature", {
            **_text_options("Temperature", kerning=1.0),
            "autoColor": False,
            "thickness": 3,
            "timeSpan": "Current",
            "timeSpanOffset": "1",
            "unitDisplayLevel": "None",
        }, color=3, **_place(HUD_POS["temp"])),

        _layer("BatteryIndicator", "Readout: Shields (Battery)", {
            "indicatorType": "normal",
            "autoBatteryColor": False,
            "desiredThemeColorIndexForBatteryLevel": "2",
            "desiredThemeColorIndexForOutline": "6",
            "innerPadding": "0.0",
            "outlineWidth": "1.0",
        }, color=2, **_place(HUD_POS["battery"])),
    ]
    return layers


def tron_layers(lib: AssetLibrary) -> list[dict]:
    """The light cycle match runs as a looping video underneath the clock."""
    movie = lib.movie_filename
    return [
        _layer("ColorTexture", "Grid: Void", _texture_options(tinted=False, transparent=False), color=1),
        _layer("VideoTexture", "Grid: Light Cycle Match",
               {"filename": "", "numberOfLoops": -1}, color=0,
               scale=lib.video_scale, image=movie),
        _layer("ImageTexture", "HUD: Circuit Frame", _texture_options(tinted=True, transparent=True),
               color=2, alpha=0.9, image=lib.filename("tron_frame")),

        _layer("TextLabel", "Readout: Label",
               _text_options("HHMM", custom_text="THE GRID", kerning=6.0),
               color=6, **_place(TRON_POS["label"])),
        _layer("DateTimeLabel", "Readout: Time",
               _text_options("HHMM", kerning=1.0, outline_width=5.0, outline_color=1),
               color=0, **_place(TRON_POS["time"])),
        _layer("DateTimeLabel", "Readout: Date",
               _text_options("DADD", kerning=3.0, outline_width=3.0, outline_color=1),
               color=2, **_place(TRON_POS["date"])),

        _layer("HealthLabel", "Readout: Heart Rate",
               _text_options("HeartRate", kerning=1.0, outline_width=3.0, outline_color=1),
               color=4, hidden=True, **_place(TRON_POS["hull"])),
    ]


def pacman_layers(lib: AssetLibrary) -> list[dict]:
    """The board plays underneath; the clock lives in the empty chamber."""
    return [
        _layer("ColorTexture", "Board: Black", _texture_options(tinted=False, transparent=False), color=1),
        # Clockology fits a movie to the watch canvas rather than placing it pixel
        # for pixel, so this scale pulls the board back inside the screen. The
        # frame's own margins are black, so trimming it only shows more black.
        _layer("VideoTexture", "Board: Maze Game",
               {"filename": "", "numberOfLoops": -1}, color=0,
               scale=lib.video_scale, image=lib.movie_filename),
        _layer("DateTimeLabel", "Readout: Time",
               _text_options("HHMM", kerning=1.0, font=lib.clock_font),
               color=0, **_place(PACMAN_POS["time"])),
        _layer("DateTimeLabel", "Readout: Date",
               _text_options("DADD", kerning=2.0, font=lib.clock_font),
               color=3, **_place(PACMAN_POS["date"])),
        _layer("BatteryIndicator", "Readout: Battery", {
            "indicatorType": "normal",
            "autoBatteryColor": False,
            "desiredThemeColorIndexForBatteryLevel": "4",
            "desiredThemeColorIndexForOutline": "10",
            "innerPadding": "0.0",
            "outlineWidth": "1.0",
        }, color=4, hidden=True, **_place(PACMAN_POS["battery"])),
    ]


DESIGNS = {
    "analog": {
        "title": "Star Fighter Analog",
        "layers": analog_layers,
        "categories": ["analog", "health", "hd"],
        "palette": "starfighter",
        "variants": ["green", "amber", "ice"],
    },
    "hud": {
        "title": "Star Fighter HUD",
        "layers": hud_layers,
        "categories": ["digital", "weather", "health", "hd"],
        "palette": "starfighter",
        "variants": ["green", "amber", "ice"],
    },
    "tron": {
        "title": "Light Cycle",
        "layers": tron_layers,
        "categories": ["digital", "animated", "hd"],
        "palette": "tron",
        "variants": ["blue"],
        "sizes": ["45mm"],
        "square_video": True,
    },
    "pacman": {
        "title": "Maze Chase",
        "layers": pacman_layers,
        "categories": ["digital", "animated", "hd"],
        "palette": "pacman",
        "variants": ["arcade"],
        "sizes": ["45mm"],
    },
}


# --- thumbnail -------------------------------------------------------------

PIXEL_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Silkscreen-Regular.ttf"


def _pixel_font(size: int):
    """Silkscreen, the closest free stand-in for the arcade score font."""
    try:
        return ImageFont.truetype(str(PIXEL_FONT), size)
    except OSError:
        return _font(size)


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _tint(image: Image.Image, color, alpha: float = 1.0) -> Image.Image:
    solid = Image.new("RGBA", image.size, color + (255,))
    channel = image.getchannel("A")
    if alpha != 1.0:
        channel = channel.point(lambda v: int(v * alpha))
    solid.putalpha(channel)
    return solid


def render_thumbnail(lib: AssetLibrary, design: str, colors: list[str]) -> bytes:
    """A 2x JPEG preview, matching how Clockology stores face thumbnails.

    Text is placed from the same layout table the layers use, so the preview is
    a real check on the composition rather than a hand-tuned mock-up.
    """
    w, h = lib.width, lib.height
    canvas = Image.new("RGBA", (w, h), _hex_to_rgb(colors[1]) + (255,))
    canvas.alpha_composite(lib.image("starfield"))

    accent = _hex_to_rgb(colors[2])
    scanner = _hex_to_rgb(colors[3])
    alert = _hex_to_rgb(colors[4])
    chrome = _hex_to_rgb(colors[6])
    white = _hex_to_rgb(colors[0])

    if design == "pacman":
        canvas.alpha_composite(lib.image("arena_still"))
    elif design == "tron":
        canvas.alpha_composite(lib.image("arena_still"))
        canvas.alpha_composite(_tint(lib.image("tron_frame"), accent, alpha=0.9))
    else:
        if design == "hud":
            sweep = _tint(lib.image("radar_sweep"), accent, alpha=0.55)
            canvas.alpha_composite(sweep.rotate(-250, resample=Image.BICUBIC))
        canvas.alpha_composite(_tint(lib.image("hud_ring"), accent))
        canvas.alpha_composite(_tint(lib.image("hud_frame"), chrome))

    draw = ImageDraw.Draw(canvas)

    def write(entry, text, fill, pixel=False):
        x, y, scale = entry
        px = w / 2 + x * w / 2
        py = h / 2 - y * h / 2
        size = max(6, int(scale * h * TEXT_SCALE_TO_HEIGHT))
        font = _pixel_font(size) if pixel else _font(size)
        draw.text((px, py), text, font=font, fill=fill, anchor="mm")

    def battery(entry, level=0.72):
        x, y, scale = entry
        px = w / 2 + x * w / 2
        py = h / 2 - y * h / 2
        bw = scale * h * 0.10
        bh = bw * 0.46
        box = [px - bw / 2, py - bh / 2, px + bw / 2, py + bh / 2]
        draw.rounded_rectangle(box, radius=bh * 0.28, outline=chrome, width=max(1, int(bh * 0.12)))
        pad = bh * 0.22
        draw.rounded_rectangle(
            [box[0] + pad, box[1] + pad, box[0] + pad + (bw - 2 * pad) * level, box[3] - pad],
            radius=bh * 0.14, fill=accent,
        )
        draw.rounded_rectangle(
            [box[2] + bh * 0.06, py - bh * 0.18, box[2] + bh * 0.22, py + bh * 0.18],
            radius=bh * 0.06, fill=chrome,
        )

    if design == "pacman":
        write(PACMAN_POS["time"], "10:09", _hex_to_rgb(colors[0]), pixel=True)
        write(PACMAN_POS["date"], "MON 09", _hex_to_rgb(colors[3]), pixel=True)
    elif design == "tron":
        write(TRON_POS["label"], "T H E  G R I D", chrome)
        write(TRON_POS["time"], "10:09", white)
        write(TRON_POS["date"], "MON 09", accent)
    elif design == "analog":
        canvas.alpha_composite(_tint(lib.image("reticle"), scanner))
        # A conventional 10:09:30 pose.
        canvas.alpha_composite(_tint(lib.image("hand_hour"), white).rotate(-300, resample=Image.BICUBIC))
        canvas.alpha_composite(_tint(lib.image("hand_minute"), white).rotate(-54, resample=Image.BICUBIC))
        canvas.alpha_composite(_tint(lib.image("hand_second"), alert).rotate(-180, resample=Image.BICUBIC))
        canvas.alpha_composite(_tint(lib.image("center_cap"), white))
        draw = ImageDraw.Draw(canvas)
        write(ANALOG_POS["date"], "MON 09", accent)
        write(ANALOG_POS["hull"], "62", alert)
        battery(ANALOG_POS["battery"])
    else:
        write(HUD_POS["callsign"], "S T A R  F I G H T E R", chrome)
        write(HUD_POS["time"], "10:09", white)
        write(HUD_POS["date"], "MON 09", accent)
        write(HUD_POS["hull_label"], "HULL", chrome)
        write(HUD_POS["hull"], "62", alert)
        write(HUD_POS["temp_label"], "TEMP", chrome)
        write(HUD_POS["temp"], "18\u00b0", scanner)
        battery(HUD_POS["battery"])

    preview = canvas.convert("RGB").resize((w * 2, h * 2), Image.LANCZOS)
    buffer = io.BytesIO()
    preview.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


def _pad_square(frames, width: int, height: int, side: int):
    """Centre each frame on a black square of the given side."""
    ox, oy = (side - width) // 2, (side - height) // 2
    for frame in frames:
        square = Image.new("RGB", (side, side), (0, 0, 0))
        square.paste(frame.convert("RGB"), (ox, oy))
        yield square


def _attach_movie(lib: AssetLibrary, design: str, size: str, seconds: float, seed: int) -> None:
    """Render the design's animation, encode it, and register the movie.

    One frame is kept as a still so the face thumbnail shows the animation without
    the whole sequence having to be held in memory.
    """
    import tempfile
    from pathlib import Path

    if design == "tron":
        from . import lightcycle as engine
        name = f"LightCycleArena-{size}.mov"
        frames = engine.render_match(lib.width, lib.height, seconds=seconds, seed=seed)
        capture = int(seconds * engine.FPS * 0.62)
    else:
        from . import pacman as engine
        name = f"PacManBoard-{size}.mov"
        chosen, _ = engine.find_winning_seed(start=seed)
        frames = engine.render_match(lib.width, lib.height, seed=chosen)
        capture = engine.still_frame_index(chosen)

    # Clockology shows a movie in a square viewport whose side is the layer scale
    # times the screen width, cropping a portrait movie top and bottom. Padding
    # the movie to a square as tall as the screen, then scaling the layer by
    # height/width, maps every frame pixel onto the screen 1:1.
    enc_w, enc_h = lib.width, lib.height
    square = DESIGNS[design].get("square_video")
    if square:
        side = max(lib.width, lib.height)
        frames = _pad_square(frames, lib.width, lib.height, side)
        enc_w = enc_h = side
        lib.video_scale = side / lib.width

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        data, still = engine.encode_mov(
            frames, enc_w, enc_h, path, capture_index=capture
        )
    if square:
        ox, oy = (enc_w - lib.width) // 2, (enc_h - lib.height) // 2
        still = still.crop((ox, oy, ox + lib.width, oy + lib.height))
    lib.movie_filename = lib.add_raw(name, data)
    lib.put_image("arena_still", still.convert("RGBA"))


def build_face(design: str, size: str, variant: str, seed: int = 7,
               seconds: float = 12.0, font: str = "", video_scale: float = 1.0) -> dict:
    """Assemble the full archive graph for one face."""
    width, height = CANVASES[size]
    spec = DESIGNS[design]
    colors = palette_for(design, variant)
    lib = AssetLibrary(width, height, seed)
    lib.clock_font = font
    lib.video_scale = video_scale

    if design in ("tron", "pacman"):
        _attach_movie(lib, design, size, seconds, seed)

    layers = spec["layers"](lib)
    thumbnail = render_thumbnail(lib, design, colors)

    return {
        "faceSetting": {
            "title": f"{spec['title']} ({font or variant.title()})",
            "uniqueID": str(uuid.uuid4()).upper(),
            "filterCategories": spec["categories"],
            "faceColors": colors,
            "lastUpdateDate": 0.0,
            "faceLayers": layers,
        },
        "mediaAssets": lib.assets,
        "thumbnailImageData": thumbnail,
        "syncModePreference": "",
    }
