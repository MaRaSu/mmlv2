#!/usr/bin/env node
// Headless screenshots of the comparison page: one PNG per location and zoom, all panels side
// by side at the same view. Needs no HTTP server: the page is served through a Playwright route.
//
//   node tools/compare/shoot.mjs [--loc nuuksio|all] [--at z/lat/lon] [--name NAME]
//        [--panels mmlv2,mml-raster,mtb] [--size 1800x700] [--scale 2] [--split]
//        [--query "profile=gravel&d.contour=0"] [--inspect lng,lat] [--out DIR] [--jpeg 75]
//
// --split also saves each panel as its own PNG. --inspect prints, per panel, the rendered colour
// and the vector layers at that point (the page's click inspector).
// Network goes through $HTTPS_PROXY when it is set.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { handle, parseArgs } from './app.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const opts = parseArgs(process.argv.slice(2));

async function loadPlaywright() {
	try {
		return await import('playwright');
	} catch {
		// The playwright that ships with the globally installed @playwright/cli
		const global = path.join(
			path.dirname(process.execPath),
			'../lib/node_modules/@playwright/cli/node_modules/playwright/index.mjs'
		);
		return await import(global);
	}
}

const ORIGIN = 'http://compare.local';
const panels = opts.panels || 'mmlv2,mml-raster,mtb';
const [width, height] = String(opts.size || '1800x700').split('x').map(Number);
const scale = Number(opts.scale || 2);
const outDir = path.resolve(opts.out || path.join(HERE, 'out'));
fs.mkdirSync(outDir, { recursive: true });

// Shots: --at z/lat/lon, or --loc NAME|all from locations.json (all its zooms, or --zoom)
// --locations FILE: another list in the same format (default locations.json)
const locations = JSON.parse(fs.readFileSync(path.resolve(HERE, opts.locations || 'locations.json'), 'utf8'));
const shots = [];
if (opts.at) {
	const [z, lat, lon] = String(opts.at).split('/').map(Number);
	shots.push({ name: opts.name || 'at', z, lat, lon });
} else {
	const want = opts.loc || 'nuuksio';
	const zooms = opts.zoom ? String(opts.zoom).split(',').map(Number) : null;
	for (const l of locations) {
		if (want !== 'all' && !want.split(',').includes(l.name)) continue;
		for (const z of zooms || l.zooms) shots.push({ name: l.name, z, lat: l.lat, lon: l.lon });
	}
	if (!shots.length) throw new Error(`no location ${want}; have ${locations.map((l) => l.name).join(', ')}`);
}

function proxyFromEnv() {
	const raw = process.env.HTTPS_PROXY || process.env.https_proxy;
	if (!raw) return undefined;
	const u = new URL(raw);
	return {
		server: `${u.protocol}//${u.host}`,
		username: decodeURIComponent(u.username) || undefined,
		password: decodeURIComponent(u.password) || undefined,
		bypass: 'compare.local'
	};
}

// The newest Playwright headless shell in the cache: it needs no profile singleton, so it also
// runs inside a sandbox where full Chrome cannot start. --browser PATH overrides.
function headlessShell() {
	const cache = path.join(process.env.HOME || '', 'Library/Caches/ms-playwright');
	if (!fs.existsSync(cache)) return undefined;
	const dirs = fs
		.readdirSync(cache)
		.filter((d) => d.startsWith('chromium_headless_shell-'))
		.sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
	for (const d of dirs) {
		for (const sub of ['chrome-headless-shell-mac-arm64', 'chrome-headless-shell-mac-x64', 'chrome-headless-shell-linux64']) {
			const bin = path.join(cache, d, sub, 'chrome-headless-shell');
			if (fs.existsSync(bin)) return bin;
		}
	}
	return undefined;
}

