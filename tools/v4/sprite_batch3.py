"""Shared Trailmap sprite batch 3: append mmlhc_sym_32715, mmlhc_sym_44591 and mmlhc_sym_45200
(mmlv2 v4.6, Lapland) to the sprite on mtb-trailmap origin/master, as a new strip below batch 2.
Additive only: every existing entry and pixel stays; the 1x icons are the 2x ones box-averaged.

    python3 -I tools/v4/make_patterns.py && python3 -I tools/v4/sprite_batch3.py
    # writes tools/v4/sprite-batch3/spritev2{,@2x}.{json,png}
"""
import json, os, struct, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MTB = os.path.join(HERE, '../../../mtb-trailmap')
BASE = 'origin/master'
NEW = ['mmlhc_sym_32715', 'mmlhc_sym_44591', 'mmlhc_sym_45200']
OUT = os.path.join(HERE, 'sprite-batch3')


def git_show(p):
    return subprocess.check_output(['git', '-C', MTB, 'show', f'{BASE}:{p}'])


def png_decode(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    i, idat = 8, b''
    while i < len(data):
        n, t = struct.unpack('>I4s', data[i:i + 8])
        c = data[i + 8:i + 8 + n]
        if t == b'IHDR':
            w, h, depth, ctype, _, _, inter = struct.unpack('>IIBBBBB', c)
            assert (depth, ctype, inter) == (8, 6, 0), (depth, ctype, inter)
        elif t == b'IDAT':
            idat += c
        i += 12 + n
    raw = zlib.decompress(idat)
    stride, bpp = w * 4, 4
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, out


def png_encode(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(data)


def half(w, h, px):
    """2x2 box average with premultiplied alpha."""
    W, H = w // 2, h // 2
    o = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            acc = [0, 0, 0, 0]
            for dy in (0, 1):
                for dx in (0, 1):
                    i = ((2 * y + dy) * w + 2 * x + dx) * 4
                    a = px[i + 3]
                    for k in range(3):
                        acc[k] += px[i + k] * a
                    acc[3] += a
            j = (y * W + x) * 4
            if acc[3]:
                for k in range(3):
                    o[j + k] = round(acc[k] / acc[3])
            o[j + 3] = round(acc[3] / 4)
    return W, H, o


def build(suffix, ratio, icons):
    text = git_show(f'docs/spritev2{suffix}.json').decode()
    meta = json.loads(text)
    w, h, px = png_decode(git_show(f'docs/spritev2{suffix}.png'))
    assert h == max(v['y'] + v['height'] for v in meta.values()), 'base sheet height'
    assert not set(NEW) & set(meta)
    gap = ratio
    strip = max(ih for _, iw, ih, _ in icons)
    H = h + strip
    sheet = bytearray(w * H * 4)
    sheet[:len(px)] = px
    x = 0
    for name, iw, ih, ipx in icons:
        assert x + iw <= w
        for yy in range(ih):
            r = ((h + yy) * w + x) * 4
            sheet[r:r + iw * 4] = ipx[yy * iw * 4:(yy + 1) * iw * 4]
        meta[name] = {'height': ih, 'pixelRatio': ratio, 'width': iw, 'x': x, 'y': h}
        x += iw + gap
    png_encode(os.path.join(OUT, f'spritev2{suffix}.png'), w, H, sheet)
    # a pure text append, so master's own formatting (trailing spaces, no final newline) stays
    assert text.endswith('\n}')
    add = ',\n'.join('  ' + json.dumps(n) + ': ' + json.dumps(meta[n], indent=2).replace('\n', '\n  ') for n, *_ in icons)
    out = text[:-2] + ',\n' + add + '\n}'
    assert json.loads(out) == meta
    open(os.path.join(OUT, f'spritev2{suffix}.json'), 'w').write(out)
    print(f'spritev2{suffix}: {w}x{h} -> {w}x{H}, {len(meta)} entries')


os.makedirs(OUT, exist_ok=True)
two = []
for n in NEW:
    iw, ih, ipx = png_decode(open(os.path.join(HERE, 'patterns', n + '.png'), 'rb').read())
    two.append((n, iw, ih, ipx))
build('@2x', 2, two)
build('', 1, [(n, *half(iw, ih, ipx)) for n, iw, ih, ipx in two])
