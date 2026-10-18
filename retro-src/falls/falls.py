#!/usr/bin/env python3
"""EverGrims Falls -- a 90s "lighted motion" waterfall picture for ImageFrame (3x3 blocks, animated GIF).

The old motion pictures were a still print lit from behind by a slowly turning slotted cylinder, so bands
of light rolled through the painted water while nothing in the scene moved. This recreates that: the
scene (dusk sky, pine cliffs, log cabin, footbridge, faux wood-grain plastic frame, built-in clock,
brass plaque) is identical in every frame; only the water's light changes. Every water pixel has a
fixed phase from its place along the flow and picks its shade from a cycling ramp of map colours, so
bands roll down the falls, rings spread over the pool, the river runs out under the bridge, mist
sparkles and wet rocks glint. Phases advance by exactly 1/FRAMES per frame, so the loop is seamless.

Frame 1 is a finished still (Bedrock shows only frame 1). 64 design px per block, written 2x nearest.
Python standard library only (egwpix kit). Run it to rebuild evergrims_falls_3x3.gif + previews.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'kit'))
import egwpix as e  # noqa: E402

NAME = 'evergrims_falls'
HB, WB = 3, 3                      # height x width in blocks
FRAMES = 12
DELAY = 100                        # ms per frame (multiple of 50)
W, H = WB * e.BLOCK, HB * e.BLOCK  # 192 x 192 design px
FR = 13                            # frame (moulding) width in design px
X0, Y0, X1, Y1 = FR, FR, W - FR, H - FR   # picture area, [X0, X1) x [Y0, Y1)

M = e.mc
SEED = 1991


# ------------------------------------------------------------------------------------------ noise

def _h(*k):
    """Deterministic hash of ints -> [0, 1)."""
    n = SEED * 0x9E3779B1
    for v in k:
        n = (n ^ (int(v) & 0xffffffff)) * 0x85EBCA6B & 0xffffffff
        n ^= n >> 13
        n = n * 0xC2B2AE35 & 0xffffffff
        n ^= n >> 16
    return n / 4294967296.0


def _s(t):
    return t * t * (3 - 2 * t)


def noise1(x, ch=0):
    i = math.floor(x)
    t = _s(x - i)
    a, b = _h(ch, i), _h(ch, i + 1)
    return a + (b - a) * t


def noise2(x, y, ch=0):
    i, j = math.floor(x), math.floor(y)
    tx, ty = _s(x - i), _s(y - j)
    a, b = _h(ch, i, j), _h(ch, i + 1, j)
    c, d = _h(ch, i, j + 1), _h(ch, i + 1, j + 1)
    return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty


def frac(v):
    return v - math.floor(v)


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


# ----------------------------------------------------------------------------- layered canvas

class Scene(e.Canvas):
    """Canvas that remembers which pixels are animated water. Painting a static pixel over an animated
    one makes it static again, so rocks, the bridge and trees occlude water in every frame."""

    def __init__(self, w, h, fill):
        super().__init__(w, h, fill)
        self.anim = {}

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y][x] = c
            self.anim.pop((x, y), None)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            for x in range(max(0, int(x0)), min(self.w, int(x1))):
                self.px(x, y, c)

    def water(self, x, y, fn):
        """Animated pixel: fn(f) -> colour for frame f (0-based). Frame 0 is painted now."""
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y][x] = fn(0)
            self.anim[(x, y)] = fn

    def render(self, f):
        out = e.Canvas.__new__(e.Canvas)
        out.w, out.h = self.w, self.h
        out.p = [row[:] for row in self.p]
        for (x, y), fn in self.anim.items():
            out.p[y][x] = fn(f)
        return out


def ramp_pick(ramp, b):
    return ramp[int(clamp(b) * (len(ramp) - 1) + 0.5)]


# ----------------------------------------------------------------------------------- colours

INK = M('TERRACOTTA_BLACK', 0)          # (19, 11, 8) darkest outline
SKY = [M('COLOR_BLUE', 0), M('TERRACOTTA_BLUE', 1), M('COLOR_PURPLE', 0), M('COLOR_PURPLE', 1),
       M('COLOR_MAGENTA', 1), M('COLOR_PINK', 1), M('COLOR_PINK', 2), M('COLOR_ORANGE', 2),
       M('COLOR_ORANGE', 3), M('GOLD', 3)]

FALLS = [M('COLOR_BLUE', 2), M('LAPIS', 2), M('COLOR_LIGHT_BLUE', 2), M('COLOR_LIGHT_BLUE', 3),
         M('ICE', 3), M('SNOW', 2), M('SNOW', 3)]
POOL_RAMP = [M('COLOR_BLUE', 0), M('COLOR_BLUE', 1), M('COLOR_BLUE', 2), M('LAPIS', 1), M('LAPIS', 2),
        M('COLOR_LIGHT_BLUE', 3), M('ICE', 3), M('SNOW', 2)]
WARM = [M('COLOR_BLUE', 1), M('TERRACOTTA_ORANGE', 1), M('COLOR_ORANGE', 2), M('GOLD', 3)]
STREAM = [M('COLOR_PURPLE', 0), M('COLOR_PURPLE', 1), M('COLOR_MAGENTA', 1), M('COLOR_PINK', 2),
          M('TERRACOTTA_WHITE', 3), M('SAND', 3)]


# ------------------------------------------------------------------------------------- the sky

def draw_sky(c):
    stops = SKY
    e.bayer_vgrad(c, X0, Y0, X1, 84, stops)
    c.rect(X0, 84, X1, 100, stops[-1])
    # stars in the dark upper sky
    rng = random.Random(SEED + 1)
    for _ in range(26):
        x, y = rng.randrange(X0 + 2, X1 - 2), rng.randrange(Y0 + 2, 46)
        if math.hypot(x - CLOCK[0], y - CLOCK[1]) < CLOCK[2] + 5:
            continue
        c.px(x, y, rng.choice([M('ICE', 3), M('QUARTZ', 2), M('ICE', 2)]))
    for (x, y) in ((118, 22), (66, 40), (172, 48)):
        c.px(x, y, M('QUARTZ', 3))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c.px(x + dx, y + dy, M('ICE', 2))
    # crescent moon
    mx, my, r = 151, 25, 6
    for y in range(my - r - 2, my + r + 3):
        for x in range(mx - r - 2, mx + r + 3):
            d = math.hypot(x + .5 - mx, y + .5 - my)
            d2 = math.hypot(x + .5 - (mx + 3.2), y + .5 - (my - 2.0))
            if d <= r and d2 > r - 0.6:
                c.px(x, y, M('SAND', 3) if d2 > r + 0.8 else M('SAND', 2))
            elif r < d <= r + 1.2 and d2 > r + 0.5:
                c.px(x, y, M('COLOR_MAGENTA', 2))


def ridge(c, x0, x1, base, amp, freq, ch, col, rim=None):
    tops = {}
    for x in range(x0, x1):
        t = base - amp * (0.6 * noise1(x * freq, ch) + 0.4 * noise1(x * freq * 2.7, ch + 7))
        t = int(round(t))
        tops[x] = t
        for y in range(t, 140):
            c.px(x, y, col)
        if rim:
            c.px(x, t, rim)
    return tops


# --------------------------------------------------------------------------------------- pines

def pine(c, x, yb, h, w, body, shadow, rim=None, seed=0):
    """Pine silhouette: tip at (x, yb - h), base half-width w/2 at yb, three-ish jagged tiers."""
    rng = random.Random(seed)
    tiers = 3 + h // 14
    for i in range(h):
        y = yb - h + i
        t = i / max(1, h - 1)
        tier = frac(t * tiers)
        hw = (w / 2) * (0.25 + 0.75 * t) * (0.55 + 0.45 * tier) + (rng.random() - 0.5) * 0.9
        hw = max(0.5, hw)
        xl, xr = int(round(x - hw)), int(round(x + hw))
        for xx in range(xl, xr + 1):
            col = shadow if xx > x + 0.3 * hw else body
            c.px(xx, y, col)
        if rim and tier < 0.18 and i > 1:
            c.px(xl, y, rim)
    # trunk stub
    c.px(x, yb, shadow)


# --------------------------------------------------------------------------------- the frame

def draw_frame(c):
    """Faux wood-grain plastic moulding with a gloss line, a gold bead and a dark inner step."""
    prof = {0: M('TERRACOTTA_BLACK', 0), 1: M('COLOR_BROWN', 1), 2: M('PODZOL', 1), 3: M('PODZOL', 2),
            4: M('DIRT', 3), 5: M('PODZOL', 2), 6: M('PODZOL', 1), 7: M('PODZOL', 1), 8: M('COLOR_BROWN', 1),
            9: M('TERRACOTTA_BROWN', 1), 10: M('PODZOL', 1), 11: M('GOLD', 1), 12: M('TERRACOTTA_BLACK', 0)}
    for y in range(H):
        for x in range(W):
            d = min(x, y, W - 1 - x, H - 1 - y)
            if d >= FR:
                continue
            # which rail (mitred corners)
            if d == y:
                along, rail = x, 0
            elif d == x:
                along, rail = y, 1
            elif d == H - 1 - y:
                along, rail = x, 2
            else:
                along, rail = y, 3
            col = prof[d]
            if 2 <= d <= 10 and d != 4:
                g = noise2(along * 0.09, d * 0.55 + rail * 9, 21) + 0.35 * noise1(along * 0.6 + d * 3.1, 22 + rail)
                if g > 0.95:
                    col = e.shade(col, -1)
                elif g < 0.38:
                    col = e.shade(col, +1)
            if d == 4 and rail in (2, 3):
                col = M('DIRT', 2)          # gloss is dimmer on the shaded rails
            if d == 11 and rail in (2, 3):
                col = M('GOLD', 0)
            c.px(x, y, col)


def draw_plaque(c):
    """Little brass title plate screwed to the bottom rail."""
    s = 'EverGrims Falls'
    tw = e.text_width(s)
    px0 = (W - tw) // 2 - 6
    px1 = px0 + tw + 12
    y0, y1 = H - FR + 1, H - 1          # rows 180..190
    c.rect(px0, y0, px1, y1, M('TERRACOTTA_YELLOW', 0))
    c.rect(px0 + 1, y0 + 1, px1 - 1, y1 - 1, M('GOLD', 1))
    c.rect(px0 + 1, y0 + 1, px1 - 1, y0 + 2, M('GOLD', 2))
    c.rect(px0 + 1, y1 - 2, px1 - 1, y1 - 1, M('GOLD', 0))
    for sx in (px0 + 3, px1 - 4):
        sy = (y0 + y1) // 2
        c.px(sx, sy, M('TERRACOTTA_YELLOW', 0))
        c.px(sx, sy - 1, M('GOLD', 3))
    c.text(px0 + 6, y0 + 2, s, M('TERRACOTTA_BROWN', 0), case=True)


# ---------------------------------------------------------------------------------- the clock

CLOCK = (38, 37, 15)       # centre x, y and outer radius (thresholds sit on half-pixels: no nubs)


def draw_clock(c):
    cx, cy, R = CLOCK
    cx += 0.5
    cy += 0.5
    for y in range(int(cy - R - 2), int(cy + R + 3)):
        for x in range(int(cx - R - 2), int(cx + R + 3)):
            d = math.hypot(x + .5 - cx, y + .5 - cy)
            if d <= R + 0.5:
                if d > R - 0.5:
                    col = INK
                elif d > R - 1.5:
                    col = M('GOLD', 3) if (y < cy - (x - cx) * 0.4) else M('GOLD', 1)
                elif d > R - 2.5:
                    col = M('GOLD', 2) if (y < cy - (x - cx) * 0.4) else M('TERRACOTTA_YELLOW', 2)
                elif d > R - 3.5:
                    col = M('TERRACOTTA_YELLOW', 0)
                else:
                    col = M('SAND', 3)
                c.px(x, y, col)
    rf = R - 3.5                     # face radius
    # a soft shadow inside the bezel along the top-left
    for y in range(int(cy - rf) - 1, int(cy + rf) + 2):
        for x in range(int(cx - rf) - 1, int(cx + rf) + 2):
            d = math.hypot(x + .5 - cx, y + .5 - cy)
            if rf - 1.3 < d <= rf and (x + .5 - cx) + (y + .5 - cy) < 0:
                c.px(x, y, M('SAND', 2))
    ink = M('TERRACOTTA_BROWN', 0)
    for k in range(12):
        a = math.radians(k * 30 - 90)
        if k % 3 == 0:
            for rr in (rf - 1.6, rf - 2.6):
                c.px(cx + rr * math.cos(a) - 0.5, cy + rr * math.sin(a) - 0.5, ink)
        else:
            rr = rf - 1.8
            c.px(cx + rr * math.cos(a) - 0.5, cy + rr * math.sin(a) - 0.5, M('SAND', 0))

    def hand(angle_deg, length, col, w=1):
        a = math.radians(angle_deg - 90)
        for i in range(int(length * 3) + 1):
            r = i / 3
            hx, hy = cx + r * math.cos(a) - 0.5, cy + r * math.sin(a) - 0.5
            c.px(hx, hy, col)
            if w > 1 and r < length - 1:
                c.px(hx + (1 if abs(math.sin(a)) > 0.5 else 0), hy + (0 if abs(math.sin(a)) > 0.5 else 1), col)
    hand(305, 5.5, ink, w=2)              # hour hand (10 o'clock)
    hand(60, 8.5, ink)                    # minute hand (two past)
    hand(210, 9.0, M('FIRE', 2))          # sweep second hand
    c.px(cx - 0.5, cy - 0.5, M('GOLD', 1))
    c.px(cx + 0.5, cy - 0.5, M('GOLD', 3))


# ------------------------------------------------------------------------------- the landscape

FALLS_TOP, FALLS_BOT = 80, 138          # lip row and the row where the falls meets the pool
POOL = (95.0, 144.0, 58.0, 9.5)        # pool ellipse cx, cy, rx, ry
ROCK = [M('TERRACOTTA_BLUE', 0), M('TERRACOTTA_BLUE', 1), M('TERRACOTTA_LIGHT_BLUE', 0),
        M('TERRACOTTA_LIGHT_BLUE', 1), M('TERRACOTTA_LIGHT_BLUE', 2)]
ROCK_RIM = M('TERRACOTTA_MAGENTA', 1)
WET = [M('COLOR_BLACK', 2), M('TERRACOTTA_BLUE', 0), M('TERRACOTTA_BLUE', 1), M('TERRACOTTA_LIGHT_BLUE', 0),
       M('COLOR_CYAN', 0)]


def falls_edges(y):
    t = clamp((y - FALLS_TOP) / (FALLS_BOT - FALLS_TOP))
    L = 82 - 7 * t + (1.2 + 1.6 * t) * (noise1(y * 0.2, 31) - 0.5)
    R = 105 + 8 * t + (1.2 + 1.6 * t) * (noise1(y * 0.17, 32) - 0.5)
    return L, R


def in_pool(x, y, grow=0.0):
    cx, cy, rx, ry = POOL
    rx += grow
    ry += grow
    wob = 1.0 + 0.06 * (noise1(x * 0.11, 92) - 0.5)
    dx, dy = (x + .5 - cx) / (rx * wob), (y + .5 - cy) / ry
    return dx * dx + dy * dy <= 1.0


def worley(x, y, gx, gy, ch):
    """(dist to nearest feature, dist to 2nd nearest, offset dx, dy to nearest) on a jittered grid."""
    i0, j0 = math.floor(x / gx), math.floor(y / gy)
    best = [(1e9, 0, 0), (1e9, 0, 0)]
    for j in range(j0 - 1, j0 + 2):
        for i in range(i0 - 1, i0 + 2):
            fx = (i + 0.15 + 0.7 * _h(ch, i, j, 1)) * gx
            fy = (j + 0.15 + 0.7 * _h(ch, i, j, 2)) * gy
            d = math.hypot((x - fx) / gx, (y - fy) / gy)
            if d < best[0][0]:
                best = [(d, x - fx, y - fy), best[0]]
            elif d < best[1][0]:
                best[1] = (d, x - fx, y - fy)
    return best[0][0], best[1][0], best[0][1], best[0][2]


def rock_px(x, y, ch, ramp=ROCK, gx=7.0, gy=11.0, bias=0.0):
    """Stacked-boulder rock: dark cracks between cells, each boulder lit along its top edge."""
    d1, d2, ox, oy = worley(x + 0.5, y + 0.5, gx, gy, ch)
    if d2 - d1 < 0.12:
        return ramp[0]
    lit = -oy / gy * 1.2 - ox / gx * 0.9 + 0.3 * (noise2(x * 0.5, y * 0.25, ch + 3) - 0.5) + bias
    k = int(clamp(1.6 + lit * 2.2, 1, len(ramp) - 1))
    if d2 - d1 < 0.25:
        k = max(1, k - 1)
    return ramp[k]


def draw_land(c):
    # far mountains (hazy purple) behind everything
    ridge(c, X0, X1, 78, 20, 0.035, 41, M('TERRACOTTA_MAGENTA', 2), rim=M('COLOR_PINK', 2))
    ridge(c, X0, X1, 82, 9, 0.06, 43, M('TERRACOTTA_PURPLE', 2), rim=M('TERRACOTTA_MAGENTA', 2))
    # far forest line against the glow
    for i, x in enumerate(range(X0 - 2, X1 + 3, 4)):
        h = 4 + int(6 * _h(44, i))
        pine(c, x + int(3 * _h(45, i)), 79 + int(2 * _h(46, i)), h, 5, M('TERRACOTTA_PURPLE', 1),
             M('TERRACOTTA_PURPLE', 0), None, seed=300 + i)

    # the land: one skyline dipping to the river's far end at the centre, rock below, grass on top
    left_top, right_top = {}, {}
    for x in range(X0, X1):
        if x < 94:
            t = 64 + 13 * _s(clamp((x - 28) / (88 - 28))) + 2.0 * (noise1(x * 0.15, 61) - 0.5)
            left_top[x] = int(round(t))
        else:
            t = 77 - 13 * _s(clamp((x - 99) / 40)) + 2.0 * (noise1(x * 0.13, 62) - 0.5)
            right_top[x] = int(round(t))
    grass_dk = M('TERRACOTTA_GREEN', 0)
    L0_, R0_ = falls_edges(FALLS_TOP)

    def rock_top(x):
        # jagged rock crest, lowest at the brink, climbing away from the falls
        if x < L0_:
            r = FALLS_TOP - 1 - (L0_ - x) * 0.42
        elif x > R0_:
            r = FALLS_TOP - 1 - (x - R0_) * 0.38
        else:
            r = FALLS_TOP - 1
        r += 3.0 * (noise1(x * 0.35, 66) - 0.5) + (2 if _h(67, x // 3) < 0.25 else 0)
        return int(round(r))

    rtop = {}
    for tops, ch in ((left_top, 63), (right_top, 64)):
        for x, t in tops.items():
            rt = max(t + 2, rock_top(x))
            rtop[x] = rt
            for y in range(t, 152):
                if y < rt:
                    col = grass_dk if _h(65, x, y) < 0.8 else M('TERRACOTTA_GREEN', 1)
                else:
                    col = rock_px(x, y, ch)
                c.px(x, y, col)
            c.px(x, t, M('TERRACOTTA_GREEN', 1))
            c.px(x, rt, ROCK_RIM)
            c.px(x, rt + 1, e.shade(rock_px(x, rt + 1, ch), 1))
    # the brink where the water pours over
    for x in range(int(L0_) - 2, int(R0_) + 3):
        c.px(x, FALLS_TOP - 1, ROCK_RIM)

    # forest: a hazy back crest, a green front crest, then rows down the outer slopes (back to front)
    rng = random.Random(SEED + 33)
    haze = (M('TERRACOTTA_LIGHT_BLUE', 0), M('TERRACOTTA_BLUE', 1), M('TERRACOTTA_MAGENTA', 1))
    mid = (M('COLOR_GREEN', 0), M('TERRACOTTA_GREEN', 0), M('TERRACOTTA_LIGHT_GREEN', 1))
    deep = (M('TERRACOTTA_GREEN', 0), M('TERRACOTTA_BLACK', 2), M('TERRACOTTA_GREEN', 2))
    tops = dict(left_top)
    tops.update(right_top)

    def top_at(x):
        return tops[min(max(x, X0), X1 - 1)]

    for layer, (cols, hmin, hvar, lift, step) in enumerate(((haze, 12, 20, 4, (3, 7)), (mid, 9, 15, 0, (4, 8)))):
        x = X0 - 3 + layer * 2
        while x < X1 + 4:
            far = clamp(abs(x - 93) / 28)
            h = int((hmin + hvar * rng.random() ** 1.4) * (0.3 + 0.7 * far))
            if h >= 4:
                pine(c, x, top_at(x) + 3 - lift + rng.randrange(3), h, 6 + rng.randrange(6), *cols,
                     seed=5000 + layer * 500 + x)
            x += rng.randrange(*step)
    # left slope rows stop short of the gorge wall; right rows climb behind the cabin
    for side in (0, 1):
        for row, yb in enumerate(range(88 if side == 0 else 90, 150 if side == 0 else 136, 7)):
            cols = mid if row < 2 else deep
            if side == 0:
                xa, xb = X0 - 3 + rng.randrange(4), int(64 - (yb - 86) * 0.3 + 10 * (noise1(yb * 0.15, 68) - 0.5))
            else:
                xa, xb = int(124 + (yb - 90) * 0.15 + 10 * (noise1(yb * 0.15, 69) - 0.5)), X1 + 4
            x = xa
            while x < xb:
                if rng.random() > 0.12:
                    pine(c, x, yb + rng.randrange(4), 11 + rng.randrange(12), 8 + rng.randrange(5), *cols,
                         seed=7000 + side * 999 + row * 50 + x)
                x += rng.randrange(4, 8)

    # shrubs clinging to ledges on the rock faces
    for i in range(16):
        side = i % 2
        y = 88 + int(_h(160, i) * 44)
        L, R = falls_edges(y)
        x = int(L - 8 - _h(161, i) * 14) if side == 0 else int(R + 8 + _h(161, i) * 14)
        w = 3 + int(_h(162, i) * 3)
        for dy in range(2):
            for dx in range(-w // 2 - (1 - dy), w // 2 + 1 + (1 - dy) * 0):
                c.px(x + dx, y - dy, M('TERRACOTTA_GREEN', 0) if dy == 0 else M('COLOR_GREEN', 0))
        c.px(x, y - 2, M('TERRACOTTA_LIGHT_GREEN', 1))
        c.px(x - w // 2, y + 1, ROCK[0])

    # wet gorge walls right beside the falls (darker, slick)
    for y in range(83, FALLS_BOT + 4):
        L, R = falls_edges(y)
        for x in range(int(L) - 6, int(L)):
            if c.get(x, y) in (ROCK_RIM,) or y < left_top.get(x, 0):
                continue
            c.px(x, y, rock_px(x, y, 63, WET))
        for x in range(int(math.ceil(R)) + 1, int(math.ceil(R)) + 7):
            if y < right_top.get(x, 0):
                continue
            c.px(x, y, rock_px(x, y, 64, WET))

    # the falls: every 1-px column is a strand with its own speed and phase (a whole number of periods per
    # loop, so it stays seamless); a long streak with a bright head runs down it, and one broad band of
    # light sweeps down the whole curtain like the turning cylinder in the old pictures
    for y in range(FALLS_TOP, FALLS_BOT + 1):
        L, R = falls_edges(y)
        for x in range(int(math.floor(L)), int(math.ceil(R)) + 1):
            per = 12.0 + 8.0 * _h(84, x)
            off = _h(85, x)
            body = noise1(x * 0.4, 81)
            edge = clamp(min(x + 0.5 - L, R - x - 0.5) / 2.5)
            lip = clamp(1 - (y - FALLS_TOP) / 4)
            foot = clamp((y - (FALLS_BOT - 10)) / 10)

            def fn(f, y=y, per=per, off=off, body=body, edge=edge, lip=lip, foot=foot):
                yy = y - FALLS_TOP
                v = frac(yy / per + off - f / FRAMES)
                streak = clamp((v - 0.4) / 0.6) ** 2
                band = frac(yy / 29.0 - f / FRAMES)
                sweep = clamp(1 - abs(band - 0.88) / 0.14)
                b = 0.22 + 0.30 * body + 0.46 * streak * (0.6 + 0.4 * body) + 0.16 * sweep
                b = b * (0.45 + 0.55 * edge) + 0.5 * lip + 0.3 * foot
                return ramp_pick(FALLS, b)
            c.water(x, y, fn)

    # pool
    cx, cy, rx, ry = POOL
    fx = (falls_edges(FALLS_BOT)[0] + falls_edges(FALLS_BOT)[1]) / 2
    for y in range(int(cy - ry) - 2, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 4, int(cx + rx) + 4):
            if not in_pool(x, y):
                continue
            if y <= FALLS_BOT:
                L, R = falls_edges(y)
                if L <= x <= R:
                    continue
            dist = math.hypot((x + .5 - fx) / 2.8, (y + .5 - (FALLS_BOT - 1)))
            near = clamp(1 - dist / 20)
            shore = 0.0 if in_pool(x, y, -2.2) else 1.0
            jit = 0.2 * noise2(x * 0.3, y * 0.6, 91)
            refl = clamp(1 - abs(x + .5 - fx) / 15) * clamp((y - FALLS_BOT) / 3) * (0.5 + 0.5 * _h(93, x))
            warm = y >= 139 and abs(x + 0.5 - 141.5) <= 4.5 - (y - 139) * 0.32

            def fn(f, dist=dist, near=near, jit=jit, shore=shore, refl=refl, warm=warm, x=x, y=y):
                v = frac(dist / 4.0 + jit - f / FRAMES)
                ring = clamp(1 - abs(v - 0.85) / 0.15)
                if warm:
                    w = frac((x + 0.5) / 5.0 + y * 0.37 - f / FRAMES)
                    if (y % 2 == 1) and w < 0.6:
                        return ramp_pick(WARM, 0.4 + 0.4 * ring + 0.3 * (y < 144))
                b = 0.22 + 0.25 * near + 0.25 * refl + ring * (0.18 + 0.5 * near + 0.2 * refl)
                b -= 0.18 * shore
                return ramp_pick(POOL_RAMP, b)
            c.water(x, y, fn)

    # river out of the pool toward the viewer
    for y in range(146, Y1):
        t = (y - 146) / (Y1 - 146)
        cxm = 97 + 4 * t + 2.5 * math.sin(y * 0.16)
        hw = 20 + 20 * t
        for x in range(int(cxm - hw), int(cxm + hw) + 1):
            if in_pool(x, y):
                continue
            s = noise2(x * 0.5, y * 0.14, 101)
            s = clamp((s - 0.42) / 0.4)
            off = 0.35 * noise1(x * 0.25, 102)
            edge = clamp(min(x - (cxm - hw), (cxm + hw) - x) / 5)

            def fn(f, y=y, s=s, off=off, t=t, edge=edge):
                v = frac((y - 146) / (7.0 + 7 * t) + off - f / FRAMES)
                b = 0.12 + 0.16 * s + 0.62 * s * (v ** 2.5)
                return ramp_pick(POOL_RAMP, b * (0.55 + 0.45 * edge))
            c.water(x, y, fn)
    return left_top, right_top


def boulder(c, bx, by, rx, ry, foam=True, seed=0):
    """A wet stone: lit along its top by the falls, dark underside, a foam line where it meets water.
    Returns a good glint spot near its top."""
    ramp = [M('COLOR_BLACK', 2), M('TERRACOTTA_BLUE', 0), M('TERRACOTTA_BLUE', 1), M('TERRACOTTA_LIGHT_BLUE', 0),
            M('TERRACOTTA_LIGHT_BLUE', 1), M('COLOR_LIGHT_BLUE', 0)]
    body = []
    for y in range(int(by - ry) - 1, int(by + ry) + 2):
        for x in range(int(bx - rx) - 1, int(bx + rx) + 2):
            dx, dy = (x + .5 - bx) / rx, (y + .5 - by) / ry
            wob = 1 + 0.12 * (noise2(x * 0.7, y * 0.7, 140 + seed) - 0.5)
            d = (dx * dx + dy * dy) * wob
            if d > 1:
                continue
            lit = -dy * 1.2 - dx * 0.35 + 0.35 * (noise2(x * 0.8, y * 0.8, 150 + seed) - 0.5)
            k = int(clamp(1.5 + lit * 1.8, 1, 3))
            if d > 0.7 and dy > 0.1:
                k = 0
            c.px(x, y, ramp[k])
            body.append((x, y))
    bset = set(body)
    water_below = [(x, y + 1) for (x, y) in body if (x, y + 1) not in bset and (x, y + 1) in c.anim]
    # wet sheen along the upper rim
    for x in range(int(bx - rx * 0.7), int(bx + rx * 0.45) + 1):
        y = int(math.floor(by - ry * math.sqrt(max(0, 1 - ((x + .5 - bx) / rx) ** 2)) + 0.5))
        c.px(x, y, ramp[5])
    if foam:
        for i, (x, y) in enumerate(water_below):
            c.water(x, y, (lambda f, x=x, s=seed: M('ICE', 3) if frac(x / 4.0 + s * 0.37 - f / FRAMES) < 0.4 else M('ICE', 1)))
    return (int(bx - rx * 0.3), int(by - ry * 0.75))


def draw_mist_and_rocks(c):
    """Boulders at the foot of the falls and in the river, mist over the plunge, twinkling glints."""
    spots = []
    for i, (bx, by, rx, ry) in enumerate([(71, 138, 7, 4.5), (80, 142, 4, 2.6), (114, 138, 7, 4.5),
                                          (122, 143, 4.5, 2.6), (57, 147, 4, 2.4), (133, 148, 3.5, 2),
                                          (64, 166, 5, 3), (133, 163, 5, 3), (88, 176, 4, 2.2), (114, 177, 5, 2.2)]):
        spots.append(boulder(c, bx, by, rx, ry, seed=i))
    # mist over the plunge pool: random-threshold speckle, densest at the foot, a few sparkles
    mx = (falls_edges(FALLS_BOT)[0] + falls_edges(FALLS_BOT)[1]) / 2
    my = FALLS_BOT + 1.0
    for y in range(int(my - 10), int(my + 7)):
        for x in range(int(mx - 26), int(mx + 27)):
            dx = (x + .5 - mx) / 24.0
            dy = (y + .5 - my) / (9.0 if y < my else 5.5)
            dens = 1 - (dx * dx + dy * dy)
            if dens <= 0 or (x, y) not in c.anim:
                continue
            if _h(112, x, y) > dens * 0.8:
                continue
            r = _h(113, x, y)
            base = (M('SNOW', 2) if r < 0.3 else M('ICE', 3)) if dens > 0.6 else M('ICE', 2) if dens > 0.3 else M('ICE', 1)
            k = int(_h(110, x, y) * FRAMES)
            sp = _h(111, x, y) < 0.14
            under = c.anim[(x, y)]
            ghost = dens < 0.3 and _h(114, x, y) < 0.5      # thin mist: the water shows through on alternate frames

            def fn(f, base=base, k=k, sp=sp, under=under, ghost=ghost):
                dd = (f - k) % FRAMES
                if sp:
                    if dd == 0:
                        return M('SNOW', 3)
                    if dd in (1, FRAMES - 1):
                        return M('ICE', 3)
                if ghost and dd >= FRAMES // 2:
                    return under(f)
                return base
            c.water(x, y, fn)
    return spots


def add_glints(c, spots):
    """Each glint flashes a 4-point star on its own frame, then fades over the next."""
    for i, (x, y) in enumerate(spots):
        k = (i * 5) % FRAMES
        cells = {(x, y): 0, (x - 1, y): 1, (x + 1, y): 1, (x, y - 1): 1, (x, y + 1): 1}
        for (gx, gy), arm in cells.items():
            base = c.get(gx, gy)
            if base is None:
                continue
            under = c.anim.get((gx, gy))

            def fn(f, base=base, under=under, arm=arm, k=k):
                dd = (f - k) % FRAMES
                if dd == 0:
                    return M('SNOW', 3) if not arm else M('ICE', 3)
                if dd == 1 and not arm:
                    return M('ICE', 3)
                return under(f) if under else base
            c.water(gx, gy, fn)


def river_edges(y):
    t = (y - 146) / (Y1 - 146)
    cxm = 97 + 4 * t + 2.5 * math.sin(y * 0.16)
    hw = 20 + 20 * t
    return cxm - hw, cxm + hw


def draw_banks(c):
    """Dark grassy banks around the pool and river, with lit grass tips and shore stones."""
    grass = [M('TERRACOTTA_BLACK', 2), M('TERRACOTTA_GREEN', 0), M('TERRACOTTA_GREEN', 1), M('COLOR_GREEN', 0)]
    for y in range(138, Y1):
        for x in range(X0, X1):
            if (x, y) in c.anim:
                continue
            L, R = river_edges(max(146, y))
            below_pool = y >= 147 or (not in_pool(x, y) and in_pool(x, y, 3.5) and y > 140)
            if not below_pool:
                continue
            n = noise2(x * 0.25, y * 0.25, 120)
            k = 1 if n > 0.35 else 0
            if n > 0.7:
                k = 2
            c.px(x, y, grass[k])
    # grass blades catching the light
    rng = random.Random(SEED + 7)
    for _ in range(260):
        x, y = rng.randrange(X0, X1), rng.randrange(146, Y1)
        if (x, y) in c.anim or (x, y + 1) in c.anim:
            continue
        hgt = rng.choice((1, 2, 2, 3))
        col = rng.choice((grass[2], grass[3], M('TERRACOTTA_LIGHT_GREEN', 1)))
        for i in range(hgt):
            if (x, y - i) not in c.anim:
                c.px(x, y - i, col if i == hgt - 1 else grass[2])
    # shore stones along the water's edge
    edge = []
    for y in range(136, Y1):
        for x in range(X0, X1):
            if (x, y) not in c.anim and ((x + 1, y) in c.anim or (x - 1, y) in c.anim or (x, y - 1) in c.anim):
                if y > 139 and _h(121, x, y) < 0.5:
                    edge.append((x, y))
    for (x, y) in edge:
        c.px(x, y, ROCK[1] if _h(122, x, y) < 0.6 else ROCK[3])


def draw_cabin(c):
    logs_a, logs_b, gap = M('TERRACOTTA_BROWN', 2), M('PODZOL', 0), M('TERRACOTTA_BLACK', 1)
    side_a, side_b = M('TERRACOTTA_BROWN', 1), M('TERRACOTTA_BROWN', 0)
    gx0, gx1, sx1, wy0, wy1 = 133, 151, 167, 121, 138
    # clearing under the cabin
    for y in range(133, 141):
        for x in range(127, 172):
            if (x, y) not in c.anim and not in_pool(x, y, 1.0):
                c.px(x, y, M('TERRACOTTA_GREEN', 0) if _h(130, x, y) < 0.7 else M('TERRACOTTA_GREEN', 1))
    # gable wall (facing us) and side wall (shaded)
    for y in range(wy0, wy1):
        r = (y - wy0) % 3
        for x in range(gx0, gx1):
            c.px(x, y, gap if r == 2 else (logs_a if r == 0 else logs_b))
        for x in range(gx1, sx1):
            c.px(x, y, gap if r == 2 else (side_a if r == 0 else side_b))
        if r == 0:
            c.px(gx0 - 1, y, M('DIRT', 1))           # log ends at the corners
            c.px(gx0 - 1, y + 1, M('TERRACOTTA_BROWN', 2))
            c.px(gx1, y, M('DIRT', 1))
    # roof: side plane with shingle rows, then the gable end with bargeboards
    peak = (142, 107)
    c.poly([peak, (165, 105), (171, 122), (153, 123)], M('TERRACOTTA_GRAY', 1))
    for i in range(1, 9):
        a = (peak[0] + (153 - peak[0]) * i / 9, peak[1] + (123 - peak[1]) * i / 9)
        b = (165 + (171 - 165) * i / 9, 105 + (122 - 105) * i / 9)
        c.line(a[0], a[1], b[0], b[1], M('TERRACOTTA_GRAY', 0))
    c.line(peak[0] + 1, peak[1], 165, 105, M('TERRACOTTA_PINK', 1))        # ridge catching the dusk
    c.poly([(gx0 + 1, wy0), (peak[0], peak[1] + 3), (gx1 - 1, wy0)], M('TERRACOTTA_BROWN', 1))
    for y in range(peak[1] + 4, wy0, 3):
        c.line(gx0, y, gx1, y, gap)
    c.poly([(gx0 + 1, wy0), (peak[0], peak[1] + 3), (gx1 - 1, wy0)], None) if False else None
    for y in range(peak[1] + 3, wy0):
        hw = (y - peak[1] - 3) * (gx1 - gx0 - 2) / 2 / (wy0 - peak[1] - 3)
        for x in range(int(peak[0] - hw), int(peak[0] + hw) + 1):
            r = (y - wy0) % 3
            c.px(x, y, gap if r == 2 else (logs_a if r == 0 else logs_b))
    c.line(gx0 - 3, wy0 + 2, peak[0], peak[1], M('PODZOL', 2), w=1)
    c.line(gx0 - 2, wy0 + 2, peak[0], peak[1] + 1, M('TERRACOTTA_BROWN', 0), w=1)
    c.line(peak[0], peak[1], gx1 + 3, wy0 + 2, M('PODZOL', 1), w=1)
    c.line(peak[0], peak[1] + 1, gx1 + 2, wy0 + 2, M('TERRACOTTA_BROWN', 0), w=1)
    c.px(peak[0], peak[1] - 1, M('TERRACOTTA_PINK', 1))
    # chimney + a curl of smoke
    c.rect(159, 97, 164, 110, M('TERRACOTTA_LIGHT_GRAY', 0))
    for y in range(98, 110, 2):
        c.px(160 + (y // 2) % 3, y, M('TERRACOTTA_GRAY', 2))
    c.rect(158, 96, 165, 98, M('TERRACOTTA_LIGHT_GRAY', 1))
    for i in range(9):
        t = i / 8
        sx = 161 - 16 * t - 3 * math.sin(t * 5)
        sy = 94 - 11 * t
        r = 0.8 + 1.8 * t
        for y in range(int(sy - r) - 1, int(sy + r) + 2):
            for x in range(int(sx - r) - 1, int(sx + r) + 2):
                if math.hypot(x + .5 - sx, y + .5 - sy) <= r and _h(170, x, y) < 0.9 - 0.45 * t:
                    c.px(x, y, M('TERRACOTTA_LIGHT_BLUE', 3) if t < 0.35 else M('TERRACOTTA_LIGHT_BLUE', 2))
    # warm window on the gable, door + small window on the side
    def window(x0, y0, w, h):
        c.rect(x0 - 2, y0 - 2, x0 + w + 2, y0 + h + 2, M('TERRACOTTA_ORANGE', 0))
        c.rect(x0 - 1, y0 - 1, x0 + w + 1, y0 + h + 1, gap)
        c.rect(x0, y0, x0 + w, y0 + h, M('GOLD', 3))
        c.rect(x0, y0 + h - 2, x0 + w, y0 + h, M('COLOR_ORANGE', 3))
        c.rect(x0 + w // 2, y0, x0 + w // 2 + 1, y0 + h, M('COLOR_ORANGE', 1))
        c.rect(x0, y0 + h // 2, x0 + w, y0 + h // 2 + 1, M('COLOR_ORANGE', 1))
    window(137, 125, 9, 6)
    window(161, 126, 4, 5)
    c.rect(153, 126, 159, wy1, gap)                     # door, ajar and lit
    c.rect(154, 127, 158, wy1, M('COLOR_ORANGE', 2))
    c.rect(154, 127, 156, wy1, M('GOLD', 3))
    c.px(152, 126, M('GOLD', 3))                        # porch lantern
    c.px(152, 125, M('TERRACOTTA_YELLOW', 1))
    for (dx, dy) in ((-1, 0), (0, 1), (0, -1)):
        if c.get(152 + dx, 126 + dy) not in (M('GOLD', 3),):
            c.px(152 + dx, 126 + dy, M('COLOR_ORANGE', 1))
    # stone footing
    for x in range(gx0 - 1, sx1 + 1):
        c.px(x, wy1, ROCK[2] if (x // 2) % 2 else ROCK[1])
    # path from the door down toward the bridge
    path = [(156, 139), (154, 142), (151, 145), (149, 148), (147, 151), (145, 154), (144, 157), (143, 160)]
    for (x, y) in path:
        for dx in range(-1, 2):
            if (x + dx, y) not in c.anim:
                c.px(x + dx, y, M('PODZOL', 0) if dx else M('DIRT', 0))


def draw_bridge(c):
    """Arched plank footbridge over the river, rails and posts silhouetted on the bright water."""
    x0, x1, yb, rise = 54, 146, 171, 10
    plank, plank_hi, under, rail, rail_dk = M('PODZOL', 1), M('DIRT', 2), M('TERRACOTTA_BROWN', 0), M('PODZOL', 2), M('TERRACOTTA_BROWN', 1)

    def ydeck(x):
        t = (x - x0) / (x1 - x0)
        return yb - rise * math.sin(math.pi * t)
    # far rail first (darker, a little higher)
    for x in range(x0 + 3, x1 - 2):
        y = int(round(ydeck(x))) - 8
        c.px(x, y, rail_dk)
    for x in range(x0 + 3, x1 - 2, 9):
        y = int(round(ydeck(x)))
        for yy in range(y - 8, y):
            c.px(x + 2, yy, rail_dk)
    for x in range(x0, x1 + 1):
        y = int(round(ydeck(x)))
        c.px(x, y - 1, plank_hi)
        c.px(x, y, plank if x % 4 else under)
        c.px(x, y + 1, plank)
        c.px(x, y + 2, under)
        c.px(x, y + 3, INK)
    # near rail with posts
    for x in range(x0, x1 + 1):
        y = int(round(ydeck(x)))
        c.px(x, y - 6, rail)
        c.px(x, y - 5, under)
    for x in list(range(x0, x1 + 1, 9)) + [x1]:
        y = int(round(ydeck(x)))
        for yy in range(y - 7, y + 3):
            c.px(x, yy, rail)
            c.px(x + 1, yy, under)
        c.px(x, y - 7, plank_hi)
    # end posts on the banks
    for x in (x0 - 1, x1 + 1):
        y = int(round(ydeck(x)))
        for yy in range(y - 9, y + 6):
            c.px(x, yy, rail)
            c.px(x + 1, yy, under)
        c.px(x, y - 10, plank_hi)
        c.px(x + 1, y - 10, rail)


def draw_foreground(c):
    # big foreground pine on the left, ferns in the bottom corners
    pine(c, 23, Y1 + 6, 122, 32, M('TERRACOTTA_BLACK', 2), M('COLOR_BLACK', 2), M('TERRACOTTA_GREEN', 1), seed=999)
    for (fx, fy, s) in ((X0 + 4, Y1 - 2, 9), (X1 - 8, Y1 - 1, 10), (X1 - 22, Y1 + 1, 7), (48, Y1 + 1, 6)):
        for k in range(-3, 4):
            a = math.radians(-90 + k * 24)
            for i in range(s):
                r = i * (1 - abs(k) * 0.1)
                x = fx + r * math.cos(a)
                y = fy + r * math.sin(a) + (i * i) * 0.02 * abs(k)
                c.px(x, y, M('TERRACOTTA_GREEN', 1) if i > s - 3 else M('TERRACOTTA_GREEN', 0))


def build():
    c = Scene(W, H, e.BLACK)
    draw_sky(c)
    draw_land(c)
    draw_banks(c)
    tops = draw_mist_and_rocks(c)
    draw_cabin(c)
    draw_bridge(c)
    draw_foreground(c)
    add_glints(c, tops[:8] + [(77, 104), (109, 96), (111, 120)])
    draw_clock(c)
    draw_frame(c)
    draw_plaque(c)
    return c


def main():
    c = build()
    frames = [c.render(f) for f in range(FRAMES)]
    gif = os.path.join(HERE, e.out_name(NAME, HB, WB, 'gif'))
    info = e.save_gif(frames, DELAY, gif)
    still = os.path.join(HERE, NAME + '_still_preview.png')
    e.save_png(frames[0], still)
    sheet = os.path.join(HERE, NAME + '_preview.png')
    e.preview(frames, sheet, scale=2, delays_ms=DELAY, cols=4, title='EverGrims Falls 3x3')
    # close-up of the moving water (falls, pool, river) for reviewing the light cycling
    x0, y0, x1, y1 = 44, 76, 150, 179
    crops = []
    for f in frames:
        cr = e.Canvas(x1 - x0, y1 - y0, e.BLACK)
        cr.p = [row[x0:x1] for row in f.p[y0:y1]]
        crops.append(cr)
    e.preview(crops, os.path.join(HERE, NAME + '_water_preview.png'), scale=3, delays_ms=DELAY, cols=6,
              title='EverGrims Falls water close-up')
    for k in ('path', 'w', 'h', 'frames', 'colours', 'snapped_pixels', 'bytes', 'duration_ms',
              'imageframe_fake_maps', 'per_tile'):
        print(k, info[k])
    return frames


if __name__ == '__main__':
    main()
