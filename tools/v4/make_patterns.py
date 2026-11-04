"""MML maastokartta fill patterns for mmlv2-v4, as transparent PNG tiles at pixel ratio 2.

The fill colour of each class is drawn by its own layer underneath; these add the MML symbol on
top, as the raster does: heath (varvikko) yellow diagonal hatch, open forest land (avoin
metsämaa) green-yellow hatch, difficult mire horizontal blue lines, boulder field (kivikko)
black triangles. Colours are MML's (2018 SLD values, confirmed on the live raster).

    python3 -I tools/v4/make_patterns.py        # writes tools/v4/patterns/*.png

They are meant for the shared Trailmap sprite (mtb-trailmap docs/spritev2*); until they are
there, the comparison tool supplies them to the map when the style asks for them.
"""
import os, struct, zlib, math

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'patterns')


def png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(data)


def canvas(n):
    return [0] * (n * n * 4)


def put(px, n, x, y, rgb, a):
    """Blend one pixel (anti-aliasing coverage a in 0..1) over a transparent tile."""
    x %= n
    y %= n
    i = (y * n + x) * 4
    old = px[i + 3] / 255
    na = a + old * (1 - a)
    if na <= 0:
        return
    for k in range(3):
        px[i + k] = round((rgb[k] * a + px[i + k] * old * (1 - a)) / na)
    px[i + 3] = round(na * 255)


def hatch(n, rgb, period, width, direction=1, alpha=1.0):
    """Diagonal stripes; n must be a multiple of period so the tile repeats seamlessly."""
    px = canvas(n)
    for y in range(n):
        for x in range(n):
            d = (x + 0.5 + direction * (y + 0.5)) % period
            dist = min(d, period - d) / math.sqrt(2)   # perpendicular distance to the nearest stripe axis
            cov = max(0.0, min(1.0, width / 2 + 0.5 - dist))
            if cov > 0:
                put(px, n, x, y, rgb, cov * alpha)
    return px


def hlines(n, rgb, period, width):
    px = canvas(n)
    for y in range(n):
        d = y % period
        cov = max(0.0, min(1.0, width - d))
        if cov > 0:
            for x in range(n):
                put(px, n, x, y, rgb, cov)
    return px


def triangles(n, rgb, size, points):
    """Filled upward triangles at the given centres (tile px)."""
    px = canvas(n)
    h = size * math.sqrt(3) / 2
    for cx, cy in points:
        for yy in range(int(cy - h), int(cy + h) + 2):
            for xx in range(int(cx - size), int(cx + size) + 2):
                # 4x4 supersampling for coverage
                cov = 0
                for sy in range(4):
                    for sx in range(4):
                        px_, py_ = xx + (sx + 0.5) / 4, yy + (sy + 0.5) / 4
                        ty = (py_ - (cy - h / 2)) / h        # 0 at apex, 1 at base
                        if 0 <= ty <= 1 and abs(px_ - cx) <= ty * size / 2:
                            cov += 1
                if cov:
                    put(px, n, xx, yy, rgb, cov / 16)
    return px


os.makedirs(OUT, exist_ok=True)
N = 32  # 16 css px at pixel ratio 2
# The raster's hatch scales with zoom; a pattern does not, so there is a fine version for z11-13
# and a bold one from z14 (the style switches with a zoom step)
png(os.path.join(OUT, 'mmlhc_varvikko.png'), N, N, hatch(N, (242, 204, 0), 16, 6))
png(os.path.join(OUT, 'mmlhc_varvikko_fine.png'), 24, 24, hatch(24, (242, 204, 0), 12, 2.2))
png(os.path.join(OUT, 'mmlhc_avoin_metsamaa.png'), N, N, hatch(N, (184, 217, 0), 16, 5, -1))
png(os.path.join(OUT, 'mmlhc_avoin_metsamaa_fine.png'), 24, 24, hatch(24, (184, 217, 0), 12, 2, -1))
png(os.path.join(OUT, 'mmlhc_suo_vaikea.png'), N, N, hlines(N, (64, 176, 230), 8, 2.4))
png(os.path.join(OUT, 'mmlhc_kivikko.png'), 48, 48, triangles(48, (0, 0, 0), 9, [(10, 12), (34, 20), (18, 38), (42, 44)]))


# ---------------------------------------------------------------- point symbols (sprite batch 2)
# MML maastokartta point symbols for the classes of finland_ways symboli / maasto_piste / poi,
# drawn from the raster's look. Shapes are lists of thick segments, polygons and circles in tile
# px; rasterised with 4x4 supersampling.

def seg_dist(px_, py_, a, b):
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((px_ - x1) * dx + (py_ - y1) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px_ - (x1 + t * dx), py_ - (y1 + t * dy))


def inside(px_, py_, poly):
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > py_) != (y2 > py_) and px_ < (x2 - x1) * (py_ - y1) / (y2 - y1) + x1:
            c = not c
    return c


