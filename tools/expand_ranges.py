#!/usr/bin/env python3
"""
Attach range-labelled photos to every address they cover.

Many photos are captioned with a span of house numbers ("100-104 Brown St") because
one frame shows several buildings. The original data attached each of those to only
some of the addresses in the span, so a photo of 100-104 was invisible when you
opened 100 or 102.

This pass is additive: it never removes an existing link. It
  1. reads every derivative in docs/thumbs so photos missing from data.json entirely
     are picked up too (descending ranges like "139-135 Jackson St" were dropped),
  2. parses a leading number or number range off each filename,
  3. links the photo to every EXISTING address on that street inside the range, and
  4. sorts each address's photos oldest first, undated last.

  python3 tools/expand_ranges.py [--dry-run]

Note on parity: a photo captioned "500-510" is one side of the street, so strictly
it belongs to the even numbers only. This script follows the span literally and
links every existing number in it, which also catches 501 across the road. Set
PARITY_STRICT = True to restrict to the parity of the endpoints when they agree.
"""
import json, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data.json')
THUMBS = os.path.join(ROOT, 'docs', 'thumbs')

PARITY_STRICT = False

YEAR_RE = re.compile(r'\b(18|19|20)\d{2}\b')
# Leading "12", "12-16", "12 - 16"; optionally wrapped like "120(116-118)"
LEAD_RE = re.compile(r'^\s*(\d+)\s*(?:\(\s*(\d+)\s*-\s*(\d+)\s*\))?\s*(?:-\s*(\d+))?\s*(?=[A-Za-z(])')


def house_num(address):
    m = re.match(r'^(\d+)', address)
    return int(m.group(1)) if m else None


def parse_span(filename):
    """Return (lo, hi) of house numbers the filename claims, or None."""
    stem = os.path.splitext(filename)[0]
    m = LEAD_RE.match(stem)
    if not m:
        return None
    first = int(m.group(1))
    nums = [first]
    if m.group(2) and m.group(3):          # 120(116-118)
        nums += [int(m.group(2)), int(m.group(3))]
    if m.group(4):                         # 100-104, or 139-135
        nums.append(int(m.group(4)))
    lo, hi = min(nums), max(nums)
    # A "year" is not a house number. Nothing in this district numbers above 700.
    if lo > 700:
        return None
    return lo, hi


def year_of(filename):
    m = YEAR_RE.search(filename)
    return m.group(0) if m else None


def slug(name):
    s = os.path.splitext(name)[0].lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s + '.jpg'


def main():
    dry = '--dry-run' in sys.argv
    d = json.load(open(DATA))

    addrs = d['addresses']
    by_street = defaultdict(list)
    for a in addrs:
        n = house_num(a['address'])
        if n is not None:
            by_street[a['street']].append((n, a))

    # Existing links, so this stays additive.
    have = {a['address']: {p['clean_file'] for p in a['photos']} for a in addrs}
    known = {p['clean_file'] for a in addrs for p in a['photos']}
    scene_files = {s['clean_file'] for s in d['scenes']}

    # Every derivative on disk, as the canonical photo list.
    on_disk = []
    for r, _, fs in os.walk(THUMBS):
        for f in fs:
            if not f.endswith('.webp'):
                continue
            rel = os.path.relpath(os.path.join(r, f), THUMBS).replace('.webp', '.jpg')
            on_disk.append(rel)

    added = defaultdict(list)
    recovered = []

    for rel in sorted(on_disk):
        street, fname = os.path.split(rel)
        if street == '_scenes' or rel in scene_files:
            continue
        if street not in by_street:
            continue
        span = parse_span(fname)
        if not span:
            continue
        lo, hi = span
        if rel not in known:
            recovered.append(rel)

        targets = [a for n, a in by_street[street] if lo <= n <= hi]
        if PARITY_STRICT and lo % 2 == hi % 2:
            targets = [a for a in targets if house_num(a['address']) % 2 == lo % 2]

        for a in targets:
            if rel in have[a['address']]:
                continue
            a['photos'].append({
                'file': slug(fname),
                'original': fname,
                'year': year_of(fname),
                'street': street,
                'clean_file': rel,
            })
            have[a['address']].add(rel)
            added[rel].append(a['address'])

    # Oldest first, undated last, so the strip reads chronologically.
    for a in addrs:
        a['photos'].sort(key=lambda p: (p['year'] is None, p['year'] or '', p['clean_file']))

    links = sum(len(v) for v in added.values())
    print(f'photos on disk (address, not scenes): {len([r for r in on_disk if not r.startswith("_scenes")])}')
    print(f'photos recovered that were in no address at all: {len(recovered)}')
    for r in recovered:
        print(f'    {r} -> {", ".join(added.get(r, ["(no matching address)"]))}')
    print(f'new address-photo links added: {links} across {len(added)} photos')
    per_street = defaultdict(int)
    for rel, who in added.items():
        per_street[rel.split("/")[0]] += len(who)
    for s, n in sorted(per_street.items(), key=lambda t: -t[1]):
        print(f'    {s:20s} +{n}')

    total = sum(len(a['photos']) for a in addrs)
    print(f'total address-photo links now: {total}')

    if dry:
        print('\n--dry-run: nothing written')
        return
    json.dump(d, open(DATA, 'w'), indent=1, ensure_ascii=False)
    print(f'\nwrote {DATA}')


if __name__ == '__main__':
    main()
