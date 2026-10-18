#!/usr/bin/env python3
"""Re-derive map_palette.json from the real Minecraft 26.3 server jar (Python standard library only).

What it does, step by step:
  1. Opens the vanilla 26.3 bundler jar (mojang_26.3.jar), reads META-INF/versions.list, pulls the inner
     server-26.3.jar out of it in memory and checks its SHA-256 against versions.list.
  2. Parses the class files net/minecraft/world/level/material/MapColor.class and MapColor$Brightness.class
     (26.x jars are not obfuscated) with a small class-file reader, and walks the bytecode of each class's
     static initialiser:  new MapColor; dup; <push id>; <push col>; invokespecial <init>(II)V; putstatic NAME
     gives every base colour, and the Brightness enum's <init>(String,int,int,int) calls give each
     brightness id and modifier (LOW=180, NORMAL=220, HIGH=255, LOWEST=135 in 26.3).
  3. Checks net/minecraft/util/ARGB.scaleRGB(int,int) still does channel * modifier / 255 as long maths
     (i2l, i2l, lmul, ldc2_w 255L, ldiv -- three times, one per channel), which is what
     MapColor.calculateARGBColor calls, and that calculateARGBColor returns 0 for NONE.
  4. Builds the table: packed map colour id = base_id * 4 + brightness_id (MapColor.getPackedId), rgb =
     channel * modifier // 255.  NONE (base id 0, packed ids 0-3) is transparent and left out.
  5. Cross-checks the result against org.bukkit.map.MapPalette.colors in the Paper API jar the live server
     runs (paper-api 26.3 build 194) -- that is the table ImageFrame's default "nearest-color" mode matches
     against -- and fails loudly if any entry differs.
"""
import hashlib
import io
import json
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.abspath(os.path.join(HERE, '..', '..'))
VANILLA_JAR = os.path.join(SCRATCH, 'port-263-fxpf', 'bladefx', 'jars', 'mojang_26.3.jar')
PAPER_API_JAR = os.path.join(
    SCRATCH, 'port263-dreadplate', 'review-docs-r2', 'srv-off', 'libraries', 'io', 'papermc', 'paper',
    'paper-api', '26.3.build.194-stable', 'paper-api-26.3.build.194-stable.jar')
GEYSER_JAR = '/home/tricks/Downloads/backup-ed0f3f2c-feeb-47a2-8cf7-eea898ff8f03/plugins/Geyser-Spigot-mushroomfix.jar'
OUT = os.path.join(HERE, 'map_palette.json')


# ------------------------------------------------------------------------------ class-file reader

def _oplen(code, pc):
    """Length in bytes of the JVM instruction at pc."""
    op = code[pc]
    if op == 0xaa:                                   # tableswitch
        p = (pc + 4) & ~3
        lo, hi = struct.unpack('>ii', code[p + 4:p + 12])
        return p + 12 + 4 * (hi - lo + 1) - pc
    if op == 0xab:                                   # lookupswitch
        p = (pc + 4) & ~3
        n, = struct.unpack('>i', code[p + 4:p + 8])
        return p + 8 + 8 * n - pc
    if op == 0xc4:                                   # wide
        return 6 if code[pc + 1] == 0x84 else 4
    if op in (0x10, 0x12, 0x15, 0x16, 0x17, 0x18, 0x19, 0x36, 0x37, 0x38, 0x39, 0x3a, 0xa9, 0xbc):
        return 2
    if op in (0x11, 0x13, 0x14, 0x84) or 0x99 <= op <= 0xa8 or 0xb2 <= op <= 0xb8 \
            or op in (0xbb, 0xbd, 0xc0, 0xc1, 0xc6, 0xc7):
        return 3
    if op == 0xc5:
        return 4
    if op in (0xb9, 0xba, 0xc8, 0xc9):
        return 5
    return 1