def symbol(w, h, rgb, segs=(), width=2.4, polys=(), discs=(), rings=()):
    px = [0] * (w * h * 4)
    for y in range(h):
        for x in range(w):
            cov = 0
            for sy in range(4):
                for sx in range(4):
                    X, Y = x + (sx + 0.5) / 4, y + (sy + 0.5) / 4
                    hit = any(seg_dist(X, Y, a, b) <= width / 2 for a, b in segs) \
                        or any(inside(X, Y, p) for p in polys) \
                        or any(math.hypot(X - cx, Y - cy) <= r for cx, cy, r in discs) \
                        or any(abs(math.hypot(X - cx, Y - cy) - r) <= width / 2 for cx, cy, r in rings)
                    cov += hit
            if cov:
                i = (y * w + x) * 4
                px[i:i + 4] = [rgb[0], rgb[1], rgb[2], round(255 * cov / 16)]
    return px


K = (0, 0, 0)
SYM = {
    # Λ (32710)
    'mmlhc_sym_32710': (20, 24, K, dict(segs=[((3, 22), (10, 2)), ((10, 2), (17, 22))])),
    # small ring over Λ (32714)
    'mmlhc_sym_32714': (20, 28, K, dict(segs=[((3, 26), (10, 13)), ((10, 13), (17, 26))], rings=[(10, 7, 4.5)])),
    # ⊥ (maasto_piste 34600)
    'mmlhc_sym_34600': (14, 14, K, dict(segs=[((7, 2), (7, 12)), ((1.5, 12), (12.5, 12))])),  # ~0.7x: the raster's ⊥ is small
    # rock point (maasto_piste 34100): small dot in rock grey-mauve
    'mmlhc_sym_34100': (10, 10, (168, 150, 160), dict(discs=[(5, 5, 3.4)])),
    # crossing / barrier mark on a way (symboli 12200), rotated by the style
    'mmlhc_sym_12200': (20, 20, K, dict(segs=[((3, 3), (17, 17)), ((17, 3), (3, 17))])),
    # stream direction arrow (symboli 36392), points up, rotated by the style
    'mmlhc_sym_36392': (16, 28, (0, 128, 255), dict(segs=[((8, 26), (8, 6))], polys=[[(2, 10), (8, 1), (14, 10)]])),
    # open arc (symboli 32713), opening to the lower right as in the raster
    'mmlhc_sym_32713': (20, 20, K, dict(segs=[((10 + 7 * math.cos(math.radians(a)), 10 - 7 * math.sin(math.radians(a))),
                                               (10 + 7 * math.cos(math.radians(a + 15)), 10 - 7 * math.sin(math.radians(a + 15))))
                                              for a in range(-30, 240, 15)])),
    # "II" (symboli 32891, on meadows)
    'mmlhc_sym_32891': (16, 20, K, dict(segs=[((5, 3), (5, 17)), ((11, 3), (11, 17))])),
    # spring (maasto_piste 36100): blue dot in a black cup
    'mmlhc_sym_36100': (20, 20, K, dict(segs=[((3, 2), (3, 11)), ((17, 2), (17, 11))], rings=[])),
    # blue V (maasto_piste 36400)
    'mmlhc_sym_36400': (20, 22, (0, 128, 255), dict(segs=[((3, 2), (10, 20)), ((10, 20), (17, 2))])),
    # mast (poi 44800, MTK masto): filled disc with a cross, as in the raster
    'mmlhc_poi_44800': (24, 24, K, dict(segs=[((12, 1), (12, 23)), ((1, 12), (23, 12))], discs=[(12, 12, 5)])),
    # campfire site (poi 45710, MTK tulentekopaikka): three triangles pointing to the centre
    'mmlhc_poi_45710': (28, 22, K, dict(polys=[[(14.0, 11.5), (20.0, 0.5), (8.0, 0.5)], [(15.47, 13.31), (25.08, 20.98), (27.37, 10.22)], [(12.53, 13.31), (0.63, 10.22), (2.92, 20.98)]])),
}
# Line symbols are drawn thin: the raster's symbols are large but fine-lined, not bold
THIN = {'mmlhc_sym_32710', 'mmlhc_sym_32713', 'mmlhc_sym_32714', 'mmlhc_sym_32891', 'mmlhc_sym_34600',
        'mmlhc_sym_12200', 'mmlhc_sym_36400'}
for name, (w, h, rgb, kw) in SYM.items():
    if name in THIN:
        kw = {**kw, 'width': 1.6}
    px = symbol(w, h, rgb, **kw)
    if name == 'mmlhc_sym_36100':
        # the cup's bottom arc in black, the water dot in blue
        cup = symbol(w, h, K, rings=[(10, 11, 7)], width=1.8)
        for y in range(h):
            for x in range(w):
                i = (y * w + x) * 4
                if y >= 11 and cup[i + 3]:
                    px[i:i + 4] = cup[i:i + 4]
        dot = symbol(w, h, (0, 128, 255), discs=[(10, 10, 4.5)])
        for i in range(0, len(px), 4):
            if dot[i + 3]:
                px[i:i + 4] = dot[i:i + 4]
    png(os.path.join(OUT, name + '.png'), w, h, px)

print('written', sorted(os.listdir(OUT)))
