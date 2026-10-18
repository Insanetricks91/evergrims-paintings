#!/usr/bin/env python3
"""EverGrims retro backlit set -- the NEON SIGNS.

  neon_open_1x2.png          classic shop-window OPEN: red tube letters, blue tube border, fully lit
  neon_closed_1x2.png        the matching CLOSED (same housing, border and colours, so the two swap)
  neon_sushi_1x3.png         pink script "Sushi" + a salmon nigiri tube icon, teal border
  neon_fishin_dock_2x3.gif   FISHIN' DOCK on a board that has hung outside for 50 years; lights up
                             letter by letter, flashes, goes dark, and loops back to fully lit (frame 1)

Drawn at 64 design px per block with the shared kit (../kit/egwpix.py), written 2x nearest, so every
block is one 128-px map. Every pixel is a Minecraft map colour. Python standard library only.
Run:  python3 neon.py            (writes the finished files + review sheets beside this script)
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'kit'))
import egwpix as e  # noqa: E402

OUT = HERE
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)

C = e.mc
BLACK = e.BLACK

# ------------------------------------------------------------------------------------ tube geometry


def _unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d else (0.0, 0.0)


def fillet(pts, closed=False, steps=10):
    """Polyline through pts (x, y[, r]) with each corner rounded by radius r (a quadratic fillet)."""
    pts = [tuple(p) + ((0,) if len(p) == 2 else ()) for p in pts]
    n = len(pts)
    out = []
    rng = range(n) if closed else range(n)
    for i in rng:
        x, y, r = pts[i]
        if (not closed and (i == 0 or i == n - 1)) or r <= 0:
            out.append((x, y))
            continue
        px_, py_, _ = pts[i - 1]
        nx, ny, _ = pts[(i + 1) % n]
        l1, l2 = math.hypot(px_ - x, py_ - y), math.hypot(nx - x, ny - y)
        rr = min(r, l1 / 2, l2 / 2)
        d1, d2 = _unit(px_ - x, py_ - y), _unit(nx - x, ny - y)
        ax, ay = x + d1[0] * rr, y + d1[1] * rr
        bx, by = x + d2[0] * rr, y + d2[1] * rr
        for k in range(steps + 1):
            t = k / steps
            qx = (1 - t) ** 2 * ax + 2 * (1 - t) * t * x + t * t * bx
            qy = (1 - t) ** 2 * ay + 2 * (1 - t) * t * y + t * t * by
            out.append((qx, qy))
    if closed:
        out.append(out[0])
    return out


def catmull(pts, steps=12):
    """Smooth curve through pts (Catmull-Rom, ends clamped)."""
    if len(pts) < 3:
        return list(pts)
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(pts[-1])
    return out


def ellipse_pts(cx, cy, rx, ry, a0=0, a1=360, steps=48):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / steps)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / steps))) for k in range(steps + 1)]


def stroke_pixels(path, w=3):
    """Pixels covered by a round brush of diameter w swept along a polyline of float points."""
    R = w / 2.0
    out = set()
    for (a, b) in zip(path, path[1:] if len(path) > 1 else path):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25))
        for k in range(n + 1):
            t = k / n
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            for iy in range(int(math.floor(y - R)) - 1, int(math.ceil(y + R)) + 1):
                for ix in range(int(math.floor(x - R)) - 1, int(math.ceil(x + R)) + 1):
                    if (ix + 0.5 - x) ** 2 + (iy + 0.5 - y) ** 2 <= R * R + 1e-6:
                        out.add((ix, iy))
    return out


def snap(v):
    """Snap a coordinate onto a pixel centre so straight tubes come out an exact width."""
    return math.floor(v) + 0.5

# ------------------------------------------------------------------------------------ tube alphabet
# Blocky rounded "sign shop" capitals. Units: cap height 10, y down. Each glyph = (width, [strokes]);
# a stroke is ('p', [(x, y, corner_r), ...]) a filleted polyline, or ('c', [(x, y), ...]) a smooth curve.


def G(width, *strokes):
    return (width, list(strokes))


ALPHA = {
    'O': G(7.4, ('p', [(0, 0, 3.2), (7.4, 0, 3.2), (7.4, 10, 3.2), (0, 10, 3.2)], 'closed')),
    'P': G(6.4, ('p', [(0, 10), (0, 0, 0.6), (6.4, 0, 2.6), (6.4, 5.4, 2.6), (0, 5.4)])),
    'E': G(5.8, ('p', [(5.8, 0), (0, 0, 0.6), (0, 10, 0.6), (5.8, 10)]), ('p', [(0, 5), (4.8, 5)])),
    'N': G(6.8, ('p', [(0, 10), (0, 0, 0.5), (6.8, 10, 0.5), (6.8, 0)])),
    'C': G(6.6, ('p', [(6.6, 0.4), (6.6, 0), (0, 0, 3.2), (0, 10, 3.2), (6.6, 10), (6.6, 9.6)])),
    'L': G(5.6, ('p', [(0, 0), (0, 10, 0.6), (5.6, 10)])),
    'S': G(6.6, ('p', [(6.6, 0), (0, 0, 2.4), (0, 5, 2.4), (6.6, 5, 2.4), (6.6, 10, 2.4), (0, 10)])),
    'D': G(6.8, ('p', [(0, 0, 0.6), (3.6, 0, 3.2), (6.8, 3.2, 3.0), (6.8, 6.8, 3.0), (3.6, 10, 3.2), (0, 10, 0.6)], 'closed')),
    'F': G(5.8, ('p', [(5.8, 0), (0, 0, 0.6), (0, 10)]), ('p', [(0, 5), (4.6, 5)])),
    'I': G(0.0, ('p', [(0, 0), (0, 10)])),
    'H': G(6.6, ('p', [(0, 0), (0, 10)]), ('p', [(6.6, 0), (6.6, 10)]), ('p', [(0, 5), (6.6, 5)])),
    'K': G(6.4, ('p', [(0, 0), (0, 10)]), ('p', [(6.4, 0), (0.6, 5.2, 0.8), (6.4, 10)])),
    "'": G(0.6, ('p', [(0.6, 0), (0.6, 2.2, 0.6), (0, 3.6)])),
}


def word_layout(word, height, gap, w=3):
    """Width in px of `word` set in the tube alphabet at cap `height` px (stroke centre to centre)."""
    s = (height - w) / 10.0
    total = 0.0
    for i, ch in enumerate(word):
        total += ALPHA[ch][0] * s + (gap if i < len(word) - 1 else 0)
    return total + w


def word_tubes(word, x, y, height, gap, w=3, snap_xy=True):
    """Return [(char, [pixel set per stroke ...]) ...] for word with its outer top-left at (x, y)."""
    s = (height - w) / 10.0
    ox = x + w / 2.0
    oy = y + w / 2.0
    res = []
    for ch in word:
        gw, strokes = ALPHA[ch]
        tubes = []
        for st in strokes:
            kind, pts = st[0], st[1]
            closed = len(st) > 2 and st[2] == 'closed'
            if kind == 'p':
                P = []
                for p in pts:
                    X, Y = ox + p[0] * s, oy + p[1] * s
                    if snap_xy:
                        X, Y = snap(X), snap(Y)
                    P.append((X, Y, (p[2] * s if len(p) > 2 else 0)))
                path = fillet(P, closed=closed)
            else:
                path = catmull([(ox + p[0] * s, oy + p[1] * s) for p in pts])
            tubes.append({'path': path, 'px': stroke_pixels(path, w)})
        res.append((ch, tubes))
        ox += gw * s + gap
    return res

# ------------------------------------------------------------------------------------ lighting


def ring_halo(core, extra=()):
    """Halo rings for a tube: two darker shades of its own hue, then any extra outer rings."""
    return [e.shade(core, -2), e.shade(core, -3)] + list(extra)


def light_tube(cv, px, core, hot=None, halo=None, blend=None):
    """Light a tube. blend=(t2, t3, ...) keeps ring 1 a solid halo shade but tints the outer rings into the
    surface underneath (the board's texture shows through the glow) -- for the textured dock board."""
    if blend is None:
        e.glow(cv, px, core, halo=halo if halo is not None else ring_halo(core), hot=hot)
        return
    halo = halo if halo is not None else ring_halo(core)
    pts = {(int(p[0]), int(p[1])) for p in px}
    radius = 1 + len(blend)
    rings = {}
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d = math.hypot(dx, dy)
            if 0 < d <= radius + 0.5:
                k = max(1, int(math.ceil(d - 0.5)))
                for (x, y) in pts:
                    q = (x + dx, y + dy)
                    if q not in pts and (q not in rings or rings[q] > k):
                        rings[q] = k
    tint = e.shade(core, -1)
    for (x, y), k in rings.items():
        under = cv.get(x, y)
        if under is None:
            continue
        col = e.nearest(halo[0]) if k == 1 else e.nearest(e.mix(under, tint, blend[k - 2]))
        if e.lum(col) > e.lum(under):
            cv.px(x, y, col)
    e.glow(cv, pts, core, halo=[], hot=hot)


def dead_colours(core):
    """Switched-off glass: the coating's tint, desaturated -- a lit-side glint, a body and a shadow side."""
    return (e.nearest(e.mix(core, (128, 128, 128), 0.76)), e.nearest(e.mix(core, (72, 72, 72), 0.76)),
            e.nearest(e.mix(core, (30, 30, 30), 0.78)))


def dead_tube(cv, px, core):
    """An unlit glass tube: dull tinted body, a glint on its upper-left side, shade on its lower-right."""
    hi, body, lo = dead_colours(core)
    for (x, y) in px:
        if (x + 1, y) not in px or (x, y + 1) not in px:
            cv.px(x, y, lo)
        elif (x - 1, y) not in px or (x, y - 1) not in px:
            cv.px(x, y, hi)
        else:
            cv.px(x, y, body)


# ------------------------------------------------------------------------------------ OPEN / CLOSED

RED = C('FIRE', 3)
RED_HOT = C('COLOR_PINK', 3)
RED_HALO = [C('FIRE', 0), C('NETHER', 2), C('NETHER', 0)]
BLUE = C('LAPIS', 3)
BLUE_HOT = C('ICE', 3)
BLUE_HALO = [C('LAPIS', 0), C('COLOR_BLUE', 1), C('COLOR_BLUE', 0)]


def backer(cv):
    """Black acrylic backer: a faint bevelled rim and four corner standoffs, so it reads as a real object."""
    W, H = cv.w, cv.h
    rim, rim2 = C('COLOR_BLACK', 3), C('COLOR_BLACK', 1)
    cv.rect(0, 0, W, 1, rim)
    cv.rect(0, 0, 1, H, rim)
    cv.rect(0, H - 1, W, H, rim2)
    cv.rect(W - 1, 0, W, H, rim2)
    for (sx, sy) in ((2, 2), (W - 4, 2), (2, H - 4), (W - 4, H - 4)):
        cv.rect(sx, sy, sx + 2, sy + 2, C('COLOR_GRAY', 1))
        cv.px(sx, sy, C('DEEPSLATE', 1))
        cv.px(sx + 1, sy + 1, C('COLOR_GRAY', 0))


def shop_sign(word, height, gap, y_top=None):
    """1x2 window sign: blue rounded tube border, red tube word, black backer. Returns the canvas."""
    cv = e.blocks(1, 2)
    W, H = cv.w, cv.h
    backer(cv)
    border = stroke_pixels(fillet([(snap(4), snap(4), 9), (snap(W - 5), snap(4), 9), (snap(W - 5), snap(H - 5), 9),
                                   (snap(4), snap(H - 5), 9)], closed=True), 3)
    ww = word_layout(word, height, gap)
    x0 = round((W - ww) / 2)
    y0 = round((H - height) / 2) if y_top is None else y_top
    letters = word_tubes(word, x0, y0, height, gap)
    light_tube(cv, border, BLUE, hot=BLUE_HOT, halo=BLUE_HALO)
    for ch, tubes in letters:
        for t in tubes:
            light_tube(cv, t['px'], RED, hot=RED_HOT, halo=RED_HALO)
    return cv


def zoom_sheet(frames, name, scale=4, delays=None, title=None):
    return e.preview(frames, os.path.join(WORK, name), scale=scale, delays_ms=delays, title=title)


# ------------------------------------------------------------------------------------ SUSHI
# Script "Sushi" as bent tubes. Units: cap/ascender height 10, x-height at y=5, baseline y=10.

SCRIPT_SUSHI = [
    # capital S, traced from its lower-left curl up to the top-right terminal
    ('c', [(0.2, 7.6), (0.9, 9.4), (2.6, 10.1), (4.6, 9.6), (5.5, 8.0), (4.9, 6.3), (3.2, 5.2),
           (1.8, 4.0), (1.6, 2.1), (2.8, 0.5), (4.8, 0.0), (6.3, 0.5), (6.9, 1.4)]),
    # u, with its lead-in and exit
    ('c', [(6.4, 5.6), (7.2, 5.0), (7.6, 6.2), (7.4, 8.4), (7.9, 9.8), (9.0, 10.0), (10.0, 9.1), (10.5, 7.2),
           (10.6, 5.1), (10.6, 7.5), (10.8, 9.4), (11.7, 10.0)]),
    # s: rises to a point, swings round its bowl and curls off at the lower left
    ('c', [(11.7, 10.0), (12.6, 8.4), (13.3, 6.2), (13.6, 4.9), (14.3, 6.1), (15.1, 7.5), (15.1, 9.1),
           (14.2, 10.1), (12.9, 10.0), (12.2, 9.2)]),
    # h: a flicked-in ascender straight down to the baseline, then the hump
    ('c', [(16.0, 1.1), (16.5, 0.3), (17.1, 0.0), (16.9, 2.4), (16.5, 6.0), (16.1, 10.0)]),
    ('c', [(16.1, 10.0), (16.4, 7.6), (17.2, 5.6), (18.3, 5.1), (19.2, 5.8), (19.3, 7.8), (19.3, 9.2),
           (19.9, 10.0), (20.8, 9.4), (21.4, 7.4), (21.6, 5.2)]),
    # i stem and tail
    ('c', [(21.6, 5.2), (21.6, 8.2), (21.8, 9.6), (22.6, 10.0), (23.6, 9.4)]),
]
SCRIPT_DOT = (21.7, 2.6)
# give the h and i a little more air from the s
SCRIPT_SUSHI = SCRIPT_SUSHI[:3] + [(k, [(x + 0.7, y) for (x, y) in pts]) for (k, pts) in SCRIPT_SUSHI[3:]]
SCRIPT_DOT = (SCRIPT_DOT[0] + 0.7, SCRIPT_DOT[1])


def script_tubes(strokes, x, y, s, w=3):
    out = []
    for kind, pts in strokes:
        path = catmull([(x + p[0] * s, y + p[1] * s) for p in pts], steps=16)
        out.append(stroke_pixels(path, w))
    return out

PINK = C('COLOR_PINK', 3)
PINK_HOT = C('QUARTZ', 2)
PINK_HALO = [C('COLOR_PINK', 1), C('COLOR_PINK', 0), C('CRIMSON_STEM', 0)]
AQUA = C('DIAMOND', 3)
AQUA_HOT = C('QUARTZ', 2)
AQUA_HALO = [C('DIAMOND', 0), C('WARPED_NYLIUM', 1), C('WARPED_NYLIUM', 0)]
SALMON = C('COLOR_ORANGE', 3)
SALMON_HOT = C('SAND', 3)
SALMON_HALO = [C('COLOR_ORANGE', 0), C('TERRACOTTA_ORANGE', 0), C('TERRACOTTA_BROWN', 1)]
RICE = C('QUARTZ', 2)
RICE_HOT = C('QUARTZ', 3)
RICE_HALO = [C('QUARTZ', 0), C('STONE', 1), C('COLOR_GRAY', 0)]
FAT = C('QUARTZ', 2)


def nigiri_tubes(x, y):
    """A salmon nigiri drawn in tube: rice mound (white), draped salmon slice (orange), fat stripes."""
    rice = catmull([(x + 5, y + 19), (x + 3, y + 25), (x + 8, y + 30), (x + 22, y + 31), (x + 36, y + 30),
                    (x + 41, y + 25), (x + 39, y + 19)], steps=14)
    salmon = catmull([(x + 1, y + 19), (x + 3, y + 12), (x + 11, y + 6), (x + 23, y + 3.5), (x + 35, y + 5),
                      (x + 43, y + 11), (x + 44, y + 17), (x + 38, y + 19), (x + 30, y + 17.5), (x + 21, y + 19),
                      (x + 11, y + 18.5), (x + 4, y + 20.5), (x + 1, y + 19)], steps=14)
    stripes = [catmull([(x + a, y + b), (x + a - 2.0, y + b + 5), (x + a - 3.2, y + b + 9)], steps=10)
               for (a, b) in ((14, 7.5), (23, 5.5), (32, 6.5))]
    return {'rice': stroke_pixels(rice, 3), 'salmon': stroke_pixels(salmon, 3),
            'stripes': [stroke_pixels(p, 2) for p in stripes]}


def sushi_sign():
    cv = e.blocks(1, 3)
    W, H = cv.w, cv.h
    backer(cv)
    border = stroke_pixels(fillet([(snap(4), snap(4), 9), (snap(W - 5), snap(4), 9), (snap(W - 5), snap(H - 5), 9),
                                   (snap(4), snap(H - 5), 9)], closed=True), 3)
    light_tube(cv, border, AQUA, hot=AQUA_HOT, halo=AQUA_HALO)
    ix, iy = 21, 14
    nig = nigiri_tubes(ix, iy)
    light_tube(cv, nig['rice'], RICE, hot=RICE_HOT, halo=RICE_HALO)
    light_tube(cv, nig['salmon'], SALMON, hot=SALMON_HOT, halo=SALMON_HALO)
    for st in nig['stripes']:
        e.glow(cv, st, FAT, halo=[C('COLOR_ORANGE', 1)])
    s, wx, wy = 3.7, 78, 12
    for px in script_tubes(SCRIPT_SUSHI, wx, wy, s):
        light_tube(cv, px, PINK, hot=PINK_HOT, halo=PINK_HALO)
    dx, dy = SCRIPT_DOT
    dot = stroke_pixels([(wx + dx * s, wy + dy * s), (wx + dx * s + 0.01, wy + dy * s)], 4)
    light_tube(cv, dot, PINK, hot=PINK_HOT, halo=PINK_HALO)
    return cv

# ------------------------------------------------------------------------------------ FISHIN' DOCK
# A painted plank board that has hung on a dock for 50 years: sun-faded paint peeling off grey wood,
# a rusted angle-iron frame, rust bleeding down from every bolt, grime, a gull's opinion or two.

P = {   # board palette (all map colours)
    'paint': C('COLOR_CYAN', 0), 'paint_lt': C('COLOR_CYAN', 1), 'paint_dk': C('TERRACOTTA_CYAN', 0),
    'paint_fade': C('TERRACOTTA_CYAN', 1), 'wood': C('TERRACOTTA_LIGHT_GRAY', 0), 'wood_lt': C('TERRACOTTA_LIGHT_GRAY', 1),
    'wood_dk': C('TERRACOTTA_GRAY', 1), 'wood_grey': C('STONE', 0), 'seam': C('TERRACOTTA_BLACK', 1),
    'seam_lt': C('TERRACOTTA_CYAN', 1), 'rust': C('TERRACOTTA_ORANGE', 0), 'rust_lt': C('TERRACOTTA_ORANGE', 1),
    'rust_dk': C('TERRACOTTA_RED', 0), 'rust_br': C('COLOR_BROWN', 0), 'rust_hot': C('COLOR_ORANGE', 0),
    'iron': C('DEEPSLATE', 0), 'iron_lt': C('DEEPSLATE', 1), 'iron_dk': C('COLOR_GRAY', 0),
    'grime': C('TERRACOTTA_BROWN', 0), 'grime2': C('TERRACOTTA_GREEN', 0), 'moss': C('COLOR_GREEN', 0),
    'poop': C('QUARTZ', 0), 'poop2': C('WOOL', 0), 'poop3': C('TERRACOTTA_WHITE', 0),
}


class ValueNoise:
    """Smooth 2-D value noise (bilinear grid of randoms, a few octaves), 0..1."""

    def __init__(self, rng, cell=16, octaves=3, sx=1.0, sy=1.0):
        self.o = []
        for k in range(octaves):
            c = max(2, cell >> k)
            grid = {}
            self.o.append((c, grid, 0.5 ** k, rng.random() * 1000))
        self.rng = rng
        self.sx, self.sy = sx, sy

    def _g(self, grid, i, j):
        if (i, j) not in grid:
            grid[(i, j)] = self.rng.random()
        return grid[(i, j)]

    def __call__(self, x, y):
        tot = wsum = 0.0
        for (c, grid, w, _o) in self.o:
            fx, fy = x / (c * self.sx), y / (c * self.sy)
            i, j = int(math.floor(fx)), int(math.floor(fy))
            tx, ty = fx - i, fy - j
            tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
            a = self._g(grid, i, j) + (self._g(grid, i + 1, j) - self._g(grid, i, j)) * tx
            b = self._g(grid, i, j + 1) + (self._g(grid, i + 1, j + 1) - self._g(grid, i, j + 1)) * tx
            tot += (a + (b - a) * ty) * w
            wsum += w
        return tot / wsum


def _noise_blob(cx, cy, rx, ry, rng, wob=0.35):
    """A ragged blob (pixel set) for peeled paint, rust patches and grime."""
    out = set()
    k = [rng.uniform(-wob, wob) for _ in range(6)]
    ph = [rng.uniform(0, 6.28) for _ in range(6)]
    for y in range(int(cy - ry * 1.6) - 1, int(cy + ry * 1.6) + 2):
        for x in range(int(cx - rx * 1.6) - 1, int(cx + rx * 1.6) + 2):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            a = math.atan2(dy, dx)
            r = 1 + sum(k[i] * math.sin((i + 2) * a + ph[i]) for i in range(6)) / 2
            if dx * dx + dy * dy <= r * r:
                out.add((x, y))
    return out


def rust_streak(cv, x, y, length, rng, width=2, strong=1.0):
    """Rust bleeding down from a bolt: dense and orange at the top, thinning to brown specks."""
    xx = x
    for i in range(length):
        t = i / max(1, length)
        if rng.random() < 0.25:
            xx += rng.choice((-1, 0, 0, 1)) * 0.5
        for w in range(width):
            if rng.random() < (1.0 - t * 0.85) * strong:
                col = P['rust_lt'] if t < 0.18 else (P['rust'] if t < 0.5 else (P['rust_dk'] if rng.random() < 0.6 else P['rust_br']))
                cv.px(int(xx) + w, y + i, col)


def bolt(cv, x, y, streak=0, rng=None):
    cv.rect(x - 1, y - 1, x + 2, y + 2, P['rust_dk'])
    cv.px(x, y, P['rust_lt'])
    cv.px(x - 1, y - 1, P['rust'])
    cv.px(x + 1, y + 1, P['seam'])
    if streak and rng:
        rust_streak(cv, x - 1, y + 2, streak, rng, width=3, strong=0.9)


def dock_board(rng):
    W, H = 3 * e.BLOCK, 2 * e.BLOCK
    cv = e.Canvas(W, H, P['paint'])
    F = 5                                         # frame thickness
    fade = ValueNoise(rng, cell=24, octaves=3, sx=2.2, sy=1.0)   # sun-fade blotches, stretched along the grain
    seams = [F, 29, 52, 76, 99, H - F]
    # ---- planks: faded paint, darker near seams, grain streaks
    for i in range(len(seams) - 1):
        y0, y1 = seams[i], seams[i + 1]
        for y in range(y0, y1):
            for x in range(F, W - F):
                f = fade(x, y) + (0.22 if y < 40 else 0.0) * (1 - y / 40) - 0.03 * i + rng.uniform(-0.07, 0.07)
                if f > 0.66:
                    col = P['wood_grey'] if f > 0.8 else P['paint_fade']
                elif f < 0.36:
                    col = P['paint_dk']
                else:
                    col = P['paint']
                cv.px(x, y, col)
        for _ in range(26):                       # grain: long thin streaks of darker / lighter paint
            gy = rng.randrange(y0 + 2, y1 - 1)
            gx = rng.randrange(F, W - F - 10)
            ln = rng.randrange(8, 40)
            col = rng.choice((P['paint_dk'], P['paint_dk'], P['paint_lt']))
            for x in range(gx, min(W - F, gx + ln)):
                if rng.random() < 0.8:
                    cv.px(x, gy, col)
        cv.rect(F, y0, W - F, y0 + 1, P['seam'])          # gap between planks
        cv.rect(F, y0 + 1, W - F, y0 + 2, P['paint_dk'])
        # plank butt joint somewhere along the plank
        jx = rng.randrange(40, W - 40)
        cv.rect(jx, y0, jx + 1, y1, P['seam'])
    # ---- peeling paint: patches of bare sun-grey wood with a curled light rim
    for _ in range(26):
        cx, cy = rng.uniform(F + 4, W - F - 4), rng.uniform(F + 3, H - F - 3)
        blob = _noise_blob(cx, cy, rng.uniform(3, 11), rng.uniform(1.5, 4.5), rng)
        for (x, y) in blob:
            if F <= x < W - F and F + 1 <= y < H - F:
                r = rng.random()
                cv.px(x, y, P['wood_grey'] if r < 0.55 else (P['paint_fade'] if r < 0.8 else P['wood']))
        for (x, y) in blob:
            if (x, y + 1) not in blob and rng.random() < 0.8:
                cv.px(x, y + 1, P['paint_lt'])            # the curled paint edge catches the light
            if (x, y - 1) not in blob and rng.random() < 0.6:
                cv.px(x, y, P['wood_dk'])                 # shadow under the lifted edge
        for (x, y) in blob:                                 # grain in the bare wood
            if rng.random() < 0.12:
                cv.px(x, y, P['wood_lt'] if rng.random() < 0.4 else P['wood_dk'])
    for i in range(len(seams) - 1):                       # seams re-cut through the peels
        cv.rect(F, seams[i], W - F, seams[i] + 1, P['seam'])
    # ---- general age
    e.weather(cv, (F, F, W - F, H - F), rng, density=0.08, delta=-1)
    # ---- grime: the bottom plank and the lower corners went dark and green
    grime = ValueNoise(rng, cell=10, octaves=3, sx=1.6, sy=1.0)
    for y in range(H - 40, H - F):
        t = (y - (H - 40)) / 35
        for x in range(F, W - F):
            gv = grime(x, y) * 0.7 + t * 0.62 + rng.uniform(-0.05, 0.05)
            if gv > 0.92:
                cv.px(x, y, P['grime'] if grime(x * 3, y * 3) > 0.5 else P['grime2'])
            elif gv > 0.74:
                cv.px(x, y, P['paint_dk'])
    for _ in range(18):                                   # rain stains running down the planks
        sx, sy = rng.randrange(F + 4, W - F - 4), rng.choice([s + 2 for s in seams[:-1]])
        for d in range(rng.randrange(6, 20)):
            if rng.random() < 0.7:
                cv.px(sx, sy + d, P['paint_dk'])
    for (cx, cy) in ((F + 6, H - F - 4), (W - F - 8, H - F - 3), (F + 4, F + 30)):
        for (x, y) in _noise_blob(cx, cy, 9, 6, rng, 0.5):
            if F <= x < W - F and F <= y < H - F and rng.random() < 0.6:
                cv.px(x, y, rng.choice((P['moss'], P['grime2'], P['grime2'])))
    # ---- the rusted angle-iron frame
    for y in range(H):
        for x in range(W):
            d = min(x, y, W - 1 - x, H - 1 - y)
            if d < F:
                col = (P['iron_lt'] if d == 1 else P['iron'] if d < 4 else P['iron_dk'])
                if d == 0:
                    col = P['seam']
                if d >= 1 and (y == d or x == d) and d < 3:
                    col = P['iron_lt']
                cv.px(x, y, col)
    frame_px = [(x, y) for y in range(H) for x in range(W) if 0 < min(x, y, W - 1 - x, H - 1 - y) < F]
    for _ in range(46):                                   # rust eating through the frame paint
        cx, cy = rng.choice(frame_px)
        for (x, y) in _noise_blob(cx, cy, rng.uniform(2, 7), rng.uniform(1.5, 4), rng, 0.5):
            if 0 < min(x, y, W - 1 - x, H - 1 - y) < F:
                cv.px(x, y, rng.choice((P['rust'], P['rust'], P['rust_dk'], P['rust_lt'], P['rust_br'])))
    e.weather(cv, frame_px, rng, density=0.15, delta=-1)
    cv.rect(F, F, W - F, F + 1, P['seam'])                 # frame lip shadow on the board
    cv.rect(F, F, F + 1, H - F, P['seam'])
    # rust run-off from the frame's top edge and corners
    for _ in range(12):
        rust_streak(cv, rng.randrange(F + 2, W - F - 3), F + 1, rng.randrange(6, 22), rng, width=rng.choice((1, 2)), strong=0.7)
    # ---- bolts holding the planks (each one bleeds rust)
    for i in range(len(seams) - 1):
        yc = (seams[i] + seams[i + 1]) // 2
        for xc in (F + 4, W - F - 5):
            bolt(cv, xc, yc, streak=rng.randrange(6, 16), rng=rng)
    # ---- the neon's own mounting bolts, between the rows of tube, each with its rust run
    for (xc, yc) in ((24, 50), (100, 49), (171, 50), (60, 94), (128, 93), (176, 95)):
        bolt(cv, xc, yc, streak=rng.randrange(8, 15), rng=rng)
    # ---- a gull was here
    for (bx, by, n) in ((61, 4, 3), (138, 4, 2), (178, 52, 2)):
        for k in range(n):
            x = bx + rng.randrange(-4, 5)
            y = by + rng.randrange(0, 2)
            cv.rect(x, y, x + 2, y + 2, P['poop'])
            cv.px(x + 2, y, P['poop2'])
            for d in range(rng.randrange(2, 6)):          # drip
                cv.px(x + (d % 2), y + 2 + d, P['poop2'] if d < 3 else P['poop3'])
    return cv


def fish_hook_tubes(x, y, k=1.0):
    """Fish (facing right) about to take a hook hanging on its line. Returns dict of pixel sets."""
    def T(pts):
        return [(x + px_ * k, y + py_ * k) + tuple(r * k for r in rest) for (px_, py_, *rest) in pts]
    body = catmull(T([(36, 17), (30, 10.5), (21, 8.5), (12, 11), (8, 16), (12, 21), (21, 23.5), (30, 21.5), (36, 17)]), steps=14)
    tail = fillet(T([(8.5, 16), (1.5, 9.5, 1.2), (2.5, 16), (1.5, 22.5, 1.2), (8.5, 16)]))
    gill = catmull(T([(27, 11.5), (25, 16), (27, 20.5)]), steps=10)
    ex, ey = T([(31, 14.5)])[0]
    eye = stroke_pixels([(ex, ey), (ex + 0.01, ey)], 2.4)
    hx = snap(x + 44 * k)
    line = [(hx, y - 4), (hx, y + 17 * k)]
    line = [(hx, y - 4), (hx, y + 11 * k)]
    hook = catmull([(hx, y + 11 * k)] + T([(44.0, 20), (44.0, 25.5), (42.6, 29.4), (39.6, 30.4), (36.9, 28.6),
                                           (36.2, 25.0), (36.6, 22.4)]), steps=14)
    bx, by = T([(36.6, 22.4)])[0]
    barb = [(bx, by), (bx + 2.6, by + 3.2)]
    return {'fish': stroke_pixels(body, 3) | stroke_pixels(tail, 3) | stroke_pixels(gill, 2) | eye,
            'line': stroke_pixels(line, 1), 'hook': stroke_pixels(hook, 3) | stroke_pixels(barb, 2)}


def wave_tube(x0, x1, y, amp=3.0, period=22.0):
    pts = [(x0 + i * 0.5, y + amp * math.sin((i * 0.5) / period * 2 * math.pi)) for i in range(int((x1 - x0) * 2) + 1)]
    return stroke_pixels(pts, 3)


ORANGE = C('COLOR_ORANGE', 3)
ORANGE_HOT = C('SAND', 3)
ORANGE_HALO = [C('COLOR_ORANGE', 1), C('COLOR_ORANGE', 0), C('TERRACOTTA_ORANGE', 0)]
DOCK_AQUA = C('DIAMOND', 3)
DOCK_AQUA_HALO = [C('DIAMOND', 1), C('DIAMOND', 0), C('WARPED_NYLIUM', 1)]
FISH_GREEN = C('COLOR_LIGHT_GREEN', 3)
FISH_HALO = [C('COLOR_LIGHT_GREEN', 1), C('COLOR_LIGHT_GREEN', 0), C('COLOR_GREEN', 0)]
HOOK_RED = C('FIRE', 3)
HOOK_HALO = [C('FIRE', 1), C('FIRE', 0), C('NETHER', 2)]
WAVE_BLUE = C('LAPIS', 3)
WAVE_HALO = [C('LAPIS', 1), C('LAPIS', 0), C('COLOR_BLUE', 0)]


def _worn(px, rng, spots, r=2.2):
    """Patches of a tube whose coating has worn thin (they glow a shade dimmer)."""
    pts = sorted(px)
    out = set()
    for _ in range(spots):
        cx, cy = rng.choice(pts)
        for (x, y) in pts:
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                out.add((x, y))
    return out


def _ends(tubes):
    """Open tube ends (where the electrodes sit) of a letter's strokes."""
    out = []
    for t in tubes:
        p = t['path']
        if math.hypot(p[0][0] - p[-1][0], p[0][1] - p[-1][1]) > 1.0:
            out += [p[0], p[-1]]
    return out


def _blackened(px, ends, rng, share=0.55):
    """Old neon goes dark near its electrodes: {pixel: levels darker} for a random share of the tube ends."""
    out = {}
    for (ex, ey) in ends:
        if rng.random() > share:
            continue
        reach = rng.uniform(3.0, 5.0)
        for (x, y) in px:
            d = math.hypot(x + 0.5 - ex, y + 0.5 - ey)
            if d <= reach:
                k = 2 if d <= reach * 0.45 else 1
                out[(x, y)] = max(out.get((x, y), 0), k)
    return out


def dock_layout(rng):
    """All tube groups of the FISHIN' DOCK sign. Each: dict(name, px, core, hot, halo[, worn, line])."""
    W = 3 * e.BLOCK
    groups = []
    h1, g1 = 36, 8
    ww = word_layout("FISHIN'", h1, g1)
    x1 = round((W - ww) / 2) + 2
    for i, (ch, tubes) in enumerate(word_tubes("FISHIN'", x1, 9, h1, g1)):
        groups.append({'name': f'{ch}{i}', 'px': set().union(*[t['px'] for t in tubes]), 'core': ORANGE,
                       'hot': ORANGE_HOT, 'halo': ORANGE_HALO, 'ends': _ends(tubes)})
    h2, g2 = 34, 7
    ww2 = word_layout('DOCK', h2, g2)
    k = 1.2
    icon_w = round(46 * k)
    total = icon_w + 9 + ww2
    xi = round((W - total) / 2)
    xd = xi + icon_w + 9
    for i, (ch, tubes) in enumerate(word_tubes('DOCK', xd, 55, h2, g2)):
        groups.append({'name': f'{ch}{i + 7}', 'px': set().union(*[t['px'] for t in tubes]), 'core': DOCK_AQUA,
                       'hot': C('QUARTZ', 2), 'halo': DOCK_AQUA_HALO, 'ends': _ends(tubes)})
    fh = fish_hook_tubes(xi, 53, k)
    groups.append({'name': 'fish', 'px': fh['fish'], 'core': FISH_GREEN, 'hot': C('GOLD', 3), 'halo': FISH_HALO})
    groups.append({'name': 'hook', 'px': fh['hook'], 'core': HOOK_RED, 'hot': None, 'halo': HOOK_HALO,
                   'line': fh['line']})
    groups.append({'name': 'wave', 'px': wave_tube(15, W - 16, 106), 'core': WAVE_BLUE, 'hot': C('ICE', 3),
                   'halo': WAVE_HALO})
    # fifty years of weather on the glass: a few worn-thin patches, and one tired old C tube
    by = {g['name']: g for g in groups}
    for name, spots in (('S2', 3), ('N5', 2), ('F0', 1), ('O8', 2), ('K10', 2), ('wave', 5)):
        by[name]['worn'] = _worn(by[name]['px'], rng, spots)
    for g in groups:
        if g.get('ends'):
            g['black'] = _blackened(g['px'], g['ends'], rng)
    by['C9']['core'] = C('DIAMOND', 2)
    by['C9']['halo'] = [C('DIAMOND', 0), C('WARPED_NYLIUM', 1), C('WARPED_NYLIUM', 0)]
    return groups


def dock_frame(board, groups, lit_names):
    cv = board.copy()
    shadow = C('TERRACOTTA_BLACK', 0)
    for g in groups:                          # tubes stand off the board: a soft shadow below-right
        for (x, y) in g['px']:
            for (dx, dy) in ((1, 2), (2, 2), (1, 3)):
                q = (x + dx, y + dy)
                if q not in g['px']:
                    cv.px(q[0], q[1], shadow)
    for g in groups:
        if 'line' in g:
            for (x, y) in g['line']:
                cv.px(x, y, C('STONE', 1))
    for g in groups:
        if g['name'] not in lit_names:
            dead_tube(cv, g['px'], g['core'])
            lo = dead_colours(g['core'])[2]
            for (x, y), k in g.get('black', {}).items():   # the electrode soot shows when it is off, too
                if k == 2:
                    cv.px(x, y, lo)
    for g in groups:
        if g['name'] in lit_names:
            light_tube(cv, g['px'], g['core'], hot=g['hot'], halo=g['halo'], blend=DOCK_BLEND)
            for (x, y) in g.get('worn', ()):
                if cv.get(x, y) == g['core']:
                    cv.px(x, y, e.shade(g['core'], -1))
                elif cv.get(x, y) == e.nearest(g['hot']):
                    cv.px(x, y, e.shade(g['core'], -1))
            for (x, y), k in g.get('black', {}).items():
                cv.px(x, y, e.shade(g['core'], -k - (1 if k == 2 else 0)))
    return cv


DOCK_BLEND = (0.55, 0.32, 0.15)   # outer glow rings tint the board instead of covering it

DOCK_STEPS = [   # (lit groups, ms). F1 = fully lit (also the Bedrock still)
    ('ALL', 3000),
    ([], 700),
    (['F0', 'I1'], 300),
    (['S2', 'H3'], 300),
    (['I4', 'N5'], 300),
    (["'6"], 300),
    (['D7', 'O8'], 300),
    (['C9', 'K10'], 300),
    (['fish', 'hook'], 300),
    (['wave'], 500),
    ('OFF', 200),
    ('ALL', 250),
    ('OFF', 200),
    ('ALL', 400),
    ('OFF', 800),
]


def dock_frames(seed=1950):
    rng = random.Random(seed)
    board = dock_board(rng)
    groups = dock_layout(random.Random(seed + 1))
    every = {g['name'] for g in groups}
    frames, delays, lit = [], [], set()
    for (step, ms) in DOCK_STEPS:
        if step == 'ALL':
            now = every
        elif step == 'OFF':
            now = set()
        else:
            lit |= set(step)
            now = set(lit)
        frames.append(dock_frame(board, groups, now))
        delays.append(ms)
    return frames, delays


# ------------------------------------------------------------------------------------ build + checks


def _check_png(path, hxw):
    cv = e.read_png(path)
    assert (cv.h // e.MAP_PX, cv.w // e.MAP_PX) == hxw, (path, cv.w, cv.h)
    assert not e.off_palette(cv), path
    return cv


def build():
    prev = os.path.join(OUT, 'previews')
    os.makedirs(prev, exist_ok=True)
    report = []
    statics = [('neon_open', 1, 2, lambda: shop_sign('OPEN', 32, 6)),
               ('neon_closed', 1, 2, lambda: shop_sign('CLOSED', 24, 5)),
               ('neon_sushi', 1, 3, sushi_sign)]
    for name, h, w, fn in statics:
        cv = fn()
        assert not e.off_palette(cv), name            # drawn entirely in map colours, nothing snapped
        path = os.path.join(OUT, e.out_name(name, h, w))
        info = e.save_png(cv, path, quantize=False)
        _check_png(path, (h, w))
        pv = e.preview(cv, os.path.join(prev, f'{name}_{h}x{w}_preview.png'), scale=4,
                       title=f'{name} {h}x{w} (HxW blocks) - static, fully lit')
        report.append((path, info, pv))
    frames, delays = dock_frames()
    for f in frames:
        assert not e.off_palette(f)
    path = os.path.join(OUT, e.out_name('neon_fishin_dock', 2, 3, 'gif'))
    info = e.save_gif(frames, delays, path, quantize=False)
    g = e.read_gif(path)
    assert g['loop'] == 0 and g['delays_ms'] == delays and len(g['frames']) == len(frames)
    for f0, f1 in zip(frames, g['frames']):
        assert f1 == e.upscale(f0) and not e.off_palette(f1)
    sheet = e.preview(frames, os.path.join(prev, 'neon_fishin_dock_2x3_sheet.png'), scale=2, delays_ms=delays, cols=5,
                      title="neon_fishin_dock 2x3 - lit, dark, letters 1-2 at a time, flash, dark, loop")
    still = e.preview(frames[0], os.path.join(prev, 'neon_fishin_dock_2x3_frame1.png'), scale=4,
                      title='frame 1 = the Bedrock still')
    off = e.preview(frames[1], os.path.join(prev, 'neon_fishin_dock_2x3_off.png'), scale=4,
                    title='switched off (frames 2, 11, 13, 15)')
    report.append((path, info, sheet))
    return report, (still, off)


if __name__ == '__main__':
    rep, extra = build()
    for path, info, pv in rep:
        keep = {k: info[k] for k in ('w', 'h', 'blocks_hxw', 'colours', 'snapped_pixels', 'bytes', 'frames', 'duration_ms',
                                     'imageframe_fake_maps') if k in info}
        print(os.path.basename(path), keep, '->', os.path.basename(pv))
    print('extra previews:', [os.path.basename(p) for p in extra])
