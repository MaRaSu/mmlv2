// Request handler shared by server.mjs (HTTP, for a person's browser) and shoot.mjs
// (Playwright route, no port needed). Styles are read fresh on every request, so an edit to
// mmlv2-style.json shows on the next reload.

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { PANELS } from './panels.mjs';
import { buildTrailmapV2, buildMmlLegacy } from './build-style.mjs';
import { getTile } from './pmtiles.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '../..');

export const DEFAULTS = {
	mtbRepo: path.join(REPO, '../mtb-trailmap'),
	mtbRef: 'v81.9',
	maplibre: path.join(REPO, '../../trailmap/next-trailmap/node_modules/maplibre-gl/dist')
};

/** Parses --name value pairs over DEFAULTS */
export function parseArgs(argv) {
	const opts = { ...DEFAULTS };
	for (let i = 0; i < argv.length; i++) {
		if (!argv[i].startsWith('--')) continue;
		const key = argv[i].slice(2).replace(/-(\w)/g, (_, c) => c.toUpperCase());
		opts[key] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
	}
	return opts;
}

const cache = new Map(); // url -> {at, json}: remote styles, 5 min

async function fetchJson(url) {
	const hit = cache.get(url);
	if (hit && Date.now() - hit.at < 300_000) return hit.json;
	const res = await fetch(url);
	if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
	const json = await res.json();
	cache.set(url, { at: Date.now(), json });
	return json;
}

// A style source: {file}, {git: [repo, ref, path]} or {url}
async function loadSource(src) {
	if (src.file) return JSON.parse(fs.readFileSync(path.resolve(REPO, src.file), 'utf8'));
	if (src.git) {
		const [repo, ref, file] = src.git;
		const out = execFileSync('git', ['-C', repo, 'show', `${ref}:${file}`], {
			maxBuffer: 64 * 1024 * 1024
		});
		return JSON.parse(out.toString('utf8'));
	}
	if (src.url) return structuredClone(await fetchJson(src.url));
	throw new Error('panel has no source');
}

// --local-tiles name=FILE[,name=FILE]: working-copy panels read vector.trailmap.fi/data/<name>
// from a local PMTiles archive instead (a rebuilt tile set, before it is deployed). Deployed
// panels keep the live tiles, so the two sides compare before and after.
function localTiles(opts) {
	if (typeof opts.localTiles !== 'string') return {};
	return Object.fromEntries(opts.localTiles.split(',').map((kv) => kv.split('=')));
}

function useLocalTiles(style, opts, origin) {
	const local = localTiles(opts);
	for (const s of Object.values(style.sources)) {
		for (const name of Object.keys(local)) {
			if (s.tiles?.some((t) => t.includes(`/data/${name}/`))) s.tiles = [`${origin}/local/${name}/{z}/{x}/{y}.pbf`];
		}
	}
}

async function panelStyle(id, query, opts, origin) {
	const panel = PANELS[id];
	if (!panel) throw new Error(`unknown panel ${id}`);
	if (panel.style) return panel.style; // inline style (raster panels)
	const src = { ...panel.source };
	if (src.git) {
		src.git = src.git.map((v) =>
			v.replace('$MTB_REPO', path.resolve(opts.mtbRepo)).replace('$MTB_REF', opts.mtbRef)
		);
		if (query.get('ref')) src.git[1] = query.get('ref');
	}
	const style = await loadSource(src);
	if (src.file) useLocalTiles(style, opts, origin);
	const details = {};
	for (const [k, v] of query) if (k.startsWith('d.')) details[k.slice(2)] = v === '1';
	if (query.get('raw') === '1' || !panel.build) return style;
	if (panel.build === 'trailmap') {
		return buildTrailmapV2(style, {
			profile: query.get('profile') || panel.profile || 'mtb',
			hc: query.get('hc') === '1',
			details
		});
	}
	if (panel.build === 'mml') return buildMmlLegacy(style, { details });
	throw new Error(`unknown builder ${panel.build}`);
}

const TYPES = {
	'.html': 'text/html; charset=utf-8',
	'.mjs': 'text/javascript',
	'.js': 'text/javascript',
	'.css': 'text/css',
	'.json': 'application/json',
	'.map': 'application/json',
	'.png': 'image/png'
};

function file(f) {
	if (!fs.existsSync(f) || !fs.statSync(f).isFile()) return { status: 404, type: 'text/plain', body: 'not found' };
	return {
		status: 200,
		type: TYPES[path.extname(f)] || 'application/octet-stream',
		body: fs.readFileSync(f)
	};
}

const json = (v) => ({ status: 200, type: 'application/json', body: JSON.stringify(v) });

/** -> {status, type, body} for a request path and query */
export async function handle(pathname, query, opts = DEFAULTS, origin = '') {
	const p = decodeURIComponent(pathname);
	try {
		if (p === '/' || p === '/index.html') return file(path.join(HERE, 'compare.html'));
		if (p === '/panels.json') {
			return json(
				Object.entries(PANELS).map(([id, v]) => ({
					id,
					label: v.label.replace('$MTB_REF', query.get('ref') || opts.mtbRef),
					kind: v.kind || 'vector'
				}))
			);
		}
		if (p === '/locations.json') return file(path.join(HERE, 'locations.json'));
		const m = p.match(/^\/style\/([\w.-]+)\.json$/);
		if (m) return json(await panelStyle(m[1], query, opts, origin));
		const t = p.match(/^\/local\/([\w.-]+)\/(\d+)\/(\d+)\/(\d+)\.pbf$/);
		if (t) {
			const file = localTiles(opts)[t[1]];
			const tile = file && getTile(file, +t[2], +t[3], +t[4]);
			return tile ? { status: 200, type: 'application/x-protobuf', body: tile } : { status: 204, type: 'text/plain', body: '' };
		}
		if (p.startsWith('/vendor/maplibre/')) return file(path.join(path.resolve(opts.maplibre), path.basename(p)));
		// Pattern images not yet in the shared sprite (tools/v4/make_patterns.py)
		if (p.startsWith('/patterns/')) return file(path.join(REPO, 'tools/v4/patterns', path.basename(p)));
		return { status: 404, type: 'text/plain', body: 'not found' };
	} catch (err) {
		console.error(err);
		return { status: 500, type: 'text/plain', body: String(err.stack || err) };
	}
}
