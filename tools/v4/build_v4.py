"""Derives mmlv2-v4 from the released -v3 style (tag v3.1). Every run starts from the same base,
so the result is reproducible while v4 is under review:

    python3 -I tools/v4/build_v4.py [OUT]        # default OUT: mmlv2-style-v4.json

v4 is released (tags v4.x on main, served as mmlv2-style.json): that file is the source of truth
and is edited directly; this script is the record of how it was made.

Principle (owner, 28 Oct): mmlv2 is the high-contrast MML map. Colours are MML's saturated
maastokartta palette as the raster shows it (the 2018 SLD values, confirmed by sampling the live
WMTS tiles), symbols are opaque black, and line weights grow with zoom the way the raster's do
(roughly doubling per level from z14), calibrated with `shoot.mjs --measure`. Ways (owner's
option C): MML roads, tracks and cycle/footways as in the raster, plus OSM paths.
"""
import json, sys, copy, os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'mmlv2-style-v4.json')
S = json.loads(subprocess.check_output(['git', '-C', REPO, 'show', 'v3.1:mmlv2-style.json']))
S['metadata']['trailmap:variant'] = 'v4'
L = S['layers']


def idx(i):
    for n, l in enumerate(L):
        if l['id'] == i:
            return n
    raise KeyError(i)


def get(i):
    return L[idx(i)]


def both(i):
    """The layer and its '(ways)' twin, when the archive split made one."""
    out = [get(i)]
    for l in L:
        if l['id'] == i + ' (ways)':
            out.append(l)
    return out


def interp(stops, base=1.5):
    e = ['interpolate', ['exponential', base], ['zoom']]
    for z, v in stops:
        e += [z, v]
    return e


def ground(z12, z13, z14, low=None):
    """Width that follows the raster: given up to z14, then about x1.8 per level (the raster's
    lines are drawn in ground units, so they double per level; slightly less keeps z17+ sane)."""
    stops = list(low or []) + [(12, z12), (13, z13), (14, z14), (15, z14 * 1.8), (16, z14 * 3.4), (17, z14 * 6.4), (18, z14 * 12), (20, z14 * 40)]
    return interp(stops, 2)


VIS = {'visibility': 'visible'}

# ---------------------------------------------------------------- palette (MML raster)
P = {
    'water': '#80ffff',
    'water_edge': '#0080ff',
    'stream': '#0080ff',
    'water_text': '#0066cc',
    'road': '#cc1400',
    'case': '#000000',
    'black': '#000000',
    'contour': '#ab5700',
    'field': '#ffd980',
    'meadow': '#fff266',
    'park': '#b3ff66',
    'cemetery': '#80ff80',
    'sport': '#e6ff80',
    'rock': '#d1c7d1',
    'sand': '#ffff66',
    'shore_open': '#ffff40',
    'gravel_pit': '#e6cc80',
    'peat': '#cfb873',
    'quarry': '#ffffd9',
    'storage': '#f2f2e6',
    'mire_open': '#d1cc40',
    'mire_wooded': '#c7ebeb',
    'mire_wet': '#e6f5f5',
    'silting': '#b3ffff',
    'border': '#4d00ff',
    'reserve': '#00b300',
    'building_res': '#333333',
}

# ---------------------------------------------------------------- clean-ups (phase 0)
# Hillshade: varjomap to z14 inside Finland, near the app raster's 20 %
S['sources']['mml_hillshade'].update({'minzoom': 10, 'maxzoom': 14, 'bounds': [19.2, 59.5, 31.7, 70.2]})
get('mml_hillshade')['paint']['raster-opacity'] = interp([(11, 0.15), (13, 0.2), (15, 0.22)], 1)

# Finland bounds on the Finland-only sources (v81.9 does the same)
for s in ('lipas_routes', 'lipas_points', 'kiinteisto-avoin'):
    S['sources'][s]['bounds'] = [19.08, 59.45, 31.59, 70.1]

# ---------------------------------------------------------------- contours
# Guard features without an elevation; opaque MML brown; raster-like weights
idx20 = ['==', ['%', ['get', 'korkeusarvo'], 20000], 0]


def contour_w(i20):
    stops = [(12, (0.9, 0.5)), (13, (1.3, 0.75)), (14, (2.0, 1.2)), (15, (3.6, 2.2)), (16, (6.6, 4.1)), (17, (12, 7.7)), (20, (70, 48))]
    return interp([(z, ['case', i20, a, b]) for z, (a, b) in stops], 2)


c = get('korkeus_viiva')
c['filter'] = ['all', ['has', 'korkeusarvo'], ['==', ['%', ['get', 'korkeusarvo'], 5000], 0]]
c['paint'] = {'line-color': P['contour'], 'line-width': contour_w(idx20)}
c = get('korkeus_apuviiva')
c['filter'] = ['all', ['has', 'korkeusarvo'], ['!=', ['%', ['get', 'korkeusarvo'], 5000], 0]]
c['paint'] = {'line-color': P['contour'], 'line-opacity': interp([(13, 0), (13.5, 1)], 1),
              'line-width': ground(0.5, 0.75, 1.2), 'line-dasharray': [6, 2]}
