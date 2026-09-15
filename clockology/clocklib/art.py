"""Procedural artwork for the Star Fighter watch face.

Everything is generated at `SUPERSAMPLE` times the target resolution and then
resampled down, which is how the thin HUD strokes stay smooth on the watch.
Clockology expects every image asset to be the full size of the face canvas,
with the rotation anchor of a hand at the centre of its image.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

SUPERSAMPLE = 4


def _canvas(w: int, h: int):
    img = Image.new("RGBA", (w * SUPERSAMPLE, h * SUPERSAMPLE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _finish(img: Image.Image, w: int, h: int) -> Image.Image:
    return img.resize((w, h), Image.LANCZOS)


def _polar(cx: float, cy: float, radius: float, degrees: float):
    """Screen position `radius` away from centre, measured clockwise from 12."""
    rad = math.radians(degrees - 90.0)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)


def starfield(w: int, h: int, seed: int = 7) -> Image.Image:
    """Deep-space backdrop: a nebula wash, dust, stars and a few bright ones."""
    rng = random.Random(seed)
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    W, H = w * s, h * s

    # Two soft nebula blooms, painted large and blurred into a haze.
    neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(neb)
    for cx, cy, rad, color in (
        (W * 0.24, H * 0.20, W * 0.46, (32, 74, 140, 92)),
        (W * 0.82, H * 0.80, W * 0.42, (92, 34, 120, 78)),
        (W * 0.62, H * 0.32, W * 0.26, (18, 96, 108, 60)),
    ):
        ndraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=color)
    neb = neb.filter(ImageFilter.GaussianBlur(radius=W * 0.10))
    img.alpha_composite(neb)

    # Faint dust band across the face.
    dust = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dust)
    for _ in range(420):
        t = rng.random()
        x = W * (-0.1 + 1.2 * t)
        y = H * (0.18 + 0.72 * t) + rng.gauss(0, H * 0.055)
        r = rng.uniform(0.4, 1.5) * s
        a = rng.randint(18, 70)
        ddraw.ellipse([x - r, y - r, x + r, y + r], fill=(180, 210, 255, a))
    dust = dust.filter(ImageFilter.GaussianBlur(radius=1.2 * s))
    img.alpha_composite(dust)

    # Field stars.
    for _ in range(260):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.uniform(0.35, 1.5) * s
        warmth = rng.random()
        color = (
            int(200 + 55 * warmth),
            int(214 + 32 * (1 - abs(warmth - 0.5) * 2)),
            255,
            rng.randint(70, 230),
        )
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # Hero stars with diffraction spikes.
    for _ in range(9):
        x, y = rng.uniform(W * 0.06, W * 0.94), rng.uniform(H * 0.06, H * 0.94)
        r = rng.uniform(1.6, 2.6) * s
        spike = r * rng.uniform(4.0, 7.0)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.line([x - spike, y, x + spike, y], fill=(190, 225, 255, 150), width=max(1, int(0.7 * s)))
        gdraw.line([x, y - spike, x, y + spike], fill=(190, 225, 255, 150), width=max(1, int(0.7 * s)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=0.9 * s))
        img.alpha_composite(glow)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))

    return _finish(img, w, h)


def hud_ring(w: int, h: int) -> Image.Image:
    """Minute/hour tick dial plus a broken outer rail. Drawn white, meant to be tinted."""
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    radius = min(w, h) * s / 2

    rail = radius * 0.965
    # Outer rail, four arcs with gaps on the diagonals.
    box = [cx - rail, cy - rail, cx + rail, cy + rail]
    for start in (-83, 7, 97, 187):
        draw.arc(box, start=start, end=start + 76, fill=(255, 255, 255, 120), width=max(1, int(0.9 * s)))

    for i in range(60):
        angle = i * 6.0
        major = i % 5 == 0
        cardinal = i % 15 == 0
        outer = radius * 0.932
        length = radius * (0.085 if cardinal else 0.060 if major else 0.030)
        width = max(1, int((3.4 if cardinal else 2.4 if major else 1.3) * s))
        alpha = 255 if major else 130
        x1, y1 = _polar(cx, cy, outer, angle)
        x2, y2 = _polar(cx, cy, outer - length, angle)
        draw.line([x1, y1, x2, y2], fill=(255, 255, 255, alpha), width=width)

    # Small pips inboard of the quarters, pointing back out at the dial.
    for angle in (0, 90, 180, 270):
        tip = radius * 0.836
        back = radius * 0.800
        half = 1.9
        p0 = _polar(cx, cy, tip, angle)
        p1 = _polar(cx, cy, back, angle - half)
        p2 = _polar(cx, cy, back, angle + half)
        draw.polygon([p0, p1, p2], fill=(255, 255, 255, 190))

    return _finish(img, w, h)


def hud_frame(w: int, h: int) -> Image.Image:
    """Corner targeting brackets and edge rails. Drawn white, meant to be tinted."""
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    W, H = w * s, h * s
    inset = min(W, H) * 0.055
    arm = min(W, H) * 0.115
    width = max(1, int(2.6 * s))
    color = (255, 255, 255, 235)

    corners = [
        (inset, inset, 1, 1),
        (W - inset, inset, -1, 1),
        (inset, H - inset, 1, -1),
        (W - inset, H - inset, -1, -1),
    ]
    for x, y, dx, dy in corners:
        draw.line([x, y, x + arm * dx, y], fill=color, width=width)
        draw.line([x, y, x, y + arm * dy], fill=color, width=width)

    # Edge rails with a centre notch, top and bottom.
    rail = min(W, H) * 0.20
    thin = max(1, int(1.6 * s))
    for y, dy in ((inset * 0.62, 1), (H - inset * 0.62, -1)):
        draw.line([W / 2 - rail, y, W / 2 - rail * 0.22, y], fill=(255, 255, 255, 120), width=thin)
        draw.line([W / 2 + rail * 0.22, y, W / 2 + rail, y], fill=(255, 255, 255, 120), width=thin)
        draw.line([W / 2, y, W / 2, y + 5 * s * dy], fill=(255, 255, 255, 170), width=thin)

    return _finish(img, w, h)


def reticle(w: int, h: int) -> Image.Image:
    """Centre targeting reticle: dashed ring, gapped crosshair, range pips."""
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    radius = min(w, h) * s / 2
    ring = radius * 0.415

    box = [cx - ring, cy - ring, cx + ring, cy + ring]
    for start in range(0, 360, 30):
        draw.arc(box, start=start, end=start + 16, fill=(255, 255, 255, 150), width=max(1, int(1.5 * s)))

    gap = ring * 0.34
    reach = ring * 1.24
    width = max(1, int(1.8 * s))
    for angle in (0, 90, 180, 270):
        x1, y1 = _polar(cx, cy, gap, angle)
        x2, y2 = _polar(cx, cy, reach, angle)
        draw.line([x1, y1, x2, y2], fill=(255, 255, 255, 190), width=width)

    for angle in (45, 135, 225, 315):
        x1, y1 = _polar(cx, cy, ring * 0.86, angle)
        x2, y2 = _polar(cx, cy, ring * 1.02, angle)
        draw.line([x1, y1, x2, y2], fill=(255, 255, 255, 120), width=max(1, int(1.2 * s)))

    return _finish(img, w, h)


def radar_sweep(w: int, h: int) -> Image.Image:
    """A fading wedge trailing a bright leading edge, used as the second hand."""
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    reach = min(w, h) * s * 0.455
    span = 58.0

    # Build the trail from thin slices so the alpha ramps smoothly.
    steps = 120
    for i in range(steps):
        t = i / (steps - 1)
        a0 = -span * t
        a1 = -span * (t + 1.0 / steps) - 0.35
        alpha = int(72 * (1.0 - t) ** 1.7)
        if alpha <= 0:
            continue
        draw.polygon(
            [(cx, cy), _polar(cx, cy, reach, a0), _polar(cx, cy, reach, a1)],
            fill=(255, 255, 255, alpha),
        )

    # Leading edge.
    draw.line([cx, cy, *_polar(cx, cy, reach, 0)], fill=(255, 255, 255, 230), width=max(1, int(1.8 * s)))
    hub = 3.4 * s
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=(255, 255, 255, 255))
    return _finish(img, w, h)


def _blade(draw, cx, cy, length, half_base, half_waist, tail):
    """One swept fighter-style hand, nose at 12 o'clock and pivot at the centre."""
    body = [
        (cx, cy - length),
        (cx + half_waist, cy - length * 0.55),
        (cx + half_base, cy - length * 0.05),
        (cx + half_base * 0.45, cy + tail),
        (cx - half_base * 0.45, cy + tail),
        (cx - half_base, cy - length * 0.05),
        (cx - half_waist, cy - length * 0.55),
    ]
    draw.polygon(body, fill=(255, 255, 255, 255))


