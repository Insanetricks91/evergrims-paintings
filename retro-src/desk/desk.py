#!/usr/bin/env python3
"""Desk-toy wall art for the EverGrims retro backlit ImageFrame set: three small looping GIFs.

    lava_lamp_2x1.gif     2 tall x 1 wide  -- rocket lava lamp, orange wax rising/splitting/sinking in violet
    fish_tank_1x2.gif     1 tall x 2 wide  -- lit 90s aquarium: neon gravel, castle, air stone, three fish
    plasma_globe_2x2.gif  2 tall x 2 wide  -- plasma ball, wandering crackling filaments

Drawn at 64 design px per block, written 2x nearest (128 px per block = one map per block) with egwpix,
every pixel a Minecraft map colour.  Frame 1 of every GIF is a finished still (Bedrock shows only frame 1).
Each piece sits on a dark room wall so a glow item frame makes it read as a glowing object in a dark room.
Python standard library only.   Run: python3 desk.py [lava|fish|globe ...]
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'kit'))
import egwpix as e  # noqa: E402

TAU = 2 * math.pi
mc = e.mc
BAYER = e.BAYER4


def thr(x, y):
    return (BAYER[y & 3][x & 3] + 0.5) / 16


def ramp(cols, v, x, y):
    """Pick from a dark->bright colour list by v in [0,1], ordered-dithered between neighbours."""
    n = len(cols) - 1
    v = max(0.0, min(1.0, v)) * n
    k = int(v)
    if k >= n:
        return cols[n]
    return cols[k + 1] if (v - k) > thr(x, y) else cols[k]


def brighter(c, x, y, col):
    if 0 <= x < c.w and 0 <= y < c.h and e.lum(col) > e.lum(c.p[y][x]):
        c.p[y][x] = col


def radial_glow(c, cx, cy, rx, ry, cols, power=1.0, box=None):
    """Light spill: cols run inner -> outer; dithered rings; only brightens what is there."""
    n = len(cols)
    x0, y0, x1, y1 = box or (0, 0, c.w, c.h)
    for y in range(max(0, int(y0)), min(c.h, int(y1))):
        for x in range(max(0, int(x0)), min(c.w, int(x1))):
            d = math.hypot((x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry)
            if d >= 1:
                continue
            t = (d ** power) * n
            k = int(t)
            idx = k + (1 if (t - k) > thr(x, y) else 0)
            if idx < n:
                brighter(c, x, y, cols[idx])


def wall(c, top, bottom, y0=0, y1=None, stripes=None):
    """Dark room wall: dithered vertical gradient, optional faint wallpaper stripes."""
    y1 = c.h if y1 is None else y1
    e.bayer_vgrad(c, 0, y0, c.w, y1, [top, bottom])
    if stripes:
        col, every = stripes
        for y in range(y0, y1):
            for x in range(0, c.w, every):
                if (y // 2) % 3 != 0:
                    c.p[y][x] = col


def desk_top(c, y0, glow_cx, glow_r, warm):
    """A dark wooden desk top whose front edge catches the toy's light."""
    wood = [mc('TERRACOTTA_BLACK', 1), mc('TERRACOTTA_BROWN', 0), mc('TERRACOTTA_BROWN', 1),
            mc('TERRACOTTA_BROWN', 2), mc('COLOR_BROWN', 2)]
    rng = random.Random(7)
    for y in range(y0, c.h):
        for x in range(c.w):
            d = abs(x + 0.5 - glow_cx) / glow_r
            v = max(0.0, 1 - d) ** 1.3
            depth = (y - y0) / max(1, c.h - y0)
            v *= 1.0 - 0.75 * depth
            col = ramp(wood, v * 0.95, x, y)
            if (x * 7 + (y - y0) * 31) % 23 == 0 or rng.random() < 0.04:   # grain
                col = e.shade(col, -1)
            c.p[y][x] = col
    for x in range(c.w):                                     # lit front lip
        d = abs(x + 0.5 - glow_cx) / glow_r
        v = max(0.0, 1 - d)
        c.p[y0][x] = ramp([mc('TERRACOTTA_BROWN', 1), warm[0], warm[1], warm[2]], v, x, y0)


def metal_col(u, cols):
    """Cylinder shading across a metal part: u in [-1,1] left->right. cols dark->bright."""
    # highlight band left of centre, dark at both rims
    v = math.exp(-((u + 0.38) / 0.28) ** 2) * 0.95 + 0.35 * (1 - abs(u)) ** 0.7
    if u > 0.75 or u < -0.92:
        v *= 0.5
    return v


# =============================================================================================== LAVA LAMP

LAVA_FRAMES, LAVA_MS = 24, 250
L_CX = 32
G0, G1 = 22, 92          # glass top / bottom (design px rows)


def glass_hw(y):
    u = (y - G0) / (G1 - G0)
    if u < 0.80:
        s = u / 0.80
        return 6.0 + 10.5 * (1 - (1 - s) ** 1.25)
    s = (u - 0.80) / 0.20
    return 16.5 - 5.0 * s ** 1.6


