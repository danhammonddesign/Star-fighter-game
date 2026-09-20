"""A maze chase game, simulated and rendered to a looping QuickTime movie.

The maze is reshaped from the arcade's tall 28x31 board into a 21x25 board that
suits a watch, and the ghost house in the middle is enlarged into an empty
chamber where the watch face puts the clock. Everything else follows the arcade:
blue double-line walls, a pink gate, scatter/chase ghost targeting, power pellets
that turn the ghosts blue, and a maze flash when the board is cleared.

The hero always clears the board — see `render_match`, which re-runs the
simulation with a fresh seed if he is ever caught.
"""

from __future__ import annotations

import math
import random
import subprocess
from collections import deque

from PIL import Image, ImageDraw

RENDER_SCALE = 2
FPS = 24
FRAMES_PER_STEP = 2          # hero moves one tile every N frames
GHOST_FRAMES_PER_STEP = 3    # ghosts are slower, so the hero can always escape
FRIGHT_STEPS = 34            # how many ghost steps a power pellet lasts

# Hero caution, tuned by sweeping win rate over many seeds (see AI notes in README).
THREAT_PENALTY = {3: 60.0, 5: 18.0, 7: 4.0}
ROOM_PENALTY = {8: 120.0, 16: 45.0, 26: 12.0}
ROOM_HORIZON = 12

WALL, PELLET, POWER, EMPTY, GATE, CHAMBER = "#", ".", "o", " ", "=", "X"

# 19 columns x 21 rows. Row 14 is the warp tunnel; rows 8-13 hold the chamber.
MAZE = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.##.###.#.###.##.#",
    "#.................#",
    "#.##.#.##.##.#.##.#",
    "#....#..#.#..#....#",
    "#.##.###   ###.##.#",
    "#...####===####...#",
    "#.#.#XXXXXXXXX#.#.#",
    "#.#.#XXXXXXXXX#.#.#",
    "#...#XXXXXXXXX#...#",
    "#.#.#XXXXXXXXX#.#.#",
    "#.#.###########.#.#",
    "  ...............  ",
    "#.##.###.#.###.##.#",
    "#..#.....#.....#..#",
    "##.#.###.#.###.#.##",
    "#........#........#",
    "#o##...#####...##o#",
    "###################",
]

ROWS, COLS = len(MAZE), len(MAZE[0])
HERO_START = (14, 9)
GATE_TILE = (7, 9)       # just above the gate; ghosts emerge here
SCATTER = {"blinky": (-2, COLS + 1), "pinky": (-2, -2),
           "inky": (ROWS + 1, COLS + 1), "clyde": (ROWS + 1, -2)}

UP, DOWN, LEFT, RIGHT = (-1, 0), (1, 0), (0, -1), (0, 1)
MOVES = [UP, LEFT, DOWN, RIGHT]  # arcade tie-break order

COLORS = {
    "wall": (33, 33, 222),
    "wall_flash": (255, 255, 255),
    "gate": (255, 184, 255),
    "pellet": (255, 184, 174),
    "hero": (255, 255, 0),
    "blinky": (255, 0, 0),
    "pinky": (255, 184, 255),
    "inky": (0, 255, 255),
    "clyde": (255, 184, 82),
    "fright": (33, 33, 255),
    "fright_end": (255, 255, 255),
    "eye": (255, 255, 255),
    "pupil": (33, 33, 222),
}


def wrap(row: int, col: int):
    return row, col % COLS


def tile_at(row: int, col: int) -> str:
    if not 0 <= row < ROWS:
        return WALL
    return MAZE[row][col % COLS]


def walkable(row: int, col: int, *, ghost: bool = False) -> bool:
    tile = tile_at(row, col)
    if tile == GATE:
        return ghost
    return tile not in (WALL, CHAMBER)


