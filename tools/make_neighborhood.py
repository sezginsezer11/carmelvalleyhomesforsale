#!/usr/bin/env python3
"""Draft tools/communities/<slug>.json for a single-family neighborhood from the data.

    python3 tools/make_neighborhood.py Lexington
    python3 tools/build_communities.py lexington

Everything written is derived from the sold data, the neighborhood map and the school
maps: no builder names, HOA amounts or amenities are invented. Add hand-written facts
(photos, HOA, builder, amenities, an "analysis" section) to the JSON afterwards; this
script refuses to overwrite a file that exists unless you pass --force.
Stdlib only.
"""
import collections
import datetime
import json
import os
import re
import statistics
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from sold_data import load_sales, AREA_LABELS  # noqa: E402
from schools import elementary_for, DMUSD  # noqa: E402

# Neighborhood and school pages that exist on the site (name -> path).
NEIGHBORHOOD_PAGES = {"Lexington": "/lexington-carmel-valley-homes-for-sale/"}
SCHOOL_PAGES = {"Sage Canyon Elementary": "/sage-canyon-elementary-homes-for-sale/"}
HUB = "/carmel-valley-neighborhoods/"
# Area pages (tools/build_area.py) for every area with a boundary in tools/kml/carmel-valley-areas.kml.
AREA_PAGES = {k: f"/{re.sub(r'[^a-z0-9]+', '-', AREA_LABELS[k].lower()).strip('-')}-homes-for-sale/"
              for k in ["n", "s", "cch", "phr", "tdm", "th", "dmm"]}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:
        return t.replace(year=t.year - n, day=28)


def short(n):
    return "${}M".format(("%.2f" % (n / 1e6 + 1e-9)).rstrip("0").rstrip(".")) if n >= 1e6 else "${:,.0f}K".format(n / 1e3)


def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def centroid(rings):
    pts = [p for r in rings for p in r]
    return round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6)


