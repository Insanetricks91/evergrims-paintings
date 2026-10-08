#!/usr/bin/env python3
"""ImageFrame paintings: a sushi restaurant set and a Grims Crops kitchen set.

Drawn as pixel art at 64 px per block and scaled up 2x with nearest neighbour, so every image lands
at 128 px per block -- one Minecraft map per block, the size ImageFrame renders -- and flat colours
survive the map palette. Python standard library only; run it to regenerate every PNG beside it.
Sizes are in blocks, height x width, and in each file name.
"""
import math
import os
import random
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = 64          # design pixels per block
SCALE = 2           # 64 x 2 = 128 px per block, one map


# ----------------------------------------------------------------------------------------- canvas

def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def dark(c, t=0.25):
    return mix(c, (0, 0, 0), t)


def light(c, t=0.25):
    return mix(c, (255, 255, 255), t)


class Canvas:
    def __init__(self, w, h, fill):
        self.w, self.h = w, h
        self.p = [[fill] * w for _ in range(h)]

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
        """Banded vertical gradient through cols, top to bottom."""
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
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for oy in range(w):
                for ox in range(w):
                    self.px(x + ox - w // 2, y + oy - w // 2, c)

    def speckle(self, pixels, cols, density, rng):
        for (x, y, *_rest) in pixels:
            if rng.random() < density:
                self.px(x, y, rng.choice(cols))

    def text(self, x, y, s, c, scale=1):
        for ch in s:
            glyph = FONT.get(ch.upper())
            if glyph:
                for gy, row in enumerate(glyph):
                    for gx, bit in enumerate(row):
                        if bit == '#':
                            self.rect(x + gx * scale, y + gy * scale,
                                      x + (gx + 1) * scale, y + (gy + 1) * scale, c)
            x += 6 * scale

    def frame(self):
        """A dark wooden picture frame, four pixels deep, so every piece reads as a painting."""
        w, h = self.w, self.h
        for i, col in enumerate([(46, 28, 16), (70, 44, 24), (112, 74, 40), (150, 104, 58)]):
            self.rect(i, i, w - i, i + 1, col)
            self.rect(i, h - i - 1, w - i, h - i, dark(col, 0.15))
            self.rect(i, i, i + 1, h - i, col)
            self.rect(w - i - 1, i, w - i, h - i, dark(col, 0.15))

    def save(self, name):
        self.frame()
        rows = []
        for row in self.p:
            line = bytearray()
            for c in row:
                line += bytes(c) * SCALE
            rows.extend([bytes(line)] * SCALE)
        w, h = self.w * SCALE, self.h * SCALE
        raw = b''.join(b'\x00' + r for r in rows)

        def chunk(t, d):
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
        path = os.path.join(HERE, name)
        open(path, 'wb').write(data)
        return path, w, h


FONT = {
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '6': ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    'X': ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
}

# ------------------------------------------------------------------------------------- palette

RICE = (246, 244, 236)
RICE_SHADE = (214, 210, 198)
NORI = (26, 38, 30)
SALMON = (246, 128, 72)
TUNA = (196, 34, 52)
TAMAGO = (246, 206, 74)
WASABI = (128, 178, 58)
GINGER = (238, 168, 168)
WOOD = (204, 156, 96)
INDIGO = (32, 48, 110)
LANTERN = (212, 44, 40)
TOMATO = (214, 48, 40)
LEAF = (82, 150, 52)


# ------------------------------------------------------------------------------------ pieces

def rice(c, cx, cy, rx=16, ry=6, rng=None):
    px = c.oell(cx, cy, rx, ry, RICE, (150, 148, 138))
    for (x, y, u, v) in px:
        if v > ry * 0.45:
            c.px(x, y, RICE_SHADE)
    c.speckle(px, [RICE_SHADE, (255, 255, 252)], 0.18, rng)


def salmon_slab(c, cx, cy, rx=18, ry=5.5, ang=-0.06):
    px = c.oell(cx, cy, rx, ry, SALMON, (176, 72, 40), ang)
    for (x, y, u, v) in px:
        if int(u * 0.9 - v * 1.6) % 6 == 0:
            c.px(x, y, (255, 200, 168))
        elif v < -ry * 0.55:
            c.px(x, y, light(SALMON, 0.18))


def tuna_slab(c, cx, cy, rx=18, ry=5.5, ang=0.05):
    px = c.oell(cx, cy, rx, ry, TUNA, (116, 14, 28), ang)
    for (x, y, u, v) in px:
        if v < -ry * 0.45 and abs(u) < rx * 0.7:
            c.px(x, y, (228, 82, 98))


def tamago_slab(c, cx, cy, w=34, h=11):
    x0, y0 = cx - w // 2, cy - h // 2
    c.rect(x0 - 1, y0 - 1, x0 + w + 1, y0 + h + 1, (186, 136, 36))
    c.rect(x0, y0, x0 + w, y0 + h, TAMAGO)
    for yy in range(y0 + 3, y0 + h, 3):
        c.rect(x0, yy, x0 + w, yy + 1, (232, 186, 56))
    c.rect(x0, y0, x0 + w, y0 + 1, light(TAMAGO, 0.3))
    ext = 8 if h >= 11 else max(2, h // 2 + 1)
    half = 3 if w >= 34 else max(1, w // 8)
    c.rect(cx - half, y0 - 1, cx + half + 1, y0 + h + ext, NORI)
    c.rect(cx - half + 1, y0 - 1, cx - half + 2, y0 + h + ext, (44, 62, 48))


def wasabi(c, cx, cy):
    px = c.oell(cx, cy, 5, 3.5, WASABI, (76, 110, 30))
    for (x, y, u, v) in px:
        if v < -1.5 and u < 1:
            c.px(x, y, light(WASABI, 0.3))


def ginger(c, cx, cy):
    for dx, dy, a in ((-3, 1, 0.5), (2, 0, -0.4), (0, -2, 0.1)):
        c.oell(cx + dx, cy + dy, 4.5, 2.5, GINGER, (196, 118, 128), a)


def lantern(c, cx, cy, rx=7, ry=9, body=LANTERN, glow=False):
    if glow:
        for (gr, t) in ((7, 0.14), (4, 0.26)):
            r = max(rx, ry) + gr + 1
            for y in range(int(cy - r), int(cy + r) + 1):
                for x in range(int(cx - r), int(cx + r) + 1):
                    if ((x + 0.5 - cx) / (rx + gr)) ** 2 + ((y + 0.5 - cy) / (ry + gr)) ** 2 <= 1.0:
                        under = c.get(x, y)
                        if under is not None:
                            c.px(x, y, mix(under, (255, 176, 84), t))
    px = c.oell(cx, cy, rx, ry, body, dark(body, 0.45))
    for (x, y, u, v) in px:
        if int(v + ry) % 3 == 0:
            c.px(x, y, dark(body, 0.2))
        elif u < -rx * 0.35 and abs(v) < ry * 0.6:
            c.px(x, y, light(body, 0.25))
    c.rect(cx - 4, cy - ry - 2, cx + 5, cy - ry + 1, (30, 22, 18))
    c.rect(cx - 4, cy + ry, cx + 5, cy + ry + 3, (30, 22, 18))
    c.line(cx, cy + ry + 3, cx, cy + ry + 6, (220, 180, 70))


def tomato(c, cx, cy, r=5):
    px = c.oell(cx, cy, r, r * 0.9, TOMATO, (120, 20, 16))
    for (x, y, u, v) in px:
        if u < -r * 0.2 and v < -r * 0.2 and u * u + v * v < r * r * 0.35:
            c.px(x, y, (246, 120, 104))
    c.rect(cx - 1, cy - r, cx + 2, cy - r + 2, (60, 120, 40))
    c.px(cx - 2, cy - r + 1, (60, 120, 40)); c.px(cx + 2, cy - r + 1, (60, 120, 40))


def chili(c, x, y, length=12, ang=1.35, col=(206, 36, 30)):
    for i in range(length):
        t = i / (length - 1)
        w = 2.6 * (1 - t) + 0.6
        cx, cy = x + math.cos(ang) * i, y + math.sin(ang) * i + math.sin(t * 2.2) * 1.5
        c.ell(cx, cy, w, w, col)
        if i % 3 == 0:
            c.px(cx - 1, cy - 1, light(col, 0.3))
    c.rect(x - 1, y - 3, x + 2, y, (70, 120, 40))


def corn_cob(c, x, y, w=8, h=20, ang=0.0):
    for (px_, py_, u, v) in c.oell(x, y, w / 2, h / 2, (240, 200, 60), (170, 120, 20), ang):
        if (int(u + 10) % 2 == 0) ^ (int(v + 10) % 2 == 0):
            c.px(px_, py_, (250, 222, 100))
    c.ell(x - w * 0.55, y + h * 0.15, 2.5, h * 0.45, (122, 168, 70), ang - 0.25)
    c.ell(x + w * 0.55, y + h * 0.15, 2.5, h * 0.45, (98, 146, 56), ang + 0.25)


def lettuce(c, cx, cy, r=10):
    for i, col in enumerate([(70, 130, 44), (98, 164, 58), (132, 196, 80), (170, 220, 110)]):
        c.ell(cx, cy + i * 0.6, r - i * 2.3, (r - i * 2.3) * 0.85, col)
    for a in range(0, 360, 45):
        c.px(cx + math.cos(math.radians(a)) * (r - 1), cy + math.sin(math.radians(a)) * (r - 1) * 0.85, (56, 110, 36))


def grapes(c, cx, cy):
    pts = [(0, 0), (-4, 0), (4, 0), (-2, 4), (2, 4), (0, 8), (-6, -4), (6, -4), (-2, -4), (2, -4)]
    for dx, dy in pts:
        for (x, y, u, v) in c.oell(cx + dx, cy + dy, 2.6, 2.6, (110, 50, 130), (60, 22, 72)):
            if u < -0.6 and v < -0.6:
                c.px(x, y, (170, 110, 190))
    c.line(cx, cy - 8, cx + 2, cy - 5, (100, 70, 40))
    c.ell(cx + 4, cy - 8, 3, 2, LEAF)


def steam(c, x, y, h, col):
    for i in range(h):
        c.px(x + math.sin(i / 3.0) * 2.2, y - i, col)


def seigaiha(c, x0, y0, x1, y1, a, b, r=7):
    """Overlapping wave scales, row by row, clipped to the box."""
    sub = Canvas(x1 - x0, y1 - y0, b)
    row = 0
    for cy in range(0, y1 - y0 + r * 2, r):
        off = (r if row % 2 else 0)
        for cx in range(-r * 2 + off, x1 - x0 + r * 2, r * 2):
            for k, col in enumerate([a, b, a, b]):
                sub.ell(cx, cy, r - k * 1.7, r - k * 1.7, col)
        row += 1
    for y in range(y1 - y0):
        for x in range(x1 - x0):
            c.px(x0 + x, y0 + y, sub.p[y][x])


# ------------------------------------------------------------------------------------ sushi set

def nigiri_trio():
    rng = random.Random(1)
    c = Canvas(3 * BLOCK, BLOCK, (28, 32, 58))
    for x in range(0, c.w, 12):
        c.rect(x, 0, x + 1, c.h, (38, 44, 76))
        c.rect(x + 6, 0, x + 7, c.h, (22, 26, 48))
    c.vgrad(0, 4, c.w, 22, [(46, 40, 70), (28, 32, 58)])
    c.rect(12, 40, 180, 45, (214, 168, 104))
    c.rect(12, 40, 180, 41, (234, 194, 132))
    c.rect(12, 45, 180, 51, (168, 118, 64))
    for x in range(16, 178, 10):
        c.rect(x, 47, x + 5, 48, (148, 102, 54))
    c.rect(22, 51, 30, 57, (112, 74, 38)); c.rect(162, 51, 170, 57, (112, 74, 38))
    c.rect(12, 56, 180, 57, (18, 20, 38))
    rice(c, 44, 37, rng=rng); salmon_slab(c, 44, 31)
    rice(c, 86, 37, rng=rng); tuna_slab(c, 86, 31)
    rice(c, 128, 37, rng=rng); tamago_slab(c, 128, 31)
    wasabi(c, 156, 38); ginger(c, 169, 38)
    return c


def noren_curtain():
    c = Canvas(3 * BLOCK, BLOCK, (64, 42, 30))
    for x in range(0, c.w, 16):
        c.rect(x, 0, x + 1, c.h, (50, 32, 22))
    c.vgrad(4, 46, c.w - 4, 60, [(150, 96, 40), (250, 196, 110), (255, 226, 160)])
    c.rect(4, 4, c.w - 4, 15, (38, 24, 14))
    c.rect(4, 14, c.w - 4, 15, (24, 14, 8))
    c.text(81, 6, "SUSHI", (230, 190, 90))
    c.rect(8, 15, c.w - 8, 17, (16, 14, 14))
    panels = [(12, 64), (68, 124), (128, 180)]
    for i, (x0, x1) in enumerate(panels):
        c.rect(x0, 17, x1, 50, INDIGO)
        if i != 1:
            seigaiha(c, x0 + 2, 30, x1 - 2, 48, (58, 80, 156), INDIGO, r=6)
        c.rect(x0, 17, x1, 19, dark(INDIGO, 0.25))
        c.rect(x0, 48, x1, 50, dark(INDIGO, 0.3))
    c.oell(96, 33, 12, 12, (242, 236, 220), (20, 28, 70))
    c.ell(94, 33, 7, 3.5, INDIGO, -0.15)
    c.poly([(100, 33), (106, 28), (106, 38)], INDIGO)
    c.px(90, 32, (242, 236, 220))
    return c


def lantern_alley():
    rng = random.Random(3)
    c = Canvas(3 * BLOCK, BLOCK, (20, 24, 60))
    c.vgrad(0, 0, c.w, c.h, [(16, 20, 54), (44, 30, 82), (104, 52, 92)])
    for _ in range(40):
        c.px(rng.randrange(6, c.w - 6), rng.randrange(5, 24), (200, 200, 230))
    roofs = [(0, 46, 40), (36, 40, 34), (66, 44, 40), (102, 38, 36), (134, 43, 30), (160, 39, 40)]
    for x, top, w in roofs:
        c.rect(x, top + 4, x + w, c.h, (16, 14, 30))
        c.poly([(x - 4, top + 5), (x + w // 2, top - 2), (x + w + 4, top + 5)], (12, 10, 24))
        for wx in range(x + 5, x + w - 6, 10):
            c.rect(wx, top + 10, wx + 5, top + 15, (250, 196, 96))
    pts = []
    for i in range(0, 185):
        x = 4 + i
        y = 12 + 9 * math.sin(math.pi * i / 184)
        pts.append((x, y))
        c.px(x, y, (30, 24, 20))
    for lx in (28, 62, 96, 130, 164):
        ly = 12 + 9 * math.sin(math.pi * (lx - 4) / 184)
        c.line(lx, ly, lx, ly + 3, (30, 24, 20))
        lantern(c, lx, ly + 13, glow=True)
    return c


def maki_platter():
    rng = random.Random(4)
    c = Canvas(2 * BLOCK, BLOCK, (196, 170, 112))
    for y in range(0, c.h, 3):
        c.rect(0, y, c.w, y + 1, (172, 146, 92))
    c.rect(9, 11, 119, 53, (70, 70, 74))
    c.rect(10, 12, 118, 52, (30, 30, 34))
    c.rect(10, 12, 118, 13, (54, 54, 60))
    fills = [((2, -1), SALMON, (-3, 2), (98, 170, 60)),
             ((-2, 1), TUNA, (3, -2), (150, 200, 90)),
             ((0, 2), SALMON, (-1, -3), (98, 170, 60)),
             ((1, -2), (250, 226, 120), (-2, 2), (98, 170, 60))]
    for i, mx in enumerate((28, 52, 76, 100)):
        c.ell(mx + 1, 34, 11, 11, (16, 16, 18))
        c.oell(mx, 32, 10, 10, NORI, (10, 14, 12))
        px = c.ell(mx, 32, 8, 8, RICE)
        c.speckle(px, [RICE_SHADE, (255, 255, 250)], 0.22, rng)
        (ox, oy), col, (gx, gy), gcol = fills[i]
        c.oell(mx + ox, 32 + oy, 3.3, 2.6, col, dark(col, 0.35))
        c.ell(mx + gx, 32 + gy, 1.8, 1.8, gcol)
    c.line(14, 58, 66, 55, (186, 128, 70), 2)
    c.line(16, 60, 68, 57, (166, 112, 60), 2)
    c.rect(70, 54, 78, 59, (60, 90, 150))
    return c


def koi_wave():
    c = Canvas(2 * BLOCK, BLOCK, (236, 224, 196))
    c.vgrad(0, 0, c.w, 34, [(240, 230, 204), (230, 214, 180)])
    c.ell(100, 17, 9, 9, (204, 64, 52))
    for x in range(c.w):
        yb = 32 + 4 * math.sin(x / 9.0)
        c.rect(x, yb, x + 1, c.h, (96, 146, 196))
    for x in range(c.w):
        yf = 42 + 5 * math.sin(x / 7.0 + 1.3)
        c.rect(x, yf, x + 1, c.h, (28, 58, 118))
        if (x // 3) % 4 == 0:
            c.px(x, yf + 6, (60, 96, 156))
    for x in range(4, c.w, 7):
        yf = 42 + 5 * math.sin(x / 7.0 + 1.3)
        if math.cos(x / 7.0 + 1.3) > 0.3:
            c.ell(x, yf - 1, 2.2, 1.6, (246, 246, 240))
    for x in range(0, c.w, 9):
        yb = 32 + 4 * math.sin(x / 9.0)
        if math.cos(x / 9.0) > 0.4:
            c.ell(x, yb - 1, 2, 1.4, (250, 250, 246))
    ang = -0.55
    body = c.oell(58, 27, 11, 4.2, (236, 106, 36), (120, 40, 10), ang)
    for (x, y, u, v) in body:
        if (u > 2 and v < 0) or (-4 < u < 0 and v > 1):
            c.px(x, y, (248, 244, 236))
    tail = [(66.5, 21.5), (75, 15), (73, 22), (77, 25)]
    c.poly(tail, (230, 92, 30))
    c.poly([(54, 30), (50, 36), (57, 32)], (230, 92, 30))
    c.px(50, 33, (20, 20, 20))
    for (dx, dy, r) in ((40, 38, 1.6), (36, 33, 1.2), (44, 33, 1.0), (33, 39, 1.0), (47, 39, 1.3), (39, 29, 0.9)):
        c.ell(dx, dy, r, r, (250, 250, 246))
    return c


def sushi_boat():
    rng = random.Random(6)
    c = Canvas(3 * BLOCK, 2 * BLOCK, (88, 34, 30))
    for y in range(0, c.h, 8):
        for x in range(0, c.w, 8):
            if (x // 8 + y // 8) % 2 == 0:
                c.rect(x, y, x + 8, y + 8, (98, 40, 34))
    c.ell(96, 104, 86, 10, (54, 20, 18))
    hull = [(10, 56), (24, 52), (172, 52), (184, 46), (182, 60), (168, 96), (34, 98), (16, 76)]
    c.poly(hull, (120, 76, 40))
    c.poly([(14, 58), (24, 55), (172, 55), (180, 50), (178, 60), (166, 92), (36, 94), (19, 75)], (178, 122, 68))
    for y in (66, 76, 86):
        c.rect(26, y, 170, y + 1, (140, 92, 48))
    c.rect(24, 52, 174, 56, (214, 164, 100))
    c.rect(24, 52, 174, 53, (236, 196, 136))
    c.poly([(172, 52), (184, 46), (188, 47), (176, 55)], (214, 164, 100))
    c.rect(150, 18, 152, 52, (214, 164, 100))
    c.rect(150, 18, 151, 52, (236, 196, 136))
    c.poly([(152, 20), (172, 30), (152, 40)], (238, 230, 214))
    c.ell(161, 30, 3, 3, (204, 52, 44))
    c.ell(60, 48, 22, 7, (240, 238, 232))
    c.speckle(c.ell(60, 47, 20, 5, (248, 248, 244)), [(222, 222, 216)], 0.25, rng)
    for i, a in enumerate((-0.9, -0.5, -0.1)):
        c.oell(36 + i * 6, 42 - i, 7, 3, LEAF, dark(LEAF, 0.4), a)
    for i in range(6):
        salmon_slab(c, 48 + i * 7, 40 - (i % 2) * 2, rx=8, ry=4, ang=-0.7 + i * 0.12)
    for i in range(4):
        tuna_slab(c, 90 + i * 8, 42 - (i % 2) * 2, rx=8, ry=4, ang=-0.4 + i * 0.15)
    for i in range(3):
        c.oell(124 + i * 6, 41, 6, 3.5, (244, 226, 222), (180, 150, 146), -0.3 + i * 0.2)
    lem = c.oell(142, 46, 6, 6, (246, 222, 80), (190, 150, 30))
    for (x, y, u, v) in lem:
        if abs(u) < 0.6 or abs(v) < 0.6:
            c.px(x, y, (255, 246, 190))
    wasabi(c, 80, 49)
    rice(c, 116, 112, rx=14, ry=5, rng=rng); salmon_slab(c, 116, 107, rx=15, ry=4.5)
    rice(c, 152, 112, rx=14, ry=5, rng=rng); tuna_slab(c, 152, 107, rx=15, ry=4.5)
    c.line(20, 118, 80, 104, (186, 128, 70), 2)
    c.line(22, 121, 82, 107, (166, 112, 60), 2)
    return c


def soy_chopsticks():
    c = Canvas(BLOCK, BLOCK, (78, 50, 34))
    for y in range(0, c.h, 5):
        for x in range(0, c.w):
            if int(x / 7 + y * 0.9) % 6 == 0:
                c.px(x, y, (64, 40, 26))
    c.ell(26, 38, 16, 13, (54, 34, 22))
    c.oell(25, 36, 15, 12, (238, 236, 230), (150, 146, 140))
    soy = c.ell(25, 37, 11, 8.5, (66, 34, 18))
    for (x, y, u, v) in soy:
        if -6 < u < -1 and -5 < v < -2:
            c.px(x, y, (150, 96, 60))
    c.line(36, 8, 58, 50, (196, 140, 80), 2)
    c.line(41, 7, 61, 47, (178, 122, 66), 2)
    c.rect(50, 50, 62, 55, (62, 96, 156))
    c.rect(50, 50, 62, 51, (110, 144, 200))
    ginger(c, 14, 14)
    return c


# ---------------------------------------------------------------------------------- kitchen set

def harvest_shelf():
    rng = random.Random(7)
    c = Canvas(3 * BLOCK, BLOCK, (226, 210, 180))
    for _ in range(260):
        c.px(rng.randrange(c.w), rng.randrange(c.h), (214, 196, 164))
    c.rect(6, 47, 186, 52, (150, 98, 50))
    c.rect(6, 47, 186, 48, (186, 132, 76))
    c.rect(6, 52, 186, 53, (96, 60, 30))
    for bx in (20, 170):
        c.poly([(bx, 53), (bx + 6, 53), (bx + 1, 60)], (96, 60, 30))

    def jar(x, w, h, fill, lid, pattern=None):
        top = 47 - h
        c.rect(x - 1, top - 1, x + w + 1, 47, (150, 160, 166))
        c.rect(x, top, x + w, 47, (214, 230, 236))
        c.rect(x + 1, top + 3, x + w - 1, 47, fill)
        if pattern:
            pattern(x + 1, top + 3, x + w - 1, 47)
        c.rect(x + 1, top + 3, x + 3, 47, light(fill, 0.25))
        c.rect(x - 1, top - 4, x + w + 1, top, lid)
        c.rect(x - 1, top - 4, x + w + 1, top - 3, light(lid, 0.3))

    def dots(col):
        def f(x0, y0, x1, y1):
            for y in range(y0, y1, 2):
                for x in range(x0 + (y % 4) // 2, x1, 2):
                    c.px(x, y, col)
        return f
    jar(12, 18, 24, (200, 40, 32), (60, 120, 40), dots((240, 100, 70)))
    jar(36, 16, 20, (240, 200, 60), (180, 60, 40), dots((255, 232, 120)))
    jar(58, 14, 26, (244, 242, 232), (90, 70, 50), dots((212, 208, 196)))
    c.poly([(80, 47), (82, 26), (90, 22), (100, 22), (108, 26), (110, 47)], (176, 146, 96))
    c.rect(86, 22, 104, 25, (150, 120, 76))
    for y in range(28, 46, 4):
        c.rect(84, y, 106, y + 1, (156, 126, 80))
    c.ell(95, 20, 6, 3, (92, 56, 32))
    for i in range(6):
        c.ell(91 + i * 2, 19 - (i % 2), 1.6, 1.2, (60, 36, 20))
    c.rect(116, 36, 150, 47, (166, 120, 60))
    for x in range(116, 150, 4):
        c.rect(x, 36, x + 2, 47, (142, 98, 46))
    for y in range(38, 47, 3):
        c.rect(116, y, 150, y + 1, (186, 140, 80))
    for i, (tx, ty) in enumerate([(122, 33), (130, 32), (138, 33), (145, 34), (126, 28), (135, 27)]):
        tomato(c, tx, ty, r=4.6)
    c.rect(158, 34, 178, 47, (196, 96, 56))
    c.rect(156, 32, 180, 35, (172, 80, 44))
    lettuce(c, 168, 26, r=9)
    return c


def ristra_garlic():
    c = Canvas(2 * BLOCK, BLOCK, (232, 222, 206))
    for row, y in enumerate(range(0, c.h, 6)):
        c.rect(0, y, c.w, y + 1, (206, 194, 176))
        for x in range((row % 2) * 7, c.w, 14):
            c.rect(x, y, x + 1, y + 6, (206, 194, 176))
    for nx in (30, 64, 98):
        c.rect(nx - 1, 6, nx + 2, 9, (70, 60, 56))
        c.line(nx, 8, nx, 56, (150, 120, 70))
    for i in range(8):
        y = 12 + i * 5.6
        chili(c, 26 + (i % 2) * 4, y, length=8, ang=1.2 if i % 2 == 0 else 1.9)
    for i in range(6):
        y = 14 + i * 7
        for (x, yy, u, v) in c.oell(64 + (2 if i % 2 else -2), y, 5, 4.4, (240, 234, 220), (170, 160, 140)):
            if int(u + 9) % 3 == 0:
                c.px(x, yy, (214, 204, 188))
        c.line(64 + (2 if i % 2 else -2), y - 4, 64, y - 7, (200, 180, 140))
    for i in range(6):
        y = 15 + i * 6.5
        for dx in (-3, 3):
            for (x, yy, u, v) in c.oell(98 + dx, y + (dx > 0) * 2, 3.6, 4.6, (150, 196, 92), (76, 120, 44)):
                if int(v + 9) % 2 == 0:
                    c.px(x, yy, (124, 172, 72))
    return c


def copper_pot():
    c = Canvas(2 * BLOCK, BLOCK, (236, 240, 244))
    for y in range(0, 46, 8):
        c.rect(0, y, c.w, y + 1, (176, 196, 214))
    for x in range(0, c.w, 8):
        c.rect(x, 0, x + 1, 46, (176, 196, 214))
    for y in range(4, 44, 16):
        for x in range(4, c.w, 16):
            c.rect(x + 3, y + 3, x + 5, y + 5, (90, 130, 190))
    c.rect(0, 46, c.w, c.h, (46, 46, 52))
    c.rect(0, 46, c.w, 48, (90, 90, 100))
    c.ell(60, 52, 22, 4, (26, 26, 30))
    c.ell(60, 52, 16, 2.5, (230, 110, 40))
    body = [(36, 26), (84, 26), (82, 46), (38, 46)]
    c.poly([(35, 25), (85, 25), (83, 47), (37, 47)], (110, 50, 24))
    c.poly(body, (196, 104, 52))
    c.rect(40, 28, 44, 45, (236, 156, 100))
    c.rect(46, 28, 48, 45, (220, 136, 80))
    c.rect(33, 23, 87, 27, (150, 72, 34))
    c.rect(26, 29, 36, 32, (60, 40, 30)); c.rect(84, 29, 94, 32, (60, 40, 30))
    c.ell(60, 23, 22, 3, (176, 88, 42))
    c.rect(58, 17, 63, 21, (60, 40, 30))
    for sx, h in ((50, 12), (60, 15), (70, 11)):
        steam(c, sx, 16, h, (196, 204, 212))
    c.rect(104, 6, 106, 40, (150, 104, 60))
    c.ell(105, 42, 5, 4, (150, 104, 60))
    c.rect(102, 4, 108, 7, (70, 60, 56))
    c.rect(10, 8, 22, 9, (70, 60, 56))
    c.line(16, 9, 16, 26, (120, 80, 50))
    c.oell(16, 32, 7, 6, (60, 60, 66), (30, 30, 34))
    return c


def rice_terraces():
    c = Canvas(3 * BLOCK, BLOCK, (150, 190, 220))
    c.vgrad(0, 0, c.w, 30, [(118, 168, 214), (196, 196, 206), (252, 196, 140)])
    c.ell(150, 26, 9, 9, (255, 236, 170))
    for x in range(c.w):
        y = 22 + 5 * math.sin(x / 23.0) + 3 * math.sin(x / 7.0)
        c.rect(x, y, x + 1, 32, (120, 116, 160))
    greens = [(96, 160, 62), (128, 188, 74), (84, 146, 54), (140, 196, 86), (104, 170, 64)]
    for band in range(6):
        base = 28 + band * 6
        col = greens[band % len(greens)]
        for x in range(c.w):
            y = base + 2.5 * math.sin(x / 15.0 + band * 0.9)
            c.rect(x, y, x + 1, c.h, col)
            c.px(x, y, light(col, 0.35))
            if band < 4 and x % 11 < 6:
                c.px(x, y + 2, (252, 214, 160))
    c.rect(36, 34, 52, 41, (150, 100, 60))
    c.poly([(33, 35), (44, 28), (55, 35)], (90, 84, 90))
    c.rect(42, 37, 46, 41, (60, 40, 26))
    rng = random.Random(9)
    for _ in range(70):
        x = rng.randrange(6, c.w - 6)
        y = rng.randrange(52, 59)
        c.line(x, y, x + rng.choice((-1, 0, 1)), y - 4, (70, 130, 44))
    return c


def tomato_basket():
    c = Canvas(BLOCK, BLOCK, (240, 236, 230))
    for y in range(0, c.h, 8):
        for x in range(0, c.w, 8):
            if (x // 8) % 2 == 0 or (y // 8) % 2 == 0:
                c.rect(x, y, x + 8, y + 8, (226, 120, 112) if (x // 8 + y // 8) % 2 else (240, 168, 160))
    c.ell(32, 54, 24, 5, (150, 80, 74))
    for (tx, ty) in [(20, 30), (30, 27), (40, 29), (46, 34), (16, 36), (25, 36), (35, 35), (28, 20), (38, 21)]:
        tomato(c, tx, ty, r=6)
    c.poly([(8, 36), (56, 36), (50, 56), (14, 56)], (176, 128, 64))
    for y in range(38, 56, 4):
        c.rect(10, y, 54, y + 2, (150, 104, 48))
    for x in range(12, 54, 6):
        c.line(x, 37, x + 2, 55, (196, 150, 84))
    c.rect(7, 35, 57, 38, (196, 150, 84))
    c.line(12, 36, 22, 10, (150, 104, 48), 2)
    c.line(52, 36, 42, 10, (150, 104, 48), 2)
    c.line(22, 10, 42, 10, (150, 104, 48), 2)
    return c


def market_crate():
    rng = random.Random(11)
    c = Canvas(2 * BLOCK, 2 * BLOCK, (200, 174, 126))
    for _ in range(900):
        c.px(rng.randrange(c.w), rng.randrange(c.h), rng.choice([(186, 160, 112), (212, 188, 140)]))
    lettuce(c, 34, 66, r=16)
    lettuce(c, 58, 60, r=14)
    for i, a in enumerate((-0.5, -0.2, 0.15)):
        corn_cob(c, 80 + i * 9, 58, w=9, h=26, ang=a)
    for (tx, ty) in [(30, 80), (42, 78), (54, 80), (66, 78), (36, 72), (60, 72), (48, 70)]:
        tomato(c, tx, ty, r=6)
    grapes(c, 106, 70)
    for i in range(4):
        chili(c, 72 + i * 6, 70 + (i % 2) * 2, length=12, ang=1.2 + i * 0.12)
    c.rect(14, 82, 114, 120, (166, 116, 62))
    for y in (82, 95, 108):
        c.rect(14, y, 114, y + 2, (196, 146, 86))
        c.rect(14, y + 11, 114, y + 13, (120, 80, 40))
    c.rect(14, 82, 18, 120, (120, 80, 40)); c.rect(110, 82, 114, 120, (120, 80, 40))
    c.rect(72, 92, 104, 108, (40, 46, 44))
    c.rect(72, 92, 104, 93, (120, 90, 50))
    c.text(74, 97, "FRESH", (238, 238, 230))
    c.line(76, 92, 82, 84, (90, 70, 40)); c.line(100, 92, 94, 84, (90, 70, 40))
    return c


# ------------------------------------------------------------------- minecraft sushi bar helpers

SPRUCE = [(104, 78, 47), (94, 70, 42)]
CHERRY = (228, 170, 160)


def planks(c, x0, y0, x1, y1, cols, seam, row=8, seed=0):
    """Minecraft-style planks: rows of boards with staggered end seams."""
    rng = random.Random(seed)
    for i, y in enumerate(range(y0, y1, row)):
        c.rect(x0, y, x1, min(y + row, y1), cols[i % len(cols)])
        c.rect(x0, y, x1, y + 1, seam)
        off = rng.randrange(0, 24)
        for x in range(x0 + off, x1, 24):
            c.rect(x, y, x + 1, min(y + row, y1), seam)


def stone_bricks(c, x0, y0, x1, y1, seed=0):
    rng = random.Random(seed)
    c.rect(x0, y0, x1, y1, (122, 122, 122))
    for i, y in enumerate(range(y0, y1, 8)):
        c.rect(x0, y, x1, y + 1, (84, 84, 86))
        for x in range(x0 + (i % 2) * 8, x1, 16):
            c.rect(x, y, x + 1, y + 8, (84, 84, 86))
    for _ in range((x1 - x0) * (y1 - y0) // 14):
        c.px(rng.randrange(x0, x1), rng.randrange(y0, y1), rng.choice([(110, 110, 112), (134, 134, 134)]))


def text_shadow(c, x, y, s, col, scale=1, shadow=(63, 63, 63)):
    c.text(x + scale, y + scale, s, shadow, scale)
    c.text(x, y, s, col, scale)


def text_width(s, scale=1):
    return (6 * len(s) - 1) * scale


def oak_sign(c, x0, y0, x1, y1, lines, col=(40, 30, 20)):
    c.rect(x0, y0, x1, y1, (112, 82, 48))
    c.rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, (184, 146, 92))
    for y in range(y0 + 4, y1 - 1, 4):
        c.rect(x0 + 1, y, x1 - 1, y + 1, (168, 132, 80))
    total = len(lines) * 9 - 2
    y = y0 + (y1 - y0 - total) // 2
    for line, scale in lines:
        c.text(x0 + (x1 - x0 - text_width(line, scale)) // 2, y, line, col, scale)
        y += 9 * scale


def minecart(c, cx, y_top):
    x0, x1 = cx - 16, cx + 16
    c.rect(x0, y_top, x1, y_top + 11, (62, 62, 70))
    c.rect(x0 + 1, y_top + 1, x1 - 1, y_top + 10, (124, 124, 132))
    c.rect(x0 + 1, y_top + 1, x1 - 1, y_top + 2, (176, 176, 184))
    for x in range(x0 + 4, x1 - 2, 6):
        c.rect(x, y_top + 3, x + 1, y_top + 9, (96, 96, 104))
    for wx in (cx - 10, cx + 10):
        c.ell(wx, y_top + 11.5, 3, 3, (36, 36, 40))
        c.px(wx, y_top + 11, (120, 120, 128))


def plate(c, cx, cy, rim):
    c.ell(cx, cy + 1, 13, 2.6, dark(rim, 0.4))
    c.ell(cx, cy, 13, 2.6, rim)
    c.ell(cx, cy - 0.4, 10, 1.8, (244, 242, 236))


def maki(c, cx, cy, r, center, rng):
    c.oell(cx, cy, r, r, (44, 54, 32), (24, 30, 18))
    c.speckle(c.ell(cx, cy, r - 1.6, r - 1.6, RICE), [RICE_SHADE], 0.2, rng)
    c.ell(cx, cy, max(1.2, r * 0.32), max(1.2, r * 0.32), center)


def fish_side(c, cx, cy, body, back, belly, length=9, height=3.6, face_right=True, stripes=None):
    d = 1 if face_right else -1
    px = c.oell(cx, cy, length, height, body, dark(body, 0.5))
    for (x, y, u, v) in px:
        if v < -height * 0.35:
            c.px(x, y, back)
        elif v > height * 0.45:
            c.px(x, y, belly)
        if stripes and any(abs(u - sx) < 1 for sx in stripes):
            c.px(x, y, (246, 244, 238))
    tx = cx - d * length
    c.poly([(tx, cy), (tx - d * 5, cy - 4), (tx - d * 5, cy + 4)], back)
    c.px(cx + d * (length - 3), cy - 1, (16, 16, 16))


def pufferfish(c, cx, cy, size=12):
    h = size
    for i in range(-h - 3, h + 4, 4):
        for (sx, sy, ex, ey) in ((cx + i, cy - h - 3, cx + i, cy - h), (cx + i, cy + h, cx + i, cy + h + 3),
                                 (cx - h - 3, cy + i, cx - h, cy + i), (cx + h, cy + i, cx + h + 3, cy + i)):
            if abs(i) <= h:
                c.line(sx, sy, ex, ey, (244, 242, 226))
    c.rect(cx - h - 1, cy - h + 1, cx + h + 1, cy + h - 1, (150, 110, 30))
    c.rect(cx - h + 1, cy - h - 1, cx + h - 1, cy + h + 1, (150, 110, 30))
    c.rect(cx - h, cy - h, cx + h, cy + h, (236, 200, 56))
    c.rect(cx - h, cy + h // 3, cx + h, cy + h, (214, 172, 44))
    c.rect(cx - h, cy - h, cx + h, cy - h + 2, (250, 226, 110))
    rng = random.Random(cx * 31 + cy)
    for _ in range(size):
        x, y = cx + rng.randrange(-h + 2, h - 2), cy + rng.randrange(-h + 2, h // 3)
        c.rect(x, y, x + 2, y + 2, (176, 132, 40))
    for ex in (cx - h // 2 - 2, cx + h // 2 - 1):
        c.rect(ex, cy - h // 3, ex + 4, cy - h // 3 + 4, (20, 20, 20))
        c.px(ex + 1, cy - h // 3 + 1, (250, 250, 250))
    c.rect(cx - 2, cy + 2, cx + 3, cy + 4, (120, 60, 30))
    c.poly([(cx - h - 1, cy), (cx - h - 6, cy - 4), (cx - h - 6, cy + 4)], (230, 140, 50))


def tokkuri(c, cx, base, h, body=(242, 240, 232), band=(54, 86, 160), glint=False):
    """A sake bottle: round belly, narrow neck, flared lip. Returns its pixels."""
    before = None
    if glint:
        r = int(h) + 2
        box = [(x, y) for y in range(int(base - h - 2), int(base) + 2) for x in range(int(cx - r), int(cx + r))]
        before = {(x, y): c.get(x, y) for (x, y) in box}
    br = h * 0.36
    px = c.oell(cx, base - br, br, br, body, (120, 118, 112))
    nh = h - br * 2
    c.rect(cx - h * 0.12 - 1, base - br * 2 - nh, cx + h * 0.12 + 2, base - br * 1.6, (120, 118, 112))
    c.rect(cx - h * 0.12, base - br * 2 - nh, cx + h * 0.12 + 1, base - br * 1.6, body)
    c.ell(cx, base - br * 2 - nh, h * 0.18, h * 0.06 + 0.8, body)
    for (x, y, u, v) in px:
        if abs(v) < br * 0.18:
            c.px(x, y, band)
        elif u < -br * 0.45 and v < 0:
            c.px(x, y, light(body, 0.5))
    if glint:
        for (x, y), was in before.items():
            col = c.get(x, y)
            if col is not None and col != was and (x + y) % 6 in (0, 1):
                c.px(x, y, mix(col, (200, 90, 255), 0.45))
    return px


def ochoko(c, cx, top, w=8):
    c.poly([(cx - w / 2 - 1, top - 1), (cx + w / 2 + 1, top - 1), (cx + w / 2 - 1, top + 6), (cx - w / 2 + 1, top + 6)], (120, 118, 112))
    c.poly([(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2 - 1.5, top + 5), (cx - w / 2 + 1.5, top + 5)], (242, 240, 232))
    c.rect(cx - w / 2 + 1, top, cx + w / 2, top + 1, (236, 224, 180))
    c.rect(cx - w / 2 + 1, top + 2, cx + w / 2 - 1, top + 3, (54, 86, 160))


def cherry_leaves(c, cx, cy, rx, ry, rng):
    for (x, y, u, v) in c.ell(cx, cy, rx, ry, (238, 160, 196)):
        roll = rng.random()
        if roll < 0.28:
            c.px(x, y, (250, 206, 226))
        elif roll < 0.5:
            c.px(x, y, (214, 128, 170))
        elif roll < 0.56:
            c.px(x, y, (190, 104, 150))


def slot_icon(name, name_col, draw_item, count=None):
    """A Minecraft inventory slot with a tooltip over it: the item, its name, its stack."""
    c = Canvas(BLOCK, BLOCK, (198, 198, 198))
    c.rect(4, 4, 60, 60, (198, 198, 198))
    c.rect(4, 4, 60, 5, (255, 255, 255)); c.rect(4, 4, 5, 60, (255, 255, 255))
    c.rect(4, 59, 60, 60, (85, 85, 85)); c.rect(59, 4, 60, 60, (85, 85, 85))
    w = text_width(name) + 6
    x0 = (BLOCK - w) // 2
    c.rect(x0, 6, x0 + w, 19, (16, 2, 16))
    c.rect(x0 + 1, 7, x0 + w - 1, 8, (80, 0, 200)); c.rect(x0 + 1, 17, x0 + w - 1, 18, (40, 0, 120))
    c.rect(x0 + 1, 7, x0 + 2, 18, (68, 0, 176)); c.rect(x0 + w - 2, 7, x0 + w - 1, 18, (68, 0, 176))
    text_shadow(c, x0 + 3, 9, name, name_col, shadow=(40, 20, 40))
    c.rect(14, 22, 50, 58, (55, 55, 55))
    c.rect(16, 24, 50, 58, (255, 255, 255))
    c.rect(16, 24, 48, 56, (139, 139, 139))
    draw_item(c, 32, 41)
    if count:
        text_shadow(c, 49 - text_width(count), 49, count, (255, 255, 255))
    return c


# --------------------------------------------------------------------- minecraft sushi bar set

def minecart_kaiten():
    rng = random.Random(21)
    c = Canvas(3 * BLOCK, BLOCK, SPRUCE[0])
    planks(c, 0, 0, c.w, c.h, SPRUCE, (70, 52, 30), seed=21)
    for lx in (48, 96, 144):
        c.line(lx, 4, lx, 7, (30, 24, 20))
        lantern(c, lx, 15, rx=5, ry=6, glow=True)
    c.rect(4, 46, c.w - 4, 48, (150, 150, 156))
    c.rect(4, 46, c.w - 4, 47, (196, 196, 202))
    for x in range(6, c.w - 6, 8):
        c.rect(x, 48, x + 5, 51, (112, 80, 46))
    for cx, rim in ((36, (200, 56, 56)), (96, (60, 96, 180)), (156, (214, 170, 50))):
        minecart(c, cx, 33)
        plate(c, cx, 31, rim)
    rice(c, 36, 29, rx=9, ry=3.5, rng=rng); salmon_slab(c, 36, 25.5, rx=10, ry=3)
    for mx in (87, 96, 105):
        maki(c, mx, 26, 4.2, SALMON if mx != 96 else TUNA, rng)
    rice(c, 150, 29, rx=5, ry=3, rng=rng); tuna_slab(c, 150, 26, rx=6, ry=2.6)
    rice(c, 163, 29, rx=5, ry=3, rng=rng); tamago_slab(c, 163, 26, w=11, h=4)
    c.rect(0, 51, c.w, c.h, CHERRY)
    c.rect(0, 51, c.w, 53, (242, 198, 190))
    c.rect(0, 53, c.w, 54, (176, 120, 116))
    for x in range(10, c.w, 22):
        c.rect(x, 54, x + 1, c.h, (196, 136, 130))
    return c


def sake_cellar():
    c = Canvas(3 * BLOCK, BLOCK, (122, 122, 122))
    stone_bricks(c, 0, 0, c.w, c.h, seed=22)
    c.rect(4, 40, c.w - 4, 44, (66, 44, 26))
    c.rect(4, 40, c.w - 4, 41, (96, 66, 40))
    for lx in (16, 176):
        c.rect(lx, 44, lx + 4, 60, (66, 44, 26))
    rungs = [("RAW", (242, 240, 232), (54, 86, 160)), ("AGED", (226, 196, 130), (150, 96, 40)),
             ("OLD", (120, 72, 40), (220, 180, 70))]
    for (label, body, band), cx in zip(rungs, (40, 96, 152)):
        x0, y0 = cx - 14, 12
        c.rect(x0, y0, x0 + 28, y0 + 28, (86, 58, 32))
        c.rect(x0 + 2, y0 + 2, x0 + 26, y0 + 26, (164, 118, 66))
        for y in range(y0 + 6, y0 + 26, 5):
            c.rect(x0 + 2, y, x0 + 26, y + 1, (140, 98, 54))
        c.rect(x0 + 6, y0 + 6, x0 + 22, y0 + 22, (112, 76, 40))
        c.rect(x0 + 8, y0 + 8, x0 + 20, y0 + 20, (150, 106, 58))
        c.rect(x0 + 12, y0 + 12, x0 + 16, y0 + 16, (56, 36, 20))
        tokkuri(c, cx, 12, 9, body=body, band=band)
        oak_sign(c, cx - 15, 46, cx + 15, 58, [(label, 1)])
    return c


def villager_itamae():
    rng = random.Random(23)
    c = Canvas(3 * BLOCK, BLOCK, (232, 214, 172))
    for x in range(10, c.w, 26):
        c.rect(x, 0, x + 3, c.h, (168, 184, 94))
        for y in range(6, c.h, 11):
            c.rect(x - 1, y, x + 4, y + 1, (130, 150, 70))
    c.rect(4, 4, c.w - 4, 10, INDIGO)
    for x in range(20, c.w - 10, 38):
        c.ell(x, 7, 2.5, 2.5, (240, 236, 220))
    skin, shade = (178, 128, 100), (150, 104, 80)
    c.rect(80, 32, 112, 46, (236, 236, 230))
    c.rect(80, 32, 84, 46, (214, 214, 206)); c.rect(108, 32, 112, 46, (214, 214, 206))
    c.rect(78, 38, 114, 44, (218, 218, 210))
    c.rect(78, 38, 114, 39, (244, 244, 240))
    c.rect(82, 39, 86, 43, skin); c.rect(106, 39, 110, 43, skin)
    c.rect(84, 11, 108, 33, skin)
    c.rect(104, 11, 108, 33, shade)
    c.rect(84, 14, 108, 18, (244, 244, 240))
    c.rect(94, 14, 98, 18, (204, 40, 40))
    c.rect(86, 20, 106, 22, (70, 46, 30))
    for ex in (87, 100):
        c.rect(ex, 22, ex + 5, 25, (244, 244, 240))
        c.rect(ex + 2, 22, ex + 4, 25, (54, 150, 70))
    c.rect(93, 22, 99, 32, (160, 108, 82))
    c.rect(93, 30, 99, 32, (136, 90, 68))
    def case(x0, x1, fishes):
        c.rect(x0, 26, x1, 45, (78, 80, 92))
        c.rect(x0 + 1, 27, x1 - 1, 44, (200, 232, 238))
        c.rect(x0 + 1, 40, x1 - 1, 44, (236, 246, 250))
        c.speckle([(x, y) for x in range(x0 + 1, x1 - 1) for y in range(40, 44)], [(206, 226, 236)], 0.3, rng)
        for draw in fishes:
            draw()
        for d in range(0, x1 - x0, 14):
            c.line(x0 + 3 + d, 38, x0 + 9 + d, 29, (240, 250, 252))
        c.rect(x0, 26, x1, 27, (120, 124, 136))
    case(12, 74, [lambda: fish_side(c, 28, 35, (204, 72, 56), (150, 46, 40), (236, 140, 110)),
                  lambda: fish_side(c, 56, 35, (198, 172, 130), (150, 124, 88), (226, 210, 180), face_right=False)])
    case(118, 180, [lambda: fish_side(c, 134, 35, (240, 140, 40), (200, 100, 30), (250, 190, 120), length=8, stripes=(0, 4)),
                    lambda: pufferfish(c, 163, 34, size=5)])
    c.rect(0, 45, c.w, c.h, CHERRY)
    c.rect(0, 45, c.w, 47, (242, 198, 190))
    c.rect(0, 47, c.w, 48, (176, 120, 116))
    for x in range(14, c.w, 24):
        c.rect(x, 48, x + 1, c.h, (196, 136, 130))
    return c


def fugu_warning():
    rng = random.Random(24)
    c = Canvas(2 * BLOCK, BLOCK, (48, 94, 168))
    c.vgrad(0, 0, 66, c.h, [(70, 130, 200), (38, 80, 150), (24, 54, 110)])
    for _ in range(9):
        bx, by = rng.randrange(8, 60), rng.randrange(8, 58)
        c.oell(bx, by, 1.8, 1.8, (120, 170, 220), (200, 230, 250))
    pufferfish(c, 36, 33, size=12)
    planks(c, 64, 0, c.w, c.h, SPRUCE, (70, 52, 30), seed=24)
    c.rect(68, 10, 122, 54, (112, 82, 48))
    c.rect(69, 11, 121, 53, (184, 146, 92))
    for y in range(15, 53, 4):
        c.rect(69, y, 121, y + 1, (168, 132, 80))
    c.text(95 - text_width("FUGU", 2) // 2, 15, "FUGU", (170, 26, 26), 2)
    c.text(95 - text_width("CHEF") // 2, 34, "CHEF", (40, 30, 20))
    c.text(95 - text_width("ONLY") // 2, 43, "ONLY", (40, 30, 20))
    return c


def kelp_maki():
    rng = random.Random(25)
    c = Canvas(2 * BLOCK, BLOCK, SPRUCE[0])
    planks(c, 0, 0, c.w, 34, SPRUCE, (70, 52, 30), seed=25)
    c.rect(0, 34, c.w, c.h, (90, 60, 34))
    c.rect(6, 36, 122, 58, (120, 84, 46))
    c.rect(7, 36, 121, 57, (214, 176, 120))
    for y in range(39, 57, 4):
        c.rect(7, y, 121, y + 1, (198, 160, 104))
    c.rect(14, 16, 40, 42, (20, 26, 14))
    c.rect(15, 17, 39, 41, (44, 54, 32))
    for y in range(18, 41, 4):
        for x in range(15, 39):
            if int(2 * math.sin(x / 2.5 + y)) == 0:
                c.px(x, y, (78, 96, 52))
    c.speckle([(x, y) for x in range(15, 39) for y in range(17, 41)], [(30, 38, 22), (60, 74, 40)], 0.08, rng)
    c.rect(15, 17, 39, 18, (70, 86, 48))
    c.rect(54, 27, 102, 31, (204, 208, 214))
    c.rect(54, 27, 102, 28, (238, 240, 244))
    c.rect(54, 30, 102, 31, (150, 154, 160))
    c.poly([(54, 27), (48, 31), (54, 31)], (204, 208, 214))
    c.rect(102, 26, 118, 32, (60, 40, 30))
    for rx in (106, 112):
        c.px(rx, 28, (200, 200, 200)); c.px(rx, 29, (200, 200, 200))
    for mx, col in ((58, SALMON), (78, TUNA), (98, SALMON)):
        maki(c, mx, 45, 8, col, rng)
        c.ell(mx + 2.5, 44, 1.2, 1.2, (110, 180, 70))
    return c


def cherry_sake():
    rng = random.Random(26)
    c = Canvas(2 * BLOCK, BLOCK, (250, 214, 200))
    c.vgrad(0, 0, c.w, 46, [(252, 222, 206), (240, 180, 186), (176, 150, 196)])
    c.line(4, 9, 60, 13, (70, 44, 44), 2)
    c.line(60, 13, 124, 8, (70, 44, 44), 2)
    c.line(44, 12, 54, 22, (70, 44, 44))
    c.line(92, 10, 98, 19, (70, 44, 44))
    for (lx, ly, rx_, ry_) in ((18, 12, 10, 7), (40, 9, 9, 6), (56, 20, 7, 5), (76, 13, 10, 7), (98, 18, 8, 6), (114, 9, 9, 6)):
        cherry_leaves(c, lx, ly, rx_, ry_, rng)
    for _ in range(26):
        x, y = rng.randrange(6, 122), rng.randrange(22, 44)
        c.px(x, y, (246, 176, 206)); c.px(x + 1, y, (226, 140, 180))
    c.rect(0, 46, c.w, c.h, CHERRY)
    c.rect(0, 46, c.w, 48, (242, 198, 190))
    c.rect(0, 48, c.w, 49, (176, 120, 116))
    for x in range(12, c.w, 22):
        c.rect(x, 49, x + 1, c.h, (196, 136, 130))
    c.rect(24, 42, 96, 47, (150, 30, 30))
    c.rect(26, 41, 94, 44, (30, 24, 24))
    tokkuri(c, 44, 42, 24)
    ochoko(c, 66, 35); ochoko(c, 82, 35)
    tie = (113, 47)
    for i, tx in enumerate(range(103, 124, 3)):
        ty = 24 + abs(tx - 113) // 2 + (i % 2) * 2
        c.line(113 + (tx - 113) * 0.25, 58, tie[0], tie[1], (176, 146, 70))
        c.line(tie[0], tie[1], tx, ty, (196, 164, 80))
        lean = 1 if tx >= 113 else -1
        for g in range(5):
            gx, gy = tx + lean * (g // 2), ty + g * 2
            c.px(gx, gy, (240, 214, 124)); c.px(gx + lean, gy + 1, (214, 184, 90))
    c.rect(109, 45, 118, 49, (150, 104, 48))
    c.rect(109, 45, 118, 46, (186, 138, 70))
    return c


def sushi_plate(rim, pieces, garnish):
    rng = random.Random(sum(rim))
    c = Canvas(BLOCK, BLOCK, CHERRY)
    planks(c, 0, 0, c.w, c.h, [CHERRY, (220, 160, 150)], (186, 128, 122), row=8, seed=sum(rim))
    c.ell(32, 38, 27, 17, dark(CHERRY, 0.35))
    c.oell(32, 35, 26, 16, rim, dark(rim, 0.4))
    c.ell(32, 35, 21, 12.5, (246, 244, 238))
    c.ell(32, 37, 19, 10, (232, 230, 222))
    for (x, top) in pieces:
        rice(c, x, 39, rx=9, ry=4, rng=rng)
        top(c, x, 35)
    garnish(c)
    return c


def salmon_plate():
    return sushi_plate((200, 56, 56),
                       [(20, lambda c, x, y: salmon_slab(c, x, y, rx=9.5, ry=3.4)),
                        (44, lambda c, x, y: salmon_slab(c, x, y, rx=9.5, ry=3.4))],
                       lambda c: (wasabi(c, 32, 46), ginger(c, 47, 46)))


def tuna_tamago_plate():
    return sushi_plate((60, 96, 180),
                       [(20, lambda c, x, y: tuna_slab(c, x, y, rx=9.5, ry=3.4)),
                        (44, lambda c, x, y: tamago_slab(c, x, y, w=19, h=7))],
                       lambda c: wasabi(c, 32, 46))


def nigiri_slot():
    rng = random.Random(27)
    def item(c, x, y):
        rice(c, x, y + 5, rx=12, ry=5, rng=rng)
        salmon_slab(c, x, y - 1, rx=13, ry=4.5)
    return slot_icon("NIGIRI", (255, 255, 255), item, "64")


def onigiri_slot():
    rng = random.Random(28)
    def item(c, x, y):
        c.poly([(x - 13, y + 11), (x, y - 12), (x + 13, y + 11)], (150, 148, 138))
        c.poly([(x - 11, y + 10), (x, y - 10), (x + 11, y + 10)], RICE)
        c.speckle([(px_, py_) for px_ in range(x - 11, x + 12) for py_ in range(y - 10, y + 10)
                   if c.get(px_, py_) == RICE], [RICE_SHADE], 0.18, rng)
        c.rect(x - 6, y + 3, x + 7, y + 11, NORI)
        c.rect(x - 5, y + 4, x - 3, y + 10, (44, 62, 48))
        c.ell(x, y - 3, 2.4, 2.4, (200, 40, 70))
    return slot_icon("ONIGIRI", (255, 255, 85), item, "16")


def old_sake_slot():
    def item(c, x, y):
        tokkuri(c, x, y + 13, 25, body=(124, 76, 42), band=(220, 180, 70), glint=True)
    return slot_icon("OLD SAKE", (255, 85, 255), item)


# ------------------------------------------------------------------ dining plates (top-down)

WALNUT = [(92, 60, 40), (84, 54, 36)]


def table(seed):
    c = Canvas(BLOCK, BLOCK, WALNUT[0])
    planks(c, 0, 0, BLOCK, BLOCK, WALNUT, (62, 40, 26), row=8, seed=seed)
    return c


def shade(c, cx, cy, rx, ry, t=0.35, ang=0.0):
    """Darkens whatever is under an ellipse: a soft contact shadow, offset down-right."""
    r = max(rx, ry) + 1
    ca, sa = math.cos(ang), math.sin(ang)
    for y in range(int(cy - r), int(cy + r) + 2):
        for x in range(int(cx - r), int(cx + r) + 2):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1.0 and c.get(x, y) is not None:
                c.px(x, y, dark(c.get(x, y), t))


def nigiri_top(c, cx, cy, kind, rng, ang=0.0):
    px = c.oell(cx, cy, 6.4, 4.2, RICE, (150, 148, 138), ang)
    c.speckle(px, [RICE_SHADE], 0.2, rng)
    if kind == "salmon":
        salmon_slab(c, cx, cy - 0.5, rx=6.2, ry=3.2, ang=ang)
    elif kind == "tuna":
        tuna_slab(c, cx, cy - 0.5, rx=6.2, ry=3.2, ang=ang)
    else:
        c.rect(cx - 6, cy - 4, cx + 7, cy + 3, (186, 136, 36))
        c.rect(cx - 5, cy - 3, cx + 6, cy + 2, TAMAGO)
        c.rect(cx - 5, cy - 3, cx + 6, cy - 2, light(TAMAGO, 0.3))
        c.rect(cx - 1, cy - 4, cx + 2, cy + 4, NORI)


def grains(c, pts):
    for (x, y) in pts:
        c.px(x, y, RICE)
        c.px(x + 1, y, RICE_SHADE)


def chopsticks_top(c, x0, y0, x1, y1, gap=3, tip_close=1):
    """A pair seen from above: lacquered backs, natural tips, a shadow under them."""
    for off in (0, gap):
        c.line(x0 + 1, y0 + off + 2, x1 + 1, y1 + off * tip_close / max(1, gap) + 2, dark((92, 60, 40), 0.35), 2)
    for off, col in ((0, (150, 44, 34)), (gap, (128, 36, 28))):
        ex, ey = x1, y1 + off * tip_close / max(1, gap)
        mx, my = x0 + (ex - x0) * 0.62, y0 + off + (ey - y0 - off) * 0.62
        c.line(x0, y0 + off, mx, my, col, 2)
        c.line(mx, my, ex, ey, (206, 156, 96), 2)


def soy_dish(c, cx, cy, r=6, level=1.0, wasabi_swirl=True):
    shade(c, cx + 1.5, cy + 2, r + 1, r + 1)
    c.oell(cx, cy, r, r, (240, 238, 232), (150, 146, 140))
    soy = c.ell(cx, cy, (r - 1.6) * level, (r - 1.6) * level, (66, 34, 18))
    for (x, y, u, v) in soy:
        if -2.5 < u < -0.5 and -2.5 < v < -0.8:
            c.px(x, y, (130, 82, 50))
    if wasabi_swirl:
        for i in range(6):
            a = i * 0.7
            c.px(cx + math.cos(a) * (1 + i * 0.35), cy + math.sin(a) * (1 + i * 0.35), (128, 160, 60))


def ochoko_top(c, cx, cy, r=5, full=True):
    shade(c, cx + 1.5, cy + 2, r + 1, r + 1)
    c.oell(cx, cy, r, r, (242, 240, 232), (150, 146, 140))
    c.ell(cx, cy, r - 1.5, r - 1.5, (54, 86, 160))
    c.ell(cx, cy, r - 2.5, r - 2.5, (242, 240, 232))
    if r > 4:
        c.ell(cx, cy, r - 3.5, r - 3.5, (54, 86, 160))
    if full:
        c.ell(cx, cy, r - 1.6, r - 1.6, (236, 222, 170))
        c.px(cx - 1, cy - 1, (255, 248, 220))


def tea_cup(c, cx, cy, r=6):
    shade(c, cx + 1.5, cy + 2, r + 1, r + 1)
    c.oell(cx, cy, r, r, (150, 120, 90), (90, 70, 50))
    c.ell(cx, cy, r - 1.4, r - 1.4, (150, 176, 72))
    c.px(cx - 1, cy - 1, (196, 214, 120))


def miso_bowl(c, cx, cy, r=8):
    shade(c, cx + 1.5, cy + 2, r + 1, r + 1)
    c.oell(cx, cy, r, r, (40, 24, 22), (20, 12, 10))
    soup = c.ell(cx, cy, r - 1.5, r - 1.5, (168, 112, 56))
    for (x, y, u, v) in soup:
        if int(u * 0.7 + v) % 4 == 0:
            c.px(x, y, (186, 132, 72))
    for (dx, dy) in ((-2, -1), (2, 1), (0, 3)):
        c.rect(cx + dx, cy + dy, cx + dx + 2, cy + dy + 2, (244, 240, 226))
    for (dx, dy) in ((-3, 2), (3, -2), (1, -3)):
        c.px(cx + dx, cy + dy, (90, 160, 60))


def napkin(c, x0, y0):
    shade(c, x0 + 7, y0 + 6, 8, 6)
    c.poly([(x0, y0 + 3), (x0 + 6, y0), (x0 + 13, y0 + 2), (x0 + 15, y0 + 8), (x0 + 9, y0 + 12), (x0 + 2, y0 + 10)], (236, 232, 222))
    c.line(x0 + 3, y0 + 4, x0 + 10, y0 + 8, (196, 192, 182))
    c.line(x0 + 7, y0 + 2, x0 + 9, y0 + 9, (196, 192, 182))


def round_plate(c, cx, cy, r, rim):
    shade(c, cx + 2, cy + 2.5, r + 1, r + 1)
    c.oell(cx, cy, r, r, rim, dark(rim, 0.4))
    c.ell(cx, cy, r - 2.2, r - 2.2, (246, 244, 238))
    c.ell(cx, cy + 0.6, r - 4.5, r - 4.5, (236, 234, 226))


def dine_nigiri_board():
    rng = random.Random(41)
    c = table(41)
    shade(c, 28, 28, 18, 16, ang=0)
    c.rect(9, 11, 43, 41, (120, 84, 46))
    c.rect(10, 12, 42, 39, (214, 172, 112))
    c.rect(10, 12, 42, 13, (234, 196, 138))
    for y in range(16, 39, 5):
        c.rect(10, y, 42, y + 1, (200, 158, 100))
    nigiri_top(c, 18, 20, "salmon", rng, 0.1)
    nigiri_top(c, 34, 31, "tuna", rng, -0.08)
    nigiri_top(c, 18, 31, "tamago", rng)
    grains(c, [(31, 18), (35, 21), (33, 23), (37, 19)])
    c.px(36, 24, (90, 50, 30)); c.px(37, 24, (110, 66, 40))
    soy_dish(c, 52, 18, r=6, level=0.85)
    ginger(c, 52, 33)
    c.rect(43, 47, 50, 55, (60, 96, 156)); c.rect(43, 47, 50, 48, (110, 144, 200))
    chopsticks_top(c, 10, 50, 57, 46, gap=3, tip_close=3)
    return c


def dine_maki_ring():
    rng = random.Random(42)
    c = table(42)
    round_plate(c, 28, 30, 19, (60, 96, 180))
    for i in range(8):
        if i in (1, 2):
            continue
        a = math.radians(i * 45 - 90)
        maki(c, 28 + math.cos(a) * 11, 30 + math.sin(a) * 11, 4.2, SALMON if i % 2 else TUNA, rng)
    grains(c, [(37, 20), (40, 24), (39, 28)])
    ginger(c, 27, 30); wasabi(c, 31, 34)
    soy_dish(c, 53, 13, r=6, level=0.7)
    shade(c, 44, 44, 5, 5, 0.3)
    maki(c, 42, 41, 4.4, SALMON, rng)
    chopsticks_top(c, 60, 60, 43, 39, gap=4, tip_close=1)
    return c


def dine_chirashi_miso():
    rng = random.Random(43)
    c = table(43)
    shade(c, 38, 40, 17, 17)
    c.oell(36, 38, 16, 16, (40, 22, 22), (20, 10, 10))
    c.ell(36, 38, 14.5, 14.5, (150, 28, 28))
    rice_px = c.ell(36, 38, 12.5, 12.5, RICE)
    c.speckle(rice_px, [RICE_SHADE], 0.22, rng)
    for (dx, dy, a) in ((-6, -5, 0.5), (-1, -8, -0.3), (5, -6, 0.9)):
        salmon_slab(c, 36 + dx, 38 + dy, rx=4, ry=2, ang=a)
    for (dx, dy) in ((-8, 1), (-3, 3)):
        c.rect(36 + dx, 38 + dy, 36 + dx + 4, 38 + dy + 3, TUNA)
    for (dx, dy) in ((1, -2), (-5, 6)):
        c.rect(36 + dx, 38 + dy, 36 + dx + 3, 38 + dy + 3, TAMAGO)
    for (dx, dy) in ((-1, 2), (-7, -1), (2, 4)):
        c.ell(36 + dx, 38 + dy, 1.2, 1.2, (250, 120, 40))
    c.ell(42, 44, 5, 4, RICE_SHADE)
    grains(c, [(43, 42), (40, 46), (44, 47), (52, 50), (25, 53)])
    miso_bowl(c, 14, 14, r=8)
    chopsticks_top(c, 33, 8, 59, 22, gap=5, tip_close=4)
    return c


def dine_sashimi_for_two():
    rng = random.Random(44)
    c = table(44)
    shade(c, 34, 30, 23, 14)
    c.oell(32, 27, 22, 13, (246, 244, 238), (150, 146, 140))
    c.ell(32, 27, 20, 11, (54, 86, 160))
    c.ell(32, 27, 19, 10, (246, 244, 238))
    px = c.ell(30, 28, 6, 4, (240, 240, 236))
    for (x, y, u, v) in px:
        if (x + y) % 2 == 0:
            c.px(x, y, (214, 214, 210))
    c.oell(27, 25, 4, 2.5, LEAF, dark(LEAF, 0.4), -0.6)
    for i in (0, 2, 3):
        salmon_slab(c, 18 + i * 3, 22 + i * 2, rx=5, ry=2.4, ang=-0.9)
    for i in (0, 2):
        tuna_slab(c, 40 + i * 4, 21 + i * 2, rx=5, ry=2.4, ang=0.8)
    grains(c, [(21, 30), (44, 32)])
    ochoko_top(c, 11, 50, r=5, full=False)
    ochoko_top(c, 24, 52, r=5, full=True)
    chopsticks_top(c, 34, 58, 59, 45, gap=3, tip_close=2)
    chopsticks_top(c, 8, 7, 38, 6, gap=3, tip_close=3)
    return c


def dine_bento():
    rng = random.Random(45)
    c = table(45)
    shade(c, 31, 31, 22, 18)
    c.rect(7, 11, 51, 47, (24, 20, 20))
    c.rect(9, 13, 49, 45, (168, 30, 30))
    c.rect(29, 13, 31, 45, (24, 20, 20)); c.rect(31, 28, 49, 30, (24, 20, 20))
    px = [(x, y) for x in range(10, 29) for y in range(14, 44)]
    c.rect(10, 14, 29, 44, RICE)
    c.speckle(px, [RICE_SHADE], 0.2, rng)
    c.poly([(11, 41), (18, 22), (25, 41)], (150, 148, 138))
    c.poly([(12, 40), (18, 24), (24, 40)], RICE)
    c.rect(14, 34, 23, 41, NORI)
    c.ell(18, 29, 1.6, 1.6, (200, 40, 70))
    for (bx, by, r) in ((22, 28, 2.6), (24, 31, 2.2)):
        c.ell(bx, by, r, r, RICE_SHADE)
    for y in (16, 20, 24):
        c.rect(33, y, 47, y + 3, TAMAGO)
        c.rect(33, y, 47, y + 1, light(TAMAGO, 0.3))
    for x in range(32, 49, 3):
        c.poly([(x, 30), (x + 1.5, 33), (x + 3, 30)], (60, 150, 60))
    for (tx, ty) in ((35, 37), (41, 39)):
        c.oell(tx, ty, 3, 2.4, (240, 214, 70), (180, 150, 30))
    ginger(c, 44, 41)
    tea_cup(c, 55, 18, r=4)
    chopsticks_top(c, 8, 52, 58, 50, gap=3, tip_close=3)
    return c


def dine_last_piece():
    rng = random.Random(46)
    c = table(46)
    round_plate(c, 30, 30, 18, (200, 56, 56))
    for i in range(4):
        x0, y0 = 20 + i * 4, 26 + (i % 2) * 6
        c.line(x0, y0, x0 + 6, y0 + 3, (96, 56, 32))
    grains(c, [(22, 22), (26, 36), (38, 38), (34, 22), (19, 32), (40, 28)])
    nigiri_top(c, 33, 29, "salmon", rng, -0.2)
    chopsticks_top(c, 51, 8, 57, 42, gap=4, tip_close=4)
    tokkuri_px = c.oell(14, 52, 7, 5, (242, 240, 232), (120, 118, 112), 0.25)
    for (x, y, u, v) in tokkuri_px:
        if abs(u) < 1:
            c.px(x, y, (54, 86, 160))
    c.rect(20, 53, 27, 56, (242, 240, 232))
    c.px(27, 55, (66, 34, 18)); c.px(28, 56, (66, 34, 18))
    napkin(c, 44, 46)
    return c


PIECES = [
    ("sushi_nigiri_trio_1x3.png", nigiri_trio),
    ("sushi_noren_curtain_1x3.png", noren_curtain),
    ("sushi_lantern_alley_1x3.png", lantern_alley),
    ("sushi_maki_platter_1x2.png", maki_platter),
    ("sushi_koi_wave_1x2.png", koi_wave),
    ("sushi_soy_chopsticks_1x1.png", soy_chopsticks),
    ("sushi_boat_2x3.png", sushi_boat),
    ("kitchen_harvest_shelf_1x3.png", harvest_shelf),
    ("kitchen_rice_terraces_1x3.png", rice_terraces),
    ("kitchen_ristra_garlic_hops_1x2.png", ristra_garlic),
    ("kitchen_copper_pot_1x2.png", copper_pot),
    ("kitchen_tomato_basket_1x1.png", tomato_basket),
    ("kitchen_market_crate_2x2.png", market_crate),
    ("bar_minecart_kaiten_1x3.png", minecart_kaiten),
    ("bar_sake_cellar_1x3.png", sake_cellar),
    ("bar_villager_itamae_1x3.png", villager_itamae),
    ("bar_fugu_warning_1x2.png", fugu_warning),
    ("bar_kelp_maki_1x2.png", kelp_maki),
    ("bar_cherry_blossom_sake_1x2.png", cherry_sake),
    ("bar_slot_nigiri_1x1.png", nigiri_slot),
    ("bar_slot_onigiri_1x1.png", onigiri_slot),
    ("bar_slot_old_sake_1x1.png", old_sake_slot),
    ("bar_plate_salmon_pair_1x1.png", salmon_plate),
    ("bar_plate_tuna_tamago_1x1.png", tuna_tamago_plate),
    ("bar_dine_nigiri_board_1x1.png", dine_nigiri_board),
    ("bar_dine_maki_ring_1x1.png", dine_maki_ring),
    ("bar_dine_chirashi_miso_1x1.png", dine_chirashi_miso),
    ("bar_dine_sashimi_for_two_1x1.png", dine_sashimi_for_two),
    ("bar_dine_bento_1x1.png", dine_bento),
    ("bar_dine_last_piece_1x1.png", dine_last_piece),
]

if __name__ == "__main__":
    for name, draw in PIECES:
        path, w, h = draw().save(name)
        print(f"{name:40} {w}x{h} px  ({h // 128}x{w // 128} blocks, HxW)")