c = get('korkeus_viiva_pieni_zoom')
idx20s = ['==', ['%', ['coalesce', ['get', 'korkeus'], 1], 20], 0]
c['paint'] = {
    'line-color': P['contour'],
    'line-opacity': interp([(8, 0.25), (10, 0.6), (11, 0.85), (12, 1)], 1),
    'line-width': interp([(8, ['case', idx20s, 0.5, 0.3]), (11, ['case', idx20s, 0.8, 0.45]), (12, ['case', idx20s, 0.9, 0.5]), (13, ['case', idx20s, 1.2, 0.7])], 1.5),
}

# ---------------------------------------------------------------- land
LU = ['match', ['get', 'kohdeluokka'],
      32111, P['quarry'],          # maa-aineksenottoalue
      32112, P['gravel_pit'],      # karkea kivennäisaines
      32113, P['peat'],            # hieno / turvetuotanto
      32200, P['cemetery'],
      32300, P['quarry'],          # kaatopaikka
      32500, P['quarry'],          # louhos
      32611, P['field'],           # pelto
      32612, P['field'],           # puutarha
      32800, P['meadow'],          # niitty
      32900, P['park'],
      33100, P['sport'],
      34300, P['sand'],
      38900, P['storage'],
      '#f7f7f3']
for l in both('maankaytto'):
    l['paint']['fill-color'] = copy.deepcopy(LU)
    l['paint']['fill-outline-color'] = 'hsla(0, 0%, 0%, 0)'

# Black edges of fields, gardens, parks and cemeteries, as heavy as the raster's
edge_at = idx('maankaytto-asutus')
edges = []
for l in both('maankaytto'):
    e = {'id': l['id'].replace('maankaytto', 'maankaytto-reuna'), 'type': 'line', 'source': l['source'],
         'source-layer': 'maankaytto', 'minzoom': 11,
         'filter': ['match', ['get', 'kohdeluokka'], [32611, 32612, 32200, 32900, 33100, 32111], True, False],
         'layout': {'line-join': 'round', **VIS},
         'paint': {'line-color': P['black'], 'line-opacity': interp([(11, 0), (12, 1)], 1), 'line-width': ground(0.4, 0.55, 0.8)}}
    edges.append(e)
L[edge_at + 1:edge_at + 1] = edges

MA = ['match', ['get', 'kohdeluokka'],
      [35412, 35422, 35401, 35402], P['mire_wooded'],
      [35411, 35421], P['mire_open'],
      34100, P['rock'],
      [34700, 38600], 'hsla(0, 0%, 100%, 0)',  # kivikko: triangles only, over whatever is underneath (MML)
      34300, P['sand'],
      39130, P['shore_open'],
      38300, P['silting'],
      [38700, 38400, 35300], P['mire_wet'],
      39120, 'hsla(48, 100%, 55%, 0.08)',  # varvikko: light tint under the yellow hatch (MML: hatch on white)
      39110, 'hsla(70, 100%, 45%, 0.12)',  # avoin metsämaa: same, green-yellow
      33000, P['quarry'],
      'hsla(0, 0%, 100%, 0)']
# Rock and boulder fields over heath where both are mapped (the raster shows the rock)
MA_SORT = ['match', ['get', 'kohdeluokka'], [34100, 34700, 38600], 2, [39110, 39120], 0, 1]
for l in both('maasto_alue') + both('maasto_alue_vesi'):
    l['paint']['fill-color'] = copy.deepcopy(MA)
    l['paint']['fill-outline-color'] = ['match', ['get', 'kohdeluokka'], 33000, '#000000', 'hsla(0, 0%, 100%, 0)']
    l['layout'] = {**(l.get('layout') or {}), 'fill-sort-key': MA_SORT}
for l in both('maasto_alue_vesi'):
    l['paint']['fill-opacity'] = 1


# MML symbol patterns on top of the class colours (tools/v4/make_patterns.py; the images go into
# the shared Trailmap sprite). Heath and open forest land: diagonal hatch; boulder fields: black
# triangles; difficult mires: horizontal blue lines.
def pattern_layers(base_id, suffix, classes, image, minzoom=11):
    out = []
    for l in both(base_id):
        out.append({'id': l['id'].replace(base_id, f'{base_id}-{suffix}'), 'type': 'fill', 'source': l['source'],
                    'source-layer': l['source-layer'], 'minzoom': minzoom,
                    'filter': ['match', ['get', 'kohdeluokka'], classes, True, False],
                    'layout': VIS.copy(),
                    'paint': {'fill-pattern': image, 'fill-opacity': interp([(minzoom, 0), (minzoom + 0.7, 1)], 1)}})
    return out