def draft(name):
    atlas = json.load(open(os.path.join(TOOLS, "atlas_data.json"), encoding="utf-8"))
    comms = atlas["c"]
    c = next((x for x in comms if x["n"].lower() == name.lower()), None)
    if not c:
        raise SystemExit(f"{name} is not on the neighborhood map (tools/atlas_data.json)")
    name, area = c["n"], AREA_LABELS.get(c["sub"], "Carmel Valley")
    all_rows = load_sales()
    rows = [r for r in all_rows if (r.get("community_name") or "").strip().lower() == name.lower()]
    five = [r for r in rows if r["_d"] >= years_ago(5)]
    if len(five) < 5:
        raise SystemExit(f"{name}: only {len(five)} single-family sales in 5 years, too few for a page")
    cv5 = [r for r in all_rows if r["_d"] >= years_ago(5)]
    prices = [r["close_price"] for r in five]
    sqft = [r["living_area"] for r in five if r.get("living_area")]
    yb = [r["year_built"] for r in rows if r.get("year_built")]
    lots = [r["lot_size_sqft"] for r in five if r.get("lot_size_sqft")]
    dom = med([r.get("days_on_market") for r in five])
    cv_dom = med([r.get("days_on_market") for r in cv5])
    cv_lot = med([r.get("lot_size_sqft") for r in cv5])
    m5, cv_m5 = med(prices), med([r["close_price"] for r in cv5])
    beds = collections.Counter(r.get("beds_total") for r in five if r.get("beds_total"))
    common = [b for b, _ in beds.most_common()]
    card_beds = sorted(b for b, n in beds.items() if n >= 2)[:3]
    per_year = len(five) / 5
    elem = collections.Counter(elementary_for(r.get("lat"), r.get("lng")) for r in rows if r.get("lat"))
    school, share = (elem.most_common(1)[0] if elem else (None, 0))
    lat, lng = centroid(c["p"])
    homes = c.get("homes")
    yb_txt = (f"{min(yb)}&ndash;{max(yb)}" if max(yb) > min(yb) else str(min(yb))) if yb else None
    sq_txt = f"{min(sqft):,}&ndash;{max(sqft):,}" if sqft else None
    path = f"/{slug(name)}-carmel-valley-homes-for-sale/"

    facts = [{"icon": "price", "value": f"{short(min(prices))}&ndash;{short(max(prices))}", "label": "Sold, 5 yrs"},
             {"icon": "price", "value": short(m5), "label": "Median sale"}]
    if homes:
        facts.append({"icon": "units", "value": f"{homes}", "label": "Homes"})
    if yb_txt:
        facts.append({"icon": "built", "value": yb_txt, "label": "Built"})
    if sq_txt:
        facts.append({"icon": "sqft", "value": sq_txt, "label": "Sq ft"})
    if lots:
        facts.append({"icon": "sqft", "value": f"{med(lots):,.0f} sq ft", "label": "Median lot"})
    if dom is not None:
        facts.append({"icon": "time", "value": f"{round(dom)} days", "label": "Median on market"})
    facts = facts[:8]

    if school and share / sum(elem.values()) >= 0.8:
        elem_entry = {"level": "Elementary", "name": school, "district": DMUSD}
        school_line = f"{name} is in the {school} attendance area ({DMUSD})."
    else:
        elem_entry = {"level": "Elementary", "name": "Confirm with the district",
                      "district": "Del Mar Union SD or Solana Beach SD, depending on the street"}
        school_line = f"Elementary school depends on the street in {name}; confirm the address with the district."
    schools = [elem_entry,
               {"level": "Middle School", "name": "Confirm with the district", "district": "San Dieguito Union High School District"},
               {"level": "High School", "name": "Torrey Pines High", "district": "San Dieguito Union High School District (Canyon Crest Academy and San Dieguito Academy by lottery)"}]

    by_idx = {i: x for i, x in enumerate(comms)}
    nb = [(by_idx[j], miles) for j, miles in c.get("nb", [])]
    nearby = [[x["n"], "next door" if m < 0.05 else f"{m:.1f} mi"] for x, m in nb[:6]]
    similar = []
    for x, m in nb:
        g = [r for r in all_rows if (r.get("community_name") or "").strip().lower() == x["n"].lower() and r["_d"] >= years_ago(5)]
        if len(g) < 3:
            continue
        mm = med([r["close_price"] for r in g])
        href = NEIGHBORHOOD_PAGES.get(x["n"]) or AREA_PAGES.get(x["sub"]) or HUB
        similar.append({"href": href, "img": "", "alt": "", "name": x["n"],
                        "meta": f'{len(g)} sales in 5 yrs &middot; median {short(mm)}',
                        "desc": f'{"Next door" if m < 0.05 else f"{m:.1f} miles away"} in {AREA_LABELS.get(x["sub"], "Carmel Valley")}.',
                        "cta": "Neighborhood guide" if x["n"] in NEIGHBORHOOD_PAGES else f'{AREA_LABELS.get(x["sub"], "Area")} guide'})
        if len(similar) == 3:
            break

    vs = "above" if m5 > cv_m5 else "below"
    reasons = []
    if sqft and med(sqft) >= 3000:
        reasons.append(["Big floor plans.", f"The median home here has {med(sqft):,.0f} sq ft, and {common[0]}-bedroom homes are the most common."])
    elif common:
        reasons.append(["Family-sized homes.", f"{common[0]}-bedroom homes are the most common, around {med(sqft):,.0f} sq ft."])
    if lots and cv_lot and med(lots) > cv_lot * 1.1:
        reasons.append(["Bigger lots.", f"The median lot is about {med(lots):,.0f} sq ft, larger than the Carmel Valley median of {cv_lot:,.0f}."])
    if school and SCHOOL_PAGES.get(school):
        reasons.append(["School area.", f'Homes here are in the <a href="{SCHOOL_PAGES[school]}">{school}</a> attendance area.'])
    elif school:
        reasons.append(["School area.", f"Homes here are in the {school} attendance area."])
    if dom is not None and cv_dom is not None and dom <= cv_dom:
        reasons.append(["Homes sell quickly.", f"The median home sold in {round(dom)} days, versus {round(cv_dom)} across Carmel Valley."])
    good, weigh = [], []
    good.append(["Buyers who want space", f'{sq_txt} sq ft homes with {", ".join(str(b) for b in sorted(common[:3]))} bedrooms.'] if sq_txt else
                ["Family buyers", "Single-family homes in a settled Carmel Valley neighborhood."])
    if school:
        good.append(["School-focused families", f"{school} for elementary, Torrey Pines High for high school."])
    good.append(["Buyers who like predictable comps", f"About {per_year:.0f} sales a year, so pricing is easy to check."] if per_year >= 5 else
                ["Buyers who want a quieter neighborhood", f"Only about {per_year:.0f} sales a year, so homes don't come up often."])
    weigh.append([f"Prices {vs} the Carmel Valley median", f"{name}'s 5-year median is {short(m5)}, versus {short(cv_m5)} for all Carmel Valley houses."])
    if yb and max(yb) < 2005:
        weigh.append(["Homes are 20+ years old", "Check roofs, windows and HVAC, and budget for updates in homes that haven't been remodeled."])
    if dom is not None and dom <= 10:
        weigh.append(["Move fast", f"Half of all homes sell within {round(dom)} days. Get pre-approved before you start touring."])

    faq = [
        {"q": f"How much do homes in {name} cost?",
         "a": f"<p>Over the last 5 years, {len(five)} single-family homes in {name} sold between {short(min(prices))} and {short(max(prices))}, "
              f"with a median of {short(m5)}. See the price-by-bedroom cards and recent sales on this page for current numbers.</p>"},
        {"q": f"What school area is {name} in?",
         "a": f"<p>{school_line} High school is Torrey Pines High (San Dieguito Union HSD), with Canyon Crest Academy and San Dieguito Academy "
              "available by lottery. School boundaries change, so confirm any address with the district before you buy.</p>"},
        {"q": f"How fast do homes sell in {name}?",
         "a": f"<p>The median {name} home sold in {round(dom)} days on market over the last 5 years. Well-priced homes often go under contract in the first week.</p>"},
        {"q": f"Where is {name} in Carmel Valley?",
         "a": f"<p>{name} is in {area}, next to {', '.join(n for n, _ in nearby[:3])}. See the map on this page for its boundary.</p>"},
    ]
    if homes:
        faq.insert(1, {"q": f"How many homes are in {name}?",
                       "a": f"<p>{name} has about {homes} homes, built {yb_txt.replace('&ndash;', ' to ')}." if yb_txt else f"<p>{name} has about {homes} homes."})
        faq[1]["a"] += "</p>"

    return slug(name), {
        "slug": slug(name), "name": name, "path": path, "type": "sfr",
        "parent_name": "Neighborhoods", "parent_url": HUB, "api_community": name,
        "seo": {"title": f"{name} Homes for Sale | Carmel Valley, San Diego 92130",
                "description": f"{name} homes for sale in Carmel Valley 92130: live listings, sold prices by bedroom, school area, map and FAQs.",
                "jsonld_description": f"{name} single-family homes for sale in {area}, Carmel Valley, San Diego. 5-year median sale {short(m5)}."},
        "geo": {"lat": lat, "lng": lng}, "boundary": c["p"],
        "hero": {"eyebrow": f"{area} &middot; Single-family", "h1": f"{name} Homes for Sale",
                 "lead": f"{homes or 'A'}{' ' if homes else ' '}single-family homes{f' built {yb_txt}' if yb_txt else ''} in {area}"
                         f"{f', in the {school} area' if school else ''}. Live listings, real sold prices and what to know before you buy.",
                 "img": "", "alt": ""},
        "facts": facts,
        "location_intro": (f'{name} is in <a href="{AREA_PAGES[c["sub"]]}">{area}</a>.' if c.get("sub") in AREA_PAGES else f"{name} is in {area}.")
                          + f" Its closest neighbors are {', '.join(n for n, _ in nearby[:3])}.",
        "schools": schools, "nearby": nearby,
        "glance": {"h2": f"What a {name} Home Costs by Bedrooms",
                   "lede": f"Closed single-family sales in {name} over the last 5 years, by bedroom count.",
                   "cards": [{"beds": b, "count": "", "size": "", "median": "", "range": ""} for b in card_beds],
                   "ratio": f"{common[0]}-bedroom homes made up {beds[common[0]]} of the {len(five)} sales."},
        "life": {"lead": f"{name} is a neighborhood of {homes or 'single-family'}{' ' if homes else ''}{'homes' if homes else 'homes'}"
                         f"{f' built {yb_txt}' if yb_txt else ''} in {area}. Homes run {sq_txt} sq ft"
                         f"{f' on lots around {med(lots):,.0f} sq ft' if lots else ''}, and about {per_year:.0f} sell each year.",
                 "reasons": reasons},
        "similar": {"h2": f"Neighborhoods Near {name}", "intro": f"Worth comparing if you like {name}'s location.", "cards": similar},
        "fit": {"good": good, "weigh": weigh},
        "faq_h2": f"{name} Homes: Common Questions", "faq": faq,
        "contact_lead": f"Buying or selling in {name}? I track every sale here and can tell you what a home is really worth, with the comps to back it up.",
    }


def main(argv):
    force = "--force" in argv
    names = [a for a in argv if a != "--force"]
    for n in names:
        s, data = draft(n)
        dest = os.path.join(TOOLS, "communities", s + ".json")
        if os.path.exists(dest) and not force:
            print(f"skip {dest} (exists; use --force to overwrite)")
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        json.dump(data, open(dest, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"wrote {os.path.relpath(dest, os.path.dirname(TOOLS))}")


if __name__ == "__main__":
    main(sys.argv[1:])
