#!/usr/bin/env python3
"""
Turn a one-time Overpass extract into a static SVG basemap for the widget.

Run once at build time. The output, docs/basemap.json, is committed alongside the widget
and the app makes no network calls of any kind at runtime.

  python3 tools/build_basemap.py tools/osm-extract.json docs/basemap.json

OSM data is ODbL. The attribution string is baked into the output and the widget
renders it; keep it.
"""
import json, math, sys
from collections import defaultdict

# The district plus a margin, so the map has context at the edges.
BBOX = (39.7500, -84.1930, 39.7660, -84.1730)   # S, W, N, E
WIDTH = 1000.0                                   # SVG user units across the bbox

# What we draw, in paint order. Each layer names the tags it claims.
ROAD_CLASSES = {
    'motorway': 'road-major', 'motorway_link': 'road-major',
    'trunk': 'road-major', 'trunk_link': 'road-major',
    'primary': 'road-major', 'primary_link': 'road-major',
    'secondary': 'road-arterial', 'secondary_link': 'road-arterial',
    'tertiary': 'road-arterial', 'tertiary_link': 'road-arterial',
    'residential': 'road-minor', 'unclassified': 'road-minor',
    'living_street': 'road-minor', 'service': 'road-service',
    'footway': 'path', 'path': 'path', 'pedestrian': 'path',
    'steps': 'path', 'cycleway': 'path', 'track': 'path',
}
GREEN_LANDUSE = {'grass', 'forest', 'meadow', 'recreation_ground', 'village_green', 'cemetery'}


def mercator(lat, lon):
    x = math.radians(lon)
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def make_projector(bbox, width):
    s, w, n, e = bbox
    x0, y0 = mercator(s, w)
    x1, y1 = mercator(n, e)
    sx = width / (x1 - x0)
    height = (y1 - y0) * sx
    def project(lat, lon):
        x, y = mercator(lat, lon)
        return round((x - x0) * sx, 1), round((y1 - y) * sx, 1)
    return project, round(height, 1)


def path_d(points, closed):
    if not points:
        return ''
    out = [f'M{points[0][0]} {points[0][1]}']
    prev = points[0]
    for p in points[1:]:
        if abs(p[0] - prev[0]) < 0.15 and abs(p[1] - prev[1]) < 0.15:
            continue   # drop sub-pixel steps; the file is mostly coordinates
        out.append(f'L{p[0]} {p[1]}')
        prev = p
    if len(out) == 1:
        return ''
    return ''.join(out) + ('Z' if closed else '')


def main(src, dst):
    data = json.load(open(src))
    project, height = make_projector(BBOX, WIDTH)
    layers = defaultdict(list)
    labels = []
    seen_labels = set()

    for el in data['elements']:
        if el.get('type') != 'way' or 'geometry' not in el:
            continue
        tags = el.get('tags', {})
        pts = [project(p['lat'], p['lon']) for p in el['geometry']]
        if len(pts) < 2:
            continue
        closed = pts[0] == pts[-1]

        layer = None
        if 'building' in tags:
            layer = 'building'
        elif tags.get('natural') == 'water' or 'waterway' in tags:
            layer = 'water'
        elif tags.get('leisure') == 'park' or tags.get('landuse') in GREEN_LANDUSE:
            layer = 'green'
        elif 'railway' in tags:
            if tags['railway'] in ('rail', 'light_rail', 'subway'):
                layer = 'rail'
        elif 'highway' in tags:
            layer = ROAD_CLASSES.get(tags['highway'])

        if not layer:
            continue
        d = path_d(pts, closed or layer in ('building', 'water', 'green'))
        if d:
            layers[layer].append(d)

        # One label per named street, at the midpoint of its longest segment.
        name = tags.get('name')
        if name and layer in ('road-major', 'road-arterial', 'road-minor') and name not in seen_labels:
            best, blen = None, 0
            for a, b in zip(pts, pts[1:]):
                seg = math.hypot(b[0] - a[0], b[1] - a[1])
                if seg > blen:
                    blen, best = seg, (a, b)
            if best and blen > 12:
                (ax, ay), (bx, by) = best
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                if ang > 90:
                    ang -= 180
                elif ang < -90:
                    ang += 180
                labels.append({
                    'x': round((ax + bx) / 2, 1), 'y': round((ay + by) / 2, 1),
                    'a': round(ang, 1), 't': name,
                    'r': 1 if layer == 'road-major' else (2 if layer == 'road-arterial' else 3),
                })
                seen_labels.add(name)

    out = {
        'bbox': BBOX,
        'width': WIDTH,
        'height': height,
        'attribution': 'Map data © OpenStreetMap contributors (ODbL)',
        'layers': {k: v for k, v in layers.items()},
        'labels': labels,
    }
    json.dump(out, open(dst, 'w'), separators=(',', ':'))
    total = sum(len(v) for v in layers.values())
    print(f'{dst}: {total} paths, {len(labels)} labels, {height:.0f} units tall')
    for k in sorted(layers, key=lambda k: -len(layers[k])):
        print(f'  {k:16s} {len(layers[k])}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
