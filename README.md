# OHD Photo Archives — widget rebuild

Replacement for the dead `ohds-archives.org/archives/index.asp`, built to embed on
[oregonhistoric.org](https://www.oregonhistoric.org/) (Squarespace).

## What it does

Map-first browser for 905 archival photos across 241 addresses in the Oregon
Historic District, Dayton, Ohio, plus 61 undated-to-2003 streetscape views. Photos
captioned with a span of house numbers are attached to every address in the span,
so the collection resolves to 1,112 address-photo links.

- **Map** of the district with a pin per address, its area graduated by photo count (square-root scaled, capped at 16 so one outlier does not flatten the rest) against a small legend; framed automatically on the photographed addresses
- **Sidebar** of address tiles grouped by street, collapsed by default so the whole district scans in one screen; each tile shows a cover photo, year range, and photo count
- **Streetscapes** appear as their own group in the sidebar, alongside the streets
- **Year filter** in two interchangeable forms, switched by the toggle at the right of the year row: multi-select chips, or a timeline slider that snaps to the years the collection actually holds. The timeline stays live inside the photo viewer, where years the open address has nothing from are dimmed
- **Search** across address and street
- **Map popups** carrying a cover image, a scrollable thumbnail gallery of everything at that address, an optional description, and a link into the full viewer
- **Lightbox** with a thumbnail strip, keyboard navigation, and neighbor preloading
- **Compare years** side by side for the 118 addresses photographed in more than one year; it defaults to the widest time gap available and any second photo can be picked from the strip
- **Deep links** via `#a=<address>` so a specific address can be shared
- Responsive down to phone width, where the sidebar becomes a drawer and Compare stacks vertically

## No external dependencies

The widget makes **zero network calls beyond its own folder**. No CDN, no tile server,
no font service, no analytics. Verified by exercising every feature and reading
`performance.getEntriesByType('resource')`: 45 requests, one origin.

That cost three replacements:

| Was | Now |
|---|---|
| Leaflet from unpkg | `map.js`, a ~320-line SVG pan/zoom map written for this |
| OpenStreetMap raster tiles | `basemap.json`, a static vector basemap baked at build time |
| Google Fonts | `fonts/` + `fonts.css`, self-hosted woff2 (both faces are OFL) |

The basemap is 263KB: 3,446 SVG paths (1,453 building footprints, 908 road segments,
973 paths, rail, water, parks) plus 101 street labels, projected to Web Mercator and
drawn in a single `<g>` that pans and zooms as one transform. Pin radii, label sizes,
and stroke widths counter-scale so they hold a constant screen size at any zoom.

OSM data is ODbL. The attribution sits in the map's bottom-right corner and must stay.

## Layout

```
docs/                the published site — GitHub Pages serves this folder
  .nojekyll          REQUIRED: without it Pages hides every _scenes/ photo
  index.html         app shell, styles, and all non-map behaviour
  map.js             the SVG map engine (no dependencies)
  basemap.json       static vector basemap, built once from OSM
  data.json          241 addresses + 61 scenes
  fonts.css, fonts/  self-hosted Young Serif + Bitter (4 woff2 files)
  thumbs/            480px webp   (25MB)
  view/              1800px webp  (233MB)
  embed.html         iframe harness, to preview the embed as Squarespace renders it
tools/
  build_basemap.py     regenerates docs/basemap.json from an Overpass extract
  build_squarespace.py builds the single-code-block alternative
  osm-extract.json     the raw Overpass response the current basemap came from
squarespace/
  ohd-archive-block.html   one-code-block build, the no-external-host fallback
```

There is one copy of every file. `docs/` is both the source you edit and the folder
that ships; the app has no build step, so a separate source tree would only be a
second thing to keep in sync.

`docs/` is 259MB across 1,823 files.

## The photo originals live outside this repo

The 3336px originals (845MB, in `photos_organized/` in the working directory) are
deliberately **not** committed. Only the webp derivatives are. Keep the originals
backed up somewhere else: this repo is not the archival master.

## Running locally

```bash
python3 -m http.server 8767 --directory docs
```

Then open `http://localhost:8767/` for the widget, or
`http://localhost:8767/embed.html` to see it inside an iframe.

## Hosting: GitHub Pages

In **Settings → Pages**, set Source to *Deploy from a branch*, branch `main`, folder
`/docs`. The site lands at `https://<user>.github.io/<repo>/`.

```bash
git remote add origin git@github.com:<user>/<repo>.git
git push -u origin main
```

Sizes are well inside the limits: 259MB against a 1GB soft cap, largest single file
795KB against a 100MB cap. No Git LFS, no Actions, no build step.

`docs/.nojekyll` is not optional. GitHub Pages runs Jekyll by default, and Jekyll
hides any path beginning with an underscore. Without that file all 61 streetscapes
under `thumbs/_scenes/` and `view/_scenes/` return 404.

## Squarespace embed

Add a Code Block on the target page and paste:

```html
<iframe
  src="https://YOUR-STAGING-URL/index.html"
  title="Oregon Historic District Photo Archives"
  style="display:block;width:100%;height:720px;border:0;"
  loading="lazy"></iframe>
```

Iframes in code blocks need a Core plan or higher. GitHub Pages sets no
`X-Frame-Options`, so framing works with no configuration.

## Alternative: everything inside Squarespace

If the site must not depend on an outside host at all, `tools/build_squarespace.py`
produces `squarespace/ohd-archive-block.html`: one Code Block holding the markup,
scoped styles, map engine, basemap, and address data inlined, at 235,733 characters
against Squarespace's ~300,000 character cap. CSS is scoped under `#ohd-archive` so
it cannot restyle the host page, and the widget inherits the site's own webfonts,
so no font upload is needed.

The photos are what this cannot solve. Squarespace's Custom Files area accepts only
`.jpg .png .gif .ttf .otf .webp .woff` — no `.js`, no `.json` — and nothing on the
platform will serve a 1,800-file tree. The 905 photos would have to be bulk-uploaded
into Squarespace galleries and their CDN URLs harvested once via `?format=json`
(confirmed working on oregonhistoric.org) into a filename-to-URL map baked into the
block. That is a large manual step, and re-uploading any photo breaks its link.

Use this path only if an outside host is ruled out. GitHub Pages is simpler and
keeps the photos in version control.

## Tile covers and shared wide shots

A photo captioned with a span covers a row of buildings and is attached to every
address in it, which made the sidebar repetitive: filtering to 1974 once put the
same wide shot on ten tiles out of 37.

Two things address that, neither of which changes what a photo is attached to:

- **Cover choice prefers the narrowest span.** An address with its own photo shows
  that instead of the row shot. Distinct covers at 1974 went from 15 to 21, and
  across the whole set from 207 to 220.
- **Addresses left sharing a cover are folded into one cluster tile**, labelled with
  the span the photo claims and the number of addresses under it. Clicking it
  expands in place: the cluster head becomes a slim bar and the real address tiles
  appear beneath, each behaving exactly as a standalone tile does.

Clustering is by cover, not by adjacency, because a filter can leave gaps in which
addresses of a span are on screen and neighbour-only grouping would still show the
same photo twice in one street.

The result is no duplicate image anywhere on screen, in any filter state: 1974 goes
from 37 tiles showing 15 distinct photos to 21 tiles showing 21, and the unfiltered
sidebar from 241 tiles to 281 visible elements across 302 addresses with zero repeats.

Nothing is hidden permanently. Selecting an address from the map, the search box, or
a deep link opens its cluster first, so every address stays reachable. The viewer and
the photo strip are untouched: every address still shows every photo it is attached
to, in chronological order.

## Descriptions

Every address in `docs/data.json` carries a `description` field, empty for now:

```json
{ "address": "22 Brown St", "street": "Brown St", "lat": 39.75, "lon": -84.18,
  "description": "", "photos": [ ... ] }
```

Fill it in and the text appears in two places with no other change: in the map popup
for that address, and under the title in the photo viewer. Empty descriptions render
nothing at all, so partial coverage is fine. Bump `BUILD` in `docs/index.html` after
editing so browsers refetch the data.

## Range-labelled photos

Many photos are captioned with a span ("100-104 Brown St") because one frame shows
several buildings. `tools/expand_ranges.py` links each of those to every existing
address inside the span, recovers photos that no address referenced at all, and
sorts each address's photos oldest first with undated last. It is additive and safe
to re-run.

```bash
python3 tools/expand_ranges.py --dry-run   # report only
python3 tools/expand_ranges.py             # write docs/data.json
```

It follows the span literally, so "500-510 E. Fifth St" also attaches to 501 across
the street. Set `PARITY_STRICT = True` in the script to restrict a span to the
parity of its endpoints when they agree.

## Regenerating the basemap

Only needed if the district's streets change or the bbox should move.

```bash
curl -A "OHDS-archive-map-build/1.0" -X POST https://overpass-api.de/api/interpreter \
  --data-urlencode 'data=[out:json][timeout:90];(way["highway"](39.7500,-84.1930,39.7660,-84.1730);way["building"](39.7500,-84.1930,39.7660,-84.1730);way["natural"="water"](39.7500,-84.1930,39.7660,-84.1730);way["waterway"](39.7500,-84.1930,39.7660,-84.1730);way["leisure"="park"](39.7500,-84.1930,39.7660,-84.1730);way["landuse"](39.7500,-84.1930,39.7660,-84.1730);way["railway"](39.7500,-84.1930,39.7660,-84.1730););out geom;' \
  -o tools/osm-extract.json
python3 tools/build_basemap.py tools/osm-extract.json docs/basemap.json
```

This is the only step that touches the network, and it runs on your machine, not the
visitor's. The projection in `build_basemap.py` and the one in `map.js` must stay in
step; change one and you change both.

## Regenerating derivatives

`docs/thumbs/` and `docs/view/` are generated from the originals with Pillow. The Homebrew
`cwebp` on this machine is broken (missing `libtiff.6.dylib`), so the pipeline uses
Pillow's WebP encoder instead. Bump `BUILD` in `docs/index.html` whenever `data.json` or `basemap.json`
changes, or browsers will serve the old data from cache.

## Known gaps

- **169 of the photos carry no year.** The source filenames simply don't have one; this is a limitation of the archive, not a parsing failure. They group under "Undated".
- **The basemap is a snapshot.** It reflects OSM as of the build date and will not pick up later edits. Re-run the generator if that matters.
- **No aerial or satellite imagery is possible offline.** A photographic basemap means tiles, and tiles mean an external service. The vector map is the trade for zero dependencies.
- **"Full resolution" serves the 1800px derivative,** not the 3336px original. Originals are not committed; shipping them would add 845MB and push the repo near the Pages ceiling.
- **Geocoding is unverified.** All 241 addresses have coordinates, but nobody has checked them against the real parcels. Worth a spot-check on a sample before this goes public.
- **Eight photos were flagged as possibly rotated wrong** during an earlier QA pass and were never resolved. They ship as-is.
- **Span attachment is literal, not parity-aware.** See the range-labelled photos section; a handful of photos land on the address across the street.
- **The working directory still holds four copies of the source images** (`OHDS Pics/`, `OHDS Historic Photos/`, `widget/photos/`, `widget/photos_organized/`). Only `photos_organized/` was used to build the derivatives. Roughly 2.6GB is reclaimable there once you're confident the rest are redundant. None of it is in this repo.

## Changelog

- Rebuilt the prototype: restyled to match oregonhistoric.org (Young Serif / Bitter / #ffc700), added year filtering, year comparison, the streetscapes gallery, deep links, and a mobile layout; generated webp derivatives so the browser no longer loads 3336px originals; repaired 7 streetscape records whose filenames didn't match what was on disk.
- Removed every third-party runtime dependency: replaced Leaflet with a self-written SVG map engine, OSM raster tiles with a static vector basemap generated once from an Overpass extract, and Google Fonts with self-hosted woff2. The widget now makes no network calls outside its own folder.