del L[idx('landcover-clearcut_mml (ways)')]
del L[idx('landcover-clearcut_mml')]
at = idx('maasto_alue (ways)') + 1
# Rock and boulder fields are drawn again over the heath hatch, as in the raster
rock_over = []
for l in both('maasto_alue'):
    r = copy.deepcopy(l)
    r['id'] = l['id'].replace('maasto_alue', 'maasto_alue-kallio')
    r['filter'] = ['==', ['get', 'kohdeluokka'], 34100]
    r['layout'] = VIS.copy()
    rock_over.append(r)
L[at:at] = (pattern_layers('maasto_alue', 'varvikko', [39120], ['step', ['zoom'], 'mmlhc_varvikko_fine', 14.5, 'mmlhc_varvikko'])
            + pattern_layers('maasto_alue', 'avoin-metsamaa', [39110], ['step', ['zoom'], 'mmlhc_avoin_metsamaa_fine', 14.5, 'mmlhc_avoin_metsamaa'])
            + rock_over
            + pattern_layers('maasto_alue', 'kivikko', [34700, 38600], 'mmlhc_kivikko', 11))
at = idx('maasto_alue_vesi (ways)') + 1
L[at:at] = pattern_layers('maasto_alue_vesi', 'suo-vaikea', [35421, 35422], 'mmlhc_suo_vaikea')

# Single boulders (kivi) a little larger
get('rocks')['layout']['icon-size'] = interp([(13, 0.45), (15, 0.8), (17, 1.6)], 1)

# Built-up wash: gone by z12, as in the raster at street zooms
for l in both('maankaytto-asutus'):
    l['paint']['fill-opacity'] = interp([(10, 1), (12, 0)], 1)
    l['maxzoom'] = 12

# ---------------------------------------------------------------- water
for i in ('water', 'water-lake-osm', 'water-mml', 'water-intermittent-osm'):
    get(i)['paint']['fill-color'] = P['water']
w = get('vesisto_alue_reuna')
w['paint']['line-color'] = P['water_edge']
w['paint']['line-width'] = ground(0.8, 1.1, 1.8, [(9, 0.4)])
for l in both('vesisto_viiva'):
    l['paint']['line-color'] = P['stream']
    wide = ['==', ['get', 'kohdeluokka'], 36312]   # 2-5 m; 36311 < 2 m (ditches, brooks)
    l['paint']['line-width'] = interp([(9, ['case', wide, 0.7, 0.4]), (12, ['case', wide, 1.1, 0.7]), (13, ['case', wide, 1.6, 1.0]),
                                       (14, ['case', wide, 2.4, 1.5]), (15, ['case', wide, 4.3, 2.7]), (16, ['case', wide, 8, 5.1]),
                                       (17, ['case', wide, 15, 9.6]), (20, ['case', wide, 90, 60])], 2)

# ---------------------------------------------------------------- buildings
# Residential near-black as in the raster; from z12 (the app's raster shows tiles two levels
# deeper, so buildings are there at z12)
b = get('building-top-mml')
b['paint']['fill-color'][3] = P['building_res']
b['paint']['fill-color'][15] = P['building_res']
b['minzoom'] = 12
b['paint']['fill-opacity'] = interp([(12, 0), (12.5, 1)], 1)
b['paint']['fill-outline-color'] = '#000000'
b = get('building-mml')
b['minzoom'] = 12
b['paint']['fill-opacity'] = interp([(12, 0), (12.5, 1)], 1)

# ---------------------------------------------------------------- boundaries
h = get('hallintorajat')
# the tiles carry no attributes on hallintoalue, so border levels cannot be told apart: lighter at overview zooms
h['paint'] = {
    'line-color': P['border'],
    'line-width': ground(1.3, 1.6, 2.0, [(6, 0.6), (10, 1.1)]),
    'line-dasharray': [5, 1.5, 1, 1.5],
    'line-opacity': interp([(6, 0.35), (8, 0.6), (10, 0.9)], 1),
}

# Nature reserves: MML green dashed edge and a ticked inner band (short dashes on a wide line
# read as MML's hatch without a sprite pattern)
o = get('protected_area-outline-outer-mml')
o['paint'] = {
    'line-color': P['reserve'],
    'line-opacity': interp([(10, 0), (11, 1)], 1),
    'line-width': ground(1.2, 1.5, 2.0, [(11, 1.0)]),
    'line-dasharray': [4, 1.5],
}
o = get('protected_area-outline-inner-mml')
o['paint'] = {
    'line-color': P['reserve'],
    'line-opacity': interp([(10, 0), (11, 1)], 1),
    'line-width': ground(3.5, 4.5, 6, [(11, 3)]),
    'line-offset': ground(1.75, 2.25, 3, [(11, 1.5)]),
    'line-dasharray': [0.2, 0.4],
}
get('protected_area-fill-mml')['paint']['fill-color'] = P['reserve']
get('protected_area-fill-mml')['paint']['fill-outline-color'] = P['reserve']
# No green wash over parks where people hike (the raster has none): only a faint hint at overview zooms
get('protected_area-fill-mml')['paint']['fill-opacity'] = interp([(5, 0), (5.5, 0.1), (8, 0.08), (9, 0)], 1)
get('protected_area-fill-mml')['maxzoom'] = 9

