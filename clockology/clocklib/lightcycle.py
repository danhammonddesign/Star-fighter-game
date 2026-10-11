"""A light cycle match, simulated and rendered to a looping QuickTime movie.

Clockology animates a face through a `VideoTexture` layer, which takes a `.mov`
asset and a loop count. This module plays out rounds of a light cycle game on a
grid and encodes the result, opening and closing on black so the loop is seamless.
"""

from __future__ import annotations

import math
import random
import subprocess
from collections import deque

from PIL import Image, ImageDraw, ImageFilter

RENDER_SCALE = 2      # draw at 2x, resample down for clean glow
FPS = 24
SUBSTEPS = 2          # animation frames per grid move
TARGET_CELL_PX = 16   # desired on-screen size of one grid cell

DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # N, E, S, W

# The clock sits in a solid block in the middle of the arena. Riders treat it as
# wall, so they have to route around it. Fractions of the frame, generous enough
# that it still covers the time and date if the watch scales the movie a little.
CLOCK_BOX = (0.14, 0.28, 0.86, 0.66)  # left, top, right, bottom


def clock_box_cells(cols: int, rows: int):
    """Grid bounds of the clock block, inclusive."""
    left, top, right, bottom = CLOCK_BOX
    return (int(left * cols), int(top * rows), int(right * cols) - 1, int(bottom * rows) - 1)


def _turns(direction):
    index = DIRECTIONS.index(direction)
    return [direction, DIRECTIONS[(index + 1) % 4], DIRECTIONS[(index - 1) % 4]]


class Rider:
    def __init__(self, col, row, direction, color, name):
        self.col, self.row = col, row
        self.direction = direction
        self.color = color
        self.name = name
        self.path = [(col, row)]
        self.alive = True

    @property
    def head(self):
        return self.col, self.row


class Arena:
    """Grid state for one round, plus the very small amount of AI each rider needs."""

    def __init__(self, cols, rows, rng):
        self.cols, self.rows, self.rng = cols, rows, rng
        c0, r0, c1, r1 = clock_box_cells(cols, rows)
        # Cells are keyed (col, row) throughout.
        self.block = {(c, r) for c in range(c0, c1 + 1) for r in range(r0, r1 + 1)}
        # Start clear of the block, one above it and one below.
        self.riders = [
            Rider(c0, 2, (1, 0), "player", "player"),
            Rider(c1, rows - 3, (-1, 0), "rival", "rival"),
        ]
        self.occupied = {r.head for r in self.riders} | self.block
        self.derezz = None  # (col, row, age) once a rider crashes

    def _free(self, col, row):
        return (
            0 <= col < self.cols
            and 0 <= row < self.rows
            and (col, row) not in self.occupied
        )

    def _open_space(self, start, cap=140):
        """Flood fill from a cell, capped, as a cheap 'how much room is left' score."""
        if not self._free(*start):
            return 0
        seen = {start}
        queue = deque([start])
        while queue and len(seen) < cap:
            col, row = queue.popleft()
            for dc, dr in DIRECTIONS:
                cell = (col + dc, row + dr)
                if cell not in seen and self._free(*cell):
                    seen.add(cell)
                    queue.append(cell)
        return len(seen)

    def _choose(self, rider):
        scored = []
        for direction in _turns(rider.direction):
            cell = (rider.col + direction[0], rider.row + direction[1])
            if not self._free(*cell):
                continue
            score = self._open_space(cell)
            if direction == rider.direction:
                score *= 1.06  # hold a line unless turning is clearly better
            score *= self.rng.uniform(0.88, 1.12)
            scored.append((score, direction))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def step(self):
        """Advance one grid move. Returns False once the round is over."""
        for rider in self.riders:
            if not rider.alive:
                continue
            direction = self._choose(rider)
            if direction is None:
                rider.alive = False
                self.derezz = (rider.col, rider.row, 0)
                return False
            rider.direction = direction
            rider.col += direction[0]
            rider.row += direction[1]
            rider.path.append(rider.head)
            self.occupied.add(rider.head)
        return True


