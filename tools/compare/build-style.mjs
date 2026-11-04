// Port of the web app's style builders (next-trailmap src/ui-stores/app-config-ui-store.ts),
// reduced to what a comparison needs: a free web user in Finland with an app default profile.
//   buildTrailmapV2  = buildMapStyleV2   (MapStyle.Trailmap, profile "MTB" by default)
//   buildMmlLegacy   = buildMapStyleLegacy (MapStyle.MML in Finland, profile "Kävely")
// Slot layers (data_start, segments_start, ...) are left out: they are invisible.
// Keep in step with the app when its builder changes; checks/verify_build.py in mtb-trailmap
// is the Python twin of the same selection.

// shared/models/app-config.ts DETAILS_OPTIONS (name -> default value, minZoom for POI groups)
const DETAILS_OPTIONS = [
	['mml-ways', false],
	['poi-lipas', false],
	['poi-osm', false],
	['skiing-lipas', false],
	['wood', false],
	['white-background', false],
	['bedrock', true],
	['fixme', false],
	['hillshade', true],
	['contour', true],
	['cadastral', false],
	['depth-contour', false],
	['poi-lipas-hiking', false, 11],
	['poi-lipas-sport', false, 11],
	['poi-osm-attraction', false, 13],
	['poi-osm-lodging', false, 11],
	['poi-osm-rest', false, 12],
	['poi-osm-transit', false, 13],
	['poi-osm-service', false, 13],
	['poi-osm-water', false, 12]
];

const POI_GROUPS = new Set(DETAILS_OPTIONS.filter((d) => d[2]).map((d) => d[0]));

// APP_CONFIG_TRAILMAP_DETAILS / APP_CONFIG_MML_DETAILS: the details each map style offers
const TRAILMAP_DETAILS = DETAILS_OPTIONS.map((d) => d[0]).filter(
	(n) => n !== 'poi-lipas' && n !== 'poi-osm'
);
const MML_DETAILS = ['hillshade', 'cadastral', 'depth-contour', ...POI_GROUPS];

// APP_CONFIG_DEFAULT_DATA profiles (overrides on top of DETAILS_OPTIONS)
export const PROFILES = {
	mtb: { subStyle: 'mtb', details: { 'poi-lipas-hiking': true, wood: false, 'white-background': true } },
	gravel: {
		subStyle: 'gravel',
		details: {
			'poi-lipas-hiking': true,
			wood: false,
			'white-background': true,
			hillshade: false,
			contour: false,
			bedrock: false
		}
	},
	winter: {
		subStyle: 'mtb_winter',
		details: {
			'poi-lipas-hiking': true,
			wood: false,
			bedrock: false,
			'white-background': true,
			'skiing-lipas': true
		}
	},
	walk: { subStyle: undefined, details: { 'poi-lipas-hiking': true } }
};

const FINLAND_ONLY = new Set(['poi-lipas-hiking', 'poi-lipas-sport', 'skiing-lipas', 'mml-ways']);
const isFinlandOnly = (g) => !!g && (g.endsWith('-routes-lipas') || FINLAND_ONLY.has(g));

function details(profile, offered, overrides = {}) {
	const out = new Map();
	for (const [name, value, minZoom] of DETAILS_OPTIONS) {
		if (!offered.includes(name)) continue;
		const v = name in overrides ? overrides[name] : name in profile.details ? profile.details[name] : value;
		out.set(name, { value: v, minZoom });
	}
	return out;
}

function setVisibility(layer, visible) {
	layer.layout = { ...layer.layout, visibility: visible ? 'visible' : 'none' };
}

/**
 * buildMapStyleV2 for MapStyle.Trailmap, vectorBaseMapStyle Default (no ortho / ways-only),
 * free user, web, routes visible but none selected.
 * opts: { profile: 'mtb'|'gravel'|'winter', country: 'fin', hc: false, details: {name: bool} }
 */