def lava_blobs(t):
    """Compact metaballs (x, y, rx, ry, weight) for loop phase t in [0,1); rx/ry = influence radii."""
    out = []
    # warm pool on the heater: a flat lens plus a lump that swells and slumps
    out.append((L_CX, G1 + 3.0, 22.0, 10.0, 1.0))
    a = TAU * (t + 0.15)
    out.append((L_CX - 1 + 2.0 * math.sin(a), G1 - 5.0 - 3.0 * math.sin(a), 9.5, 7.5 + 1.5 * math.sin(a), 0.85))
    # cooled wax hanging under the cap
    out.append((L_CX + 0.5, G0 + 1.5, 7.5, 6.5, 0.75 + 0.15 * math.sin(TAU * (t + 0.4))))
    # travellers: (radius, centre y, amplitude, phase, x centre, x sway, sway phase)
    trav = [
        (10.0, 59.0, 24.0, 0.00, 31.5, 2.5, 0.7),    # big one: rises out of the pool, tops out, sinks
        (8.6, 58.0, 19.0, 0.50, 33.0, 3.0, 2.1),    # medium, opposite phase
        (6.2, 46.0, 9.0, 0.27, 29.0, 1.5, 4.0),     # little one bobbing mid-glass
    ]
    for (r, yc, amp, ph, xc, sw, sph) in trav:
        a = TAU * (t + ph)
        y = yc + amp * math.cos(a)
        sp = abs(math.sin(a))
        x = xc + sw * math.sin(a + sph)
        out.append((x, y, r / (1 + 0.10 * sp), r * (1 + 0.25 * sp), 1.0))
    # a stretching pair: same path, a little out of phase -> neck, pinch off, merge again
    for (r, lag) in ((7.0, 0.0), (6.3, 0.11)):
        a = TAU * (t + 0.77 - lag)
        y = 54.0 + 17.0 * math.cos(a)
        x = 34.0 + 2.0 * math.sin(a + 1.3)
        out.append((x, y, r, r * 1.15, 1.0))
    return out


WAX_T = 0.30          # iso level of the compact field


def lava_field(blobs, x, y):
    f = 0.0
    for (bx, by, sx, sy, w) in blobs:
        dx, dy = (x - bx) / sx, (y - by) / sy
        d2 = dx * dx + dy * dy
        if d2 < 1.0:
            q = 1.0 - d2
            f += w * q * q
    return f


