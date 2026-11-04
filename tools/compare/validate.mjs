#!/usr/bin/env node
// Validates style files against the MapLibre style spec the web app ships with.
//   node tools/compare/validate.mjs mmlv2-style.json [more.json ...]
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { DEFAULTS } from './app.mjs';

const require = createRequire(path.join(path.resolve(DEFAULTS.maplibre), '../../'));
const spec = await import(require.resolve('@maplibre/maplibre-gl-style-spec'));
const validate = spec.validateStyleMin || spec.validateStyle || spec.default?.validateStyleMin;

let failed = 0;
for (const file of process.argv.slice(2)) {
	const style = JSON.parse(fs.readFileSync(file, 'utf8'));
	const errors = validate(style);
	const ids = new Set();
	for (const l of style.layers) {
		if (ids.has(l.id)) errors.push({ message: `duplicate layer id ${l.id}` });
		ids.add(l.id);
	}
	console.log(`${file}: ${errors.length ? errors.length + ' error(s)' : 'valid'} (${style.layers.length} layers)`);
	for (const e of errors.slice(0, 30)) console.log('  ' + e.message);
	failed += errors.length ? 1 : 0;
}
process.exit(failed ? 1 : 0);