export function buildTrailmapV2(style, opts = {}) {
	const s = structuredClone(style);
	const profileName = opts.profile || 'mtb';
	const profile = PROFILES[profileName];
	const country = opts.country || 'fin';
	const countryFilter = country === 'fin' ? 'fin' : 'global';
	const hc = !!opts.hc && profile.subStyle === 'mtb';
	const det = details(profile, TRAILMAP_DETAILS, opts.details);
	const white = det.get('white-background')?.value;
	const out = [];

	for (const layer of s.layers) {
		const meta = layer.metadata || {};
		const group = meta['trailmap:group'];
		if (layer.id === 'data_start') break;
		if (country !== 'fin' && isFinlandOnly(group)) continue;
		if (meta['trailmap:app'] && meta['trailmap:app'] !== 'web') continue;
		const premium = meta['trailmap:premium'];
		if (premium === 'navi' || premium === 'plus') continue;

		let countries = meta['trailmap:country'];
		if (!Array.isArray(countries)) countries = [countries];
		if (countries[0] !== undefined || countries.length > 1) {
			let include;
			for (const c of countries) {
				if (c === country || c === 'all' || c === countryFilter) include ??= true;
				if (typeof c === 'string' && c[0] === '!' && c.slice(1) === country) include = false;
			}
			if (!include) continue;
		} else {
			// metadataCountry is [undefined]: the app's loop finds no match and drops the layer
			continue;
		}

		if (group === 'background') {
			if (layer.paint?.['background-color']) {
				layer.paint['background-color'] = white ? '#fefefa' : '#f4f5eb';
			}
			out.push(layer);
			continue;
		}

		if (group === 'woodmask' && !det.get('wood')?.value) {
			layer.paint['fill-color'] = white ? '#fefefa' : '#f4f5eb';
			layer.metadata = {
				'trailmap:mtb': true,
				'trailmap:high_contrast': 'yes',
				'trailmap:mtb_winter': true,
				'trailmap:gravel': true,
				'trailmap:mapper': true,
				'trailmap:ways_only': false,
				'trailmap:country': 'fin',
				'trailmap:simple': 1
			};
		}
		const m = layer.metadata || {};

		let visible = m['trailmap:' + profile.subStyle] === true;
		if (group && det.has(group)) {
			const d = det.get(group);
			visible = !!d.value;
			if (visible && POI_GROUPS.has(group) && d.minZoom) layer.minzoom = d.minZoom;
		}

		const hcMeta = m['trailmap:high_contrast'];
		if (hc ? !['yes', 'exclusive'].includes(hcMeta) : !['yes', 'no'].includes(hcMeta)) continue;

		setVisibility(layer, visible);
		if (visible) out.push(layer);
	}
	s.layers = out;
	return s;
}

/**
 * buildMapStyleLegacy for MapStyle.MML (the app's path for MML in Finland), profile "Kävely":
 * vectorBaseMapStyle Default, mapSubStyle undefined, so a layer keeps its own visibility
 * unless a detail group overrides it.
 */
export function buildMmlLegacy(style, opts = {}) {
	const s = structuredClone(style);
	const profile = PROFILES.walk;
	const det = details(profile, MML_DETAILS, opts.details);
	const out = [];
	for (const layer of s.layers) {
		if (layer.id === 'data_start') break;
		if (layer.id === 'background') {
			out.push(layer);
			continue;
		}
		if (layer.id.startsWith('alt_base_')) continue; // mapSubStyle visibility: none by default
		let visible = layer.layout?.visibility ? layer.layout.visibility === 'visible' : true;
		const group = layer.metadata?.['trailmap:group'];
		if (group && det.has(group)) {
			const d = det.get(group);
			visible = !!d.value;
			if (visible && POI_GROUPS.has(group) && d.minZoom) layer.minzoom = d.minZoom;
		}
		setVisibility(layer, visible);
		if (visible) out.push(layer);
	}
	s.layers = out;
	return s;
}