def draw_lava(t):
    c = e.blocks(2, 1)
    W, H = c.w, c.h
    # ---- room
    wall(c, mc('COLOR_BLACK', 0), mc('TERRACOTTA_BLACK', 2), 0, 117)
    radial_glow(c, L_CX, 62, 31, 58, [mc('TERRACOTTA_PURPLE', 0), mc('WARPED_HYPHAE', 0),
                                       mc('TERRACOTTA_BLUE', 0), mc('TERRACOTTA_GRAY', 1)], power=0.85)
    warm = [mc('TERRACOTTA_ORANGE', 0), mc('TERRACOTTA_ORANGE', 1), mc('COLOR_ORANGE', 1)]
    desk_top(c, 117, L_CX, 30, warm)
    # warm pool of light on the desk from the base holes
    radial_glow(c, L_CX, 118, 26, 7, [mc('TERRACOTTA_ORANGE', 1), mc('TERRACOTTA_ORANGE', 0),
                                       mc('TERRACOTTA_BROWN', 2)], box=(0, 117, W, H))

    # ---- glass + liquid + wax
    liquid = [mc('COLOR_PURPLE', 0), mc('COLOR_PURPLE', 1), mc('COLOR_MAGENTA', 1),
              mc('COLOR_MAGENTA', 2), mc('COLOR_MAGENTA', 3)]
    wax_cols = {
        'rim': mc('CRIMSON_NYLIUM', 3), 'dark': mc('COLOR_ORANGE', 2), 'body': mc('COLOR_ORANGE', 3),
        'lit': mc('GOLD', 2), 'hot': mc('GOLD', 3), 'cool': mc('COLOR_ORANGE', 2),
    }
    blobs = lava_blobs(t)
    for y in range(G0, G1 + 1):
        hw = glass_hw(y)
        u = (y - G0) / (G1 - G0)
        xl, xr = int(round(L_CX - hw)), int(round(L_CX + hw))
        for x in range(xl, xr):
            dx = (x + 0.5 - L_CX) / hw                  # -1..1 across the glass
            edge = x == xl or x == xr - 1
            # liquid: lit from the heater, brightest low and in the middle
            v = 0.12 + 0.78 * u ** 1.15 - 0.42 * dx * dx
            v += 0.18 * math.exp(-(dx / 0.35) ** 2) * u ** 2        # light column from the bulb
            col = ramp(liquid, v, x, y)
            if edge:
                col = e.shade(col, -1)
            # wax
            if not edge and y < G1 + 1:
                f = lava_field(blobs, x + 0.5, y + 0.5)
                if f >= WAX_T:
                    up = lava_field(blobs, x + 0.5, y - 0.5)
                    dn = lava_field(blobs, x + 0.5, y + 1.5)
                    lf = lava_field(blobs, x - 0.5, y + 0.5)
                    rt = lava_field(blobs, x + 1.5, y + 0.5)
                    gx, gy = rt - lf, dn - up                 # field gradient (points inward)
                    gl = math.hypot(gx, gy) + 1e-9
                    ny = -gy / gl                             # outward normal, +1 = facing down
                    heat = u                                  # 0 top (cool) .. 1 bottom (hot)

                    def run(dx_, dy_):
                        for k in range(1, 4):
                            if lava_field(blobs, x + 0.5 + dx_ * k, y + 0.5 + dy_ * k) < WAX_T:
                                return k
                        return 4
                    db, dt = run(0, 1), run(0, -1)
                    side = min(lf, rt) < WAX_T
                    if dt == 1 and db > 1:
                        col = wax_cols['rim'] if heat < 0.7 else wax_cols['dark']     # shadowed crown
                    elif db == 1:
                        col = wax_cols['hot'] if heat > 0.5 else wax_cols['lit']      # lit underside
                    elif side:
                        col = wax_cols['dark']
                    elif db == 2:
                        col = wax_cols['lit'] if heat > 0.25 else wax_cols['body']
                    elif heat < 0.15 and dt <= 2:
                        col = wax_cols['cool']
                    else:
                        col = wax_cols['body']
                        inner = min(db, dt, run(-1, 0), run(1, 0))
                        glowv = (inner - 3) / 1.5 + (heat - 0.55) * 0.9    # glowing core, hotter low down
                        if y >= G1 - 3:
                            glowv += 0.5                                   # the pool sits on the heater
                        if glowv > 0.55:
                            col = wax_cols['hot'] if glowv > 1.3 else wax_cols['lit']
            c.p[y][x] = col
        # glass curvature highlight (left) and shadow line (right)
        hx = int(round(L_CX - hw * 0.62))
        if 0.08 < u < 0.93 and (y % 9) != 4:
            cur = c.p[y][hx]
            c.p[y][hx] = e.shade(cur, +1) if e.base_of(cur) in ('COLOR_PURPLE', 'COLOR_MAGENTA') else cur

    # ---- cap: small cone, chrome
    chrome = [mc('COLOR_BLACK', 2), mc('COLOR_GRAY', 0), mc('COLOR_GRAY', 2), mc('DEEPSLATE', 2),
              mc('METAL', 1), mc('METAL', 3), mc('QUARTZ', 1)]
    for y in range(8, G0):
        s = (y - 8) / (G0 - 9)
        hw = 3.5 + 3.5 * s
        for x in range(int(round(L_CX - hw)), int(round(L_CX + hw))):
            uu = (x + 0.5 - L_CX) / hw
            v = metal_col(uu, chrome) * (0.55 + 0.45 * s)
            col = ramp(chrome, v, x, y)
            if y == G0 - 1:                                 # glass light on the cap's lip
                col = ramp([mc('COLOR_BLACK', 2), mc('COLOR_PURPLE', 0), mc('COLOR_MAGENTA', 1)],
                           1 - abs(uu), x, y)
            c.p[y][x] = col
    for x in range(L_CX - 3, L_CX + 3):                     # rounded top
        c.p[7][x] = ramp(chrome, metal_col((x + 0.5 - L_CX) / 3.5, chrome) * 0.45, x, 7)

    # ---- base: collar + cone with glowing holes
    def base_hw(y):
        if y <= G1 + 3:
            return 11.5
        if y >= 114:
            return 22.0
        s = (y - (G1 + 3)) / (113 - (G1 + 3))
        return 10.5 + 11.0 * s
    seams = {}                                              # x -> seam rows (rings seen from a little above)
    for y in range(G1 + 1, 117):
        hw = base_hw(y)
        for x in range(int(round(L_CX - hw)), int(round(L_CX + hw))):
            uu = (x + 0.5 - L_CX) / hw
            v = metal_col(uu, chrome) * (0.85 if y > G1 + 3 else 1.0)
            col = ramp(chrome, v, x, y)
            if y == G1 + 1:                                 # warm light under the glass
                col = ramp([mc('TERRACOTTA_ORANGE', 1), mc('COLOR_ORANGE', 1), mc('COLOR_ORANGE', 2)],
                           1 - abs(uu), x, y)
            c.p[y][x] = col
    for (ys, hwf) in ((G1 + 4, None), (113, None)):
        hw = base_hw(ys)
        for x in range(int(round(L_CX - hw)), int(round(L_CX + hw))):
            uu = (x + 0.5 - L_CX) / hw
            yy = ys + int(round(1.6 * math.sqrt(max(0.0, 1 - uu * uu))))
            c.p[yy][x] = mc('COLOR_BLACK', 1)
    # a ring of glowing round cutouts (the bulb shining through)
    hy0 = 103
    for th in (-56, -28, 0, 28, 56):
        a = math.radians(th)
        hw = base_hw(hy0 + 2)
        hx = L_CX + hw * 0.88 * math.sin(a)
        hy = hy0 + 1.8 * math.cos(a)
        wide = abs(th) < 40
        pts = [(int(math.floor(hx)), int(round(hy))), (int(math.floor(hx)), int(round(hy)) + 1)]
        if wide:
            pts += [(int(math.floor(hx)) - 1, int(round(hy))), (int(math.floor(hx)) - 1, int(round(hy)) + 1)]
        e.glow(c, pts, mc('GOLD', 3), halo=[mc('COLOR_ORANGE', 2)], lighten=False)
    return c


# =============================================================================================== FISH TANK

FISH_FRAMES, FISH_MS = 24, 200
TX0, TX1 = 8, 119          # glass columns (inclusive)
TY0, TY1 = 11, 53          # top rim row .. bottom trim last row
WATER_Y = 14               # surface row
GRAVEL = [mc('COLOR_PINK', 1), mc('COLOR_PINK', 2), mc('LAPIS', 1), mc('LAPIS', 2), mc('COLOR_YELLOW', 1),
          mc('COLOR_YELLOW', 2), mc('EMERALD', 1), mc('DIAMOND', 1), mc('COLOR_MAGENTA', 1), mc('ICE', 1)]

