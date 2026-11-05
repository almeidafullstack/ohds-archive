#!/usr/bin/env python3
"""Turn delivered filenames into readable captions in docs/data.json.

  "8-12 Clay St., July 12, 1973 n.jpg"  ->  "8–12 Clay St., July 12, 1973"
  "Cass St. from Clay (W), Nov. 20, 2003 a.JPG"  ->  "Cass St. from Clay, looking west, Nov. 20, 2003"

Additive and safe to re-run: the delivered name stays in `original`, and a scene's
first caption is kept in `caption_raw`. Codes whose meaning is not confirmed (the
trailing n / s on the 1973 shots, the a / b / 1 / 2 variant letters) are dropped
from the caption but stay in `original`.

    python3 tools/clean_captions.py --dry-run   # print a sample, write nothing
    python3 tools/clean_captions.py
"""
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'docs' / 'data.json'

# Typos and truncations in the delivered names, fixed in captions only.
FIXES = {
    'Rivival': 'Revival',
    'during construc': 'during construction',
    'Jay s ': "Jay's ",
    'Jay_s ': "Jay's ",
    'St.and ': 'St. and ',
    'Oct. 25 2003': 'Oct. 25, 2003',
}

DIRECTIONS = {'N': 'north', 'S': 'south', 'E': 'east', 'W': 'west',
              'NE': 'northeast', 'NW': 'northwest', 'SE': 'southeast', 'SW': 'southwest'}
CORNERS = {'NEC': 'northeast corner', 'NWC': 'northwest corner',
           'SEC': 'southeast corner', 'SWC': 'southwest corner'}


def clean(name: str) -> str:
    s = re.sub(r'\.(jpe?g|png|psd)$', '', name, flags=re.I)
    s = s.replace('_', ' ')
    for a, b in FIXES.items():
        s = s.replace(a, b)

    # Trailing markers, repeated because they stack: "1973(2) n-1", "2003 a", "1988 2".
    for _ in range(4):
        s = re.sub(r'\s*-\s*\d$', '', s)              # "-1" duplicate suffix
        s = re.sub(r'\s*\(\d\)$', '', s)              # "(2)"
        s = re.sub(r'[\s,]+[a-z](\s+\d)?$', '', s)    # n / s codes and a-m variant letters
        s = re.sub(r'[\s,]+\d$', '', s)                 # "1988, 2", "St. 1"
        s = re.sub(r'\s*-$', '', s)                     # dangling "-" after a code
        s = re.sub(r'(\d{4})\s+\d$', r'\1', s)        # "1988 2"
        s = re.sub(r'\s*-\s*[ns]$', '', s)            # "- n"
        s = re.sub(r'\s+\(c\)$', '', s)
    s = re.sub(r'(\d{4})\(\d\)', r'\1', s)            # "1973(2)" mid-string
    s = re.sub(r'\.\s+[a-z]\s+(\d{4})', r'., \1', s)  # "1 Green St. a 1981"

    # Ranges lost their hyphen when the scene captions were first made.
    s = re.sub(r'(\d+)\((\d+)[ -](\d+)\)', r'\1 (\2–\3)', s)
    s = re.sub(r'\b(\d+) (\d+)\b(?=,| [A-Z])', r'\1–\2', s)
    s = re.sub(r'\b(\d+)\s*-\s*(\d+)\b', r'\1–\2', s)

    # "(W)" -> ", looking west"; "(NEC)" -> ", northeast corner".
    s = re.sub(r'\s*\((NEC|NWC|SEC|SWC)\)', lambda m: ', ' + CORNERS[m[1]], s)
    s = re.sub(r'\s*\((N|S|E|W|NE|NW|SE|SW)\)', lambda m: ', looking ' + DIRECTIONS[m[1]], s)

    s = re.sub(r'\s+-\s+(\d{4})', r', \1', s)         # "Green St - 1973"
    s = re.sub(r',\s*$', '', s)                       # dangling "April,"
    s = re.sub(r'\s{2,}', ' ', s).strip(' ,')
    s = re.sub(r'(St|Ave|Blvd|Ln)\.$', r'\1', s)    # "9 Brown St." -> "9 Brown St"
    return s


def main():
    dry = '--dry-run' in sys.argv
    data = json.loads(DATA.read_text())
    changed = 0
    for a in data['addresses']:
        for p in a['photos']:
            c = clean(p['original'])
            if p.get('caption') != c:
                p['caption'] = c
                changed += 1
    for sc in data.get('scenes', []):
        sc.setdefault('caption_raw', sc['caption'])
        c = clean(sc.get('original') or sc['caption_raw'])
        if sc['caption'] != c:
            sc['caption'] = c
            changed += 1

    if dry:
        seen = set()
        for a in data['addresses']:
            for p in a['photos']:
                if p['original'] not in seen and len(seen) < 25:
                    seen.add(p['original'])
                    print(f"{p['original']!r:60} -> {p['caption']}")
        for sc in data.get('scenes', []):
            print(f"{sc['caption_raw']!r:60} -> {sc['caption']}")
        print(f'\n{changed} captions would change (dry run, nothing written)')
        return
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
    print(f'{changed} captions updated in {DATA}')


if __name__ == '__main__':
    main()