class ClassFile:
    def __init__(self, data):
        self.data = data
        assert data[:4] == b'\xca\xfe\xba\xbe', 'not a class file'
        n, = struct.unpack('>H', data[8:10])
        self.cp = [None] * n
        p, i = 10, 1
        while i < n:
            tag = data[p]
            if tag == 1:
                ln, = struct.unpack('>H', data[p + 1:p + 3])
                self.cp[i] = ('Utf8', data[p + 3:p + 3 + ln].decode('utf-8', 'replace'))
                p += 3 + ln
            elif tag in (3, 4):
                v, = struct.unpack('>i' if tag == 3 else '>f', data[p + 1:p + 5])
                self.cp[i] = ('Integer' if tag == 3 else 'Float', v)
                p += 5
            elif tag in (5, 6):
                v, = struct.unpack('>q' if tag == 5 else '>d', data[p + 1:p + 9])
                self.cp[i] = ('Long' if tag == 5 else 'Double', v)
                p += 9
                i += 1
            elif tag in (7, 8, 16, 19, 20):
                v, = struct.unpack('>H', data[p + 1:p + 3])
                self.cp[i] = ({7: 'Class', 8: 'String', 16: 'MethodType', 19: 'Module', 20: 'Package'}[tag], v)
                p += 3
            elif tag in (9, 10, 11, 12, 17, 18):
                a, b = struct.unpack('>HH', data[p + 1:p + 5])
                self.cp[i] = ({9: 'Field', 10: 'Method', 11: 'IMethod', 12: 'NameAndType',
                               17: 'Dynamic', 18: 'InvokeDynamic'}[tag], a, b)
                p += 5
            elif tag == 15:
                self.cp[i] = ('MethodHandle', data[p + 1], struct.unpack('>H', data[p + 2:p + 4])[0])
                p += 4
            else:
                raise ValueError(f'unknown constant pool tag {tag}')
            i += 1
        p += 6
        ni, = struct.unpack('>H', data[p:p + 2])
        p += 2 + 2 * ni
        self.fields, p = self._members(p)
        self.methods, p = self._members(p)

    def _members(self, p):
        n, = struct.unpack('>H', self.data[p:p + 2])
        p += 2
        out = {}
        for _ in range(n):
            _acc, ni, di, na = struct.unpack('>HHHH', self.data[p:p + 8])
            p += 8
            attrs = {}
            for _ in range(na):
                an, al = struct.unpack('>HI', self.data[p:p + 6])
                attrs[self.utf8(an)] = self.data[p + 6:p + 6 + al]
                p += 6 + al
            out[(self.utf8(ni), self.utf8(di))] = attrs
        return out, p

    def utf8(self, i):
        return self.cp[i][1]

    def class_name(self, i):
        return self.utf8(self.cp[i][1])

    def member_ref(self, i):
        """(owner, name, descriptor) of a Field/Method constant."""
        _t, ci, nti = self.cp[i]
        _t2, ni, di = self.cp[nti]
        return self.class_name(ci), self.utf8(ni), self.utf8(di)

    def code(self, name, desc):
        attr = self.methods[(name, desc)]['Code']
        ln, = struct.unpack('>I', attr[4:8])
        return attr[8:8 + ln]

    def instructions(self, name, desc):
        code = self.code(name, desc)
        pc = 0
        while pc < len(code):
            n = _oplen(code, pc)
            yield pc, code[pc], code[pc + 1:pc + n]
            pc += n

    def int_pushed(self, op, arg):
        """The int an instruction pushes, or None if it does not push an int constant."""
        if 0x02 <= op <= 0x08:
            return op - 0x03                             # iconst_m1 .. iconst_5
        if op == 0x10:
            return struct.unpack('>b', arg[:1])[0]       # bipush
        if op == 0x11:
            return struct.unpack('>h', arg[:2])[0]       # sipush
        if op in (0x12, 0x13):                           # ldc / ldc_w
            idx = arg[0] if op == 0x12 else struct.unpack('>H', arg[:2])[0]
            if self.cp[idx][0] == 'Integer':
                return self.cp[idx][1]
        return None

    def string_pushed(self, op, arg):
        if op in (0x12, 0x13):
            idx = arg[0] if op == 0x12 else struct.unpack('>H', arg[:2])[0]
            if self.cp[idx][0] == 'String':
                return self.utf8(self.cp[idx][1])
        return None


# ------------------------------------------------------------------------------ extraction

MAPCOLOR = 'net/minecraft/world/level/material/MapColor'
BRIGHT = 'net/minecraft/world/level/material/MapColor$Brightness'
ARGB = 'net/minecraft/util/ARGB'


def inner_server_jar(bundler_path):
    with zipfile.ZipFile(bundler_path) as z:
        line = z.read('META-INF/versions.list').decode().split('\n')[0].strip()
        sha, version, rel = line.split('\t')
        blob = z.read('META-INF/versions/' + rel)
        version_json = json.loads(z.read('version.json'))
    got = hashlib.sha256(blob).hexdigest()
    if got != sha:
        raise SystemExit(f'inner jar hash mismatch: {got} != {sha}')
    return blob, version, rel, sha, version_json


def read_base_colours(cf):
    ints, pending, out = [], None, []
    for _pc, op, arg in cf.instructions('<clinit>', '()V'):
        v = cf.int_pushed(op, arg)
        if v is not None:
            ints.append(v)
            continue
        if op == 0xb7:                                           # invokespecial
            owner, name, desc = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            if owner == MAPCOLOR and name == '<init>' and desc == '(II)V':
                pending = (ints[-2], ints[-1])
        elif op == 0xb3 and pending:                             # putstatic
            _o, fname, _d = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            out.append((pending[0], fname, pending[1]))
            pending = None
            ints = []
    return out