GOLDFISH = [            # facing right; t tail, d fin, o body, y belly, h highlight, e eye
    "......dd.....",
    "t...ddoooo...",
    "tt.oooohoooo.",
    "ttoooooooooeo",
    "ttooyyyyyoooo",
    "tt.oyyyyyoo..",
    "t...oofoo....",
    "......f......",
]
GOLDFISH_B = [          # tail flick pose
    "......dd.....",
    "....ddoooo...",
    "t..oooohoooo.",
    "ttooooooooeoo",
    "ttooyyyyyoooo",
    "t..oyyyyyoo..",
    "....oofoo....",
    "......f......",
]
TETRA = [
    "..ssss..",
    "tbbbbbbe",
    "trrrrss.",
    "..ssss..",
]
TETRA_B = [
    "..ssss..",
    ".bbbbbbe",
    "trrrrss.",
    "t.ssss..",
]
ANGEL = [
    "....d.....",
    "....dd....",
    "...sss....",
    "..skskk...",
    "t.skskkss.",
    "tsskskksse",
    "t.skskkss.",
    "..skskk...",
    "...sss....",
    "...dd.....",
    "..dd......",
    ".d........",
]
ANGEL_B = [
    "....d.....",
    "....dd....",
    "...sss....",
    "..skskk...",
    "..skskkss.",
    "tsskskksse",
    "..skskkss.",
    "..skskk...",
    "...sss....",
    "...dd.....",
    "...dd.....",
    "..d.......",
]


def sprite(c, rows, x, y, cols, flip=False):
    """Draw a text sprite with its centre at (x, y); flip mirrors it (facing left)."""
    h, w = len(rows), len(rows[0])
    x0, y0 = int(round(x - w / 2)), int(round(y - h / 2))
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == '.':
                continue
            xx = x0 + (w - 1 - i if flip else i)
            if TX0 < xx < TX1 and WATER_Y <= y0 + j < 50:
                c.px(xx, y0 + j, cols[ch])


def swim(t, xa, xb, phase, freq=1):
    """Across and back: position and facing (True = facing right) with a slow turn at each end."""
    p = (t * freq + phase) % 1.0
    def ease(s):
        return 0.55 * s + 0.45 * (s * s * (3 - 2 * s))
    if p < 0.5:
        return xa + (xb - xa) * ease(p * 2), True
    return xb - (xb - xa) * ease((p - 0.5) * 2), False


def gravel_top(x):
    return int(round(43.5 + 1.6 * math.sin(x * 0.11 + 0.5) + 0.8 * math.sin(x * 0.37) + (x - 64) * 0.012))


def plant(c, base_x, base_y, height, blades, t, phase, cols, lean=0.0):
    """Swaying water plant: tapered blades from one root, swaying more toward the tips."""
    for b, (dx, hf, bend) in enumerate(blades):
        hh = height * hf
        n = int(hh)
        for k in range(n):
            s = k / max(1, n - 1)
            sway = (1.6 * math.sin(TAU * (t + phase + 0.06 * b)) + bend * 3.0 + lean * 4) * s ** 1.6
            x = base_x + dx + sway
            y = base_y - k
            col = cols[min(len(cols) - 1, int(s * len(cols) * 0.999))]
            width = 2 if s < 0.55 else 1
            for wv in range(width):
                xx = int(round(x)) + wv
                if TX0 < xx < TX1 and y > WATER_Y:
                    c.px(xx, y, col)
                    if wv == 0 and width == 2 and k % 3 == 0:
                        c.px(xx, y, e.shade(col, -1))      # leaf vein shadow


