#!/usr/bin/env python3
"""egwpix -- shared pixel-art kit for the EverGrims ImageFrame "retro backlit" set.

House rules (same as assets/imageframe-paintings/paintings.py):
  * Draw at 64 design px per block (BLOCK). Files are written 2x nearest-neighbour (SCALE), so 128 px per
    block = one Minecraft map per block. Sizes are HEIGHT x WIDTH in blocks and go in the file name
    (out_name('neon_open', 1, 2) -> 'neon_open_1x2.png' is 1 tall, 2 wide; the ImageFrame command takes
    width then height).
  * Every written pixel is a Minecraft 26.3 map colour (PALETTE: 61 base colours x 4 brightness = 244,
    read from the game jar by derive_palette.py into map_palette.json, and identical to the Paper API
    MapPalette the server matches against and to Geyser's Bedrock table). ImageFrame's default
    "nearest-color" mode (no dithering) then maps every pixel to itself: crisp, nothing shifts.
  * GIF delays are multiples of 50 ms: ImageFrame samples an animation in 50 ms ticks.
    Bedrock players see only frame 1, so frame 1 must be a finished still.

Python standard library only. Canvas is a copy of paintings.py's Canvas (same methods, same pixels;
paintings.py itself is not imported because importing it would drop a __pycache__ into that folder and
its Canvas.save() writes there).  Here Canvas.save(path) == save_png(canvas, path), with no implicit frame.

Colours are (r, g, b) tuples everywhere.  Brightness "levels" in this kit run dark -> bright:
level 0 = x135 (LOWEST), 1 = x180 (LOW), 2 = x220 (NORMAL), 3 = x255 (HIGH, the base colour itself).
palette_sheet.png beside this file shows every base colour at L0..L3.

Typical use:
    import sys; sys.path.insert(0, '<scratchpad>/retro-art/kit'); import egwpix as e
    c = e.blocks(1, 2)                                  # 1 tall x 2 wide, 128x64 design px, black
    e.neon_text(c, 10, 20, 'OPEN', e.NEON['red'], scale=3)
    e.glow(c, e.rrect_pixels(2, 2, c.w - 3, c.h - 3, r=6), e.NEON['blue'])
    e.save_png(c, e.out_name('neon_open', 1, 2))        # -> neon_open_1x2.png, 256x128
    frames = [...]; e.save_gif(frames, [1500, 250, ...], 'x_2x2.gif')   # frame 1 = Bedrock still
    e.preview(frames, 'x_preview.png', delays_ms=[...])
"""
import json
import math
import os
import random
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = 64            # design pixels per block
SCALE = 2             # 64 x 2 = 128 px per block, one map
MAP_PX = BLOCK * SCALE
TICK_MS = 50          # ImageFrame plays animations in 50 ms steps
PAINTINGS_DIR = '/home/tricks/Desktop/The-WerkShop/assets/imageframe-paintings'   # never written to

# ------------------------------------------------------------------------------------- palette

with open(os.path.join(HERE, 'map_palette.json')) as _f:
    _DOC = json.load(_f)

PALETTE_IDS = {int(k): tuple(v) for k, v in _DOC['colors'].items()}      # packed map id -> rgb
PALETTE = [PALETTE_IDS[k] for k in sorted(PALETTE_IDS)]                    # 244 rgb, packed-id order
ID_OF = {rgb: k for k, rgb in PALETTE_IDS.items()}                         # rgb -> packed map id
PALETTE_SET = frozenset(PALETTE)
_INFO = {int(k): v for k, v in _DOC['info'].items()}
BASES = {}                                                                 # name -> base id
for _k, _v in _INFO.items():
    BASES[_v['base']] = _v['base_id']
LEVELS = (135, 180, 220, 255)                    # modifier per kit level 0..3 (dark -> bright)
_LEVEL_TO_BID = (3, 0, 1, 2)                     # kit level -> MapColor.Brightness id
_BID_TO_LEVEL = {3: 0, 0: 1, 1: 2, 2: 3}


def _pid(base_id, level):
    return base_id * 4 + _LEVEL_TO_BID[level]


def mc(name, level=3):
    """Map colour by game name and level 0..3 (dark->bright), e.g. mc('COLOR_PINK', 3), mc('pink', 1)."""
    key = name.upper()
    if key not in BASES:
        key = 'COLOR_' + key
    if key not in BASES:
        raise KeyError(f'no map colour base {name!r}; see BASES')
    return PALETTE_IDS[_pid(BASES[key], max(0, min(3, level)))]


def _paper_dist(a, b):
    # org.bukkit.map.MapPalette.getDistance (Paper 26.3): integer "redmean"
    s = a[0] + b[0]
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (1024 + s) * dr * dr + 2048 * dg * dg + (1534 - s) * db * db


_NEAREST = {}
_ORDERED = [(k, PALETTE_IDS[k]) for k in sorted(PALETTE_IDS)]


def nearest(c):
    """Nearest map colour, using exactly the server's metric (Paper MapPalette redmean, first id wins ties)."""
    c = (int(c[0]), int(c[1]), int(c[2]))
    hit = _NEAREST.get(c)
    if hit is None:
        if c in PALETTE_SET:
            hit = c
        else:
            best, hit = None, None
            for _k, rgb in _ORDERED:
                d = _paper_dist(c, rgb)
                if best is None or d < best:
                    best, hit = d, rgb
        _NEAREST[c] = hit
    return hit


def nearest_in(c, candidates):
    """Nearest colour to c among candidates (same metric)."""
    return min(candidates, key=lambda k: _paper_dist(c, k))


def is_map_colour(c):
    return tuple(c) in PALETTE_SET


def map_id(c):
    """Packed map colour id (the byte ImageFrame stores) of a map colour."""
    return ID_OF[tuple(c)]


def base_of(c):
    """Game name of c's base colour (c is snapped first)."""
    return _INFO[ID_OF[nearest(c)]]['base']