def hand_hour(w: int, h: int) -> Image.Image:
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    radius = min(w, h) * s / 2
    _blade(draw, cx, cy, length=radius * 0.500,
           half_base=radius * 0.055, half_waist=radius * 0.025, tail=radius * 0.080)
    return _finish(img, w, h)


def hand_minute(w: int, h: int) -> Image.Image:
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    radius = min(w, h) * s / 2
    _blade(draw, cx, cy, length=radius * 0.800,
           half_base=radius * 0.036, half_waist=radius * 0.015, tail=radius * 0.100)
    return _finish(img, w, h)


def hand_second(w: int, h: int) -> Image.Image:
    """Hairline needle carrying a small delta fighter at its tip."""
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    radius = min(w, h) * s / 2
    length = radius * 0.845
    color = (255, 255, 255, 255)

    draw.line([cx, cy + radius * 0.20, cx, cy - length * 0.90], fill=color, width=max(1, int(1.5 * s)))

    ship = radius * 0.072
    tip = cy - length
    draw.polygon(
        [
            (cx, tip),
            (cx + ship * 0.92, tip + ship * 1.55),
            (cx + ship * 0.30, tip + ship * 1.20),
            (cx, tip + ship * 1.72),
            (cx - ship * 0.30, tip + ship * 1.20),
            (cx - ship * 0.92, tip + ship * 1.55),
        ],
        fill=color,
    )
    hub = 2.6 * s
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=color)
    return _finish(img, w, h)


def center_cap(w: int, h: int) -> Image.Image:
    img, draw = _canvas(w, h)
    s = SUPERSAMPLE
    cx, cy = w * s / 2, h * s / 2
    outer = min(w, h) * s * 0.022
    draw.ellipse([cx - outer, cy - outer, cx + outer, cy + outer], fill=(255, 255, 255, 255))
    inner = outer * 0.42
    draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=(0, 0, 0, 255))
    return _finish(img, w, h)
