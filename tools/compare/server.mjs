#!/usr/bin/env node
// Map style comparison page for a person's browser.
//
//   node tools/compare/server.mjs [--port 8787] [--mtb-repo PATH] [--mtb-ref v81.9]
//        [--local-tiles finland_ways=/path/finland_ways.pmtiles]
//
// Then open http://localhost:8787/ (panels and position in the URL, see README.md).

import http from 'node:http';
import path from 'node:path';
import { handle, parseArgs } from './app.mjs';

const opts = parseArgs(process.argv.slice(2));
const port = Number(opts.port || 8787);

http
	.createServer(async (req, res) => {
		const url = new URL(req.url, 'http://localhost');
		const r = await handle(url.pathname, url.searchParams, opts, `http://${req.headers.host}`);
		res.writeHead(r.status, { 'content-type': r.type, 'cache-control': 'no-store' });
		res.end(r.body);
	})
	.listen(port, '127.0.0.1', () => {
		console.log(`compare: http://localhost:${port}/  (mtb-trailmap ${path.resolve(opts.mtbRepo)} @ ${opts.mtbRef})`);
	});