def level_of(c):
    """Brightness level 0..3 (dark->bright) of c (snapped first)."""
    return _BID_TO_LEVEL[ID_OF[nearest(c)] & 3]


def shade(c, delta):
    """Same base colour as c, `delta` levels brighter (+) or darker (-), clamped to 0..3."""
    k = ID_OF[nearest(c)]
    return PALETTE_IDS[_pid(k >> 2, max(0, min(3, _BID_TO_LEVEL[k & 3] + delta)))]


def shades(c):
    """The 4 shades of c's base colour, dark -> bright."""
    b = ID_OF[nearest(c)] >> 2
    return [PALETTE_IDS[_pid(b, lv)] for lv in range(4)]


def describe(c):
    """'COLOR_PINK L3 (id 82)' style label for a colour (snapped first)."""
    k = ID_OF[nearest(c)]
    return f"{_INFO[k]['base']} L{_BID_TO_LEVEL[k & 3]} (id {k})"


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


BLACK = mc('COLOR_BLACK', 0)          # (13, 13, 13), darkest neutral
# suggested neon tube cores (all level 3); halos come from shade()/halo_for()
NEON = {
    'red': mc('FIRE'), 'pink': mc('COLOR_PINK'), 'magenta': mc('COLOR_MAGENTA'),
    'purple': mc('COLOR_PURPLE'), 'blue': mc('LAPIS'), 'ice': mc('ICE'), 'sky': mc('COLOR_LIGHT_BLUE'),
    'cyan': mc('DIAMOND'), 'teal': mc('WARPED_WART_BLOCK'), 'green': mc('EMERALD'),
    'lime': mc('COLOR_LIGHT_GREEN'), 'yellow': mc('GOLD'), 'orange': mc('COLOR_ORANGE'),
    'white': mc('QUARTZ', 2),
}

# ---------------------------------------------------------------------- paintings.py compatible bits


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def dark(c, t=0.25):
    return mix(c, (0, 0, 0), t)


def light(c, t=0.25):
    return mix(c, (255, 255, 255), t)