class Renderer:
    def __init__(self, width, height, cols, rows, palette):
        self.w, self.h = width * RENDER_SCALE, height * RENDER_SCALE
        self.out_size = (width, height)
        self.cols, self.rows = cols, rows
        self.cell_w = self.w / cols
        self.cell_h = self.h / rows
        self.palette = palette
        self._grid = self._draw_grid()

    def _pixel(self, col, row):
        return (col + 0.5) * self.cell_w, (row + 0.5) * self.cell_h

    def _draw_grid(self):
        """The static arena floor: faint lines and a brighter perimeter."""
        grid = Image.new("RGB", (self.w, self.h), self.palette["void"])
        draw = ImageDraw.Draw(grid)
        line = self.palette["grid"]
        width = max(1, int(RENDER_SCALE * 0.5))
        for col in range(self.cols + 1):
            x = col * self.cell_w
            draw.line([x, 0, x, self.h], fill=line, width=width)
        for row in range(self.rows + 1):
            y = row * self.cell_h
            draw.line([0, y, self.w, y], fill=line, width=width)

        edge = max(1, int(RENDER_SCALE * 1.6))
        draw.rectangle([0, 0, self.w - 1, self.h - 1], outline=self.palette["border"], width=edge)

        # The clock block: solid black so no trail shows through behind the time.
        c0, r0, c1, r1 = clock_box_cells(self.cols, self.rows)
        box = [c0 * self.cell_w, r0 * self.cell_h,
               (c1 + 1) * self.cell_w, (r1 + 1) * self.cell_h]
        draw.rectangle(box, fill=self.palette["void"])
        draw.rectangle(box, outline=self.palette["border"], width=edge)
        return grid

    def frame(self, arena, fraction, effects, brightness=1.0):
        canvas = self._grid.copy()
        trails = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(trails)
        thickness = max(2, int(self.cell_w * 0.34))

        for rider in arena.riders:
            color = self.palette[rider.color]
            points = [self._pixel(c, r) for c, r in rider.path]
            if rider.alive and len(points) >= 1:
                # Slide the head between its last cell and the next one.
                hx, hy = points[-1]
                points = points + [(hx + rider.direction[0] * self.cell_w * fraction,
                                    hy + rider.direction[1] * self.cell_h * fraction)]
            if len(points) >= 2:
                draw.line(points, fill=color + (255,), width=thickness, joint="curve")

            if rider.alive:
                cx, cy = points[-1]
                size = self.cell_w * 0.40
                draw.ellipse([cx - size, cy - size, cx + size, cy + size], fill=(255, 255, 255, 255))

        flash = 0.0
        for col, row, age in effects:
            if age > 10:
                continue
            cx, cy = self._pixel(col, row)
            radius = self.cell_w * (0.5 + age * 0.85)
            alpha = max(0, int(255 * (1.0 - age / 10.0)))
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                         outline=self.palette["flash"] + (alpha,),
                         width=max(2, int(RENDER_SCALE * 2.4)))
            if age <= 2:
                flash = max(flash, (3 - age) / 3.0 * 0.55)

        glow = trails.filter(ImageFilter.GaussianBlur(radius=self.cell_w * 0.42))
        canvas.paste(glow, (0, 0), glow)
        canvas.paste(glow, (0, 0), glow)  # twice, for a hotter core
        canvas.paste(trails, (0, 0), trails)

        if flash:
            white = Image.new("RGB", (self.w, self.h), self.palette["flash"])
            canvas = Image.blend(canvas, white, flash)

        canvas = canvas.resize(self.out_size, Image.LANCZOS)
        if brightness < 1.0:
            canvas = canvas.point(lambda v: int(v * brightness))
        return canvas


def make_palette(colors: dict) -> dict:
    return colors


DEFAULT_PALETTE = {
    "void": (0, 0, 0),
    "grid": (7, 30, 48),
    "border": (0, 110, 160),
    "player": (0, 194, 255),
    "rival": (255, 118, 0),
    "flash": (200, 245, 255),
}


def render_match(width: int, height: int, seconds: float = 9.0, seed: int = 11,
                 palette: dict | None = None):
    """Yield every frame of the loop, fading up from and back down to black."""
    palette = palette or DEFAULT_PALETTE
    rng = random.Random(seed)
    cols = max(14, round(width / TARGET_CELL_PX))
    rows = max(14, round(height / TARGET_CELL_PX))
    renderer = Renderer(width, height, cols, rows, palette)

    total = int(seconds * FPS)
    fade = int(FPS * 0.5)
    arena = Arena(cols, rows, rng)
    effects: list[tuple[int, int, int]] = []
    round_over_at = None

    for index in range(total):
        if index < fade:
            brightness = (index + 1) / fade
        elif index >= total - fade:
            brightness = max(0.0, (total - index) / fade)
        else:
            brightness = 1.0

        substep = index % SUBSTEPS
        if substep == 0 and round_over_at is None:
            if not arena.step():
                round_over_at = index
                col, row, _ = arena.derezz
                effects.append((col, row, 0))

        if round_over_at is not None:
            age = index - round_over_at
            effects = [(c, r, age) for c, r, _ in effects]
            # Give the crash a moment to play, then rack up a fresh round.
            if age > 16 and index < total - fade * 2:
                arena = Arena(cols, rows, rng)
                effects = []
                round_over_at = None

        fraction = (substep + 1) / SUBSTEPS if round_over_at is None else 0.0
        yield renderer.frame(arena, fraction, effects, brightness)


def encode_mov(frames, width: int, height: int, path, crf: int = 22, capture_index=None):
    """Pipe frames into ffmpeg and return the QuickTime bytes.

    `capture_index` keeps a copy of one frame as a still, so the face thumbnail can
    show the match without buffering the whole sequence in memory.
    """
    import imageio_ffmpeg

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(FPS),
        "-i", "-", "-an",
        "-c:v", "libx264", "-profile:v", "main", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-crf", str(crf), "-g", str(FPS * 2),
        "-movflags", "+faststart", "-f", "mov", str(path),
    ]
    still = None
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    for index, frame in enumerate(frames):
        frame = frame.convert("RGB")
        if index == capture_index:
            still = frame.copy()
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the light cycle loop")
    data = open(path, "rb").read()
    return (data, still) if capture_index is not None else data