# ---------------------------------------------------------------- other symbols
for i in ('cliffs-line', 'cliffs-dashes'):
    get(i)['paint']['line-opacity'] = interp([(11, 0), (12.5, 1)], 1)
get('cliffs-line')['paint']['line-width'] = ground(1.3, 1.7, 2.3)
get('cliffs-dashes')['paint']['line-width'] = ground(2.8, 3.5, 4.6)
get('cliffs-dashes')['paint']['line-offset'] = ground(1.6, 2, 2.6)

for i in ('power-line-minor', 'power-line-minor (ways)', 'power-line-major', 'power-line-major (ways)'):
    get(i)['paint']['line-color'] = '#000000'

# ---------------------------------------------------------------- labels
for i in ('nimisto-maasto-vedet', 'nimisto-maasto-vedet-mat-prio'):
    get(i)['paint']['text-color'] = ['match', ['get', 'teema'], 'Vedet', P['water_text'], '#000000']
n = get('nimisto')
n['paint']['text-color'] = ['match', ['get', 'teema'], 'Vedet', P['water_text'], 'Suojellut kohteet', '#008f00', '#000000']
get('nimisto_luonnopuistot')['paint']['text-color'] = '#008f00'
get('tienimet')['paint']['text-color'] = '#000000'


def scale_outputs(e, k):
    """Multiply the output values of a (possibly nested) interpolate/step expression."""
    if isinstance(e, (int, float)):
        return round(e * k, 1)
    if isinstance(e, list) and e and e[0] == 'interpolate':
        return e[:3] + [v if i % 2 == 0 else scale_outputs(v, k) for i, v in enumerate(e[3:])]
    if isinstance(e, list) and e and e[0] == 'step':
        return e[:2] + [scale_outputs(e[2], k)] + [v if i % 2 == 0 else scale_outputs(v, k) for i, v in enumerate(e[3:])]
    if isinstance(e, dict) and 'stops' in e:
        return {**e, 'stops': [[z, scale_outputs(v, k)] for z, v in e['stops']]}
    return e


# Names grow with zoom as the raster's do (its lettering grows from one tile level to the next,
# and the app shows it two levels deeper), about x1.25 per level from z12, capped at z18.
# Base size at z12 by MML's prioriteetti: 1-4 landmark fells, big lakes, towns; 9+ small features.
prio = ['get', 'prioriteetti']
NAME_GROWTH = [(8, 0.8), (10, 0.9), (12, 1.0), (14, 1.3), (16, 1.65), (18, 2.0)]


def name_size(base_by_prio, first_zoom=None):
    stops = []
    for z, k in NAME_GROWTH:
        if first_zoom is not None and z < first_zoom:
            continue
        stops.append((z, ['interpolate', ['linear'], prio] + [x for p, s in base_by_prio for x in (p, round(s * k, 1))]))
    if first_zoom is not None:
        stops = [(first_zoom - 0.5, 0)] + stops
    return interp(stops, 1)


get('nimisto')['layout']['text-size'] = name_size([(1, 24), (3, 19), (5, 16), (7, 14), (10, 12.5)])
get('nimisto-maasto-vedet-mat-prio')['layout']['text-size'] = name_size([(1, 20), (4, 18), (7, 14.5), (9, 13), (22, 12)], 9.5)
get('nimisto-maasto-vedet')['layout']['text-size'] = name_size([(23, 12), (40, 11)], 13)
get('nimisto_luonnopuistot')['layout']['text-size'] = interp([(8, 14), (12, 18), (16, 26)], 1)
get('nimisto_kunnat')['layout']['text-size'] = interp([(6, 16), (10, 22), (14, 32)], 1.2)

# Names are placed before POI labels and icons (they sit above them in the stack), so a fell or
# lake name is not hidden by a LIPAS hut label next to it, as Kaunispää was
NAME_IDS = ['tienimet', 'ls_mml-selite', 'nimisto-maasto-vedet', 'nimisto-maasto-vedet-mat-prio',
            'nimisto', 'nimisto_luonnopuistot', 'nimisto_kunnat']
names = [L.pop(idx(i)) for i in NAME_IDS]
L.extend(names)

