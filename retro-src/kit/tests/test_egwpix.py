#!/usr/bin/env python3
"""Tests for egwpix (stdlib only).  python3 tests/test_egwpix.py   -> prints one line per test, exit 1 on failure.

Besides its own decoders, it cross-checks every written PNG/GIF with the code the live server runs:
ImageFrame 2026.1.5.0's bundled madgag GifDecoder + javax ImageIO, ImageFrame's own MapUtils.resize +
toMapPaletteBytes (nearest-color), and Paper API 26.3-194 MapPalette.matchColor (tests/java/GifCheck.java).
"""
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
import time
import traceback

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KIT)
import egwpix as e  # noqa: E402

OUT = os.path.join(KIT, 'tests', 'out')
os.makedirs(OUT, exist_ok=True)
JAVA_DIR = os.path.join(KIT, 'tests', 'java')
PLUGINS = '/home/tricks/Downloads/backup-ed0f3f2c-feeb-47a2-8cf7-eea898ff8f03/plugins'
LIBS = os.path.abspath(os.path.join(KIT, '..', '..', 'port263-dreadplate', 'review-docs-r2', 'srv-off', 'libraries'))
PAPER_API = os.path.join(KIT, 'derive', 'paper-api-26.3.build.194-stable.jar')
RESULTS = []


def test(fn):
    t0 = time.time()
    try:
        note = fn() or ''
        RESULTS.append((fn.__name__, True, note))
        print(f'PASS {fn.__name__:28} {time.time() - t0:5.1f}s  {note}')
    except Exception as ex:  # noqa: BLE001
        RESULTS.append((fn.__name__, False, repr(ex)))
        print(f'FAIL {fn.__name__:28} {time.time() - t0:5.1f}s  {ex!r}')
        traceback.print_exc()
    return fn


# ------------------------------------------------------------------------------------ java bridge

def _classpath():
    jars = [os.path.join(PLUGINS, 'ImageFrame-2026.1.5.0.jar'), PAPER_API]
    for root, _d, files in os.walk(LIBS):
        for f in files:
            if f.endswith('.jar') and '/paper-api/' not in root:
                jars.append(os.path.join(root, f))
    return ':'.join(jars + [JAVA_DIR])


CP = _classpath()


def java(*args):
    cls = os.path.join(JAVA_DIR, 'GifCheck.class')
    src = os.path.join(JAVA_DIR, 'GifCheck.java')
    if not os.path.exists(cls) or os.path.getmtime(cls) < os.path.getmtime(src):
        subprocess.run(['javac', '-nowarn', '-cp', CP, '-d', JAVA_DIR, src], check=True, capture_output=True)
    r = subprocess.run(['java', '-Djava.awt.headless=true', '-cp', CP, 'GifCheck', *args],
                       check=True, capture_output=True, text=True)
    return r.stdout


def h24(b):
    return hashlib.sha256(b).hexdigest()[:24]


def rgb_hash(canvas):
    return h24(b''.join(bytes(c) for row in canvas.p for c in row))


def ids_hash(canvas):
    return h24(bytes(e.ID_OF[c] for row in canvas.p for c in row))


# ------------------------------------------------------------------------------------ fixtures

