// Panels the comparison page can show. A panel is a style: from a file in this repo, a git
// ref of mtb-trailmap, a URL, or inline (raster maps). `build` runs the web app's builder
// for that map style (build-style.mjs) so the panel shows what the app shows.

const MML_KEY = 'e77a367c-c6f4-417e-870c-b55d156de596';
const MML_WMTS = (layer) =>
	`https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts/1.0.0/${layer}/default/WGS84_Pseudo-Mercator/{z}/{y}/{x}.png?api-key=${MML_KEY}`;

const MML_STYLE = (name) =>
	`https://avoin-karttakuva.maanmittauslaitos.fi/vectortiles/stylejson/v21/${name}.json?TileMatrixSet=WGS84_Pseudo-Mercator&api-key=${MML_KEY}`;

// A raster panel. tileSize 128 is how the app shows MML maastokartta (tileSize 512 /
// sizeFactor 4): MapLibre loads tiles two levels deeper than the map zoom and draws them at half
// size, crisp on a 2x screen. tileSize 256 is the raster at its own design scale (one tile pixel
// per CSS pixel).
function raster(url, { tileSize = 128, maxzoom = 17, hillshade = false } = {}) {
	const style = {
		version: 8,
		sources: { base: { type: 'raster', tiles: [url], tileSize, maxzoom } },
		layers: [{ id: 'base', type: 'raster', source: 'base', paint: { 'raster-resampling': 'linear' } }]
	};
	if (hillshade) {
		// The app's Finland topo map: varjomap at 20 % over the raster (CountryModeConfig.topoMap)
		style.sources.base2 = {
			type: 'raster',
			tiles: ['https://static.trailmap.fi/varjomap/{z}/{x}/{y}.png'],
			tileSize: 128,
			minzoom: 10,
			maxzoom: 14
		};
		style.layers.push({
			id: 'base2',
			type: 'raster',
			source: 'base2',
			paint: { 'raster-resampling': 'linear', 'raster-opacity': 0.2 }
		});
	}
	return style;
}

export const PANELS = {
	mmlv2: {
		label: 'mmlv2 (working copy)',
		source: { file: 'mmlv2-style.json' },
		build: 'mml'
	},
	'mmlv2-prod': {
		label: 'mmlv2 deployed (mmlv2-v2)',
		source: { url: 'https://tiles.trailmap.fi/styles/mmlv2-v2/style.json' },
		build: 'mml'
	},
	'mmlv2-v3': {
		label: 'mmlv2 deployed -v3 (own tiles)',
		source: { url: 'https://tiles.trailmap.fi/styles/mmlv2-v3/style.json' },
		build: 'mml'
	},
	'mmlv2-v4': {
		label: 'mmlv2 deployed -v4',
		source: { url: 'https://tiles.trailmap.fi/styles/mmlv2-v4/style.json' },
		build: 'mml'
	},
	'mml-raster': {
		label: 'MML maastokartta raster (as in app)',
		kind: 'raster',
		style: raster(MML_WMTS('maastokartta'), { hillshade: true })
	},
	'mml-raster-pure': {
		label: 'MML maastokartta raster (no hillshade)',
		kind: 'raster',
		style: raster(MML_WMTS('maastokartta'))
	},
	'mml-raster-native': {
		label: 'MML maastokartta raster (native scale)',
		kind: 'raster',
		style: raster(MML_WMTS('maastokartta'), { tileSize: 256 })
	},
	'mml-tausta': {
		label: 'MML taustakartta raster',
		kind: 'raster',
		style: raster(MML_WMTS('taustakartta'))
	},
	'mml-ortho': {
		label: 'MML ortokuva',
		kind: 'raster',
		style: raster(MML_WMTS('ortokuva'))
	},
	// MML's own vector styles (v21 is the latest schema as of 2026-10; hobby is the style the
	// MML MapLibre demo uses, and the one mmlv2 was derived from)
	'mml-hobby': {
		label: 'MML vector style: hobby (v21)',
		source: { url: MML_STYLE('hobby') }
	},
	'mml-tausta-vec': {
		label: 'MML vector style: taustakartta (v21)',
		source: { url: MML_STYLE('taustakartta') }
	},
	mtb: {
		label: 'Trailmap MTB ($MTB_REF, MTB defaults)',
		source: { git: ['$MTB_REPO', '$MTB_REF', 'style_base_v2.json'] },
		build: 'trailmap',
		profile: 'mtb'
	},
	'mtb-prod': {
		label: 'Trailmap deployed (global-v2b, MTB defaults)',
		source: { url: 'https://tiles.trailmap.fi/styles/mtb-trailmap-global-v2b/style.json' },
		build: 'trailmap',
		profile: 'mtb'
	}
};
