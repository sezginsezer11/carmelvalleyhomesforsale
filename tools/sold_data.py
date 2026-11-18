#!/usr/bin/env python3
"""Single-family closed sales for Carmel Valley (92130), shared by every builder.

    from sold_data import load_sales, area_of, AREA_LABELS
    rows = load_sales()            # every single-family sale, newest first

Rule (chosen for this site): a sale counts when the MLS says
"Single Family Residence". Communities marked "(a)" (condo / fractional
ownership) on the California Title Company chart, or "condo" in
tools/atlas_home_types.json, are always left out.

The API returns at most 500 rows per request, so every page is fetched.
Results are cached for the day in tools/.cache/ (git-ignored).
    python3 tools/sold_data.py      # refresh the cache and print a summary
Stdlib only.
"""
import datetime
import json
import os
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from build_atlas import AREAS, CHART, ALIAS  # noqa: E402

API = "https://www.sellmyhomesforcash.com/api/public/sold-listings?zip=92130&limit=500&page={}"
CACHE = os.path.join(TOOLS, ".cache", "sold-92130.json")
SFR = "Single Family Residence"
AREA_LABELS = dict(AREAS)


def _chart():
    """lower-case chart name -> (area key, homes, is_condo); first area wins."""
    out = {}
    for area, txt in CHART.items():
        for part in txt.split(";"):
            part = part.strip()
            condo = "(a)" in part
            name, homes = part.replace("(a)", "").rsplit(" ", 1)
            out.setdefault(name.strip().lower(), (area, int(homes), condo))
    return out


CHART_BY_NAME = _chart()
TYPES = json.load(open(os.path.join(TOOLS, "atlas_home_types.json"), encoding="utf-8"))


def chart_entry(community):
    if not community:
        return None
    key = community.strip().lower()
    return CHART_BY_NAME.get(ALIAS.get(key, key))


def is_condo_community(community):
    e = chart_entry(community)
    return bool(e and e[2]) or TYPES.get(community or "") == "condo"


def area_of(community):
    e = chart_entry(community)
    return e[0] if e else None


def is_sfr(r):
    return r.get("property_sub_type") == SFR and not is_condo_community(r.get("community_name"))


def _fetch_all():
    rows, page = [], 0
    while True:
        with urllib.request.urlopen(API.format(page), timeout=30) as resp:
            d = json.load(resp)
        batch = d.get("rows", [])
        rows += batch
        page += 1
        if not batch or len(rows) >= d.get("total", 0) or page > 60:
            return rows


def load_raw(refresh=False):
    today = datetime.date.today().isoformat()
    if not refresh and os.path.exists(CACHE):
        c = json.load(open(CACHE, encoding="utf-8"))
        if c.get("date") == today:
            return c["rows"]
    rows = _fetch_all()
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump({"date": today, "rows": rows}, open(CACHE, "w", encoding="utf-8"))
    return rows


def load_sales(refresh=False):
    """Deduped single-family sales with a parsed _d date, newest first."""
    seen, out = set(), []
    for r in load_raw(refresh):
        if r.get("group_key") in seen:
            continue
        seen.add(r.get("group_key"))
        if r.get("close_price") and r.get("close_date") and is_sfr(r):
            r["_d"] = datetime.date.fromisoformat(r["close_date"][:10])
            out.append(r)
    out.sort(key=lambda r: r["_d"], reverse=True)
    return out


if __name__ == "__main__":
    raw = load_raw(refresh=True)
    rows = load_sales()
    print(f"fetched {len(raw)} rows, {len({r['group_key'] for r in raw})} unique; {len(rows)} single-family sales "
          f"{rows[-1]['_d']} to {rows[0]['_d']}")


# home size ranges for the "Prices by home size" cards on school and area pages
SIZE_BANDS = [(0, 2000, "Under 2,000 sq ft"), (2000, 3000, "2,000&ndash;3,000 sq ft"), (3000, 4000, "3,000&ndash;4,000 sq ft"),
              (4000, 5000, "4,000&ndash;5,000 sq ft"), (5000, 10 ** 9, "5,000+ sq ft")]


def size_cards(rows, span, short, min_sales=3):
    """HTML cards: what homes in each size range sold for. rows: sales, newest first."""
    groups = [(lbl, [r for r in rows if r.get("living_area") and lo <= r["living_area"] < hi]) for lo, hi, lbl in SIZE_BANDS]
    groups = [(lbl, g) for lbl, g in groups if len(g) >= min_sales]
    if not groups:
        return ""
    top = max(len(g) for _, g in groups)
    out = []
    for lbl, g in groups:
        psf = sorted(r["close_price"] / r["living_area"] for r in g)[len(g) // 2]
        out.append(f'<div class="bc"><div class="bc-h"><h3>{lbl}</h3><b>{span([r["close_price"] for r in g])}</b></div>'
                   f'<div class="bc-bar"><i style="width:{round(100 * len(g) / top)}%"></i></div>'
                   f'<div class="bc-m">{len(g)} sales &middot; about ${psf:,.0f}/sq ft &middot; last sold {short(g[0]["close_price"])}, '
                   f'{g[0]["_d"].strftime("%b")} {g[0]["_d"].year}</div></div>')
    return "".join(out)