# Contour labels on index contours (every 20 m), in contour brown along the line, as in the raster.
# Below z13 the tiles carry `korkeus` (m), from z13 `korkeusarvo` (mm).
elev = ['coalesce', ['/', ['get', 'korkeusarvo'], 1000], ['get', 'korkeus']]
L.insert(idx('tienimet'), {
    'id': 'korkeus-label', 'type': 'symbol', 'source': 'mml_contours', 'source-layer': 'korkeus', 'minzoom': 12,
    'filter': ['all', ['==', ['geometry-type'], 'LineString'],
               ['any', ['has', 'korkeusarvo'], ['has', 'korkeus']],
               ['==', ['%', elev, 20], 0]],
    'layout': {'symbol-placement': 'line', 'symbol-spacing': interp([(12, 250), (15, 350)], 1),
               'text-field': ['to-string', ['round', elev]], 'text-font': ['Noto Sans Regular'],
               'text-size': interp([(12, 10), (14, 12), (16, 15), (18, 19)], 1), 'text-max-angle': 25,
               'text-padding': 4, **VIS},
    'paint': {'text-color': P['contour'], 'text-halo-color': 'rgba(255,255,255,0.9)', 'text-halo-width': 1.5},
    # v4.2: marks the start of the trailing label block (contour labels, MML point symbols, map texts,
    # names), like the water-start marker; app builders slot segment overlays before the first kept
    # layer with it. ways_only keeps the layer in ortho mode, as it was without metadata (owner, N42)
    'metadata': {'trailmap:group': 'labels-start', 'trailmap:ways_only': True},
})

# ---------------------------------------------------------------- v4.1: MML point layers
# finland_ways carries MML's symboli and poi layers and the maasto_piste / selite / korkeus point
# classes topo and contours lack (R-0160-13). Icons: tools/v4/make_patterns.py, sprite batch 2.
# `suunta` is the symbol direction in 1/10000 rad.
rot = ['*', ['coalesce', ['get', 'suunta'], 0], -0.0057296]
# Measured on the raster (Nuuksio): a Λ is ~15-22 px tall at z14 and ~40 px at z15.5, drawn with a
# ~1 px line. So large but fine-lined: the icons have thin strokes and this size curve
sym_size = interp([(13, 1.3), (14, 1.6), (15, 2.0), (16, 3.2), (17, 5.0)], 1)


def point_layer(i, sl, classes, image, minzoom, rotate=None, extra_layout=None):
    lay = {'icon-image': image, 'icon-size': sym_size, 'icon-allow-overlap': True, 'icon-ignore-placement': True, **VIS}
    if rotate is not None:
        lay.update({'icon-rotate': rotate, 'icon-rotation-alignment': 'map'})
    lay.update(extra_layout or {})
    return {'id': i, 'type': 'symbol', 'source': 'mml_ways', 'source-layer': sl, 'minzoom': minzoom,
            'filter': ['match', ['get', 'kohdeluokka'], classes, True, False], 'layout': lay, 'paint': {}}


icon_by_class = lambda prefix, classes: ['match', ['get', 'kohdeluokka']] + [x for c in classes for x in (c, f'{prefix}{c}')] + ['']
points = [
    point_layer('mml-maasto-piste-ways', 'maasto_piste', [34100, 34600, 36100, 36400], icon_by_class('mmlhc_sym_', [34100, 34600, 36100, 36400]), 13),
    point_layer('mml-symboli', 'symboli', [32710, 32713, 32714, 32891], icon_by_class('mmlhc_sym_', [32710, 32713, 32714, 32891]), 13),
    # 22395 (zigzag across a road) left out on review: reads as noise
    point_layer('mml-symboli-suunta', 'symboli', [12200, 36392], icon_by_class('mmlhc_sym_', [12200, 36392]), 14, rot),
    point_layer('mml-poi', 'poi', [44800, 45710], icon_by_class('mmlhc_poi_', [44800, 45710]), 13),
    # Lake water level (36291), MML blue, one decimal
    {'id': 'mml-vedenpinta', 'type': 'symbol', 'source': 'mml_ways', 'source-layer': 'korkeus', 'minzoom': 14,
     'filter': ['==', ['get', 'kohdeluokka'], 36291],
     'layout': {'text-field': ['number-format', ['/', ['get', 'keskikorkeus'], 1000], {'min-fraction-digits': 1, 'max-fraction-digits': 1}],
                'text-font': ['Noto Sans Regular'], 'text-size': interp([(14, 11), (16, 14), (18, 18)], 1), **VIS},
     'paint': {'text-color': '#0050a0', 'text-halo-color': 'rgba(255,255,255,0.8)', 'text-halo-width': 1}},
    # Map texts (selite) the topo archive lacks, e.g. "näkötorni", Finnish (or untagged) only
    {'id': 'mml-selite-ways', 'type': 'symbol', 'source': 'mml_ways', 'source-layer': 'selite', 'minzoom': 14,
     'filter': ['all', ['has', 'teksti'], ['match', ['coalesce', ['get', 'kielikoodi'], 'fin'], 'fin', True, False],
                ['!=', ['get', 'kohdeluokka'], 12181]],
     'layout': {'text-field': ['get', 'teksti'], 'text-font': ['Noto Sans Regular'], 'text-max-width': 10,
                'text-size': interp([(14, 11), (16, 14), (18, 18)], 1), **VIS},
     'paint': {'text-color': '#000000', 'text-halo-color': 'rgba(255,255,255,0.85)', 'text-halo-width': 1.2}},
]
at = idx('tienimet')
L[at:at] = points
# National park names: the topo selite 72603 holds only the word "kansallispuisto", so the name
# comes from nimisto (laji Kansallispuisto/Luonnonpuisto), drawn as the raster does: bold MML green
np_ = get('nimisto_luonnopuistot')
np_['layout']['text-font'] = ['Noto Sans Bold']
np_['layout']['text-max-width'] = 12
np_['paint']['text-color'] = '#00a000'

