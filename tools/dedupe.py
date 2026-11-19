"""Remove near-duplicate photos listed in tools/duplicates.json from docs/data.json.

Each removed photo's address links are transferred to the photo that replaces it,
so no address loses coverage. Idempotent: safe to re-run. Pass --dry-run to report only.
"""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'docs' / 'data.json'
dry = '--dry-run' in sys.argv

removed = json.load(open(ROOT / 'tools' / 'duplicates.json'))['removed']
data = json.load(open(DATA))

records = {}
for a in data['addresses']:
    for p in a['photos']:
        records.setdefault(p['clean_file'], p)

dropped = moved = 0
for a in data['addresses']:
    files = [p['clean_file'] for p in a['photos']]
    for p in list(a['photos']):
        keep = removed.get(p['clean_file'])
        if not keep:
            continue
        a['photos'].remove(p); dropped += 1
        if keep not in files and keep in records:
            a['photos'].append(dict(records[keep])); files.append(keep); moved += 1

before = len(data['scenes'])
data['scenes'] = [s for s in data['scenes'] if s['clean_file'] not in removed]
empty = [a['address'] for a in data['addresses'] if not a['photos']]

print(f"address links dropped: {dropped}, links moved to keeper: {moved}, "
      f"scenes dropped: {before - len(data['scenes'])}, addresses left empty: {empty}")
if not dry:
    json.dump(data, open(DATA, 'w'), ensure_ascii=False, indent=1); open(DATA, 'a').write('\n')
