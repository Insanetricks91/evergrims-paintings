#!/usr/bin/env python3
"""Retro game TV for the EverGrims ImageFrame set: a hero's sword swipe at a slime, on a 90s TV.

    retro_sword_tv_3x4.gif   3 tall x 4 wide  -- four poses: ready, wind-up, swipe, follow-through (800 ms loop)

The art is image-generated (assets/imageframe-paintings/retro-tv-2026-10-24/sword-swipe-v2/), cut to 128x96
logical px per frame with a shared 32-colour palette.  tv_src.png keeps those four frames as one 2x2 atlas.
This script holds the scenery still (steady), swaps each of the 32 colours for a hand-picked Minecraft map
colour (MAP below) so ImageFrame has nothing to dither, then writes the GIF with egwpix: 2x to 256x192 design px, 2x again on save = 512x384,
one map per 128 px.  Frame 1 (ready pose) is the Bedrock still.
Python standard library only.   Run: python3 tv.py      (python3 tv.py --import <gif> rebuilds tv_src.png)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'kit'))
import egwpix as e  # noqa: E402

mc = e.mc
SRC = os.path.join(HERE, 'tv_src.png')
FW, FH = 128, 96                       # logical frame size (32 px per block)
DELAYS = [350, 150, 150, 150]          # ready holds, the swing snaps

# source colour -> map colour.  The nearest map colour (server metric) would merge the slime into the sky,
# make the heart highlight darker than the heart, and grey the TV bezel; these keep every role distinct.
MAP = {
    (1, 141, 255): mc('LAPIS', 3),              # sky
    (2, 120, 166): mc('WARPED_NYLIUM', 3),      # mountains
    (6, 97, 108): mc('WARPED_NYLIUM', 1),       # mountain shade, sprite edge fringe
    (17, 0, 0): mc('COLOR_BLACK', 0),           # outlines, TV body
    (11, 29, 67): mc('COLOR_BLUE', 0),          # TV bezel
    (63, 61, 64): mc('STONE', 0),               # bezel corner, sword guard shadow
    (103, 106, 108): mc('COLOR_LIGHT_GRAY', 1),
    (244, 250, 255): mc('SNOW', 3),             # clouds, blade, heart shine
    (214, 215, 213): mc('SNOW', 2),             # blade shade
    (120, 198, 253): mc('COLOR_LIGHT_BLUE', 3),  # cloud edge
    (64, 161, 244): mc('COLOR_LIGHT_BLUE', 3),  # slime
    (52, 152, 177): mc('COLOR_LIGHT_BLUE', 2),  # slime edge
    (138, 251, 53): mc('COLOR_LIGHT_GREEN', 3),  # grass
    (80, 242, 37): mc('COLOR_LIGHT_GREEN', 3),
    (181, 247, 96): mc('COLOR_LIGHT_GREEN', 3),
    (103, 212, 121): mc('COLOR_LIGHT_GREEN', 3),
    (70, 138, 34): mc('COLOR_LIGHT_GREEN', 1),  # grass mid
    (3, 61, 15): mc('PLANT', 0),                # grass dark
    (137, 72, 44): mc('TERRACOTTA_ORANGE', 2),  # dirt
    (154, 135, 126): mc('TERRACOTTA_WHITE', 1),  # stones
    (255, 31, 31): mc('FIRE', 3),               # hood, hearts
    (186, 27, 28): mc('FIRE', 1),
    (81, 1, 2): mc('NETHER', 1),
    (247, 71, 76): mc('COLOR_PINK', 3),         # heart highlight
    (248, 126, 124): mc('COLOR_PINK', 3),
    (255, 210, 138): mc('RAW_IRON', 3),         # skin
    (193, 187, 145): mc('SAND', 1),             # trousers
    (90, 67, 0): mc('TERRACOTTA_YELLOW', 0),    # hair, boots
    (238, 130, 53): mc('COLOR_ORANGE', 3),
    (255, 249, 4): mc('GOLD', 3),               # coins, hilt
    (224, 191, 2): mc('GOLD', 2),
    (184, 146, 5): mc('TERRACOTTA_YELLOW', 3),
}


# The generated frames each redraw the whole scene, so stones, grass, coins and the bezel flicker frame to
# frame.  Outside ACTOR every frame is frame 1.  Inside it, each frame keeps its own hero, sword and slime
# (non-SCENERY pixels) over one shared backdrop: per pixel, the scenery colour most frames agree on.
ACTOR = (28, 36, 101, 71)              # x0, y0, x1, y1 (exclusive), logical px
SCENERY = {(1, 141, 255), (2, 120, 166), (6, 97, 108), (120, 198, 253), (138, 251, 53), (80, 242, 37),
           (181, 247, 96), (103, 212, 121), (70, 138, 34), (3, 61, 15), (137, 72, 44), (154, 135, 126)}


def steady(fs):
    x0, y0, x1, y1 = ACTOR
    out = [[row[:] for row in fs[0]] for _ in fs]
    for y in range(y0, y1):
        for x in range(x0, x1):
            seen = [f[y][x] for f in fs if f[y][x] in SCENERY]
            back = max(seen, key=lambda c: (seen.count(c), c == fs[0][y][x])) if seen else fs[0][y][x]
            for g, f in zip(out, fs):
                g[y][x] = back if f[y][x] in SCENERY else f[y][x]
    return out


def import_gif(path):
    """Cut the 4 frames of the source GIF (any whole-number enlargement of 128x96) into tv_src.png."""
    g = e.read_gif(path)
    k = g['w'] // FW
    assert (g['w'], g['h']) == (FW * k, FH * k) and len(g['frames']) == 4, (g['w'], g['h'], len(g['frames']))
    atlas = e.Canvas(FW * 2, FH * 2, (0, 0, 0))
    for n, f in enumerate(g['frames']):
        for y in range(FH):
            for x in range(FW):
                block = {f.p[y * k + dy][x * k + dx] for dy in range(k) for dx in range(k)}
                assert len(block) == 1, f'frame {n + 1} cell {x},{y} is not one colour'
                atlas.p[(n // 2) * FH + y][(n % 2) * FW + x] = block.pop()
    e._write_png(atlas, SRC)
    print('wrote', SRC, len(atlas.colours()), 'colours')


def frames():
    atlas = e.read_png(SRC)
    missing = atlas.colours() - set(MAP)
    assert not missing, f'colours with no map colour: {sorted(missing)}'
    raw = [[atlas.p[(n // 2) * FH + y][(n % 2) * FW:(n % 2 + 1) * FW] for y in range(FH)] for n in range(4)]
    out = []
    for rows in steady(raw):
        f = e.Canvas(FW, FH, (0, 0, 0))
        f.p = [[MAP[c] for c in row] for row in rows]
        out.append(e.upscale(f, 2))
    return out


def main():
    fs = frames()
    path = os.path.join(HERE, e.out_name('retro_sword_tv', 3, 4, 'gif'))
    info = e.save_gif(fs, DELAYS, path, quantize=False)
    e.preview(fs, os.path.join(HERE, 'retro_sword_tv_preview.png'), scale=2, delays_ms=DELAYS, cols=2,
              title='RETRO SWORD TV 3X4')
    print({k: v for k, v in info.items() if k != 'per_tile'})


if __name__ == '__main__':
    if sys.argv[1:2] == ['--import']:
        import_gif(sys.argv[2])
    else:
        main()
