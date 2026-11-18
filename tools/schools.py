#!/usr/bin/env python3
"""School attendance areas for Carmel Valley pages.

    from schools import elementary_for, ELEMENTARY, DMUSD_SHAPES

Source maps (tools/kml/):
- dmusd-elementary.kml              Del Mar Union SD elementary attendance areas
- sduhsd-middle-high-2015-16.kml    San Dieguito Union HSD (2015-16; middle-school areas overlap,
                                    so only used for the high school note)
Parts of Carmel Valley (much of Pacific Highlands Ranch, Torrey Highlands and some areas north of
Del Mar Heights Road) are in Solana Beach SD, which has no map here yet: elementary_for() returns
None for those homes. Every page that names a school tells readers to confirm with the district.
Stdlib only.
"""
import os
import re

KML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kml")

# KML school name -> (page name, district)
ELEMENTARY = {
    "Ashley Falls ES": "Ashley Falls Elementary",
    "Carmel Del Mar ES": "Carmel Del Mar Elementary",
    "Del Mar Heights ES": "Del Mar Heights Elementary",
    "Ocean Air ES": "Ocean Air Elementary",
    "Pacific Sky": "Pacific Sky Elementary",
    "Sage Canyon ES": "Sage Canyon Elementary",
    "Sycamore Ridge ES": "Sycamore Ridge Elementary",
    "Torrey Hills ES": "Torrey Hills Elementary",
}
DMUSD = "Del Mar Union School District"
DMUSD_URL = "https://www.dmusd.org/Page/191"
SDUHSD_URL = "https://www.sduhsd.net/about/boundary-maps"


def _placemarks(path):
    s = open(path, encoding="utf-8").read()
    out = []
    for pm in re.findall(r"<Placemark.*?</Placemark>", s, re.S):
        m = re.search(r"<name>([^<]*)</name>", pm)
        polys = [[tuple(map(float, x.split(",")[:2])) for x in cd.split()]
                 for cd in re.findall(r"<outerBoundaryIs>.*?<coordinates>(.*?)</coordinates>", pm, re.S)]
        if m and polys:
            out.append((m.group(1).split(" - ")[0].strip(), polys))
    return out


def _inside(x, y, poly):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            c = not c
        j = i
    return c


DMUSD_SHAPES = _placemarks(os.path.join(KML, "dmusd-elementary.kml"))  # [(kml school name, [ring of (lng, lat)])]


def elementary_for(lat, lng):
    """Page name of the Del Mar Union elementary school for a point, or None."""
    if lat is None or lng is None:
        return None
    for name, polys in DMUSD_SHAPES:
        if any(_inside(lng, lat, p) for p in polys):
            return ELEMENTARY.get(name, name)
    return None


def school_polygons(page_name):
    """Leaflet-ready [[ [lat, lng], ... ], ...] rings for one elementary school."""
    kml = {v: k for k, v in ELEMENTARY.items()}[page_name]
    return [[[round(y, 5), round(x, 5)] for x, y in p] for n, polys in DMUSD_SHAPES if n == kml for p in polys]


def _boundary_shapes():
    """Each school's overall attendance boundary (the KML "<school> - BNDRY" placemark)."""
    s = open(os.path.join(KML, "dmusd-elementary.kml"), encoding="utf-8").read()
    out = {}
    for pm in re.findall(r"<Placemark.*?</Placemark>", s, re.S):
        m = re.search(r"<name>([^<]*)</name>", pm)
        if m and m.group(1).strip().endswith("- BNDRY"):
            out[m.group(1).split(" - ")[0].strip()] = [
                [tuple(map(float, x.split(",")[:2])) for x in cd.split()]
                for cd in re.findall(r"<outerBoundaryIs>.*?<coordinates>(.*?)</coordinates>", pm, re.S)]
    return out


BOUNDARIES = _boundary_shapes()  # {kml school name: [ring of (lng, lat)]}


def school_boundary(page_name):
    """Leaflet-ready outline rings of one elementary school's whole attendance area."""
    kml = {v: k for k, v in ELEMENTARY.items()}[page_name]
    return [[[round(y, 5), round(x, 5)] for x, y in p] for p in BOUNDARIES[kml]]


def share_inside(rings, page_name, n=14):
    """Share (0-1) of a community's area inside a school's boundary. rings: [[lat, lng], ...] lists."""
    kml = {v: k for k, v in ELEMENTARY.items()}[page_name]
    return share_in(rings, BOUNDARIES[kml], n)


def share_in(rings, bnd, n=14):
    """Share (0-1) of a community's area inside boundary rings bnd ([(lng, lat), ...] lists)."""
    pts = [p for r in rings for p in r]
    la0, la1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lo0, lo1 = min(p[1] for p in pts), max(p[1] for p in pts)
    inside = hit = 0
    for i in range(n):
        for j in range(n):
            la, lo = la0 + (i + .5) * (la1 - la0) / n, lo0 + (j + .5) * (lo1 - lo0) / n
            if any(_inside(lo, la, [(q[1], q[0]) for q in r]) for r in rings):
                inside += 1
                hit += any(_inside(lo, la, b) for b in bnd)
    return hit / inside if inside else 0