def read_brightness(cf):
    ints, name, pending, out = [], None, None, []
    for _pc, op, arg in cf.instructions('<clinit>', '()V'):
        v = cf.int_pushed(op, arg)
        s = cf.string_pushed(op, arg)
        if v is not None:
            ints.append(v)
        elif s is not None:
            name, ints = s, []
        elif op == 0xb7:
            owner, mname, desc = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            if owner == BRIGHT and mname == '<init>' and desc == '(Ljava/lang/String;III)V':
                pending = (name, ints[-3], ints[-2], ints[-1])   # name, ordinal, id, modifier
        elif op == 0xb3 and pending:
            _o, fname, _d = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            assert fname == pending[0], (fname, pending)
            out.append(pending)
            pending = None
    return out


def check_scale_rgb(cf):
    """ARGB.scaleRGB(int,int): per channel  (long)c * (long)mod / 255L, clamped 0..255."""
    code = cf.code('scaleRGB', '(II)I')
    ops = []
    for _pc, op, arg in cf.instructions('scaleRGB', '(II)I'):
        if op == 0x14:
            idx, = struct.unpack('>H', arg[:2])
            ops.append(('ldc2_w', cf.cp[idx]))
        elif op in (0xb8,):
            ops.append(('invokestatic', cf.member_ref(struct.unpack('>H', arg[:2])[0])[1]))
        else:
            ops.append(op)
    want = [0x85, 0x1b, 0x85, 0x69, ('ldc2_w', ('Long', 255)), 0x6d]   # i2l iload_1 i2l lmul 255L ldiv
    hits = sum(1 for i in range(len(ops)) if ops[i:i + len(want)] == want)
    clamps = sum(1 for o in ops if o == ('invokestatic', 'clamp'))
    if hits != 3 or clamps != 3:
        raise SystemExit(f'ARGB.scaleRGB changed shape (hits={hits}, clamps={clamps}); re-check the formula')
    return len(code)


def check_calculate(cf):
    seq = []
    for _pc, op, arg in cf.instructions('calculateARGBColor', f'(L{BRIGHT};)I'):
        if op in (0xb2, 0xb4, 0xb8):
            seq.append(cf.member_ref(struct.unpack('>H', arg[:2])[0])[1])
        else:
            seq.append(op)
    # getstatic NONE / if_acmpne / iconst_0 / ireturn ... getfield col / opaque / getfield modifier / scaleRGB
    if seq[:5] != [0x2a, 'NONE', 0xa6, 0x03, 0xac] or 'scaleRGB' not in seq or 'modifier' not in seq:
        raise SystemExit(f'MapColor.calculateARGBColor changed shape: {seq}')