# Buildings as in the raster: flat (no offset shadow), heavy black outline that grows with zoom,
# residential very dark grey inside the black edge
b = get('building-top-mml')
b['paint'].pop('fill-translate', None)
b['paint']['fill-outline-color'] = 'hsla(0, 0%, 0%, 0)'
b['paint']['fill-color'][3] = '#3a3a3a'
b['paint']['fill-color'][15] = '#3a3a3a'
# holiday homes as the raster shows them (#00ff80 in MML's palette), a touch deeper under the hillshade
b['paint']['fill-color'] = [('#00e676' if v == '#00cc66' else v) for v in b['paint']['fill-color']]
b['paint']['fill-antialias'] = True
get('building-mml')['layout'] = {'visibility': 'none'}
L.insert(idx('building-top-mml') + 1, {
    'id': 'building-outline-mml', 'type': 'line', 'source': b['source'], 'source-layer': b['source-layer'], 'minzoom': 12,
    'filter': ['==', ['geometry-type'], 'Polygon'],
    'layout': {'line-join': 'miter', **VIS},
    'paint': {'line-color': '#000000', 'line-opacity': interp([(12, 0), (12.5, 1)], 1),
              'line-width': interp([(12, 0.4), (13, 0.8), (14, 1.5), (15, 2.6), (16, 4.4), (17, 7.5), (18, 13)], 1.5)},
})
# OSM buildings (outside MML coverage) the same way: no offset
for i in ('building-osm', 'building-top-osm'):
    get(i)['paint'].pop('fill-translate', None)
# Car parks and other liikenne areas: thin black edge as in the raster
get('parkkipaikka_alue')['paint']['fill-outline-color'] = '#000000'

get('lautta ja lossi')['paint']['line-color'] = '#cc4d00'

# ---------------------------------------------------------------- POIs from mtb-trailmap v81.9
# Break, supplies and car parking: drinking water taps, springs, fountains, wells; no street-side
# parking. Only filters and layout are taken; paint differs only in notation.
MTB_REPO = os.path.join(os.path.dirname(REPO), 'mtb-trailmap')
V81 = {l['id']: l for l in json.loads(subprocess.check_output(
    ['git', '-C', MTB_REPO, 'show', 'v81.9:style_base_v2.json']))['layers']}
for l in L:
    if l['id'].startswith(('poi_separate-break-', 'poi_separate-supplies_maintenance-', 'poi_separate-car_parking-')):
        src = V81[l['id']]
        l['filter'] = copy.deepcopy(src['filter'])
        vis = (l.get('layout') or {}).get('visibility')
        l['layout'] = copy.deepcopy(src.get('layout') or {})
        if vis:
            l['layout']['visibility'] = vis

# Drop the test layer and the hidden leftovers
for i in ('tiet-testi', 'hw-path-case', 'bridge-path-case', 'bridge-track-case', 'bridge-track-line-hc'):
    del L[idx(i)]

# ---------------------------------------------------------------- ways
# Every MML road/rail/path layer and the OSM path/track layers between them are replaced by one
# generated block: tunnels, MML tracks and cycle/footways, OSM paths, surface roads, bridges.
ROADS = [12111, 12112, 12121, 12122, 12131, 12132, 12141]
RAIL = [14111, 14110, 14112, 14131, 14151, 14152, 14121]

first = idx('tiet tunnelissa')
last = idx('rautatie_taytto, sillalla 5')
for i in range(last, first - 1, -1):
    l = L[i]
    if l.get('source-layer') == 'liikenne' or (l.get('source') == 'osm' and l.get('source-layer') == 'transportation' and not l['id'].startswith('bridge-path/track')):
        del L[i]
insert_at = idx('bridge-path/track/cw/fw-railings')
bridge_osm = [L.pop(idx('bridge-path/track/cw/fw-railings')), L.pop(idx('bridge-path/track/cw/fw-floor'))]
# v4.3: the boardwalk look (railings and floor) from z12, full at z13; further out a bridged path
# is drawn like the path it continues (osm-bridge-path below)
for l in bridge_osm:
    l['minzoom'] = 12
    l['paint']['line-opacity'] = interp([(12, 0), (13, 1)], 1)