const { chromium } = await loadPlaywright();
const executablePath = typeof opts.browser === 'string' ? opts.browser : headlessShell();
const browser = await chromium.launch({
	channel: executablePath ? undefined : 'chrome',
	executablePath,
	proxy: proxyFromEnv(),
	args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
});
const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale });
await context.route(`${ORIGIN}/**`, async (route) => {
	const url = new URL(route.request().url());
	const r = await handle(url.pathname, url.searchParams, opts, ORIGIN);
	await route.fulfill({ status: r.status, contentType: r.type, body: r.body });
});

const page = await context.newPage();
const problems = [];
page.on('console', (m) => {
	if (m.type() === 'warning' || m.type() === 'error') problems.push(m.text());
});
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));

const first = shots[0];
const query = new URLSearchParams(opts.query ? String(opts.query) : '');
query.set('panels', panels);
query.set('cross', '0');
await page.goto(`${ORIGIN}/?${query}#${first.z}/${first.lat}/${first.lon}`);
await page.waitForFunction(() => window.__compare, null, { timeout: 30000 });

for (const s of shots) {
	problems.length = 0;
	await page.evaluate(({ z, lat, lon }) => window.__compare.jump(z, lat, lon), s);
	const settled = await page.evaluate(() => window.__compare.idle(45000));
	await page.waitForTimeout(400);
	const base = `${s.name}-z${s.z}`;
	// --jpeg Q: JPEG at quality Q instead of PNG (smaller, for reports)
	const ext = opts.jpeg ? 'jpg' : 'png';
	const shotOpts = opts.jpeg ? { type: 'jpeg', quality: Number(opts.jpeg) || 75 } : {};
	const file = path.join(outDir, `${base}.${ext}`);
	await page.locator('#grid').screenshot({ path: file, ...shotOpts });
	if (opts.split) {
		const cells = page.locator('.cell');
		const ids = panels.split(',');
		for (let i = 0; i < (await cells.count()); i++) {
			await cells.nth(i).screenshot({ path: path.join(outDir, `${base}-${ids[i]}.${ext}`), ...shotOpts });
		}
	}
	const errors = await page.evaluate(() => window.__compare.errors().filter((e) => e.errors));
	console.log(`${file}${settled ? '' : '  (timed out waiting for tiles)'}`);
	for (const e of errors) console.log(`  ${e.id}: ${e.errors} error(s)`);
	for (const p of [...new Set(problems)].slice(0, 8)) console.log(`  ! ${p.slice(0, 300)}`);
	// --measure: line weights per colour family, each panel and its ratio to the reference panel
	// (--ref, default the second panel)
	if (opts.measure) {
		const m = await page.evaluate(() => window.__measure());
		const ids = panels.split(',');
		const ref = typeof opts.ref === 'string' ? opts.ref : ids[1];
		for (const id of ids) {
			const row = ['black', 'brown', 'blue'].map((f) => {
				const v = m[id][f], r = m[ref]?.[f];
				return `${f} ${v ?? '-'}${id !== ref && v && r ? ` (x${(v / r).toFixed(2)})` : ''}`;
			});
			console.log(`  ${id.padEnd(22)} ${row.join('  ')}`);
		}
	}
	// --colours: raster colour under each fill class of the first panel (--ref as the raster)
	if (opts.colours) {
		const ids = panels.split(',');
		const ref = typeof opts.ref === 'string' ? opts.ref : ids[1];
		const c = await page.evaluate(([v, r]) => window.__sampleClasses(v, r), [ids[0], ref]);
		for (const [k, v] of Object.entries(c).sort()) if (v.n >= 15) console.log(`  ${k.padEnd(40)} ${v.colour} ${v.share}% n=${v.n}`);
	}
	if (opts.inspect) {
		const [lng, lat] = String(opts.inspect).split(',').map(Number);
		const res = await page.evaluate(([lng, lat]) => window.__inspectLngLat(lng, lat, 3), [lng, lat]);
		console.log(JSON.stringify(res, null, 1));
	}
}

await browser.close();