class Actor:
    def __init__(self, row, col, direction, name):
        self.row, self.col = row, col
        self.direction = direction
        self.name = name
        self.prev = (row, col)
        self.progress = 0.0   # 0..1 between prev tile and current tile

    def position(self):
        """Interpolated tile position, handling a wrap across the tunnel."""
        pr, pc = self.prev
        dc = self.col - pc
        if dc > 1:
            pc += COLS
        elif dc < -1:
            pc -= COLS
        return (pr + (self.row - pr) * self.progress,
                pc + (self.col - pc) * self.progress)


class Ghost(Actor):
    def __init__(self, row, col, direction, name, release):
        super().__init__(row, col, direction, name)
        self.release = release      # ghost-steps to wait before leaving
        self.frightened = 0
        self.eaten = False
        self.active = False


class Game:
    def __init__(self, rng):
        self.rng = rng
        self.pellets = {(r, c) for r in range(ROWS) for c in range(COLS)
                        if MAZE[r][c] == PELLET}
        self.powers = {(r, c) for r in range(ROWS) for c in range(COLS)
                       if MAZE[r][c] == POWER}
        self.hero = Actor(*HERO_START, LEFT, "hero")
        self.ghosts = [
            Ghost(*GATE_TILE, LEFT, "blinky", 0),
            Ghost(*GATE_TILE, UP, "pinky", 6),
            Ghost(*GATE_TILE, UP, "inky", 16),
            Ghost(*GATE_TILE, UP, "clyde", 28),
        ]
        self.steps = 0
        self.ghost_steps = 0
        self.caught = False
        self.won = False

    # -- pathing ----------------------------------------------------------
    @staticmethod
    def _dist_map(sources, ghost=False):
        """Multi-source BFS: maze distance from every tile to the nearest source."""
        dist = {}
        queue = deque()
        for cell in sources:
            dist[cell] = 0
            queue.append(cell)
        while queue:
            row, col = queue.popleft()
            for direction in MOVES:
                cell = wrap(row + direction[0], col + direction[1])
                if cell in dist or not walkable(*cell, ghost=ghost):
                    continue
                dist[cell] = dist[(row, col)] + 1
                queue.append(cell)
        return dist

    def _safe_region(self, start, threat, cap=70):
        """How much maze the hero can still reach before a ghost could cut it off.

        Uses the speed ratio: the hero covers a tile in FRAMES_PER_STEP frames and
        a ghost in GHOST_FRAMES_PER_STEP, so he owns a tile only if he arrives first.
        """
        seen = {start}
        depth = {start: 0}
        queue = deque([start])
        while queue and len(seen) < cap:
            current = queue.popleft()
            for direction in MOVES:
                cell = wrap(current[0] + direction[0], current[1] + direction[1])
                if cell in seen or not walkable(*cell):
                    continue
                steps = depth[current] + 1
                if steps * FRAMES_PER_STEP >= threat.get(cell, 99) * GHOST_FRAMES_PER_STEP:
                    continue
                depth[cell] = steps
                seen.add(cell)
                queue.append(cell)
        return len(seen)

    def _hero_goal(self):
        """Pick the next step: head for food, but never walk into a ghost.

        Two distance fields do the work — one from every ghost, one from every
        remaining pellet — so each candidate move is scored in a single lookup.
        """
        hunters = [(g.row, g.col) for g in self.ghosts
                   if g.active and not g.frightened and not g.eaten]
        prey = [(g.row, g.col) for g in self.ghosts
                if g.active and g.frightened and not g.eaten]
        threat = self._dist_map(hunters) if hunters else {}

        here = (self.hero.row, self.hero.col)
        # Chase blue ghosts when they are worth reaching, otherwise eat pellets.
        goals = set(self.pellets | self.powers)
        if prey:
            prey_field = self._dist_map(prey)
            if prey_field.get(here, 99) <= 7:
                goals = set(prey)
        if not goals:
            return None
        food = self._dist_map(goals)

        best, best_score = None, None
        for direction in MOVES:
            cell = wrap(here[0] + direction[0], here[1] + direction[1])
            if not walkable(*cell):
                continue
            gap = threat.get(cell, 99)
            if gap <= 1:
                continue  # that is a ghost, or the tile it is about to occupy
            score = food.get(cell, 99) * 1.0
            for limit, penalty in sorted(THREAT_PENALTY.items()):
                if gap < limit:
                    score += penalty
                    break
            # Refuse to be herded into a pocket he cannot get back out of.
            if hunters and gap < ROOM_HORIZON:
                room = self._safe_region(cell, threat)
                for limit, penalty in sorted(ROOM_PENALTY.items()):
                    if room < limit:
                        score += penalty
                        break
            if direction == self.hero.direction:
                score -= 0.3  # prefer holding a line, as the arcade input does
            if best_score is None or score < best_score:
                best, best_score = direction, score

        if best is None:
            # Boxed in: take whatever puts the most maze between us and them.
            options = [d for d in MOVES if walkable(*wrap(here[0] + d[0], here[1] + d[1]))]
            if not options:
                return None
            best = max(options, key=lambda d: threat.get(wrap(here[0] + d[0], here[1] + d[1]), 99))
        return best

    # -- simulation -------------------------------------------------------
    def step_hero(self):
        direction = self._hero_goal()
        if direction is None:
            return
        self.hero.prev = (self.hero.row, self.hero.col)
        self.hero.direction = direction
        self.hero.row, self.hero.col = wrap(self.hero.row + direction[0],
                                            self.hero.col + direction[1])
        here = (self.hero.row, self.hero.col)
        self.pellets.discard(here)
        if here in self.powers:
            self.powers.discard(here)
            for ghost in self.ghosts:
                if not ghost.eaten:
                    ghost.frightened = FRIGHT_STEPS
        if not self.pellets and not self.powers:
            self.won = True
        self.steps += 1

    def _ghost_target(self, ghost):
        hero = (self.hero.row, self.hero.col)
        if ghost.eaten:
            return GATE_TILE
        if ghost.frightened:
            return None
        # Scatter for a spell, then chase, the way the arcade alternates.
        if (self.ghost_steps // 60) % 3 == 2:
            return SCATTER[ghost.name]
        if ghost.name == "blinky":
            return hero
        if ghost.name == "pinky":
            return (hero[0] + self.hero.direction[0] * 4,
                    hero[1] + self.hero.direction[1] * 4)
        if ghost.name == "inky":
            blinky = self.ghosts[0]
            pivot = (hero[0] + self.hero.direction[0] * 2,
                     hero[1] + self.hero.direction[1] * 2)
            return (pivot[0] * 2 - blinky.row, pivot[1] * 2 - blinky.col)
        distance = math.hypot(ghost.row - hero[0], ghost.col - hero[1])
        return hero if distance > 8 else SCATTER["clyde"]

    def step_ghost(self, ghost):
        if not ghost.active:
            if self.ghost_steps >= ghost.release:
                ghost.active = True
            else:
                return
        options = []
        back = (-ghost.direction[0], -ghost.direction[1])
        for direction in MOVES:
            if direction == back:
                continue
            cell = wrap(ghost.row + direction[0], ghost.col + direction[1])
            if walkable(*cell, ghost=True):
                options.append((direction, cell))
        if not options:
            options = [(back, wrap(ghost.row + back[0], ghost.col + back[1]))]

        target = self._ghost_target(ghost)
        if target is None:
            direction, cell = self.rng.choice(options)
        else:
            direction, cell = min(
                options,
                key=lambda item: math.hypot(item[1][0] - target[0],
                                            item[1][1] - target[1]),
            )
        ghost.prev = (ghost.row, ghost.col)
        ghost.direction = direction
        ghost.row, ghost.col = cell
        if ghost.eaten and (ghost.row, ghost.col) == GATE_TILE:
            ghost.eaten = False
            ghost.frightened = 0
        if ghost.frightened:
            ghost.frightened -= 1

    def collide(self):
        hero = (self.hero.row, self.hero.col)
        for ghost in self.ghosts:
            if not ghost.active or ghost.eaten:
                continue
            if (ghost.row, ghost.col) == hero or (
                (ghost.row, ghost.col) == self.hero.prev and ghost.prev == hero
            ):
                if ghost.frightened:
                    ghost.eaten = True
                    ghost.frightened = 0
                else:
                    self.caught = True


# -- rendering ------------------------------------------------------------

class MazeRenderer:
    """Draws the board. Walls are cached, since only the sprites and pellets move."""

    def __init__(self, width, height):
        self.out_size = (width, height)
        self.tile = int(min(width / COLS, height / ROWS)) * RENDER_SCALE
        self.w, self.h = width * RENDER_SCALE, height * RENDER_SCALE
        self.ox = (self.w - self.tile * COLS) / 2
        self.oy = (self.h - self.tile * ROWS) / 2
        self.base = self._draw_walls(COLORS["wall"])
        self.base_flash = self._draw_walls(COLORS["wall_flash"])

    def xy(self, row, col):
        """Centre of a tile, in render pixels."""
        return self.ox + (col + 0.5) * self.tile, self.oy + (row + 0.5) * self.tile

    def _draw_walls(self, color):
        """Outline every wall block on the sides that face open floor.

        This is how the arcade board is built: the walls are not filled shapes but
        pipes traced around each block, which is why corridors read as channels.
        """
        image = Image.new("RGB", (self.w, self.h), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        tile = self.tile
        pad = tile * 0.30
        thickness = max(2, int(tile * 0.10))
        radius = thickness / 2

        def solid(row, col):
            return tile_at(row, col) in (WALL, CHAMBER)

        def stroke(x0, y0, x1, y1):
            draw.line([x0, y0, x1, y1], fill=color, width=thickness)
            for x, y in ((x0, y0), (x1, y1)):  # round the joins
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)

        # Each edge runs the full width of its tile and is only offset inwards, so
        # neighbouring blocks join up. The ends then step out or in depending on how
        # the wall turns: out for an outer corner, flush to continue, in for an
        # inner corner, which is what makes the pipes meet cleanly.
        def extent(along_open, diagonal_open, near, far):
            if along_open:
                return near + far
            return 0.0 if diagonal_open else -far

        for row in range(ROWS):
            for col in range(COLS):
                if not solid(row, col):
                    continue
                x0 = self.ox + col * tile
                x1 = x0 + tile
                y0 = self.oy + row * tile
                y1 = y0 + tile

                if not solid(row - 1, col):
                    left = x0 + extent(not solid(row, col - 1), not solid(row - 1, col - 1), 0, pad)
                    right = x1 - extent(not solid(row, col + 1), not solid(row - 1, col + 1), 0, pad)
                    stroke(left, y0 + pad, right, y0 + pad)
                if not solid(row + 1, col):
                    left = x0 + extent(not solid(row, col - 1), not solid(row + 1, col - 1), 0, pad)
                    right = x1 - extent(not solid(row, col + 1), not solid(row + 1, col + 1), 0, pad)
                    stroke(left, y1 - pad, right, y1 - pad)
                if not solid(row, col - 1):
                    top = y0 + extent(not solid(row - 1, col), not solid(row - 1, col - 1), 0, pad)
                    bottom = y1 - extent(not solid(row + 1, col), not solid(row + 1, col - 1), 0, pad)
                    stroke(x0 + pad, top, x0 + pad, bottom)
                if not solid(row, col + 1):
                    top = y0 + extent(not solid(row - 1, col), not solid(row - 1, col + 1), 0, pad)
                    bottom = y1 - extent(not solid(row + 1, col), not solid(row + 1, col + 1), 0, pad)
                    stroke(x1 - pad, top, x1 - pad, bottom)

        # Second line just inside the border, the way the arcade frames the board.
        inset = tile * 0.10
        draw.rectangle(
            [self.ox + inset, self.oy + inset,
             self.ox + COLS * tile - inset, self.oy + ROWS * tile - inset],
            outline=color, width=thickness,
        )
        return image

    def _pacman(self, draw, game, frame):
        x, y = self.xy(*game.hero.position())
        radius = self.tile * 0.74
        # Mouth opens and shuts roughly every eight frames, as in the arcade.
        mouth = abs(math.sin(frame * math.pi / 8.0)) * 42.0
        facing = {RIGHT: 0, DOWN: 90, LEFT: 180, UP: 270}[game.hero.direction]
        box = [x - radius, y - radius, x + radius, y + radius]
        if mouth < 2:
            draw.ellipse(box, fill=COLORS["hero"])
        else:
            draw.pieslice(box, facing + mouth, facing - mouth + 360, fill=COLORS["hero"])

    def _ghost(self, draw, ghost, frame, fright_ending):
        x, y = self.xy(*ghost.position())
        half = self.tile * 0.68
        top = y - half
        bottom = y + half * 0.92

        if ghost.eaten:
            body = None
        elif ghost.frightened:
            body = COLORS["fright_end"] if (fright_ending and (frame // 4) % 2) else COLORS["fright"]
        else:
            body = COLORS[ghost.name]

        if body:
            draw.pieslice([x - half, top, x + half, top + half * 2], 180, 360, fill=body)
            draw.rectangle([x - half, y, x + half, bottom - half * 0.30], fill=body)
            # Three feet, swapping phase so the ghost looks like it is shuffling.
            foot = half * 2 / 3
            lift = (frame // 4) % 2
            for i in range(3):
                fx = x - half + foot * i
                peak = bottom if (i % 2 == lift) else bottom - half * 0.30
                draw.polygon([(fx, bottom - half * 0.30), (fx + foot / 2, peak),
                              (fx + foot, bottom - half * 0.30)], fill=body)
            draw.rectangle([x - half, y, x + half, bottom - half * 0.32], fill=body)

        if ghost.frightened and not ghost.eaten:
            pale = COLORS["fright_end"] if not (fright_ending and (frame // 4) % 2) else COLORS["fright"]
            for side in (-1, 1):
                ex = x + side * half * 0.38
                r = half * 0.16
                draw.ellipse([ex - r, y - half * 0.28 - r, ex + r, y - half * 0.28 + r], fill=pale)
            wave = []
            for i in range(7):
                wave.append((x - half * 0.6 + i * half * 0.2,
                             y + half * 0.34 + (half * 0.12 if i % 2 else -half * 0.12)))
            draw.line(wave, fill=pale, width=max(2, int(self.tile * 0.07)))
            return

        # Eyes look the way the ghost is travelling.
        dx, dy = ghost.direction[1], ghost.direction[0]
        for side in (-1, 1):
            ex = x + side * half * 0.38
            ey = y - half * 0.30
            rx, ry = half * 0.30, half * 0.36
            draw.ellipse([ex - rx, ey - ry, ex + rx, ey + ry], fill=COLORS["eye"])
            pr = half * 0.17
            px, py = ex + dx * rx * 0.45, ey + dy * ry * 0.45
            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=COLORS["pupil"])

    def frame(self, game, frame_index, *, flash=None, show_sprites=True):
        base = self.base if flash is None else (self.base_flash if flash else self.base)
        image = base.copy()
        draw = ImageDraw.Draw(image)

        if flash is None:
            for row, col in game.pellets:
                x, y = self.xy(row, col)
                r = self.tile * 0.10
                draw.ellipse([x - r, y - r, x + r, y + r], fill=COLORS["pellet"])
            if (frame_index // 7) % 2 == 0:
                for row, col in game.powers:
                    x, y = self.xy(row, col)
                    r = self.tile * 0.28
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=COLORS["pellet"])

            # The gate across the chamber door.
            gate = [(r, c) for r in range(ROWS) for c in range(COLS) if MAZE[r][c] == GATE]
            for row, col in gate:
                x, y = self.xy(row, col)
                bar = max(2, int(self.tile * 0.12))
                draw.rectangle([x - self.tile / 2, y - bar / 2,
                                x + self.tile / 2, y + bar / 2], fill=COLORS["gate"])

        if show_sprites:
            ending = any(0 < g.frightened < 10 for g in game.ghosts)
            for ghost in game.ghosts:
                if ghost.active:
                    self._ghost(draw, ghost, frame_index, ending)
            self._pacman(draw, game, frame_index)

        return image.resize(self.out_size, Image.LANCZOS)


def _play(seed, limit=9000):
    """Run one match to its end, returning the game and the frame it finished on."""
    game = Game(random.Random(seed))
    frame = 0
    while not game.won and not game.caught and frame < limit:
        frame += 1
        if frame % FRAMES_PER_STEP == 0:
            game.step_hero()
            game.collide()
        if frame % GHOST_FRAMES_PER_STEP == 0:
            for ghost in game.ghosts:
                game.step_ghost(ghost)
            game.ghost_steps += 1
            game.collide()
    return game, frame


def find_winning_seed(start=1, tries=400, max_seconds=34.0):
    """The hero has to win, so search seeds for a clean clear of a sensible length."""
    best = None
    for seed in range(start, start + tries):
        game, frames = _play(seed)
        if not game.won:
            continue
        if frames / FPS <= max_seconds:
            return seed, frames
        if best is None or frames < best[1]:
            best = (seed, frames)
    if best is None:
        raise RuntimeError("no winning match found; loosen the search")
    return best


def still_frame_index(seed, fraction=0.35):
    """A frame that shows the game in full swing: ghosts in their own colours,
    plenty of the board still to clear. Used for the face thumbnail."""
    game = Game(random.Random(seed))
    frame = 0
    total = len(game.pellets) + len(game.powers)
    best = None
    while not game.won and not game.caught and frame < 9000:
        frame += 1
        if frame % FRAMES_PER_STEP == 0:
            game.step_hero()
            game.collide()
        if frame % GHOST_FRAMES_PER_STEP == 0:
            for ghost in game.ghosts:
                game.step_ghost(ghost)
            game.ghost_steps += 1
            game.collide()
        left = (len(game.pellets) + len(game.powers)) / total
        calm = not any(g.frightened or g.eaten for g in game.ghosts)
        # Prefer a frame with his mouth open, so the thumbnail is unmistakable.
        open_mouth = abs(math.sin(frame * math.pi / 8.0)) > 0.75
        if calm and open_mouth and all(g.active for g in game.ghosts) and 0.35 <= left <= 0.72:
            if best is None or abs(left - 0.5) < best[1]:
                best = (frame, abs(left - 0.5))
    return best[0] if best else int(frame * fraction)


def render_match(width: int, height: int, seed: int = 1):
    """Yield every frame of the loop: a full clear, the maze flash, then black."""
    seed, total_frames = find_winning_seed(start=seed)
    renderer = MazeRenderer(width, height)
    game = Game(random.Random(seed))

    frame = 0
    while not game.won and frame < total_frames:
        frame += 1
        if frame % FRAMES_PER_STEP == 0:
            game.step_hero()
            game.collide()
        if frame % GHOST_FRAMES_PER_STEP == 0:
            for ghost in game.ghosts:
                game.step_ghost(ghost)
            game.ghost_steps += 1
            game.collide()
        game.hero.progress = ((frame % FRAMES_PER_STEP) + 1) / FRAMES_PER_STEP
        for ghost in game.ghosts:
            ghost.progress = ((frame % GHOST_FRAMES_PER_STEP) + 1) / GHOST_FRAMES_PER_STEP
        yield renderer.frame(game, frame)

    # Board cleared: the ghosts vanish and the maze flashes, as the arcade does.
    for i in range(int(FPS * 2.0)):
        yield renderer.frame(game, frame + i, flash=(i // 5) % 2 == 1, show_sprites=(i < 6))
    black = Image.new("RGB", (width, height), (0, 0, 0))
    for _ in range(int(FPS * 0.45)):
        yield black


def encode_mov(frames, width, height, path, crf: int = 20, capture_index=None):
    """Pipe frames into ffmpeg and return the QuickTime bytes."""
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
    for index, image in enumerate(frames):
        image = image.convert("RGB")
        if index == capture_index:
            still = image.copy()
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the maze loop")
    data = open(path, "rb").read()
    return (data, still) if capture_index is not None else data