cls = ['get', 'kohdeluokka']
rank = ['match', cls, [12111, 12112], 7, [12121, 12122], 6, [12131, 12132], 5, 12141, 4, 0]


def by_class(I, II, III, aj, default=0):
    return ['match', cls, [12111, 12112], I, [12121, 12122], II, [12131, 12132], III, 12141, aj, default]


# Fill widths per class (CSS px); casing adds a black edge on both sides. Ajotie is a single
# black line with no casing.
FILL = [(6, (1.3, 0.9, 0, 0)), (9, (2.2, 1.6, 1.0, 0.5)), (11, (2.6, 2.0, 1.4, 0.8)), (12, (3.0, 2.4, 1.7, 1.1)),
        (13, (3.4, 2.8, 2.0, 1.5)), (14, (4.4, 3.6, 2.6, 2.2)), (15, (7.4, 6.4, 4.6, 4)), (16, (14, 12, 9, 7.5)),
        (17, (26, 22, 17, 14)), (20, (160, 140, 100, 80))]
# The raster's casing is a heavy black edge on a narrower red core (Seinäjoki and Helsinki, z14-15)
EDGE = {6: 0.5, 9: 0.5, 11: 0.6, 12: 0.75, 13: 0.9, 14: 1.2, 15: 1.9, 16: 3.4, 17: 6, 20: 32}


def fill_w():
    return interp([(z, by_class(*v)) for z, v in FILL], 2)


def case_w():
    return interp([(z, by_class(*(x + 2 * EDGE[z] if x else 0 for x in v[:3]), 0)) for z, v in FILL], 2)


def level(f):
    return ['==', ['get', 'tasosijainti'], f] if isinstance(f, int) else f


def road_layers(suffix, lvl, extra=None):
    flt = ['all', ['==', ['geometry-type'], 'LineString'], ['match', cls, ROADS, True, False], level(lvl)]
    case = {
        'id': f'road-case-{suffix}', 'type': 'line', 'source': 'mml_ways', 'source-layer': 'liikenne',
        'filter': copy.deepcopy(flt),
        'layout': {'line-cap': 'butt' if suffix.startswith('bridge') else 'round', 'line-join': 'round', 'line-sort-key': rank, **VIS},
        # no casing at overview zooms: at 1-2 px it turns the red brown (MML's small-scale roads are plain red)
        'paint': {'line-color': P['case'], 'line-width': case_w(), 'line-opacity': interp([(8, 0), (10, 1)], 1)},
    }
    fill = {
        'id': f'road-fill-{suffix}', 'type': 'line', 'source': 'mml_ways', 'source-layer': 'liikenne',
        'filter': copy.deepcopy(flt),
        'layout': {'line-cap': 'round', 'line-join': 'round', 'line-sort-key': rank, **VIS},
        'paint': {'line-color': by_class(P['road'], P['road'], P['road'], P['black'], P['road']), 'line-width': fill_w()},
    }
    if extra:
        case['paint'].update(extra.get('case', {}))
        fill['paint'].update(extra.get('fill', {}))
    return [case, fill]


def rail_layers(suffix, lvl):
    flt = ['all', ['==', ['geometry-type'], 'LineString'], ['match', cls, RAIL, True, False], level(lvl)]
    return [
        {'id': f'rail-case-{suffix}', 'type': 'line', 'source': 'mml_ways', 'source-layer': 'liikenne', 'filter': copy.deepcopy(flt),
         'layout': {'line-join': 'round', **VIS},
         'paint': {'line-color': P['black'], 'line-width': ground(1.6, 2.2, 3.0, [(8, 0.7), (11, 1.2)])}},
        {'id': f'rail-fill-{suffix}', 'type': 'line', 'source': 'mml_ways', 'source-layer': 'liikenne', 'filter': copy.deepcopy(flt),
         'minzoom': 13, 'layout': {'line-join': 'round', **VIS},
         'paint': {'line-color': '#99ffff', 'line-dasharray': [2.5, 2.5], 'line-width': ground(0.5, 0.7, 1.0)}},
    ]


def mml_way(i, classes, dash, width, minzoom, color=P['black']):
    return {'id': i, 'type': 'line', 'source': 'mml_ways', 'source-layer': 'liikenne', 'minzoom': minzoom,
            'filter': ['all', ['==', ['geometry-type'], 'LineString'], ['match', cls, classes, True, False], ['>=', ['get', 'tasosijainti'], 0]],
            'layout': {'line-join': 'round', **VIS},
            'paint': {'line-color': color, 'line-dasharray': dash, 'line-width': width}}


osm = {'source': 'osm', 'source-layer': 'transportation', 'type': 'line'}
not_bt = ['!in', 'brunnel', 'bridge', 'tunnel']
bad = ['in', 'trail_visibility', 'bad', 'no', 'horrible']
pw = ['match', ['get', 'width_cat'], 'a', 0.8, ['c', 'd'], 1.2, 1]  # width factor