def stress_frames(n=12):
    """2x2 blocks; every frame holds all 244 map colours (stripes, shifted per frame) + a noise patch."""
    rng = random.Random(7)
    frames = []
    for k in range(n):
        c = e.blocks(2, 2, e.BLACK)
        for y in range(c.h):
            for x in range(c.w):
                c.p[y][x] = e.PALETTE[(x // 2 + y // 8 + k * 3) % len(e.PALETTE)]
        for y in range(40, 90):
            for x in range(20, 110):
                c.p[y][x] = rng.choice(e.PALETTE)
        e.neon_text(c, 6, 100 - k, 'FRAME', e.NEON['pink'], scale=2)
        frames.append(c)
    return frames


def neon_frames():
    """A believable 1x2 sign sequence: full lit, letters one by one, flash, off (OPEN-style test only)."""
    word = 'DOCK'
    cols = [e.NEON['cyan'], e.NEON['pink'], e.NEON['yellow'], e.NEON['red']]

    def sign(lit):
        c = e.blocks(1, 2, e.BLACK)
        e.dither_rect(c, 0, 0, c.w, c.h, e.mc('COLOR_BLACK', 0), e.mc('TERRACOTTA_BLACK', 0), 0.3)
        border = e.rrect_pixels(3, 3, c.w - 4, c.h - 4, r=6)
        if lit is None or lit >= 0:
            e.glow(c, border, e.NEON['blue'])
        else:
            c.fill_pixels(border, e.unlit(e.NEON['blue']))
        x = (c.w - e.text_width(word, 3)) // 2
        for i, ch in enumerate(word):
            px_ = e.text_pixels(x + i * 18, 22, ch, 3)
            if lit is None or i < lit:
                e.glow(c, px_, cols[i])
            else:
                c.fill_pixels(px_, e.unlit(cols[i]))
        return c
    frames = [sign(None), sign(-1), sign(1), sign(2), sign(3), sign(4), sign(-1), sign(None), sign(-1), sign(None)]
    delays = [1500, 400, 250, 250, 250, 250, 150, 150, 150, 1000]
    return frames, delays


# ------------------------------------------------------------------------------------ tests

@test
def palette_from_game():
    doc = json.load(open(os.path.join(KIT, 'map_palette.json')))
    assert doc['minecraft'] == '26.3' and doc['count'] == 244 == len(e.PALETTE)
    assert sorted(e.PALETTE_IDS) == list(range(4, 248)), 'ids are not 4..247'
    assert len(set(e.PALETTE)) == 244, 'duplicate colours'
    for k, inf in doc['info'].items():
        want = [c * inf['modifier'] // 255 for c in inf['base_rgb']]
        assert doc['colors'][k] == want, (k, inf)
    assert e.PALETTE_IDS[4 * 1 + 2] == (127, 178, 56) and e.PALETTE_IDS[4 * 1 + 3] == (67, 94, 29)
    # re-derive from the jars right now (also re-checks Paper API + Geyser tables) and compare
    spec = importlib.util.spec_from_file_location('derive_palette', os.path.join(KIT, 'derive_palette.py'))
    dp = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(dp)
    tmp = os.path.join(OUT, 'rederived.json')
    dp.OUT = tmp
    dp.main()
    again = json.load(open(tmp))
    assert again['colors'] == doc['colors'], 'map_palette.json is stale'
    return f"244 colours, re-derived from {os.path.basename(dp.VANILLA_JAR)} == file; Paper + Geyser agree"


@test
def nearest_matches_paper():
    rng = random.Random(1)
    for c in e.PALETTE:
        assert e.nearest(c) == c
    samples = [(0, 0, 0), (255, 255, 255), (128, 128, 128), (255, 0, 255), (1, 2, 3)] + \
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(3000)]
    for c in samples[:400]:
        brute = min(e.PALETTE, key=lambda p: (e._paper_dist(c, p), e.ID_OF[p]))
        assert e.nearest(c) == brute, c
    path = os.path.join(OUT, 'match.txt')
    with open(path, 'w') as f:
        f.write('\n'.join(f'{r} {g} {b}' for r, g, b in samples))
    got = [int(x) for x in java('match', path).split()]
    want = [e.ID_OF[e.nearest(c)] for c in samples]
    bad = [(samples[i], got[i], want[i]) for i in range(len(samples)) if got[i] != want[i]]
    assert not bad, bad[:5]
    return f'{len(samples)} random colours: egwpix.nearest == Paper MapPalette.matchColor'


@test
def canvas_matches_paintings():
    pdir = e.PAINTINGS_DIR
    before = sorted(os.listdir(pdir))
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('paintings_ro', os.path.join(pdir, 'paintings.py'))
    pt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pt)
    assert sorted(os.listdir(pdir)) == before, 'importing paintings.py changed its folder'
    for k, g in pt.FONT.items():
        assert e.FONT[k] == g, k

    def draw(mod):
        c = mod.Canvas(150, 120, (20, 30, 40))
        c.rect(5, 5, 60, 40, (200, 10, 10))
        c.vgrad(0, 50, 150, 90, [(10, 10, 80), (200, 120, 40), (250, 240, 200)])
        c.ell(40, 70, 18, 9, (90, 200, 90), 0.4)
        c.oell(100, 30, 14, 8, (240, 200, 60), (90, 60, 20), -0.3)
        c.poly([(10, 100), (60, 80), (90, 115), (30, 118)], (140, 70, 200))
        c.line(0, 0, 149, 119, (255, 255, 255))
        c.line(140, 5, 70, 110, (0, 200, 255), w=3)
        c.speckle(c.ell(120, 90, 20, 12, (60, 60, 60)), [(1, 1, 1), (250, 250, 250)], 0.3, random.Random(3))
        c.text(2, 2, ''.join(sorted(pt.FONT)), (255, 128, 0))
        c.text(4, 60, 'SUSHI 2X', (0, 255, 0), scale=2)
        c.frame()
        return c.p
    assert draw(pt) == draw(e), 'Canvas pixels differ from paintings.py'
    return 'rect/vgrad/ell/oell/poly/line/speckle/text/frame pixel-identical; no __pycache__ written there'


@test
def png_roundtrip_and_server_read():
    c = e.blocks(1, 2, e.BLACK)
    c.vgrad(0, 0, c.w, c.h, [(10, 20, 90), (240, 120, 40)])          # off-palette on purpose
    e.neon_text(c, 8, 20, 'EverGrims', e.NEON['cyan'], scale=2, case=True)
    off = sum(e.off_palette(c).values())
    path = os.path.join(OUT, 'roundtrip_1x2.png')
    info = e.save_png(c, path)
    assert info['w'] == 256 and info['h'] == 128 and info['blocks_hxw'] == (1, 2)
    assert info['snapped_pixels'] == off > 0
    back = e.read_png(path)
    want = e.upscale(e.quantize(c))
    assert back == want, 'PNG decode != written pixels'
    assert not e.off_palette(back)
    out = java('png', path, '2', '1').split()
    assert out[1] == rgb_hash(want) and out[4] == 'ids=' + ids_hash(want) and out[5] == 'pipe=imageframe', out
    # guards
    try:
        e.save_png(c, path, quantize=False)
        raise AssertionError('quantize=False should refuse off-palette pixels')
    except ValueError:
        pass
    try:
        e.save_png(e.Canvas(100, 64, e.BLACK), os.path.join(OUT, 'bad.png'))
        raise AssertionError('strict size check missing')
    except ValueError:
        pass
    try:
        e.save_png(c, os.path.join(e.PAINTINGS_DIR, 'nope_1x2.png'))
        raise AssertionError('paintings folder guard missing')
    except PermissionError:
        pass
    assert not os.path.exists(os.path.join(e.PAINTINGS_DIR, 'nope_1x2.png'))
    return f"256x128 ok, {off} px snapped, ImageIO + ImageFrame MapUtils map bytes == expected ids, guards hold"


@test
def lzw_fuzz():
    rng = random.Random(11)
    e.LZW_STATS.update(resets=0, eoi_bump=0)
    cases = 0
    for n in list(range(1, 700)) + [rng.randrange(1000, 200000) for _ in range(40)]:
        bits = rng.choice([2, 2, 3, 4, 5, 6, 7, 8])
        alpha = rng.randrange(1, (1 << bits) + 1)
        kind = rng.random()
        if kind < 0.3:
            data = bytes(rng.randrange(alpha) for _ in range(n))
        elif kind < 0.6:
            data = bytearray()
            while len(data) < n:
                data += bytes([rng.randrange(alpha)]) * rng.randrange(1, 60)
            data = bytes(data[:n])
        else:
            data = bytes((i // rng.randrange(1, 9) + i % 3) % alpha for i in range(n))
        enc = e._lzw_encode(data, bits)
        assert e._lzw_decode(enc, bits) == data, (n, bits, alpha)
        cases += 1
    assert e.LZW_STATS['resets'] > 0 and e.LZW_STATS['eoi_bump'] > 0, e.LZW_STATS
    return f"{cases} streams round-trip; table resets {e.LZW_STATS['resets']}, end-of-stream width bumps {e.LZW_STATS['eoi_bump']}"


def gif_check(frames, delays, path, wb, hb):
    info = e.save_gif(frames, delays, path)
    g = e.read_gif(path)
    want = [e.upscale(e.quantize(f)) for f in frames]
    assert g['loop'] == 0 and g['delays_ms'] == info['delays_ms'] and len(g['frames']) == len(frames)
    for i, (a, b) in enumerate(zip(g['frames'], want)):
        assert a == b, f'own decoder: frame {i + 1} differs'
    lines = java('gif', path, str(wb), str(hb)).splitlines()
    head = lines[0].split()
    assert head == ['MADGAG', 'status=0', f'frames={len(frames)}', 'loop=0'], head
    m = [ln.split() for ln in lines if ln.startswith('M ')]
    j = [ln.split() for ln in lines if ln.startswith('J ')]
    assert len(m) == len(j) == len(frames)
    for i, w in enumerate(want):
        assert int(m[i][2]) == info['delays_ms'][i] == int(j[i][2]), ('delay', i)
        assert m[i][3] == rgb_hash(w) == j[i][3], ('rgb', i)
        assert m[i][6] == 'ids=' + ids_hash(w), ('map bytes', i)
        assert m[i][5] == 'minAlpha=255' == j[i][5], ('alpha', i)
    assert j[0][-1] == 'loop=0' and all('disposal=doNotDispose' in ' '.join(x) for x in j)
    assert lines[-1] == 'PIPE imageframe', lines[-1]
    return info


@test
def gif_stress_all_colours():
    frames = stress_frames()
    delays = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 1000, 50]
    e.LZW_STATS.update(resets=0, eoi_bump=0)
    info = gif_check(frames, delays, os.path.join(OUT, 'stress_2x2.gif'), 2, 2)
    assert info['colours'] == 244 and info['w'] == info['h'] == 256 and e.LZW_STATS['resets'] > 0
    return (f"12 frames x 244 colours, {info['bytes'] // 1024} KB, {e.LZW_STATS['resets']} LZW resets; "
            f"own + madgag + javax decode identical, delays/loop ok, ImageFrame map bytes == expected")


@test
def gif_small_tables_and_edges():
    notes = []
    for ncol in (1, 2, 3, 4, 5, 9, 17):
        rng = random.Random(ncol)
        cols = rng.sample(e.PALETTE, ncol)
        frames = []
        for k in range(6):
            c = e.blocks(1, 1, cols[0])
            for y in range(c.h):
                for x in range(c.w):
                    if rng.random() < 0.5:
                        c.p[y][x] = rng.choice(cols)
            frames.append(c)
        info = gif_check(frames, 100, os.path.join(OUT, f'edge_{ncol}c_1x1.gif'), 1, 1)
        notes.append(f'{ncol}c:{info["bytes"]}B')
    # frames whose LZW stream ends exactly when the code width must grow (the EOI width bump): found by
    # adding noise pixels one at a time to a flat frame until the encoder reports the edge case
    four = sorted(e.PALETTE[:4], key=e.ID_OF.get)
    index = {c: i for i, c in enumerate(four)}
    rng = random.Random(99)
    spots = [(rng.randrange(64), rng.randrange(64), rng.choice(four)) for _ in range(1500)]
    frames, n = [], 0
    while len(frames) < 4 and n < len(spots):
        n += 1
        c = e.blocks(1, 1, four[0])
        for y in range(4):
            c.p[0][y] = four[y]                    # all four colours present -> same 2-bit table
        for (x, y, col) in spots[:n]:
            c.p[y][x] = col
        idx = bytes(index[px] * 1 for row in e.upscale(c).p for px in row)
        before = e.LZW_STATS['eoi_bump']
        e._lzw_encode(idx, 2)
        if e.LZW_STATS['eoi_bump'] > before:
            frames.append(c)
    assert len(frames) == 4, f'only {len(frames)} EOI-bump frames found'
    e.LZW_STATS.update(resets=0, eoi_bump=0)
    gif_check(frames, 50, os.path.join(OUT, 'edge_eoi_1x1.gif'), 1, 1)
    assert e.LZW_STATS['eoi_bump'] == 4, e.LZW_STATS
    for bad in (0, 30, 75, 120):
        try:
            e.save_gif(frames[:2], bad, os.path.join(OUT, 'bad.gif'))
            raise AssertionError(f'delay {bad} accepted')
        except ValueError:
            pass
    return ' '.join(notes) + f"; 4 EOI-width-bump frames decoded right by madgag/javax; bad delays refused"


@test
def gif_realistic_sizes():
    frames, delays = neon_frames()
    info = gif_check(frames, delays, os.path.join(OUT, 'neon_demo_1x2.gif'), 2, 1)
    e.save_png(frames[0], os.path.join(OUT, 'neon_demo_1x2.png'))
    e.preview(frames, os.path.join(OUT, 'neon_demo_preview.png'), scale=2, delays_ms=delays, title='neon demo 1x2')
    assert info['bytes'] < 60_000, info['bytes']
    # a 3x3, 12-frame "light only moves" style animation for the size budget
    base = e.blocks(3, 3, e.BLACK)
    e.bayer_vgrad(base, 0, 0, base.w, 90, [e.mc('COLOR_PURPLE', 0), e.mc('COLOR_MAGENTA', 1), e.mc('COLOR_ORANGE', 3)])
    base.rect(0, 90, base.w, base.h, e.mc('TERRACOTTA_GREEN', 0))
    base.rect(80, 40, 112, 170, e.mc('WATER', 1))
    fr = []
    for k in range(12):
        f = base.copy()
        for y in range(40, 170):
            if (y - k * 4) % 16 < 3:
                f.rect(82, y, 110, y + 1, e.mc('ICE', 3))
        fr.append(f)
    info3 = gif_check(fr, 100, os.path.join(OUT, 'falls_demo_3x3.gif'), 3, 3)
    e.preview(fr, os.path.join(OUT, 'falls_demo_preview.png'), scale=1, delays_ms=100, title='falls demo 3x3')
    assert info3['bytes'] < 250_000, info3['bytes']
    return (f"neon 1x2 10 frames {info['bytes'] // 1024} KB ({info['imageframe_fake_maps']} fake maps); "
            f"falls 3x3 12 frames {info3['bytes'] // 1024} KB ({info3['imageframe_fake_maps']} fake maps, "
            f"tiles {sorted(set(info3['per_tile'].values()))})")


@test
def glow_halo_rules():
    c = e.blocks(1, 1, e.BLACK)
    red = e.NEON['red']
    core = e.glow(c, e.line_pixels(10, 30, 50, 30), red)
    assert all(c.get(x, y) == red for (x, y) in core)
    assert c.get(30, 29) == c.get(30, 31) == e.mc('FIRE', 1) == (180, 0, 0)
    assert c.get(30, 28) == c.get(30, 32) == e.mc('FIRE', 0) == (135, 0, 0)
    assert c.get(30, 26) == e.BLACK and c.get(30, 34) == e.BLACK
    assert e.base_of(c.get(30, 29)) == 'FIRE'
    blue = e.NEON['blue']
    e.glow(c, e.line_pixels(10, 33, 50, 33), blue)            # its halo crosses the red tube
    assert all(c.get(x, y) == red for (x, y) in core), 'lighten blend overwrote a brighter core'
    thick = e.glow(c, e.thicken(e.line_pixels(10, 50, 50, 50), 3), e.NEON['pink'], hot=e.mc('QUARTZ', 3))
    assert c.get(30, 50) == e.mc('QUARTZ', 3) and c.get(30, 49) == e.NEON['pink']
    assert not e.off_palette(c)
    on, off = e.seg7_pixels(2, 2, '18:8')
    assert len(on) and len(off) and not (on & off)
    on1, off1 = e.seg7_pixels(0, 0, '1')
    on8, _ = e.seg7_pixels(0, 0, '8')
    assert len(on1) + len(off1) == len(on8) == 3 * 3 + 4 * 3
    for core in e.NEON.values():
        off_ = e.unlit(core)
        assert off_ in e.PALETTE_SET and e.lum(off_) < e.lum(e.halo_for(core)[0]), core
    return 'core 255 -> ring1 x180 -> ring2 x135 same base, lighten keeps cores, hot centre, seg7 ok'


@test
def tile_cost_model():
    a = e.blocks(1, 2, e.BLACK)
    b = a.copy()
    b.rect(0, 0, 10, 10, e.NEON['red'])                       # only the left tile changes
    cost = e.tile_cost([a, b, a, a], [100, 50, 50, 300])
    assert cost['per_tile'] == {(0, 0): 3, (1, 0): 1} and cost['fake_maps'] == 4
    assert cost['ticks'] == 10 and cost['duration_ms'] == 500
    return 'unchanged tiles cost one map; held frames cost nothing extra'


@test
def preview_and_palette_sheet():
    frames = stress_frames(5)
    p = e.preview(frames, os.path.join(OUT, 'stress_preview.png'), scale=1, delays_ms=[50, 100, 150, 200, 250])
    sheet = e.read_png(p)
    assert sheet.w > 2 * 128 and sheet.h > 128
    ps = e.palette_sheet(os.path.join(KIT, 'palette_sheet.png'))
    s2 = e.read_png(ps)
    assert all(c in s2.colours() for c in e.PALETTE)
    return f'contact sheet {sheet.w}x{sheet.h}; palette_sheet.png {s2.w}x{s2.h} shows all 244'


if __name__ == '__main__':
    bad = [r for r in RESULTS if not r[1]]
    print(f'\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed')
    sys.exit(1 if bad else 0)