def castle(c, x0, base):
    """Little aquarium castle: two towers, a keep, an arched door, windows; lit from the hood above."""
    stone = [mc('CLAY', 0), mc('CLAY', 1), mc('CLAY', 2), mc('CLAY', 3)]
    dark = mc('COLOR_BLUE', 0)
    parts = [(x0, base - 18, x0 + 6, base), (x0 + 16, base - 21, x0 + 22, base),     # towers
             (x0 + 5, base - 13, x0 + 17, base)]                                    # keep
    for (a, top, b, bot) in parts:
        for y in range(top, bot):
            for x in range(a, b):
                u = (x - a) / max(1, b - a - 1)
                v = 0.85 - 0.55 * u - 0.25 * (y - top) / max(1, bot - top)
                col = ramp(stone, v, x, y)
                if (y - top) % 4 == 3 and (x + (y - top) // 4 * 2) % 5 != 0:
                    col = e.shade(col, -1)                      # mortar
                c.px(x, y, col)
        for x in range(a, b):                                   # crenellations
            if (x - a) % 2 == 0:
                c.px(x, top - 1, stone[3])
                c.px(x, top - 2, stone[3] if x - a < 2 else stone[2])
            c.px(x, top, stone[3])
    # roof cones on the towers
    for (a, top, b) in ((x0, base - 18, x0 + 6), (x0 + 16, base - 21, x0 + 22)):
        cx_ = (a + b - 1) / 2
        for k in range(6):
            hw = 3.4 * (1 - k / 6)
            for x in range(int(round(cx_ - hw)), int(round(cx_ + hw)) + 1):
                c.px(x, top - 3 - k, mc('COLOR_RED', 3) if x < cx_ else mc('COLOR_RED', 2))
        c.px(int(cx_), top - 9, mc('COLOR_YELLOW', 3))
    # door + windows (dark, with a soft blue inside)
    dx = x0 + 9
    for y in range(base - 7, base):
        for x in range(dx, dx + 4):
            if y == base - 7 and x in (dx, dx + 3):
                continue
            c.px(x, y, dark)
    for (wx, wy) in ((x0 + 2, base - 14), (x0 + 18, base - 17), (x0 + 18, base - 10), (x0 + 2, base - 8)):
        c.px(wx, wy, dark)
        c.px(wx + 1, wy, dark)
        c.px(wx, wy + 1, dark)
        c.px(wx + 1, wy + 1, dark)
    # moss
    rng = random.Random(3)
    for (a, top, b, bot) in parts:
        for x in range(a, b):
            for y in range(bot - 3, bot):
                if rng.random() < 0.35:
                    c.px(x, y, mc('GRASS', 1 if rng.random() < 0.5 else 0))


def draw_fish(t, k):
    c = e.blocks(1, 2)
    W, H = c.w, c.h
    # ---- room: dark wall with the tank's cool light spilling onto it, desk below
    wall(c, mc('COLOR_BLACK', 0), mc('COLOR_BLACK', 2), 0, 54)
    radial_glow(c, 64, 30, 74, 36, [mc('COLOR_CYAN', 0), mc('TERRACOTTA_CYAN', 0), mc('TERRACOTTA_BLUE', 0),
                                     mc('COLOR_GRAY', 0), mc('COLOR_BLACK', 3)], power=0.8)
    desk_top(c, 54, 64, 66, [mc('COLOR_CYAN', 0), mc('COLOR_LIGHT_BLUE', 0), mc('COLOR_LIGHT_BLUE', 1)])

    # ---- water
    water = [mc('COLOR_BLUE', 1), mc('COLOR_BLUE', 2), mc('LAPIS', 1), mc('LAPIS', 2), mc('COLOR_LIGHT_BLUE', 3)]
    for y in range(WATER_Y, 50):
        for x in range(TX0 + 1, TX1):
            depth = (y - WATER_Y) / (50 - WATER_Y)
            v = 0.92 - 0.85 * depth ** 0.8
            # slanting light shafts from the hood lamp, shimmering
            sh = math.sin((x + 0.45 * (y - WATER_Y)) * 0.22 + TAU * t)
            sh2 = math.sin((x + 0.45 * (y - WATER_Y)) * 0.09 - TAU * t + 1.0)
            v += 0.10 * max(0.0, sh * sh2) * (1 - depth)
            c.p[y][x] = ramp(water, v, x, y)
    # surface: lit air gap, shimmering waterline
    for x in range(TX0 + 1, TX1):
        c.p[12][x] = ramp([mc('COLOR_LIGHT_BLUE', 1), mc('ICE', 2), mc('ICE', 3)], 0.8, x, 12)
        c.p[13][x] = mc('COLOR_LIGHT_BLUE', 1)
        wv = math.sin(x * 0.35 + TAU * t * 2) + math.sin(x * 0.13 - TAU * t)
        c.p[WATER_Y][x] = mc('ICE', 3) if wv > 0.6 else mc('DIAMOND', 2)
        if wv < -0.9:
            c.p[WATER_Y + 1][x] = mc('DIAMOND', 1)

    # ---- back plants
    greens = [mc('PLANT', 1), mc('EMERALD', 0), mc('EMERALD', 1), mc('GRASS', 2), mc('COLOR_LIGHT_GREEN', 2)]
    teal = [mc('WARPED_NYLIUM', 1), mc('WARPED_WART_BLOCK', 0), mc('WARPED_WART_BLOCK', 1),
            mc('WARPED_WART_BLOCK', 2), mc('DIAMOND', 2)]
    plant(c, 14, 45, 28, [(0, 1.0, 0.2), (2, 0.8, -0.4), (4, 0.95, 0.5), (-2, 0.7, -0.7)], t, 0.0, greens)
    plant(c, 70, 45, 22, [(0, 1.0, 0.1), (2, 0.75, 0.6), (-2, 0.85, -0.5)], t, 0.3, teal)
    # ---- castle
    castle(c, 86, 46)
    # ---- fish (angelfish behind the front plant, others in front)
    fcol = {'t': mc('COLOR_ORANGE', 2), 'd': mc('COLOR_ORANGE', 1), 'o': mc('COLOR_ORANGE', 3),
            'y': mc('GOLD', 2), 'h': mc('GOLD', 3), 'e': mc('COLOR_BLACK', 0), 'f': mc('COLOR_ORANGE', 2)}
    tcol = {'s': mc('QUARTZ', 1), 'b': mc('DIAMOND', 3), 'r': mc('FIRE', 2), 't': mc('ICE', 1), 'e': mc('COLOR_BLACK', 0)}
    acol = {'s': mc('SAND', 3), 'k': mc('COLOR_GRAY', 0), 'd': mc('SAND', 1), 't': mc('SAND', 2), 'e': mc('COLOR_BLACK', 0)}
    wag = k % 2
    ax, ar = swim(t, 38, 70, 0.25)
    sprite(c, ANGEL_B if wag else ANGEL, ax, 28 + 1.2 * math.sin(TAU * t), acol, flip=not ar)
    # ---- gravel
    rng = random.Random(11)
    for x in range(TX0 + 1, TX1):
        top = gravel_top(x)
        for y in range(top, 50):
            col = GRAVEL[rng.randrange(len(GRAVEL))]
            if y == top:
                col = e.shade(col, +1)
            elif y > top + 3:
                col = e.shade(col, -1)
            c.p[y][x] = col
    # air stone + bubbles
    sx = 24
    for (xx, yy) in ((sx - 2, 44), (sx - 1, 43), (sx, 43), (sx + 1, 43), (sx + 2, 44), (sx - 1, 44), (sx, 44), (sx + 1, 44)):
        c.px(xx, yy, mc('STONE', 2) if yy == 43 else mc('STONE', 1))
    gx, gr = swim(t, 22, 104, 0.0)
    sprite(c, GOLDFISH_B if wag else GOLDFISH, gx, 23 + 1.5 * math.sin(TAU * (t * 2 + 0.2)), fcol, flip=not gr)
    for j in range(2):                                       # a pair of tetras schooling, the second a beat behind
        tx, tr = swim(t, 32, 84, 0.55 - 0.045 * j)
        sprite(c, TETRA_B if (wag + j) % 2 else TETRA, tx, 35 + 3 * j + math.sin(TAU * (t + j * 0.3)), tcol, flip=not tr)
    # front plant
    plant(c, 60, 46, 16, [(0, 1.0, -0.2), (2, 0.8, 0.5), (-2, 0.7, -0.6)], t, 0.6, greens)
    plant(c, 112, 46, 20, [(0, 1.0, -0.3), (2, 0.7, 0.4), (-2, 0.85, -0.8)], t, 0.45, teal)
    # bubbles
    for i in range(7):
        p = (t * 2 + i / 7.0) % 1.0
        y = 42 - p * 27
        x = sx + 1.3 * math.sin(y * 0.45 + i * 1.7)
        xi, yi = int(round(x)), int(round(y))
        if p < 0.35:
            c.px(xi, yi, mc('ICE', 3))
        else:
            for (ddx, ddy, col) in ((0, 0, mc('ICE', 3)), (1, 0, mc('DIAMOND', 2)), (0, 1, mc('DIAMOND', 2)), (1, 1, mc('LAPIS', 2))):
                c.px(xi + ddx, yi + ddy, col)
    # ---- glass, frame, hood
    for y in range(12, 50):
        c.p[y][TX0] = mc('COLOR_CYAN', 1)
        c.p[y][TX1] = mc('COLOR_CYAN', 0)
    for (gx0, gy0) in ((16, 17), (20, 17)):                 # faint reflection streaks on the front glass
        for k2 in range(10 if gx0 == 16 else 6):
            xx, yy = gx0 + k2, gy0 + k2
            if yy < gravel_top(xx) - 1:
                c.px(xx, yy, e.shade(c.get(xx, yy), +1))
    for x in range(TX0 - 1, TX1 + 2):
        c.px(x, 11, mc('COLOR_BLACK', 2))                  # top rim
        for y in range(50, 54):
            c.px(x, y, mc('COLOR_BLACK', 3) if y == 50 else (mc('COLOR_BLACK', 1) if y == 53 else mc('COLOR_BLACK', 2)))
    for x in range(TX0 - 2, TX1 + 3):                      # hood
        for y in range(5, 11):
            col = mc('COLOR_BLACK', 3)
            if y == 5:
                col = mc('COLOR_GRAY', 0)
                if x in (TX0 - 2, TX1 + 2):
                    continue
            elif y == 10:
                col = mc('COLOR_BLACK', 1)
            elif y == 7 and (x // 3) % 2 == 0 and 40 < x < 88:
                col = mc('COLOR_BLACK', 1)                 # vent slots
            c.px(x, y, col)
    e.glow(c, [(TX1 - 4, 8)], mc('EMERALD', 3), halo=[mc('EMERALD', 0)], lighten=False)   # power light
    return c


# ============================================================================================ PLASMA GLOBE

GLOBE_FRAMES, GLOBE_MS = 16, 150
P_CX, P_CY, P_R = 64, 50, 40       # sphere centre and radius
CORE_R = 6
# filaments: (base angle deg, wander deg, wander phase, reaches the glass?, colour family)
FILAMENTS = [(-150, 20, 0.05, True), (-112, 16, 0.40, True), (-70, 20, 0.72, True), (-28, 18, 0.21, True),
             (12, 16, 0.58, True), (52, 14, 0.93, True), (165, 18, 0.33, True), (200, 14, 0.88, True),
             (-90, 30, 0.15, False), (120, 25, 0.66, False), (95, 12, 0.48, True)]


def filament_path(t, k, i, spec, rng):
    """Wavy path from the core to the glass (or toward the viewer) for filament i at phase t, frame k.
    The wander and the slow bend are periodic in t (seamless loop); a small per-frame jitter is the crackle."""
    base, wander, ph, reach = spec
    ang = math.radians(base + wander * math.sin(TAU * (t + ph)) + 0.4 * wander * math.sin(TAU * (2 * t + ph * 3)))
    r_end = P_R - 1.0 if reach else P_R * (0.50 + 0.10 * math.sin(TAU * (t + ph * 2)))
    ex, ey = P_CX + r_end * math.cos(ang), P_CY + r_end * math.sin(ang)
    sx, sy = P_CX + (CORE_R - 1) * math.cos(ang), P_CY + (CORE_R - 1) * math.sin(ang)
    nx, ny = -math.sin(ang), math.cos(ang)                  # perpendicular
    segs = 18
    pts = []
    p1 = TAU * (t + ph * 1.7) + i
    p2 = TAU * (2 * t + ph) + rng.uniform(-0.9, 0.9)        # the wiggle shivers frame to frame
    a1 = 3.2 * (1 if i % 2 else -1)
    a2 = 1.0
    for s_i in range(segs + 1):
        s = s_i / segs
        env = max(0.0, math.sin(math.pi * s)) ** 0.7
        off = env * (a1 * math.sin(TAU * 0.8 * s + p1) + a2 * math.sin(TAU * 2.3 * s + p2))
        if 0 < s_i < segs:
            off += rng.uniform(-0.3, 0.3)
        pts.append((sx + (ex - sx) * s + nx * off, sy + (ey - sy) * s + ny * off))
    return pts, (ex, ey), ang


def draw_globe(t, k):
    c = e.blocks(2, 2)
    W, H = c.w, c.h
    rng = random.Random(1000 + k)
    DESK = 108
    # ---- room
    wall(c, mc('COLOR_BLACK', 0), mc('COLOR_BLACK', 2), 0, DESK)
    radial_glow(c, P_CX, P_CY, 66, 62, [mc('TERRACOTTA_PURPLE', 0), mc('WARPED_HYPHAE', 0), mc('TERRACOTTA_BLUE', 0),
                                         mc('COLOR_GRAY', 0), mc('COLOR_BLACK', 3)], power=0.8)
    desk_top(c, DESK, P_CX, 54, [mc('COLOR_PURPLE', 0), mc('COLOR_MAGENTA', 0), mc('COLOR_MAGENTA', 1)])
    radial_glow(c, P_CX, DESK + 1, 46, 9, [mc('TERRACOTTA_MAGENTA', 0), mc('TERRACOTTA_PURPLE', 0),
                                           mc('WARPED_HYPHAE', 0)], box=(0, DESK, W, H))

    # ---- sphere interior: dark gas with a faint violet haze around the core
    haze = [mc('COLOR_BLACK', 2), mc('TERRACOTTA_BLUE', 0), mc('COLOR_PURPLE', 0), mc('COLOR_PURPLE', 1)]
    inside = set()
    for y in range(P_CY - P_R - 1, P_CY + P_R + 2):
        for x in range(P_CX - P_R - 1, P_CX + P_R + 2):
            d = math.hypot(x + 0.5 - P_CX, y + 0.5 - P_CY) / P_R
            if d <= 1.0:
                inside.add((x, y))
                v = max(0.0, 1 - d) ** 1.5 * 0.95
                c.px(x, y, ramp(haze, v, x, y))
    # ---- filaments: pink near the electrode, magenta through the gas, violet-blue where they hit the glass
    tips = []
    for i, spec in enumerate(FILAMENTS):
        pts, (ex, ey), ang = filament_path(t, k, i, spec, rng)
        dim = rng.random() < 0.10                           # the odd one flickers low
        n = len(pts)
        cut1, cut2 = n // 4, (3 * n) // 4
        outer = e.path_pixels(pts[cut2:], 1)
        mid = e.path_pixels(pts[cut1:cut2 + 1], 1)
        inner = e.path_pixels(pts[:cut1 + 1], 1)
        # forks fanning out toward the glass
        for f in range(2 + (rng.random() < 0.6)):
            j = int(n * rng.uniform(0.55, 0.82))
            bx, by = pts[j]
            fa = ang + rng.choice((-1, 1)) * rng.uniform(0.35, 0.9)
            ln = rng.uniform(5.0, 10.0)
            fx, fy = bx + ln * math.cos(fa), by + ln * math.sin(fa)
            dd = math.hypot(fx - P_CX, fy - P_CY)
            if dd > P_R - 1.5:
                fx, fy = P_CX + (fx - P_CX) * (P_R - 1.5) / dd, P_CY + (fy - P_CY) * (P_R - 1.5) / dd
            mx = (bx + fx) / 2 + rng.uniform(-1.2, 1.2)
            my = (by + fy) / 2 + rng.uniform(-1.2, 1.2)
            e.glow(c, e.path_pixels([(bx, by), (mx, my), (fx, fy)], 1), mc('COLOR_PURPLE', 3) if not dim else mc('COLOR_PURPLE', 2),
                   halo=[mc('COLOR_PURPLE', 0)])
            if spec[3] and dd > P_R - 3:
                tips.append((fx, fy, False))
        lvl = 2 if dim else 3
        e.glow(c, outer, mc('ICE', lvl), halo=[mc('COLOR_PURPLE', 1), mc('COLOR_PURPLE', 0)])
        e.glow(c, mid, mc('COLOR_MAGENTA', lvl), halo=[mc('COLOR_MAGENTA', 1), mc('COLOR_PURPLE', 0)])
        e.glow(c, inner, mc('COLOR_PINK', lvl), halo=[mc('COLOR_MAGENTA', 2), mc('COLOR_MAGENTA', 0)])
        tips.append((ex, ey, spec[3]))
    # where filaments touch the glass: a little hot spot spreading on the glass
    for (tx, ty, big) in tips:
        p = (int(math.floor(tx)), int(math.floor(ty)))
        pts = [p, (p[0] + 1, p[1]), (p[0], p[1] + 1), (p[0] + 1, p[1] + 1)] if big else [p]
        e.glow(c, pts, mc('ICE', 3) if big else mc('ICE', 2),
               halo=[mc('COLOR_MAGENTA', 2), mc('COLOR_PURPLE', 2), mc('COLOR_PURPLE', 0)] if big else [mc('COLOR_PURPLE', 1)])

    # ---- core electrode: a glass ball glowing pink-white, with a soft corona
    flick = 0.5 * math.sin(TAU * 3 * t) + rng.uniform(-0.3, 0.3)
    for y in range(P_CY - CORE_R - 6, P_CY + CORE_R + 7):
        for x in range(P_CX - CORE_R - 6, P_CX + CORE_R + 7):
            dc = math.hypot(x + 0.5 - P_CX, y + 0.5 - P_CY)
            if dc > CORE_R + 5:
                continue
            if dc <= CORE_R - 0.3:
                d = math.hypot(x + 0.5 - P_CX + 1.2, y + 0.5 - P_CY + 1.2)     # hot spot up-left
                v = 1 - d / (CORE_R + 1.0)
                col = ramp([mc('COLOR_MAGENTA', 3), mc('COLOR_PINK', 2), mc('COLOR_PINK', 3),
                            mc('QUARTZ', 2)], v * 1.25, x, y)
                c.px(x, y, col)
                continue
            if dc <= CORE_R + 0.7:
                col = mc('COLOR_MAGENTA', 3)                 # bright skin of the ball
            elif dc <= CORE_R + 2.2 + flick:
                col = mc('COLOR_MAGENTA', 1)
            elif dc <= CORE_R + 4.0 + flick:
                col = mc('COLOR_PURPLE', 1)
            else:
                col = mc('COLOR_PURPLE', 0)
            brighter(c, x, y, col)
    # stem below the core
    for y in range(P_CY + CORE_R + 1, P_CY + P_R):
        for x in range(P_CX - 2, P_CX + 2):
            col = mc('TERRACOTTA_BLUE', 0) if x in (P_CX - 2, P_CX + 1) else mc('COLOR_BLACK', 3)
            if x == P_CX - 1:
                col = mc('TERRACOTTA_PURPLE', 0)
            if (y - P_CY) < CORE_R + 5 and x in (P_CX - 1, P_CX):
                col = mc('COLOR_PURPLE', 0)
            brighter(c, x, y, col) if (y - P_CY) < CORE_R + 5 else c.px(x, y, col)

    # ---- glass: rim and highlights
    rim = e.arc_pixels(P_CX, P_CY, P_R + 0.3, P_R + 0.3, 0, 360, 1)
    for (x, y) in rim:
        a = math.degrees(math.atan2(y + 0.5 - P_CY, x + 0.5 - P_CX))
        lit_side = math.cos(math.radians(a + 135))          # brighter toward the upper left
        col = mc('TERRACOTTA_LIGHT_BLUE', 1) if lit_side > 0.3 else mc('TERRACOTTA_LIGHT_BLUE', 0)
        brighter(c, x, y, col)
    for (x, y) in e.arc_pixels(P_CX, P_CY, P_R - 5, P_R - 5, 200, 245, 2):
        brighter(c, x, y, mc('ICE', 1))
    for (x, y) in e.arc_pixels(P_CX, P_CY, P_R - 5, P_R - 5, 250, 258, 2):
        brighter(c, x, y, mc('ICE', 0))
    for (x, y) in e.arc_pixels(P_CX, P_CY, P_R - 4, P_R - 4, 20, 40, 1):
        brighter(c, x, y, mc('TERRACOTTA_LIGHT_BLUE', 1))

    # ---- base: black dome-cone with a lit collar
    bt, bb = 84, DESK
    for y in range(bt, bb):
        s = (y - bt) / (bb - bt - 1)
        hw = 17 + 15 * s ** 0.8
        for x in range(int(round(P_CX - hw)), int(round(P_CX + hw))):
            uu = (x + 0.5 - P_CX) / hw
            v = 0.15 + 0.35 * math.exp(-((uu + 0.4) / 0.3) ** 2) + 0.12 * (1 - abs(uu))
            col = ramp([mc('COLOR_BLACK', 0), mc('COLOR_BLACK', 2), mc('COLOR_GRAY', 0), mc('COLOR_GRAY', 1),
                        mc('DEEPSLATE', 1)], v, x, y)
            if y <= bt + 1:                                 # collar lit by the globe
                col = ramp([mc('COLOR_PURPLE', 0), mc('COLOR_MAGENTA', 0), mc('COLOR_MAGENTA', 1)],
                           (1 - abs(uu)) * 0.9, x, y)
            c.px(x, y, col)
    for x in range(P_CX - 32, P_CX + 32):                   # foot seam
        c.px(x, bb - 3, mc('COLOR_BLACK', 0))
    # red power light on the front
    e.glow(c, [(P_CX + 8, bb - 9)], mc('FIRE', 3), halo=[mc('FIRE', 0)], lighten=False)
    return c


# ================================================================================================ main

def run_lava():
    frames = [draw_lava(i / LAVA_FRAMES) for i in range(LAVA_FRAMES)]
    return 'lava_lamp', 2, 1, frames, LAVA_MS


def run_fish():
    frames = [draw_fish(i / FISH_FRAMES, i) for i in range(FISH_FRAMES)]
    return 'fish_tank', 1, 2, frames, FISH_MS


def run_globe():
    frames = [draw_globe(i / GLOBE_FRAMES, i) for i in range(GLOBE_FRAMES)]
    return 'plasma_globe', 2, 2, frames, GLOBE_MS


PIECES = {'lava': run_lava, 'fish': run_fish, 'globe': run_globe}


def main(which):
    for key in which:
        name, h, w, frames, ms = PIECES[key]()
        path = os.path.join(HERE, e.out_name(name, h, w, 'gif'))
        info = e.save_gif(frames, ms, path)
        e.save_png(frames[0], os.path.join(HERE, e.out_name(name + '_still', h, w)))
        e.preview(frames, os.path.join(HERE, name + '_preview.png'), scale=2, delays_ms=ms,
                  title=f'{name} {h}x{w}')
        e.preview(frames[0], os.path.join(HERE, name + '_zoom.png'), scale=4)
        print(name, {k: v for k, v in info.items() if k != 'per_tile'})


if __name__ == '__main__':
    main(sys.argv[1:] or list(PIECES))