def osm_path_width():
    return interp([(11, ['*', pw, 0.6]), (12, ['*', pw, 0.8]), (13, ['*', pw, 1.1]), (14, ['*', pw, 1.8]), (15, ['*', pw, 3.2]),
                   (16, ['*', pw, 6.1]), (17, ['*', pw, 11.5]), (20, ['*', pw, 70])], 2)


def osm_way(i, flt, dash, width, minzoom, extra_paint=None):
    lay = {'id': i, **osm, 'minzoom': minzoom, 'filter': flt,
           'layout': {'line-join': 'round', **VIS},
           'paint': {'line-color': P['black'], 'line-dasharray': dash, 'line-width': width,
                     'line-opacity': ['case', ['==', ['get', 'noexit'], 1], 0.6, 1]}}
    if extra_paint:
        lay['paint'].update(extra_paint)
    return lay


blk = []
# 1. tunnels: dashed black casing, pale fill
blk += road_layers('tunnel', ['<', ['get', 'tasosijainti'], 0],
                   {'case': {'line-dasharray': [1.5, 1], 'line-opacity': 0.9},
                    'fill': {'line-color': by_class('#ffc8b8', '#ffc8b8', '#ffc8b8', '#d0d0d0', '#ffc8b8')}})
blk += [dict(l, paint={**l['paint'], 'line-opacity': 0.35}) for l in rail_layers('tunnel', ['<', ['get', 'tasosijainti'], 0])]
# 2. MML ways as in the raster (option C): tracks (ajopolku) bold long dash, cycle/footways
# (kävely- ja pyörätie) longer dash, winter roads grey. MML paths (polku) come from OSM instead.
blk.append(mml_way('mml-ajopolku', [12316], [5, 1.2], ground(1.1, 1.5, 2.4, [(11, 0.8)]), 11))
blk.append(mml_way('mml-kavely-pyoratie', [12314], [7, 1.2], ground(0.8, 1.1, 1.9), 12))
blk.append(mml_way('mml-talvitie', [12312], [4, 2], ground(0.7, 0.9, 1.3), 12, '#606060'))
# 3. OSM paths: paths, bridleways and unpaved footways (forest trails tagged as footways). Paved
# footways, cycleways and pedestrian streets are MML's kävely- ja pyörätie above.
path_kind = ['any', ['!in', 'subclass', 'cycleway', 'footway', 'pedestrian', 'steps', 'corridor'],
             ['all', ['==', 'subclass', 'footway'], ['!=', 'surface', 'paved'], ['!=', 'indoor', 1]]]
path_base = ['all', ['==', '$type', 'LineString'], not_bt, ['==', 'class', 'path'], path_kind]
goodvis = ['!in', 'trail_visibility', 'bad', 'no', 'horrible']
path_fade = {'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0, 11.5, 0.7, 12.5, ['case', ['==', ['get', 'noexit'], 1], 0.6, 1]]}
badvis_fade = {'line-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0, 12.5, ['case', ['==', ['get', 'noexit'], 1], 0.6, 1]]}
blk.append(osm_way('osm-path', path_base + [goodvis], [4, 2], osm_path_width(), 11, extra_paint=path_fade))
blk.append(osm_way('osm-path-badvis', path_base + [bad], [1, 1.5], osm_path_width(), 12, extra_paint=badvis_fade))
blk.append(osm_way('osm-steps', ['all', ['==', '$type', 'LineString'], not_bt, ['==', 'class', 'path'], ['==', 'subclass', 'steps']],
                   [0.3, 0.3], ground(1.5, 2, 2.6), 14))
# 4. surface roads and rail
blk += rail_layers('surface', 0)
blk += road_layers('surface', 0)
# 5. OSM path bridges
blk += bridge_osm
# v4.3: bridged paths (boardwalks above all) draw from the same zoom, dash and fade as the path
# they continue; before, they started at z13 and left gaps in mire trails (owner, 29 Oct)
bridge_base = ['all', ['==', '$type', 'LineString'], ['==', 'brunnel', 'bridge'], ['==', 'class', 'path'], path_kind]
blk.append(osm_way('osm-bridge-path', bridge_base + [goodvis], [4, 2], osm_path_width(), 11, extra_paint=path_fade))
blk.append(osm_way('osm-bridge-path-badvis', bridge_base + [bad], [1, 1.5], osm_path_width(), 12, extra_paint=badvis_fade))
# 6. bridges by level: the black casing reads over what is below
for lv in range(1, 6):
    blk += rail_layers(f'bridge{lv}', lv)
    blk += road_layers(f'bridge{lv}', lv)

L[insert_at:insert_at] = blk

json.dump(S, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
open(out, 'a').write('\n')
print('layers', len(L))
