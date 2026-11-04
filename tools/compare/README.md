# Style comparison tool

Live side-by-side maps at one synced view: `mmlv2-style.json` (this repo, read fresh on every
reload) against MML's raster maastokartta and the production Trailmap MTB style. Vector panels
go through a port of the web app's style builder (`build-style.mjs`), so each shows what the app
shows: mmlv2 as the "Kävely" profile (`buildMapStyleLegacy`, MML in Finland), Trailmap as the
"MTB" profile (`buildMapStyleV2`, free web user, Finland, default details).

## Interactive

    node tools/compare/server.mjs            # http://localhost:8787/

URL: `?panels=mmlv2,mml-raster,mtb#13/60.307/24.505` (zoom/lat/lon, kept in sync as you pan).

- **mode=overlay**: panels stacked; the top ones get an opacity slider and a `difference` blend
  that shows colour mismatches as non-black.
- **click**: per panel, the rendered colour at that pixel and the vector layers under it.
- **r** reloads the styles in place (after editing `mmlv2-style.json`), **c** the crosshair.
- Style options for every panel: `profile=mtb|gravel|winter`, `hc=1`, `raw=1` (no builder),
  `ref=<git ref>` (mtb-trailmap version), `d.<detail>=0|1` (e.g. `d.contour=0`).
- `--local-tiles finland_ways=/path/finland_ways.pmtiles` (server and shoot): the working-copy
  panels read that tile set from a local PMTiles archive, deployed panels keep the live tiles.
  For previewing a rebuilt tile set before it is deployed.
- Server flags: `--port`, `--mtb-repo` (default `../mtb-trailmap`), `--mtb-ref` (default
  `v81.9`, read with `git show`, so the checked-out branch does not matter), `--maplibre`
  (default: next-trailmap's `node_modules/maplibre-gl/dist`, the renderer the app uses).

## Panels (`panels.mjs`)

| id | what |
|---|---|
| `mmlv2` | working copy of `mmlv2-style.json` |
| `mmlv2-prod`, `mmlv2-v3`, `mmlv2-v4` | deployed `mmlv2-v2` / `mmlv2-v3` / `mmlv2-v4` from tiles.trailmap.fi |
| `mml-raster` | MML maastokartta as the app shows it (tileSize 128, varjomap 20 %) |
| `mml-raster-pure`, `mml-raster-native` | same without hillshade / at the raster's own scale |
| `mml-tausta`, `mml-ortho` | MML taustakartta raster, ortho imagery |
| `mml-hobby`, `mml-tausta-vec` | MML's own v21 vector styles (hobby = mmlv2's ancestor) |
| `mtb` | mtb-trailmap `style_base_v2.json` at `--mtb-ref` |
| `mtb-prod` | deployed `mtb-trailmap-global-v2b` |

## Screenshots

    node tools/compare/shoot.mjs --loc nuuksio            # every zoom listed for it
    node tools/compare/shoot.mjs --loc all --zoom 13
    node tools/compare/shoot.mjs --at 14/60.2585/24.925 --name keskuspuisto --split
    node tools/compare/shoot.mjs --loc helsinki --inspect 24.9384,60.1699

PNGs go to `tools/compare/out/` (git-ignored); `--jpeg 72` writes smaller JPEGs for reports.
The server reads `panels.mjs` once at start, so restart it after adding a panel.

Spec check against the MapLibre version the app ships: `node tools/compare/validate.mjs mmlv2-style.json`. Locations are in `locations.json`. Uses the
Playwright that comes with the global `@playwright/cli` (or a local `playwright`) and the newest
cached `chrome-headless-shell`; `--browser PATH` picks another binary.

Behind an HTTP proxy, run with `NODE_USE_ENV_PROXY=1` so the server's own fetches (deployed
and MML styles) use it too. Both entry points need what the Claude Code sandbox does not allow by default: the server binds
a local port, and Chromium needs macOS Mach ports.
