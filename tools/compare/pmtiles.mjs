// Minimal PMTiles v3 reader: tiles from a local archive, so a rebuilt tile set can be previewed
// before it is deployed (--local-tiles finland_ways=/path/finland_ways.pmtiles).

import fs from 'node:fs';
import zlib from 'node:zlib';

const archives = new Map(); // path -> {fd, header, dirs}

function read(fd, offset, length) {
	const buf = Buffer.alloc(length);
	fs.readSync(fd, buf, 0, length, offset);
	return buf;
}

function decompress(buf, compression) {
	if (compression === 2) return zlib.gunzipSync(buf); // gzip
	if (compression === 1 || compression === 0) return buf; // none / unknown
	throw new Error(`pmtiles compression ${compression} not supported`);
}

function varint(buf, pos) {
	let v = 0, shift = 1, b;
	do {
		b = buf[pos.i++];
		v += (b & 0x7f) * shift;
		shift *= 128;
	} while (b & 0x80);
	return v;
}

function parseDir(buf) {
	const pos = { i: 0 };
	const n = varint(buf, pos);
	const e = Array.from({ length: n }, () => ({}));
	let id = 0;
	for (const x of e) x.tileId = id += varint(buf, pos);
	for (const x of e) x.runLength = varint(buf, pos);
	for (const x of e) x.length = varint(buf, pos);
	for (let k = 0; k < n; k++) {
		const v = varint(buf, pos);
		e[k].offset = v === 0 && k > 0 ? e[k - 1].offset + e[k - 1].length : v - 1;
	}
	return e;
}

function open(file) {
	if (archives.has(file)) return archives.get(file);
	const fd = fs.openSync(file, 'r');
	const h = read(fd, 0, 127);
	if (h.toString('utf8', 0, 7) !== 'PMTiles' || h[7] !== 3) throw new Error(`${file}: not PMTiles v3`);
	const u64 = (o) => Number(h.readBigUInt64LE(o));
	const header = {
		rootOffset: u64(8), rootLength: u64(16),
		leafOffset: u64(40), dataOffset: u64(56),
		internalCompression: h[97], tileCompression: h[98]
	};
	const a = { fd, header, dirs: new Map() };
	archives.set(file, a);
	return a;
}

function dir(a, offset, length) {
	const key = offset + ':' + length;
	if (!a.dirs.has(key)) a.dirs.set(key, parseDir(decompress(read(a.fd, offset, length), a.header.internalCompression)));
	return a.dirs.get(key);
}

function tileId(z, x, y) {
	let acc = (4 ** z - 1) / 3, d = 0;
	for (let s = 2 ** (z - 1); s >= 1; s /= 2) {
		const rx = (x & s) > 0 ? 1 : 0, ry = (y & s) > 0 ? 1 : 0;
		d += s * s * ((3 * rx) ^ ry);
		if (ry === 0) {
			if (rx === 1) { x = s - 1 - (x % s); y = s - 1 - (y % s); }
			[x, y] = [y, x];
		}
	}
	return acc + d;
}

/** Uncompressed tile bytes, or null when the archive has no tile there */
export function getTile(file, z, x, y) {
	const a = open(file);
	const id = tileId(z, x, y);
	let [offset, length] = [a.header.rootOffset, a.header.rootLength];
	for (let depth = 0; depth < 4; depth++) {
		const e = dir(a, offset, length);
		let lo = 0, hi = e.length - 1, hit = -1;
		while (lo <= hi) {
			const m = (lo + hi) >> 1;
			if (e[m].tileId <= id) { hit = m; lo = m + 1; } else hi = m - 1;
		}
		if (hit < 0) return null;
		const en = e[hit];
		if (en.runLength === 0) { [offset, length] = [a.header.leafOffset + en.offset, en.length]; continue; }
		if (id >= en.tileId + en.runLength) return null;
		return decompress(read(a.fd, a.header.dataOffset + en.offset, en.length), a.header.tileCompression);
	}
	return null;
}
