#!/usr/bin/env python3
"""Solana Beach School District elementary attendance areas for Carmel Valley -> tools/sbsd_zones.json

    python3 tools/fetch_sbsd.py

Source: the district's SchoolSite Locator (https://www.schoolsitelocator.com/apps/solanabeach/),
ArcGIS layers 718 (study areas; each school's whole attendance area is its "BNDRY" study area) and
717 (schools). Keeps the schools whose area holds Carmel Valley single-family sales and simplifies
the outlines (about 4 m). Re-run when the district updates its map. Stdlib only.
"""
import json
import os
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from schools import _inside  # noqa: E402
from sold_data import load_sales  # noqa: E402

BASE = "https://www.schoolsitelocator.com/server/rest/services/ssl_SS/MapServer"
OUT = os.path.join(TOOLS, "sbsd_zones.json")
MIN_SALES = 10  # a school needs this many Carmel Valley sales in its areas to be shown
NAMES = {"Carmel Creek ES": "Carmel Creek Elementary", "Solana Highlands ES": "Solana Highlands Elementary",
         "Solana Ranch ES": "Solana Ranch Elementary", "Solana Santa Fe ES": "Solana Santa Fe Elementary",
         "Solana Vista ES": "Solana Vista Elementary"}
# grades 4-6 for Carmel Creek (K-3) families
NOTES = {"Carmel Creek Elementary": "K&ndash;3; grades 4&ndash;6 at Solana Pacific"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "carmelvalleyhomesforsale-build"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def rdp(pts, eps):
    """Douglas-Peucker line simplification."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    n = (dx * dx + dy * dy) ** .5 or 1e-12
    i, dmax = 0, 0
    for k in range(1, len(pts) - 1):
        d = abs(dy * pts[k][0] - dx * pts[k][1] + x2 * y1 - y2 * x1) / n
        if d > dmax:
            i, dmax = k, d
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)


def simplify_ring(r, eps):
    """Douglas-Peucker for a closed ring: split it at the point farthest from the start."""
    pts = r[:-1] if r[0] == r[-1] else r
    far = max(range(len(pts)), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    a = rdp(pts[:far + 1], eps)
    b = rdp(pts[far:] + [pts[0]], eps)
    return a[:-1] + b


def main():
    schools = {f["attributes"]["SCHL_CODE"]: f["attributes"] for f in get(
        BASE + "/717/query?where=1%3D1&outFields=NAME,SCHL_CODE,GRD_RANGE&returnGeometry=false&f=json")["features"]}
    areas = get(BASE + "/718/query?outFields=STDYAREA,ELEM_&where=STDYAREA%3D%27BNDRY%27&outSR=4326&f=geojson")["features"]
    sales = [(r["lng"], r["lat"]) for r in load_sales() if r.get("lat") is not None]
    zones = {}
    for f in areas:
        code = f["properties"].get("ELEM_")
        if code not in schools:
            continue
        g = f["geometry"]
        rings = [p[0] for p in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"])]
        n = sum(1 for x, y in sales if any(_inside(x, y, r) for r in rings))
        if not n:
            continue
        name = NAMES.get(schools[code]["NAME"], schools[code]["NAME"])
        z = zones.setdefault(name, {"name": name, "grades": schools[code]["GRD_RANGE"], "sales": 0, "rings": []})
        z["sales"] += n
        for r in rings:
            s = simplify_ring([(round(x, 6), round(y, 6)) for x, y in r], 0.00004)
            if len(s) >= 4:
                z["rings"].append([[round(y, 5), round(x, 5)] for x, y in s])  # Leaflet [lat, lng]
    out = [dict(z, note=NOTES.get(z["name"], "")) for z in zones.values() if z["sales"] >= MIN_SALES]
    out.sort(key=lambda z: -z["sales"])
    json.dump({"source": "Solana Beach School District, SchoolSite Locator", "zones": out}, open(OUT, "w"), separators=(",", ":"))
    for z in out:
        print(f'{z["name"]}: {len(z["rings"])} areas, {z["sales"]} sales, {sum(len(r) for r in z["rings"])} points')
    print(f"wrote {os.path.relpath(OUT)} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
