#!/usr/bin/env python3
"""
Assemble the widget into a single Squarespace Code Block.

Squarespace will not host a folder of files. It accepts only .jpg/.png/.gif/.webp/
.ttf/.otf/.woff in Custom Files (no .js, no .json), and a Code Block caps at 400KB
(~300,000 characters). So everything that is not a photo has to be inlined into one
block: markup, styles, the map engine, the basemap, and the address data.

  python3 tools/build_squarespace.py

Writes squarespace/ohd-archive-block.html and reports the size against the cap.

Source of truth stays docs/index.html and docs/map.js. This script transforms
them rather than duplicating them:
  - CSS selectors are scoped under #ohd-archive so nothing leaks into the host page
  - fetch() of data.json / basemap.json becomes a read of inlined JSON
  - the host page's own webfonts are inherited, so no font upload is needed
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'docs')
OUT_DIR = os.path.join(ROOT, 'squarespace')
CAP = 300_000          # characters; Squarespace states 400KB / ~300k chars

# Layers that cost more bytes than they add meaning at this scale.
DROP_LAYERS = {'path', 'road-service'}
MIN_BUILDING = 2.5     # world units; drop footprints smaller than this


# ── Data compaction ──────────────────────────────────────────────────────────
def compact_data(d):
    """Columnar form. The verbose per-photo objects repeat street and filename
    data 1,050 times; this trades that for lookup tables."""
    streets = sorted({a['street'] for a in d['addresses']})
    si = {s: i for i, s in enumerate(streets)}
    years = sorted({p['year'] for a in d['addresses'] for p in a['photos'] if p['year']}
                   | {s['year'] for s in d['scenes'] if s['year']})
    yi = {y: i for i, y in enumerate(years)}

    files, fi = [], {}
    def fid(path):
        if path not in fi:
            fi[path] = len(files)
            files.append(path)
        return fi[path]

    addr = [[a['address'], si[a['street']], round(a['lat'], 6), round(a['lon'], 6),
             [[fid(p.get('clean_file') or p['file']),
               yi[p['year']] if p['year'] else -1] for p in a['photos']]]
            for a in d['addresses']]

    scenes = [[s['caption'], fid(s['clean_file']),
               yi[s['year']] if s['year'] else -1] for s in d['scenes']]

    # Descriptions are blank today, so only carry the ones that have text.
    desc = {str(i): a['description'].strip()
            for i, a in enumerate(d['addresses'])
            if (a.get('description') or '').strip()}

    return {'streets': streets, 'years': years, 'files': files,
            'addr': addr, 'scenes': scenes, 'desc': desc}


def compact_basemap(b):
    out = {}
    for layer, paths in b['layers'].items():
        if layer in DROP_LAYERS:
            continue
        keep = []
        for p in paths:
            pts = re.findall(r'[ML]([-\d.]+) ([-\d.]+)', p)
            if not pts:
                continue
            if layer == 'building':
                xs = [float(x) for x, _ in pts]
                ys = [float(y) for _, y in pts]
                if (max(xs) - min(xs)) < MIN_BUILDING and (max(ys) - min(ys)) < MIN_BUILDING:
                    continue
            s, prev = '', None
            for i, (x, y) in enumerate(pts):
                X, Y = round(float(x)), round(float(y))
                if prev == (X, Y):
                    continue
                s += ('M' if i == 0 else 'L') + str(X) + ' ' + str(Y)
                prev = (X, Y)
            if 'L' in s:
                keep.append(s + ('Z' if p.endswith('Z') else ''))
        if keep:
            out[layer] = keep
    return {'bbox': b['bbox'], 'width': b['width'], 'height': b['height'],
            'attribution': b['attribution'], 'layers': out, 'labels': b['labels']}


# ── CSS scoping ──────────────────────────────────────────────────────────────
ROOT_SEL = '#ohd-archive'

def scope_css(css):
    """Prefix every selector with #ohd-archive so the block cannot restyle the
    host page. Handles @media blocks; this CSS has no other at-rule nesting."""
    def scope_selector(sel):
        parts = []
        for one in sel.split(','):
            one = one.strip()
            if not one:
                continue
            if one in (':root', 'html, body', 'html', 'body'):
                parts.append(ROOT_SEL)
            elif one.startswith('body.'):
                parts.append(ROOT_SEL + one[4:])          # body.list-open -> #ohd-archive.list-open
            elif one.startswith('body '):
                parts.append(ROOT_SEL + ' ' + one[5:])
            elif one.startswith('*'):
                parts.append(ROOT_SEL + ' ' + one)
            else:
                parts.append(ROOT_SEL + ' ' + one)
        return ', '.join(parts)

    out, i = [], 0
    while i < len(css):
        at = css.find('@media', i)
        if at == -1:
            out.append(scope_rules(css[i:], scope_selector))
            break
        out.append(scope_rules(css[i:at], scope_selector))
        brace = css.find('{', at)
        depth, j = 1, brace + 1
        while j < len(css) and depth:
            if css[j] == '{': depth += 1
            elif css[j] == '}': depth -= 1
            j += 1
        out.append(css[at:brace + 1])
        out.append(scope_rules(css[brace + 1:j - 1], scope_selector))
        out.append('}')
        i = j
    return ''.join(out)


def scope_rules(chunk, scope_selector):
    res, pos = [], 0
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', chunk):
        res.append(chunk[pos:m.start()])
        sel, body = m.group(1), m.group(2)
        lead = re.match(r'\s*', sel).group(0)
        sel_clean = sel.strip()
        if sel_clean.startswith('@'):           # @font-face and friends: leave alone
            res.append(m.group(0))
        else:
            res.append(lead + scope_selector(sel_clean) + ' {' + body + '}')
        pos = m.end()
    res.append(chunk[pos:])
    return ''.join(res)


# ── Build ────────────────────────────────────────────────────────────────────
def main():
    html = open(os.path.join(W, 'index.html')).read()
    mapjs = open(os.path.join(W, 'map.js')).read()
    data = compact_data(json.load(open(os.path.join(W, 'data.json'))))
    base = compact_basemap(json.load(open(os.path.join(W, 'basemap.json'))))

    css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    body = re.search(r'<body>(.*?)<script src="\./map\.js"></script>', html, re.S).group(1)
    app = re.search(r'<script src="\./map\.js"></script>\s*<script>(.*?)</script>', html, re.S).group(1)

    css = scope_css(css)
    # The block is a page element, not a document: give it an explicit box.
    css = (f'{ROOT_SEL} {{ height: min(78vh, 760px); min-height: 480px; '
           f'border: 1px solid var(--line); border-radius: 4px; overflow: hidden; '
           f'contain: layout paint; }}\n') + css

    mapjs = mapjs.replace('window.createMap = createMap;', '')

    # Inlined data replaces the two fetches.
    app = re.sub(
        r'const \[basemap, data\] = await Promise\.all\(\[.*?\]\);',
        'const basemap = OHD_BASEMAP, data = expandData(OHD_DATA);',
        app, flags=re.S)
    app = app.replace("async function loadData() {", "function loadData() {")

    expander = '''
// The inlined data is columnar to fit the block size cap; rehydrate it into the
// shape the rest of the app already expects.
function expandData(c) {
  const yr = i => (i < 0 ? null : c.years[i]);
  const photo = ([f, y]) => {
    const path = c.files[f];
    return { clean_file: path, file: path.split('/').pop(), year: yr(y),
             original: path.split('/').pop() };
  };
  return {
    addresses: c.addr.map(([address, s, lat, lon, ph], i) => ({
      address, street: c.streets[s], lat, lon, photos: ph.map(photo),
      description: (c.desc && c.desc[i]) || '',
    })),
    scenes: c.scenes.map(([caption, f, y]) => ({
      caption, clean_file: c.files[f], file: c.files[f].split('/').pop(),
      original: c.files[f].split('/').pop(), year: yr(y), description: '',
    })),
  };
}
'''

    block = f'''<!-- ───────────────────────────────────────────────────────────────────────────
     Oregon Historic District — Photo Archives
     Single Squarespace Code Block. Paste whole; do not reformat.
     Built by build_squarespace.py from widget/. Edit there, not here.

     Set OHD_IMG.base below to wherever the photo derivatives live.
     ─────────────────────────────────────────────────────────────────────── -->
<div id="ohd-archive">
{body}</div>

<style>
{css}
</style>

<script type="application/json" id="ohd-basemap">{json.dumps(base, separators=(",", ":"))}</script>
<script type="application/json" id="ohd-data">{json.dumps(data, separators=(",", ":"))}</script>

<script>
(function () {{
const OHD_BASEMAP = JSON.parse(document.getElementById('ohd-basemap').textContent);
const OHD_DATA    = JSON.parse(document.getElementById('ohd-data').textContent);
{expander}
{mapjs}
{app}
}})();
</script>
'''

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, 'ohd-archive-block.html')
    open(path, 'w').write(block)

    n = len(block)
    print(f'{path}')
    print(f'  basemap   {len(json.dumps(base, separators=(",", ":"))):>7,} chars')
    print(f'  data      {len(json.dumps(data, separators=(",", ":"))):>7,} chars')
    print(f'  css+js    {len(css) + len(mapjs) + len(app):>7,} chars')
    print(f'  TOTAL     {n:>7,} chars   cap {CAP:,}   '
          f'{"OK, " + str(CAP - n) + " to spare" if n <= CAP else "OVER BY " + str(n - CAP)}')
    return 0 if n <= CAP else 1


if __name__ == '__main__':
    sys.exit(main())