FONT = {   # 5x7, identical to paintings.py for the letters it has, plus the missing ones
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    'J': ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    '.': [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ',': [".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."],
    ':': [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    '-': [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    '!': ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    '?': [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    '&': [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    '/': ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    '_': [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
}

FONT_LOWER = {   # 5x7 lowercase (rows 7-8 hang below the baseline for g j p q y); use text(..., case=True)
    'a': [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    'b': ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
    'c': [".....", ".....", ".###.", "#....", "#....", "#....", ".###."],
    'd': ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    'e': [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    'f': ["..##.", ".#...", "####.", ".#...", ".#...", ".#...", ".#..."],
    'g': [".....", ".....", ".####", "#...#", "#...#", ".####", "....#", ".###."],
    'h': ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
    'i': ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    'j': ["...#.", ".....", "..##.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'k': ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
    'l': [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    'm': [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#...#"],
    'n': [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    'o': [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    'p': [".....", ".....", "####.", "#...#", "#...#", "####.", "#....", "#...."],
    'q': [".....", ".....", ".####", "#...#", "#...#", ".####", "....#", "....#"],
    'r': [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
    's': [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
    't': [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."],
    'u': [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#"],
    'v': [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'w': [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
    'x': [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    'y': [".....", ".....", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    'z': [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"],
}

FONT3 = {   # tiny 3x5 caps + digits, for clocks, labels and price tags
    'A': [".#.", "#.#", "###", "#.#", "#.#"], 'B': ["##.", "#.#", "##.", "#.#", "##."],
    'C': [".##", "#..", "#..", "#..", ".##"], 'D': ["##.", "#.#", "#.#", "#.#", "##."],
    'E': ["###", "#..", "##.", "#..", "###"], 'F': ["###", "#..", "##.", "#..", "#.."],
    'G': [".##", "#..", "#.#", "#.#", ".##"], 'H': ["#.#", "#.#", "###", "#.#", "#.#"],
    'I': ["###", ".#.", ".#.", ".#.", "###"], 'J': ["..#", "..#", "..#", "#.#", ".#."],
    'K': ["#.#", "#.#", "##.", "#.#", "#.#"], 'L': ["#..", "#..", "#..", "#..", "###"],
    'M': ["#.#", "###", "###", "#.#", "#.#"], 'N': ["##.", "#.#", "#.#", "#.#", "#.#"],
    'O': [".#.", "#.#", "#.#", "#.#", ".#."], 'P': ["##.", "#.#", "##.", "#..", "#.."],
    'Q': [".#.", "#.#", "#.#", "##.", ".##"], 'R': ["##.", "#.#", "##.", "#.#", "#.#"],
    'S': [".##", "#..", ".#.", "..#", "##."], 'T': ["###", ".#.", ".#.", ".#.", ".#."],
    'U': ["#.#", "#.#", "#.#", "#.#", "###"], 'V': ["#.#", "#.#", "#.#", "#.#", ".#."],
    'W': ["#.#", "#.#", "###", "###", "#.#"], 'X': ["#.#", "#.#", ".#.", "#.#", "#.#"],
    'Y': ["#.#", "#.#", ".#.", ".#.", ".#."], 'Z': ["###", "..#", ".#.", "#..", "###"],
    '0': ["###", "#.#", "#.#", "#.#", "###"], '1': [".#.", "##.", ".#.", ".#.", "###"],
    '2': ["##.", "..#", ".#.", "#..", "###"], '3': ["##.", "..#", ".#.", "..#", "##."],
    '4': ["#.#", "#.#", "###", "..#", "..#"], '5': ["###", "#..", "##.", "..#", "##."],
    '6': [".##", "#..", "###", "#.#", "###"], '7': ["###", "..#", ".#.", ".#.", ".#."],
    '8': ["###", "#.#", "###", "#.#", "###"], '9': ["###", "#.#", "###", "..#", "##."],
    ':': ["...", ".#.", "...", ".#.", "..."], '.': ["...", "...", "...", "...", ".#."],
    '-': ["...", "...", "###", "...", "..."], '/': ["..#", "..#", ".#.", "#..", "#.."],
    '_': ["...", "...", "...", "...", "###"], "'": [".#.", ".#.", "...", "...", "..."],
    '*': ["...", "#.#", ".#.", "#.#", "..."], '=': ["...", "###", "...", "###", "..."],
    'x': ["...", "#.#", ".#.", "#.#", "..."], '(': [".#.", "#..", "#..", "#..", ".#."],
    ')': [".#.", "..#", "..#", "..#", ".#."], '#': ["#.#", "###", "#.#", "###", "#.#"],
}


def _glyph(ch, font, case):
    if font is None:
        font = FONT
    if case and font is FONT and ch in FONT_LOWER:
        return FONT_LOWER[ch]
    g = font.get(ch)
    return g if g is not None else font.get(ch.upper())


def text_width(s, scale=1, font=None):
    """Width in pixels of s drawn by Canvas.text / text_pixels (advance = glyph width + 1)."""
    font = font or FONT
    cell = len(next(iter(font.values()))[0]) + 1
    return max(0, len(s) * cell - 1) * scale


def text_pixels(x, y, s, scale=1, font=None, case=False):
    """Set of pixels text would cover (top-left at x, y). case=True keeps lowercase (FONT_LOWER)."""
    out = set()
    cell = len(next(iter((font or FONT).values()))[0]) + 1
    for ch in s:
        glyph = _glyph(ch, font, case)
        if glyph:
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == '#':
                        for oy in range(scale):
                            for ox in range(scale):
                                out.add((int(x + gx * scale + ox), int(y + gy * scale + oy)))
        x += cell * scale
    return out


class Canvas:
    """paintings.py's Canvas (same constructor, methods and pixel results) plus a few extras."""

    def __init__(self, w, h, fill):
        self.w, self.h = w, h
        self.p = [[tuple(fill)] * w for _ in range(h)]

    # ---- paintings.py methods (unchanged behaviour)
    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y][x] = c

    def get(self, x, y):
        return self.p[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            row = self.p[y]
            for x in range(max(0, int(x0)), min(self.w, int(x1))):
                row[x] = c

    def vgrad(self, x0, y0, x1, y1, cols):
        """Banded vertical gradient through cols, top to bottom (off-palette; snapped on save)."""
        n = int(y1 - y0)
        for i in range(n):
            t = i / max(1, n - 1) * (len(cols) - 1)
            k = min(int(t), len(cols) - 2)
            self.rect(x0, y0 + i, x1, y0 + i + 1, mix(cols[k], cols[k + 1], t - k))

    def ell(self, cx, cy, rx, ry, c, ang=0.0):
        """Filled (optionally rotated) ellipse; returns the pixels it covered."""
        out = []
        r = max(rx, ry) + 1
        ca, sa = math.cos(ang), math.sin(ang)
        for y in range(int(cy - r), int(cy + r) + 2):
            for x in range(int(cx - r), int(cx + r) + 2):
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                u = dx * ca + dy * sa
                v = -dx * sa + dy * ca
                if (u / rx) ** 2 + (v / ry) ** 2 <= 1.0:
                    self.px(x, y, c)
                    out.append((x, y, u, v))
        return out

    def oell(self, cx, cy, rx, ry, fill, outline, ang=0.0):
        """Ellipse with a one-pixel outline; returns the fill pixels."""
        self.ell(cx, cy, rx + 1, ry + 1, outline, ang)
        return self.ell(cx, cy, rx, ry, fill, ang)

    def poly(self, pts, c):
        """Scanline polygon fill."""
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            yc = y + 0.5
            xs = []
            for i in range(len(pts)):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(int(round(xs[i])), int(round(xs[i + 1]))):
                    self.px(x, y, c)

    def line(self, x0, y0, x1, y1, c, w=1):
        for (x, y) in line_pixels(x0, y0, x1, y1, w):
            self.px(x, y, c)

    def speckle(self, pixels, cols, density, rng):
        for (x, y, *_rest) in pixels:
            if rng.random() < density:
                self.px(x, y, rng.choice(cols))

    def text(self, x, y, s, c, scale=1, font=None, case=False):
        """paintings.py text (5x7 caps, advance 6*scale); font=FONT3 for tiny text, case=True for lowercase."""
        for (px_, py_) in text_pixels(x, y, s, scale, font, case):
            self.px(px_, py_, c)

    def frame(self):
        """paintings.py's dark wooden picture frame, four pixels deep (snapped to the palette on save)."""
        w, h = self.w, self.h
        for i, col in enumerate([(46, 28, 16), (70, 44, 24), (112, 74, 40), (150, 104, 58)]):
            self.rect(i, i, w - i, i + 1, col)
            self.rect(i, h - i - 1, w - i, h - i, dark(col, 0.15))
            self.rect(i, i, i + 1, h - i, col)
            self.rect(w - i - 1, i, w - i, h - i, dark(col, 0.15))

    # ---- extras
    def save(self, path, **kw):
        """Same as save_png(self, path, **kw). Unlike paintings.py it adds no frame and takes a full path."""
        return save_png(self, path, **kw)

    def copy(self):
        c = Canvas.__new__(Canvas)
        c.w, c.h = self.w, self.h
        c.p = [row[:] for row in self.p]
        return c

    def blit(self, src, x, y, key=None):
        """Paste canvas src with its top-left at (x, y); pixels equal to `key` are skipped."""
        for sy in range(src.h):
            for sx in range(src.w):
                c = src.p[sy][sx]
                if key is None or c != key:
                    self.px(x + sx, y + sy, c)

    def fill_pixels(self, pixels, c):
        for (x, y, *_r) in pixels:
            self.px(x, y, c)

    def quantize(self):
        """Snap every pixel to its nearest map colour in place; returns self."""
        for row in self.p:
            for i, c in enumerate(row):
                if c not in PALETTE_SET:
                    row[i] = nearest(c)
        return self

    def colours(self):
        """Set of distinct colours on the canvas."""
        return {c for row in self.p for c in row}

    def __eq__(self, other):
        return isinstance(other, Canvas) and self.w == other.w and self.h == other.h and self.p == other.p


def blocks(h, w, fill=BLACK):
    """Canvas for an H x W block piece at design resolution (64 px per block)."""
    return Canvas(w * BLOCK, h * BLOCK, fill)


def out_name(name, h, w, ext='png'):
    """File name per house rule: name_HxW.ext (height x width in blocks)."""
    return f'{name}_{h}x{w}.{ext}'


def quantize(canvas):
    """A snapped copy of canvas (every pixel -> nearest map colour)."""
    return canvas.copy().quantize()


def off_palette(canvas):
    """{colour: count} of pixels that are not map colours (empty dict = clean)."""
    bad = {}
    for row in canvas.p:
        for c in row:
            if c not in PALETTE_SET:
                bad[c] = bad.get(c, 0) + 1
    return bad


def upscale(canvas, k=SCALE):
    """Nearest-neighbour k x upscale (design px -> map px)."""
    c = Canvas.__new__(Canvas)
    c.w, c.h = canvas.w * k, canvas.h * k
    c.p = []
    for row in canvas.p:
        big = [px for px in row for _ in range(k)]
        for _ in range(k):
            c.p.append(big[:])
    return c

# --------------------------------------------------------------------------- shapes as pixel sets


def line_pixels(x0, y0, x1, y1, w=1):
    """Pixels of paintings.py's line() (w x w brush)."""
    out = []
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for oy in range(w):
            for ox in range(w):
                out.append((int(x + ox - w // 2), int(y + oy - w // 2)))
    return list(dict.fromkeys(out))


def path_pixels(pts, w=1, closed=False):
    """Pixels of a polyline through pts (closed=True joins the last point to the first)."""
    out = {}
    segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed and len(pts) > 2 else [])
    for (a, b) in segs:
        for p in line_pixels(a[0], a[1], b[0], b[1], w):
            out[p] = 1
    return list(out)


def arc_pixels(cx, cy, rx, ry, a0=0, a1=360, w=1):
    """Pixels of an elliptical arc from angle a0 to a1 (degrees, 0 = right, 90 = down)."""
    out = {}
    steps = max(8, int(abs(a1 - a0) / 360 * 2 * math.pi * max(rx, ry) * 2))
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        for oy in range(w):
            for ox in range(w):
                out[(int(math.floor(x + ox - w // 2)), int(math.floor(y + oy - w // 2)))] = 1
    return list(out)


def rrect_pixels(x0, y0, x1, y1, r=3, w=1):
    """Outline of a rounded rectangle with corners of radius r (x1, y1 inclusive) -- a neon border."""
    out = {}
    for p in path_pixels([(x0 + r, y0), (x1 - r, y0)], w) + path_pixels([(x0 + r, y1), (x1 - r, y1)], w) \
            + path_pixels([(x0, y0 + r), (x0, y1 - r)], w) + path_pixels([(x1, y0 + r), (x1, y1 - r)], w):
        out[p] = 1
    if r > 0:
        for (cx, cy, a0) in ((x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90)):
            for p in arc_pixels(cx + 0.5, cy + 0.5, r, r, a0, a0 + 90, w):
                out[p] = 1
    return list(out)


def thicken(pixels, w=2):
    """Grow a pixel set into a w-wide stroke (square brush)."""
    out = {}
    for (x, y, *_r) in pixels:
        for oy in range(w):
            for ox in range(w):
                out[(x + ox - w // 2, y + oy - w // 2)] = 1
    return list(out)

# ------------------------------------------------------------------------------------------ neon


def halo_for(core, radius=2):
    """Default halo colours, ring 1..radius: darker shades of core's own base (2 then 3 levels down)."""
    return [shade(core, -(k + 1)) for k in range(1, radius + 1)]


def _ring_offsets(radius):
    offs = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d = math.hypot(dx, dy)
            if 0 < d <= radius + 0.5:
                offs.append((dx, dy, max(1, int(math.ceil(d - 0.5)))))
    return offs


def glow(canvas, pixels, core, halo=None, radius=2, lighten=True, hot=None, mode='shades'):
    """Light up a neon tube: paint `pixels` in `core` and a soft halo `radius` px around them.

    halo: list of ring colours (ring 1 first). Default (mode='shades') = halo_for(core): the same hue two and
    three brightness levels down, e.g. FIRE 255 core -> 180 ring -> 135 ring. mode='blend' instead mixes the
    core into whatever is underneath (55 % then 28 %) and snaps to the palette -- good over busy walls.
    lighten=True only paints a halo pixel where it is brighter than what is already there (light adds up,
    so overlapping tubes and earlier cores survive).  hot: colour for the tube's interior pixels (only
    strokes 3+ px wide have any), a white-hot centre line.  Returns the core pixel set.
    """
    core = nearest(core)
    pts = {(int(p[0]), int(p[1])) for p in pixels}
    if halo is None and mode == 'shades':
        halo = halo_for(core, radius)
    radius = len(halo) if halo is not None else radius
    rings = {}
    for (x, y) in pts:
        for dx, dy, k in _ring_offsets(radius):
            q = (x + dx, y + dy)
            if q not in pts and (q not in rings or rings[q] > k):
                rings[q] = k
    for (x, y), k in rings.items():
        under = canvas.get(x, y)
        if under is None:
            continue
        if halo is not None:
            col = nearest(halo[k - 1])
        else:
            col = nearest(mix(under, core, (0.55, 0.28, 0.14, 0.07)[min(k, 4) - 1]))
        if not lighten or lum(col) > lum(under):
            canvas.px(x, y, col)
    for (x, y) in pts:
        canvas.px(x, y, core)
    if hot is not None:
        hot = nearest(hot)
        for (x, y) in pts:
            if {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} <= pts:
                canvas.px(x, y, hot)
    return pts


def neon_text(canvas, x, y, s, core, scale=1, font=None, case=False, thick=1, **glow_kw):
    """Neon lettering: text_pixels (optionally thickened) lit with glow(). Returns the core pixels."""
    pts = text_pixels(x, y, s, scale, font, case)
    if thick > 1:
        pts = thicken(pts, thick)
    return glow(canvas, pts, core, **glow_kw)


def neon_path(canvas, pts, core, w=1, closed=False, **glow_kw):
    """Neon tube along a polyline. Returns the core pixels."""
    return glow(canvas, path_pixels(pts, w, closed), core, **glow_kw)


def unlit(core, t=0.5, glass=(40, 40, 40)):
    """Colour for the same tube switched off: its darkest shade pulled `t` toward dull grey glass, snapped.
    Always darker than the lit tube's inner halo, so an off letter reads as off."""
    return nearest(mix(shade(core, -3), glass, t))


SEG7 = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg',
        '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': '', 'A': 'abcefg', 'P': 'abefg',
        'E': 'adefg', 'H': 'bcefg', 'L': 'def', 'O': 'abcdef', 'C': 'adef'}


def seg7_pixels(x, y, s, w=5, h=9, t=1):
    """Seven-segment display text (digits, ':', ' ', '-', A P E H L O C). Returns (lit, unlit) pixel sets."""
    on, off = set(), set()
    mid = y + (h - t) // 2
    for ch in s:
        if ch == ':':
            for cy in (y + h // 3 - t // 2, y + (2 * h) // 3 - t // 2):
                for oy in range(t):
                    for ox in range(t):
                        on.add((x + ox, cy + oy))
            x += t + 2
            continue
        segs = {
            'a': [(x + i, y + j) for i in range(t, w - t) for j in range(t)],
            'd': [(x + i, y + h - t + j) for i in range(t, w - t) for j in range(t)],
            'g': [(x + i, mid + j) for i in range(t, w - t) for j in range(t)],
            'f': [(x + i, y + j) for i in range(t) for j in range(t, mid - y)],
            'b': [(x + w - t + i, y + j) for i in range(t) for j in range(t, mid - y)],
            'e': [(x + i, mid + t + j) for i in range(t) for j in range(0, y + h - t - mid - t)],
            'c': [(x + w - t + i, mid + t + j) for i in range(t) for j in range(0, y + h - t - mid - t)],
        }
        lit = SEG7.get(ch.upper(), '')
        for name, px_ in segs.items():
            (on if name in lit else off).update(px_)
        x += w + 2
    return on, off - on

# ------------------------------------------------------------------------------ texture helpers


BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def dither_rect(canvas, x0, y0, x1, y1, c1, c2, t):
    """Fill a rect with an ordered (4x4 Bayer) mix of two map colours: t=0 all c1, t=1 all c2."""
    c1, c2 = nearest(c1), nearest(c2)
    for y in range(max(0, int(y0)), min(canvas.h, int(y1))):
        for x in range(max(0, int(x0)), min(canvas.w, int(x1))):
            canvas.p[y][x] = c2 if (BAYER4[y & 3][x & 3] + 0.5) / 16 < t else c1


def bayer_vgrad(canvas, x0, y0, x1, y1, cols):
    """Vertical gradient through map colours cols (top -> bottom), ordered-dithered between neighbours."""
    cols = [nearest(c) for c in cols]
    n = int(y1 - y0)
    for i in range(n):
        t = i / max(1, n - 1) * (len(cols) - 1)
        k = min(int(t), len(cols) - 2)
        dither_rect(canvas, x0, y0 + i, x1, y0 + i + 1, cols[k], cols[k + 1], t - k)


def weather(canvas, area, rng, density=0.12, delta=-1):
    """Age a surface: a random `density` share of pixels shift `delta` brightness levels (same hue).
    area is (x0, y0, x1, y1) or an iterable of pixels."""
    if isinstance(area, tuple) and len(area) == 4 and not isinstance(area[0], tuple):
        x0, y0, x1, y1 = area
        area = [(x, y) for y in range(int(y0), int(y1)) for x in range(int(x0), int(x1))]
    for (x, y, *_r) in area:
        c = canvas.get(x, y)
        if c is not None and rng.random() < density:
            canvas.px(x, y, shade(c, delta))

# --------------------------------------------------------------------------------- PNG in / out


def _guard(path):
    real = os.path.realpath(path)
    # the generators write beside themselves in retro-src/; the gallery's own files are copied up by hand
    if os.path.dirname(real) == PAINTINGS_DIR:
        raise PermissionError(f'egwpix never writes into the gallery {PAINTINGS_DIR}; copy the finished file up by hand')


def _png_bytes(rows, w, h):
    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def _write_png(canvas, path, scale=1):
    _guard(path)
    rows = []
    for row in canvas.p:
        line = bytearray()
        for c in row:
            line += bytes(c) * scale
        rows.extend([bytes(line)] * scale)
    data = _png_bytes(rows, canvas.w * scale, canvas.h * scale)
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


def _prepare(canvas, quantize_, what):
    bad = off_palette(canvas)
    if bad and not quantize_:
        sample = ', '.join(f'{c}x{n}' for c, n in list(bad.items())[:6])
        raise ValueError(f'{what}: {sum(bad.values())} pixels are not map colours ({sample} ...); '
                         f'pass quantize=True or snap them with nearest()')
    return (quantize(canvas) if bad else canvas), sum(bad.values())


def _check_size(w, h, strict, what):
    if strict and (w % MAP_PX or h % MAP_PX):
        raise ValueError(f'{what}: {w}x{h} px is not a whole number of {MAP_PX}-px maps '
                         f'(design canvases must be multiples of {BLOCK})')


def save_png(canvas, path, scale=SCALE, strict=True, quantize=True):
    """Write canvas as an RGB PNG, scaled `scale` x nearest. Off-palette pixels are snapped with nearest()
    (quantize=False raises instead). strict=True requires whole 128-px maps. Returns an info dict."""
    w, h = canvas.w * scale, canvas.h * scale
    _check_size(w, h, strict, path)
    snapped_canvas, snapped = _prepare(canvas, quantize, path)
    size = _write_png(snapped_canvas, path, scale)
    return {'path': path, 'w': w, 'h': h, 'blocks_hxw': (h // MAP_PX, w // MAP_PX),
            'colours': len(snapped_canvas.colours()), 'snapped_pixels': snapped, 'bytes': size}


def read_png(path):
    """Decode an 8-bit, non-interlaced PNG (grey, RGB, palette, grey+alpha, RGBA) into a Canvas (alpha dropped)."""
    data = open(path, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    p, idat, plte = 8, b'', None
    while p < len(data):
        ln, = struct.unpack('>I', data[p:p + 4])
        t, d = data[p + 4:p + 8], data[p + 8:p + 8 + ln]
        if t == b'IHDR':
            w, h, depth, ctype, _c, _f, inter = struct.unpack('>IIBBBBB', d)
        elif t == b'PLTE':
            plte = [tuple(d[i:i + 3]) for i in range(0, len(d), 3)]
        elif t == b'IDAT':
            idat += d
        p += 12 + ln
    if depth != 8 or inter != 0:
        raise ValueError('read_png only handles 8-bit non-interlaced PNGs')
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * bpp
    prev = bytearray(stride)
    c = Canvas(w, h, (0, 0, 0))
    o = 0
    for y in range(h):
        ft = raw[o]
        cur = bytearray(raw[o + 1:o + 1 + stride])
        o += 1 + stride
        for i in range(stride):
            a = cur[i - bpp] if i >= bpp else 0
            b = prev[i]
            cc = prev[i - bpp] if i >= bpp else 0
            if ft == 1:
                cur[i] = (cur[i] + a) & 255
            elif ft == 2:
                cur[i] = (cur[i] + b) & 255
            elif ft == 3:
                cur[i] = (cur[i] + (a + b) // 2) & 255
            elif ft == 4:
                pa, pb, pc = abs(b - cc), abs(a - cc), abs(a + b - 2 * cc)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else cc)
                cur[i] = (cur[i] + pr) & 255
        row = c.p[y]
        for x in range(w):
            q = x * bpp
            if ctype == 2 or ctype == 6:
                row[x] = (cur[q], cur[q + 1], cur[q + 2])
            elif ctype == 3:
                row[x] = plte[cur[q]]
            else:
                row[x] = (cur[q],) * 3
        prev = cur
    return c

# --------------------------------------------------------------------------------- GIF in / out


LZW_STATS = {'resets': 0, 'eoi_bump': 0}     # counters the tests use to prove the edge cases ran


def _lzw_encode(data, min_size):
    """GIF LZW (variable code width, LSB-first, clear at start, reset when the 4096-entry table fills)."""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    first = eoi + 1
    out = bytearray()
    acc = nbits = 0
    size = min_size + 1
    nxt = first
    table = {}
    acc |= clear << nbits
    nbits += size
    it = iter(data)
    try:
        prefix = next(it)
    except StopIteration:
        prefix = None
    for k in it:
        key = (prefix << 8) | k
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        acc |= prefix << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 255)
            acc >>= 8
            nbits -= 8
        table[key] = nxt
        nxt += 1
        if nxt > (1 << size) and size < 12:
            size += 1
        if nxt == 4096:                       # table full: clear (written at width 12) and start over
            acc |= clear << nbits
            nbits += size
            LZW_STATS['resets'] += 1
            table = {}
            size = min_size + 1
            nxt = first
        prefix = k
    if prefix is not None:
        acc |= prefix << nbits
        nbits += size
        if nxt == (1 << size) and size < 12:  # the decoder grows one step after the last data code
            size += 1
            LZW_STATS['eoi_bump'] += 1
    acc |= eoi << nbits
    nbits += size
    while nbits > 0:
        out.append(acc & 255)
        acc >>= 8
        nbits -= 8
    return bytes(out)


def _lzw_decode(data, min_size):
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    out = bytearray()
    size = min_size + 1
    table = None
    prev = None
    acc = nbits = 0
    pos = 0
    while True:
        while nbits < size and pos < len(data):
            acc |= data[pos] << nbits
            nbits += 8
            pos += 1
        if nbits < size:
            break
        code = acc & ((1 << size) - 1)
        acc >>= size
        nbits -= size
        if code == clear:
            table = [bytes([i]) for i in range(clear)] + [b'', b'']
            size = min_size + 1
            prev = None
            continue
        if code == eoi:
            break
        if table is None:
            raise ValueError('GIF LZW stream does not start with a clear code')
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            if len(table) < 4096:
                table.append(table[prev] + entry[:1])
        elif code == len(table):
            entry = table[prev] + table[prev][:1]
            if len(table) < 4096:
                table.append(entry)
        else:
            raise ValueError(f'bad LZW code {code} (table {len(table)})')
        out += entry
        if len(table) == (1 << size) and size < 12:
            size += 1
        prev = code
    return bytes(out)


def _norm_delays(delays_ms, n):
    if isinstance(delays_ms, (int, float)):
        delays_ms = [delays_ms] * n
    delays_ms = [int(d) for d in delays_ms]
    if len(delays_ms) != n:
        raise ValueError(f'{n} frames but {len(delays_ms)} delays')
    for d in delays_ms:
        if d < TICK_MS or d % TICK_MS or d > 655350:
            raise ValueError(f'delay {d} ms: use multiples of {TICK_MS} ms (ImageFrame plays in 50 ms ticks)')
    return delays_ms


def tile_cost(frames, delays_ms):
    """What ImageFrame will store/send for this animation. It samples the GIF every 50 ms; per map tile it
    makes a new 'fake map' (16 KB, sent to every viewer) only when that tile differs from the previous tick.
    Returns {'ticks', 'duration_ms', 'fake_maps', 'per_tile': {(col,row): n}} (design-res frames)."""
    delays_ms = _norm_delays(delays_ms, len(frames))
    w, h = frames[0].w, frames[0].h
    cols, rows = math.ceil(w / BLOCK), math.ceil(h / BLOCK)
    per = {}
    for ty in range(rows):
        for tx in range(cols):
            last, n = None, 0
            for f in frames:          # consecutive equal ticks inside one frame never change, so per frame
                tile = tuple(tuple(f.p[y][tx * BLOCK:(tx + 1) * BLOCK]) for y in range(ty * BLOCK, min(h, (ty + 1) * BLOCK)))
                if tile != last:
                    n += 1
                    last = tile
            per[(tx, ty)] = n
    return {'ticks': sum(delays_ms) // TICK_MS, 'duration_ms': sum(delays_ms),
            'fake_maps': sum(per.values()), 'per_tile': per}


def save_gif(frames, delays_ms, path, loop=0, scale=SCALE, strict=True, quantize=True):
    """Write an animated GIF89a: global colour table of the map colours used, LZW, NETSCAPE2.0 loop
    (loop=0 forever), one Graphic Control Extension per frame (delay in hundredths). Frames are design-res
    Canvases of one size, scaled `scale` x. delays_ms: one int or a list, multiples of 50 ms.
    Frame 1 is what Bedrock shows. Returns an info dict (incl. ImageFrame tile_cost)."""
    _guard(path)
    frames = list(frames)
    if not frames:
        raise ValueError('no frames')
    delays_ms = _norm_delays(delays_ms, len(frames))
    fw, fh = frames[0].w, frames[0].h
    for i, f in enumerate(frames):
        if (f.w, f.h) != (fw, fh):
            raise ValueError(f'frame {i + 1} is {f.w}x{f.h}, frame 1 is {fw}x{fh}')
    W, H = fw * scale, fh * scale
    _check_size(W, H, strict, path)
    snapped = 0
    ready = []
    for i, f in enumerate(frames):
        g, n = _prepare(f, quantize, f'{path} frame {i + 1}')
        ready.append(g)
        snapped += n
    used = sorted({c for f in ready for row in f.p for c in row}, key=lambda c: ID_OF[c])
    if len(used) > 256:
        raise ValueError('more than 256 colours')
    bits = max(2, (len(used) - 1).bit_length())
    table = used + [(0, 0, 0)] * ((1 << bits) - len(used))
    index = {c: i for i, c in enumerate(used)}

    out = bytearray(b'GIF89a')
    out += struct.pack('<HHBBB', W, H, 0x80 | (7 << 4) | (bits - 1), 0, 0)
    for c in table:
        out += bytes(c)
    out += b'\x21\xff\x0bNETSCAPE2.0\x03\x01' + struct.pack('<H', loop) + b'\x00'
    for f, d in zip(ready, delays_ms):
        out += b'\x21\xf9\x04' + bytes([1 << 2]) + struct.pack('<H', d // 10) + b'\x00\x00'   # disposal 1
        out += b'\x2c' + struct.pack('<HHHHB', 0, 0, W, H, 0)
        idx = bytearray()
        for row in f.p:
            line = bytearray()
            for c in row:
                line += bytes([index[c]]) * scale
            idx += bytes(line) * scale
        lzw = _lzw_encode(idx, bits)
        out.append(bits)
        for i in range(0, len(lzw), 255):
            blk = lzw[i:i + 255]
            out.append(len(blk))
            out += blk
        out.append(0)
    out.append(0x3b)
    with open(path, 'wb') as fh_:
        fh_.write(out)
    cost = tile_cost(ready, delays_ms)
    return {'path': path, 'w': W, 'h': H, 'blocks_hxw': (H // MAP_PX, W // MAP_PX), 'frames': len(frames),
            'delays_ms': delays_ms, 'colours': len(used), 'snapped_pixels': snapped, 'bytes': len(out),
            'duration_ms': cost['duration_ms'], 'imageframe_ticks': cost['ticks'],
            'imageframe_fake_maps': cost['fake_maps'], 'per_tile': cost['per_tile']}


def read_gif(path):
    """Decode a GIF (any GIF87a/89a: global/local tables, interlace, transparency, disposal 0-3) into
    {'w','h','loop','frames': [Canvas, ...] composited, 'delays_ms': [...]}."""
    d = open(path, 'rb').read()
    if d[:6] not in (b'GIF87a', b'GIF89a'):
        raise ValueError('not a GIF')
    W, H, flags, bg, _aspect = struct.unpack('<HHBBB', d[6:13])
    p = 13
    gct = None
    if flags & 0x80:
        n = 2 << (flags & 7)
        gct = [tuple(d[p + 3 * i:p + 3 * i + 3]) for i in range(n)]
        p += 3 * n
    bgc = gct[bg] if gct and bg < len(gct) else (0, 0, 0)
    canvas = Canvas(W, H, bgc)
    frames, delays, loop = [], [], None
    gce = {'delay': 0, 'disposal': 0, 'trans': None}
    while p < len(d):
        b = d[p]
        p += 1
        if b == 0x3b:
            break
        if b == 0x21:
            label = d[p]
            p += 1
            blocks = []
            while d[p]:
                blocks.append(d[p + 1:p + 1 + d[p]])
                p += 1 + d[p]
            p += 1
            if label == 0xf9 and blocks:
                pk, dl, ti = blocks[0][0], struct.unpack('<H', blocks[0][1:3])[0], blocks[0][3]
                gce = {'delay': dl * 10, 'disposal': (pk >> 2) & 7, 'trans': ti if pk & 1 else None}
            elif label == 0xff and blocks and blocks[0][:11] == b'NETSCAPE2.0' and len(blocks) > 1:
                loop = struct.unpack('<H', blocks[1][1:3])[0]
            continue
        if b != 0x2c:
            raise ValueError(f'unexpected GIF block 0x{b:02x} at {p - 1}')
        x0, y0, w, h, fl = struct.unpack('<HHHHB', d[p:p + 9])
        p += 9
        ct = gct
        if fl & 0x80:
            n = 2 << (fl & 7)
            ct = [tuple(d[p + 3 * i:p + 3 * i + 3]) for i in range(n)]
            p += 3 * n
        mcs = d[p]
        p += 1
        data = bytearray()
        while d[p]:
            data += d[p + 1:p + 1 + d[p]]
            p += 1 + d[p]
        p += 1
        idx = _lzw_decode(bytes(data), mcs)
        rows = list(range(h))
        if fl & 0x40:
            rows = list(range(0, h, 8)) + list(range(4, h, 8)) + list(range(2, h, 4)) + list(range(1, h, 2))
        before = canvas.copy()
        for i, y in enumerate(rows):
            for x in range(w):
                k = i * w + x
                if k < len(idx) and idx[k] != gce['trans']:
                    canvas.px(x0 + x, y0 + y, ct[idx[k]])
        frames.append(canvas.copy())
        delays.append(gce['delay'])
        if gce['disposal'] == 2:
            canvas.rect(x0, y0, x0 + w, y0 + h, bgc)
        elif gce['disposal'] == 3:
            canvas = before
        gce = {'delay': 0, 'disposal': 0, 'trans': None}
    return {'w': W, 'h': H, 'loop': loop, 'frames': frames, 'delays_ms': delays}

# ---------------------------------------------------------------------------------- review sheets


def preview(frames, path, scale=2, delays_ms=None, cols=None, title=None, bg=(24, 24, 28)):
    """Contact-sheet PNG of all frames (design-res Canvases) at `scale` x, each labelled 'F<n> <delay>MS'.
    Frame 1 (the Bedrock still) gets a yellow label and outline; ticks mark the 64-px map tile seams.
    A single Canvas is fine too. For review only -- not palette-restricted. Returns path."""
    if isinstance(frames, Canvas):
        frames = [frames]
    frames = list(frames)
    n = len(frames)
    fw, fh = frames[0].w * scale, frames[0].h * scale
    if cols is None:
        cols = max(1, min(n, int(math.ceil(math.sqrt(n * fh / max(1, fw))))))
    rows = math.ceil(n / cols)
    pad, lab, ts = 12, 16, 2
    lines = []
    if title:
        lines.append(title)
    if delays_ms is not None:
        dl = _norm_delays(delays_ms, n) if not isinstance(delays_ms, (int, float)) else [int(delays_ms)] * n
        lines.append(f'{n} FRAMES  {sum(dl)}MS LOOP  F1 = BEDROCK STILL')
    else:
        dl = None
    top = len(lines) * 14
    W = pad + cols * (fw + pad)
    H = top + pad + rows * (lab + fh + pad)
    sheet = Canvas(W, H, bg)
    for i, ln in enumerate(lines):
        sheet.text(pad, 6 + i * 14, ln.upper(), (230, 230, 230), ts, FONT3)
    yellow, grey, tick = (250, 220, 60), (200, 200, 205), (110, 110, 118)
    for i, f in enumerate(frames):
        cx = pad + (i % cols) * (fw + pad)
        cy = top + pad + (i // cols) * (lab + fh + pad)
        label = f'F{i + 1}' + (f' {dl[i]}MS' if dl else '')
        sheet.text(cx, cy + 2, label, yellow if i == 0 else grey, ts, FONT3)
        fy = cy + lab
        for y in range(f.h):
            for yy in range(scale):
                row = sheet.p[fy + y * scale + yy]
                for x in range(f.w):
                    c = f.p[y][x]
                    base = cx + x * scale
                    for xx in range(scale):
                        row[base + xx] = c
        for bx in range(0, f.w + 1, BLOCK):
            sheet.rect(cx + bx * scale - (1 if bx else 0), fy + fh + 1, cx + bx * scale + (0 if bx else 1), fy + fh + 5, tick)
        for by in range(0, f.h + 1, BLOCK):
            sheet.rect(cx - 5, fy + by * scale - (1 if by else 0), cx - 1, fy + by * scale + (0 if by else 1), tick)
        if i == 0 and n > 1:
            for k in (1, 2):
                sheet.rect(cx - k - 1, fy - k - 1, cx + fw + k + 1, fy - k, yellow)
                sheet.rect(cx - k - 1, fy + fh + k, cx + fw + k + 1, fy + fh + k + 1, yellow)
                sheet.rect(cx - k - 1, fy - k - 1, cx - k, fy + fh + k + 1, yellow)
                sheet.rect(cx + fw + k, fy - k - 1, cx + fw + k + 1, fy + fh + k + 1, yellow)
    _write_png(sheet, path, 1)
    return path


def palette_sheet(path, sw=22):
    """Reference PNG of all 244 map colours: one row per base (name, id), 4 swatches dark -> bright."""
    names = sorted(BASES.items(), key=lambda kv: kv[1])
    lw = 4 * 22 * 2 + 30
    W = 8 + lw + 4 * (sw + 4) + 8
    H = 8 + len(names) * (sw + 4) + 8
    H += 16
    sheet = Canvas(W, H, (24, 24, 28))
    for lv in range(4):
        sheet.text(8 + lw + lv * (sw + 4) + 2, 6, f'L{lv}', (220, 220, 220), 2, FONT3)
    for r, (name, bid) in enumerate(names):
        y = 24 + r * (sw + 4)
        sheet.text(8, y + (sw - 10) // 2, f'{bid:02d} {name}', (220, 220, 220), 2, FONT3)
        for lv in range(4):
            x = 8 + lw + lv * (sw + 4)
            sheet.rect(x, y, x + sw, y + sw, PALETTE_IDS[_pid(bid, lv)])
    _write_png(sheet, path, 1)
    return path


__all__ = [n for n in dir() if not n.startswith('_') and n not in ('json', 'math', 'os', 'random', 'struct', 'zlib')]