def paper_colours(path):
    with zipfile.ZipFile(path) as z:
        cf = ClassFile(z.read('org/bukkit/map/MapPalette.class'))
    ints, out = [], []
    for _pc, op, arg in cf.instructions('<clinit>', '()V'):
        v = cf.int_pushed(op, arg)
        if v is not None:
            ints.append(v)
        elif op == 0xb7:
            owner, name, desc = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            if owner == 'java/awt/Color' and name == '<init>':
                if desc == '(IZ)V':                           # new Color(argb, hasAlpha=true)
                    argb = ints[-2] & 0xffffffff
                    out.append(((argb >> 16) & 255, (argb >> 8) & 255, argb & 255, argb >> 24))
                elif desc == '(I)V':                          # new Color(rgb): opaque
                    rgb = ints[-1] & 0xffffff
                    out.append(((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, 255))
                elif desc == '(IIII)V':
                    out.append(tuple(ints[-4:-1]) + (ints[-1],))
                elif desc == '(III)V':
                    out.append(tuple(ints[-3:]) + (255,))
                ints = []
            if owner == 'org/bukkit/map/MapPalette' and name == 'c':
                ints = []
    return out


def geyser_colours(path):
    """Geyser's org.geysermc.geyser.level.MapColor enum: COLOR_n(r, g, b) -- what Bedrock players get."""
    with zipfile.ZipFile(path) as z:
        cf = ClassFile(z.read('org/geysermc/geyser/level/MapColor.class'))
    ints, out = [], {}
    for _pc, op, arg in cf.instructions('<clinit>', '()V'):
        v = cf.int_pushed(op, arg)
        if cf.string_pushed(op, arg) is not None:
            ints = []
        elif v is not None:
            ints.append(v)
        elif op == 0xb7:
            _o, name, desc = cf.member_ref(struct.unpack('>H', arg[:2])[0])
            if name == '<init>' and desc == '(Ljava/lang/String;IIII)V':
                out[ints[-4]] = tuple(ints[-3:])
    return out


def main():
    blob, version, rel, sha, vjson = inner_server_jar(VANILLA_JAR)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        mc = ClassFile(z.read(MAPCOLOR + '.class'))
        br = ClassFile(z.read(BRIGHT + '.class'))
        ag = ClassFile(z.read(ARGB + '.class'))
    bases = read_base_colours(mc)
    levels = read_brightness(br)
    check_scale_rgb(ag)
    check_calculate(mc)

    assert bases[0][:2] == (0, 'NONE'), bases[0]
    ids = [b[0] for b in bases]
    assert ids == list(range(len(ids))), 'base colour ids are not 0..n-1 in order'
    by_id = {lv[2]: lv for lv in levels}
    assert sorted(by_id) == [0, 1, 2, 3], levels

    colours, info = {}, {}
    for base_id, name, col in bases:
        if base_id == 0:
            continue
        r0, g0, b0 = (col >> 16) & 255, (col >> 8) & 255, col & 255
        for bid in range(4):
            lname, _ordinal, _id, mod = by_id[bid]
            rgb = [max(0, min(255, (r0 * mod) // 255)), max(0, min(255, (g0 * mod) // 255)),
                   max(0, min(255, (b0 * mod) // 255))]
            packed = base_id * 4 + bid
            colours[str(packed)] = rgb
            info[str(packed)] = {'base': name, 'base_id': base_id, 'base_rgb': [r0, g0, b0],
                                 'brightness': lname, 'modifier': mod}

    # cross-check against the Paper API table the live server's ImageFrame matches against
    paper = paper_colours(PAPER_API_JAR)
    mism = []
    for k, rgb in colours.items():
        i = int(k)
        if i >= len(paper) or tuple(paper[i][:3]) != tuple(rgb) or paper[i][3] != 255:
            mism.append((i, rgb, paper[i] if i < len(paper) else None))
    extra = [i for i in range(len(paper)) if str(i) not in colours and paper[i][3] != 0]
    if mism or extra or len(paper) != 4 + len(colours):
        raise SystemExit(f'Paper MapPalette disagrees: {mism[:5]} extra={extra} n={len(paper)}')

    # Bedrock: Geyser converts Java map colour ids with its own table; check it agrees too
    geyser_note = 'not checked (Geyser jar not found)'
    if os.path.exists(GEYSER_JAR):
        gey = geyser_colours(GEYSER_JAR)
        gdiff = [i for i in map(int, colours) if gey.get(i) != tuple(colours[str(i)])]
        if gdiff:
            raise SystemExit(f'Geyser MapColor disagrees for ids {gdiff[:10]}')
        geyser_note = GEYSER_JAR + ' :: org/geysermc/geyser/level/MapColor (identical for all ids)'

    doc = {
        'minecraft': version,
        'count': len(colours),
        'index': 'packed map colour id (the byte stored in map data) = base_id * 4 + brightness_id',
        'source': {
            'bundler_jar': VANILLA_JAR,
            'inner_jar': rel, 'inner_jar_sha256': sha,
            'build_time': vjson.get('build_time'), 'protocol_version': vjson.get('protocol_version'),
            'classes': [MAPCOLOR + '.class', BRIGHT + '.class', ARGB + '.class'],
            'cross_checked_against': PAPER_API_JAR + ' :: org/bukkit/map/MapPalette.colors (identical, '
                                     'entries 0-3 transparent)',
            'bedrock_cross_check': geyser_note,
        },
        'derivation': (
            'Base colours and ids read from the bytecode of MapColor.<clinit> (new MapColor(id, col)); '
            'brightness ids/modifiers from MapColor$Brightness.<clinit>: '
            + ', '.join(f'{lv[0]}(id {lv[2]})={lv[3]}' for lv in sorted(levels, key=lambda l: l[2]))
            + '. Colour = ARGB.scaleRGB(col, modifier): each channel (long)c * modifier / 255 '
              '(integer division, clamped 0..255), as in MapColor.calculateARGBColor. '
              'NONE (base 0, ids 0-3) is transparent and excluded. Regenerate with derive_palette.py.'),
        'brightness_levels': {lv[0]: {'id': lv[2], 'modifier': lv[3]} for lv in levels},
        'colors': colours,
        'info': info,
    }
    with open(OUT, 'w') as f:
        json.dump(doc, f, indent=1)
    print(f'{len(bases) - 1} base colours x 4 brightness = {len(colours)} colours -> {OUT}')
    print('brightness:', ', '.join(f'{lv[0]} id{lv[2]} x{lv[3]}' for lv in levels))
    print(f'Paper API MapPalette: {len(paper)} entries, identical for ids 4..{len(paper) - 1}')
    print('Geyser (Bedrock):', geyser_note)


if __name__ == '__main__':
    sys.exit(main())
