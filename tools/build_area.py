#!/usr/bin/env python3
"""Build area pages (Pacific Highlands Ranch, Torrey Hills, ...) from one shared design.

    python3 tools/build_area.py phr          # one area (keys: n s cch phr tdm th dmm rp)
    python3 tools/build_area.py              # every area that has a boundary

Inputs
- tools/kml/carmel-valley-areas.kml   area boundaries (your "Carmel Valley Area Maps" export)
- tools/atlas_data.json               neighborhood shapes (tools/build_atlas.py)
- tools/sold_data.py                  single-family sales; a sale belongs to an area when it
                                      sits inside the area boundary, so unnamed sales count too
- tools/schools.py                    elementary attendance areas (Del Mar Union map)
Shell (CSS, masthead, contact, footer) comes from tools/community-template.html. Stdlib only.
"""
import collections
import datetime
import html
import json
import os
import re
import statistics
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from sold_data import load_sales, AREA_LABELS  # noqa: E402
from schools import _placemarks, _inside, elementary_for, DMUSD_URL, SDUHSD_URL  # noqa: E402
from make_neighborhood import NEIGHBORHOOD_PAGES, SCHOOL_PAGES, slug  # noqa: E402
from build_communities_hub import load as load_hub, AREA_TEXT, COLORS  # noqa: E402

SITE = "https://carmelvalleyhomesforsale.com"
HUB = "/carmel-valley-neighborhoods/"
e = html.escape

# KML shape name -> area key (the export calls Torrey Highlands "Torrey Del Mar")
KML_AREA = {"Torrey Del Mar": "tdm", "Torrey Highlands": "tdm", "Pacific Highlands Ranch": "phr", "Del Mar Mesa": "dmm",
            "Carmel Country Highlands": "cch", "Torrey Hills": "th", "South of Del Mar Heights Road": "s",
            "North of Del Mar Heights Road": "n", "Rancho Pacifica": "rp"}
# Extra, hand-checked notes per area (shown under "Good to know"). Keep these factual.
NOTES = {
    "phr": ["Many Pacific Highlands Ranch neighborhoods pay Mello-Roos (a special tax for local infrastructure) on top of "
            "regular property tax. The amount differs by neighborhood and year, so check the tax bill on every listing."],
}


def area_path(key):
    return f"/{slug(AREA_LABELS[key])}-homes-for-sale/"


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:
        return t.replace(year=t.year - n, day=28)


def short(n):
    return "${}M".format(("%.2f" % (n / 1e6 + 1e-9)).rstrip("0").rstrip(".")) if n >= 1e6 else "${:,.0f}K".format(n / 1e3)


def money(n):
    return "${:,.0f}".format(n)


def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def span(p):
    """Low-high sold price, for showing what homes sold for (history, not an average)."""
    return f"{short(min(p))}&ndash;{short(max(p))}" if max(p) > min(p) else short(p[0])


def fmt_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def area_shapes():
    out = {}
    for name, polys in _placemarks(os.path.join(TOOLS, "kml", "carmel-valley-areas.kml")):
        k = KML_AREA.get(name)
        if k:
            out.setdefault(k, []).extend(p for p in polys if len(p) > 4)  # drop stray slivers
    return out


def build(key, shapes, hub_comms, all_rows):
    label, path = AREA_LABELS[key], area_path(key)
    rings = shapes[key]
    inside = lambda r: r.get("lat") and any(_inside(r["lng"], r["lat"], p) for p in rings)  # noqa: E731
    rows = [r for r in all_rows if inside(r)]
    five = [r for r in rows if r["_d"] >= years_ago(5)]
    t12 = [r for r in rows if r["_d"] >= years_ago(1)]
    cv5 = [r for r in all_rows if r["_d"] >= years_ago(5)]
    if len(five) < 10:
        raise SystemExit(f"{label}: only {len(five)} sales in 5 years")
    if not t12:
        raise SystemExit(f"{label}: no sales in the last 12 months")
    # Medians, $/sq ft and days on market use the last 12 months; 5 years is only for sales history.
    cv12 = [r for r in cv5 if r["_d"] >= years_ago(1)]
    m12, cv_m12 = med([r["close_price"] for r in t12]), med([r["close_price"] for r in cv12])
    psf = med([r["close_price"] / r["living_area"] for r in t12 if r.get("living_area")])
    dom = med([r.get("days_on_market") for r in t12])
    yb = sorted(r["year_built"] for r in five if r.get("year_built"))
    today = datetime.date.today()
    stamp = f'{today.strftime("%B")} {today.day}, {today.year}'

    # neighborhoods in this area (the hub's single-family list)
    comms = [c for c in hub_comms if c.get("sub") == key]
    by_name = collections.defaultdict(list)
    for r in five:
        by_name[(r.get("community_name") or "").strip().lower()].append(r)
    nb = []
    for c in comms:
        g = by_name.get(c["n"].lower(), [])
        ybs = [r["year_built"] for r in g if r.get("year_built")]
        g12 = [r["close_price"] for r in g if r["_d"] >= years_ago(1)]
        nb.append({"n": c["n"], "homes": c.get("homes"), "sales": len(g), "prices": [r["close_price"] for r in g],
                   "med": med(g12), "n12": len(g12),
                   "built": (f"{min(ybs)}" if min(ybs) == max(ybs) else f"{min(ybs)}&ndash;{max(ybs)}") if ybs else "",
                   "url": NEIGHBORHOOD_PAGES.get(c["n"]), "p": c["p"]})
    nb.sort(key=lambda x: (-x["sales"], x["n"]))
    nb_rows = ""
    for x in nb:
        name_html = '<a href="%s">%s</a>' % (x["url"], e(x["n"])) if x["url"] else e(x["n"])
        meta = " &middot; ".join(s for s in ["%s homes" % x["homes"] if x["homes"] else "",
                                             "built " + x["built"] if x["built"] else ""] if s)
        nb_rows += ('<tr id="n-%s"><td class="nm">%s<span>%s</span></td><td class="num">%s</td><td class="num">%s</td></tr>'
                    % (slug(x["n"]), name_html, meta, x["sales"] or "&mdash;", span(x["prices"]) if x["prices"] else "&mdash;"))
    priced = [x for x in nb if x["n12"] >= 3]
    lo = min(priced, key=lambda x: x["med"]) if priced else None
    hi = max(priced, key=lambda x: x["med"]) if priced else None

    # price by bedroom
    beds = collections.defaultdict(list)
    for r in five:
        if r.get("beds_total"):
            beds[r["beds_total"]].append(r)  # newest first
    top = max(len(v) for v in beds.values())
    bed_cards = "".join(
        f'<div class="bc"><div class="bc-h"><h3>{b} bedrooms</h3><b>{span([r["close_price"] for r in g])}</b></div>'
        f'<div class="bc-bar"><i style="width:{round(100 * len(g) / top)}%"></i></div>'
        f'<div class="bc-m">{len(g)} sales &middot; last sold {short(g[0]["close_price"])}, {g[0]["_d"].strftime("%b")} {g[0]["_d"].year}</div></div>'
        for b, g in sorted(beds.items()) if len(g) >= 3)

    # schools
    elem = collections.Counter(elementary_for(r.get("lat"), r.get("lng")) for r in five)
    known = [(s, n) for s, n in elem.most_common() if s]
    unknown = elem.get(None, 0)
    school_rows = "".join(
        '<li><span>%s</span><span class="cnt">%d%% of sales</span></li>'
        % ('<a href="%s">%s</a>' % (SCHOOL_PAGES[s], e(s)) if s in SCHOOL_PAGES else e(s), round(100 * n / len(five)))
        for s, n in known)
    if unknown:
        school_rows += (f'<li><span>Other schools, mostly Solana Beach School District</span>'
                        f'<span class="cnt">{round(100 * unknown / len(five))}% of sales</span></li>')

    recent = "".join(
        f'<tr><td class="addr">{e(r.get("address") or "")}<span>{e(r.get("community_name") or "")}</span></td>'
        f'<td class="num">{r.get("beds_total") or "&mdash;"} / {r.get("baths_total") or "&mdash;"}</td>'
        f'<td class="num price">{money(r["close_price"])}</td><td class="num">{fmt_date(r["_d"])}</td></tr>' for r in rows[:10])

    vs = "above" if m12 > cv_m12 else "below"
    notes = " ".join(e(n) for n in NOTES.get(key, []))
    faqs = [
        (f"How much does a house in {label} cost?",
         f"In the last 12 months, {len(t12)} single-family homes in {label} sold at a median of {money(m12)} (about {money(psf)} per sq ft), "
         f"{vs} the Carmel Valley median of {money(cv_m12)}. Over the last 5 years, {len(five)} sold for between "
         f"{money(min(r['close_price'] for r in five))} and {money(max(r['close_price'] for r in five))}."),
        (f"Which neighborhoods are in {label}?",
         f"{label} has {len(comms)} single-family neighborhoods, including {', '.join(x['n'] for x in nb[:6])}."
         + (f" Among those with at least three sales in the last 12 months, {lo['n']} had the lowest median ({short(lo['med'])}) and {hi['n']} the highest ({short(hi['med'])})."
            if lo and hi and lo is not hi else "")),
        (f"How old are the homes in {label}?",
         f"Homes that sold in the last 5 years were built between {yb[0]} and {yb[-1]}, with a median year of {yb[len(yb) // 2]}."),
        (f"What schools serve {label}?",
         ("Elementary school depends on the street: " + ", ".join(f"{s} ({round(100 * n / len(five))}% of recent sales)" for s, n in known[:4])
          + (", and Solana Beach School District schools for much of the rest" if unknown else "") + ". "
          if known else "Most homes are served by Solana Beach School District elementary schools. ")
         + "High school is Torrey Pines High, with Canyon Crest Academy and San Dieguito Academy by lottery. Confirm any address with the district."),
        (f"How fast do homes sell in {label}?",
         f"Over the last 12 months, the median home sold in {round(dom)} days on market."),
    ]
    if key in NOTES:
        faqs.insert(3, (f"Do homes in {label} pay Mello-Roos?", NOTES[key][0]))
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Neighborhoods", "item": SITE + HUB},
            {"@type": "ListItem", "position": 3, "name": label, "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    tpl = open(os.path.join(TOOLS, "community-template.html"), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", f"Looking in {label}?").replace(
        "{{contact_lead}}", f"Tell me your budget and must-haves and I&rsquo;ll send you the {label} homes that fit, including ones that haven&rsquo;t hit the market yet.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    title = f"{label} Homes for Sale | Carmel Valley, San Diego 92130"
    desc = f"{label} single-family homes in Carmel Valley: 12-month median {short(m12)}, {len(comms)} neighborhoods, sold prices, schools and a map."
    if len(desc) > 160:
        desc = f"{label} homes in Carmel Valley: 12-month median {short(m12)}, {len(comms)} neighborhoods, sold prices and a map."
    color = COLORS.get(key, "#0b5c8c")
    mapdata = json.dumps({"area": [[[round(y, 5), round(x, 5)] for x, y in p] for p in rings],
                          "nb": [{"n": x["n"], "m": short(x["med"]) if x["med"] else None, "k": x["n12"], "r": span(x["prices"]) if x["prices"] else "", "s": x["sales"], "u": x["url"], "p": x["p"]} for x in nb]},
                         separators=(",", ":"))

    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Carmel Valley Homes for Sale">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="{SITE}{path}index.md">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" media="print" onload="this.media='all'">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<link rel="stylesheet" href="/assets/rs-embed.css?v=3">
<script src="/assets/rs-embed.js?v=3" defer></script>
<style>{css}
  /* ============ AREA PAGE ============ */
  .ar-hero{{padding:28px 0 8px}}
  .ar-hero .eyebrow{{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--lake);background:#e6f0f6;padding:5px 12px;border-radius:6px;font-weight:700;margin-bottom:12px}}
  .ar-hero .eyebrow i{{width:10px;height:10px;border-radius:50%;background:{color}}}
  .ar-hero h1{{font-size:clamp(28px,4.4vw,44px);font-weight:800;line-height:1.1;letter-spacing:-.02em;max-width:820px}}
  .ar-hero p{{font-size:16px;color:#3f4852;margin-top:12px;max-width:720px}}
  .ar-map{{position:relative;z-index:0;border:1px solid var(--line);border-radius:14px;overflow:hidden}}
  #arMap{{height:min(60vh,520px);background:#e8ecef}}
  .map-views{{position:absolute;top:10px;right:10px;z-index:500;display:flex;background:#fff;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.18);overflow:hidden}}
  .map-views button{{border:0;background:#fff;font:600 12.5px var(--sans);padding:7px 11px;cursor:pointer;color:#37404a}}
  .map-views button[aria-pressed="true"]{{background:var(--lake);color:#fff}}
  .map-card{{position:absolute;left:10px;bottom:10px;right:10px;max-width:300px;z-index:500;background:#fff;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.18);padding:12px 14px;display:none}}
  .map-card.show{{display:block}}
  .map-card h3{{font-size:16px;font-weight:800;margin-right:22px}}
  .map-card .mc-m{{font-size:13.5px;color:var(--label);margin-top:3px}}
  .map-card a{{display:inline-block;margin-top:8px;background:var(--lake);color:#fff;font-weight:600;font-size:13.5px;padding:7px 12px;border-radius:7px}}
  .map-card .x{{position:absolute;top:6px;right:10px;border:0;background:none;font-size:20px;color:var(--label);cursor:pointer}}
  .leaflet-tooltip.lbl{{background:none;border:0;box-shadow:none;padding:0;color:#101418;font-weight:700;font-size:11px;text-shadow:0 0 3px #fff,0 0 3px #fff;white-space:nowrap}}
  .leaflet-tooltip.lbl::before{{display:none}}
  .note{{font-size:13px;color:var(--label);margin-top:10px}}
  .two{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;align-items:start}}
  .tbl{{width:100%;border-collapse:collapse;font-size:15px}}
  .tbl th{{text-align:left;font-size:12.5px;color:var(--label);font-weight:600;padding:0 8px 8px;border-bottom:1px solid var(--line)}}
  .tbl td{{padding:11px 8px;border-bottom:1px solid var(--mist);vertical-align:top}}
  .tbl tr[id]{{scroll-margin-top:90px}}
  .tbl tr:target td{{background:#eef5fa}}
  .tbl .num,.tbl th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .tbl .nm{{font-weight:700}}
  .tbl .nm span,.tbl .addr span{{display:block;font-weight:400;font-size:12.5px;color:var(--label)}}
  .tbl .addr{{font-weight:600}}
  .tbl .price{{font-weight:700}}
  .bcs{{display:grid;gap:10px}}
  .bc{{border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
  .bc-h{{display:flex;justify-content:space-between;align-items:baseline}}
  .bc h3{{font-size:15.5px;font-weight:700}}
  .bc-bar{{height:6px;background:#e6f0f6;border-radius:3px;margin:8px 0 6px}}
  .bc-bar i{{display:block;height:6px;background:var(--lake);border-radius:3px}}
  .bc-m{{font-size:13px;color:var(--label)}}
  .sch{{list-style:none;border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  .sch li{{display:flex;justify-content:space-between;gap:12px;padding:12px 14px;border-top:1px solid var(--mist);font-weight:600}}
  .sch li:first-child{{border-top:0}}
  .sch .cnt{{font-weight:500;color:var(--label);white-space:nowrap}}
  .know{{background:#f2f7fa;border:1px solid #d3e4ee;border-radius:12px;padding:14px 16px;margin-top:14px;font-size:15px}}
  .h3{{font-size:18px;font-weight:800;margin-bottom:10px}}
  .scroll{{overflow-x:auto}}
  @media(max-width:760px){{
    .two{{grid-template-columns:minmax(0,1fr)}}
    .tbl{{font-size:13.5px}}
    .tbl td{{padding:10px 5px}}
    #arMap{{height:56vh}}
  }}
</style>
</head>
<body>

{masthead}

<nav class="breadcrumb" aria-label="Breadcrumb">
  <div class="wrap"><a href="/">Home</a><span class="sep">/</span><a href="{HUB}">Neighborhoods</a><span class="sep">/</span><span class="current">{e(label)}</span></div>
</nav>

<section class="ar-hero" style="padding-left:0;padding-right:0">
  <div class="wrap">
    <span class="eyebrow"><i></i>Carmel Valley &middot; San Diego 92130</span>
    <h1>{e(label)} Homes for Sale</h1>
    <p>{e(AREA_TEXT.get(key, ""))}</p>
  </div>
</section>

<section class="facts" style="padding-top:12px">
  <div class="wrap facts-grid">
    <div class="fact"><div class="num">{short(m12)}</div><div class="lbl">Median sale, last 12 mo</div></div>
    <div class="fact"><div class="num">{len(t12)}</div><div class="lbl">Sold, last 12 mo</div></div>
    <div class="fact"><div class="num">{len(comms)}</div><div class="lbl">Neighborhoods</div></div>
    <div class="fact"><div class="num">{round(dom)} days</div><div class="lbl">On market, last 12 mo</div></div>
  </div>
</section>

<section id="map-section" style="padding-top:28px;padding-bottom:20px">
  <div class="wrap">
    <h2 class="h3">{e(label)} neighborhoods on the map</h2>
    <div class="ar-map"><div id="arMap" role="region" aria-label="Map of {e(label)} and its neighborhoods"></div><div class="map-views" role="group" aria-label="Map view"><button type="button" data-b="sat" aria-pressed="true">Satellite</button><button type="button" data-b="map" aria-pressed="false">Map</button></div><div class="map-card" id="mcard" aria-live="polite"></div></div>
    <p class="note">Tap a neighborhood for what its homes sold for. Boundaries are approximate.</p>
  </div>
</section>

<section class="listings" id="listings" style="padding-top:12px;padding-bottom:16px">
  <div class="wrap">
    <div class="listings-head"><h2 class="listings-title">Carmel Valley houses for sale now</h2><span class="listings-tag">Live MLS</span></div>
    <p class="note" style="margin:-6px 0 12px">This search shows all of 92130. Zoom the map to {e(label)}, or ask me for every listing inside it.</p>
    <div class="rs-embed" style="max-width:1100px;margin:0 auto">
      <iframe data-src="https://sezsezer.realscout.com/homesearch/map?ptype=SFR&amp;geo_type=zipcode&amp;geo_id=92130&amp;for_sale=1&amp;for_rent=0" title="Carmel Valley Single-Family Homes for Sale"></iframe>
    </div>
  </div>
</section>

<section id="neighborhoods">
  <div class="wrap two">
    <div>
      <h2 class="h3">Neighborhoods in {e(label)}</h2>
      <table class="tbl"><thead><tr><th>Neighborhood</th><th class="num">Sales, 5 yrs</th><th class="num">Sold for, 5 yrs</th></tr></thead>
      <tbody>{nb_rows}</tbody></table>
    </div>
    <div id="prices">
      <h2 class="h3">Prices by bedroom</h2>
      <div class="bcs">{bed_cards}</div>
      <p class="note">{len(five)} single-family sales inside {e(label)}, last 5 years, as of {stamp}.</p>
    </div>
  </div>
</section>

<section id="schools" style="padding-top:8px">
  <div class="wrap two">
    <div>
      <h2 class="h3">Elementary schools</h2>
      <ul class="sch">{school_rows}</ul>
      <p class="note">Share of the last 5 years of sales inside each attendance area. High school is Torrey Pines High; Canyon Crest Academy and San Dieguito Academy by lottery. Confirm any address with <a href="{DMUSD_URL}" target="_blank" rel="noopener">Del Mar Union</a>, Solana Beach SD or <a href="{SDUHSD_URL}" target="_blank" rel="noopener">San Dieguito Union HSD</a>.</p>
      {'<div class="know"><strong>Good to know.</strong> ' + notes + '</div>' if notes else ""}
    </div>
    <div id="sold">
      <h2 class="h3">Recently sold in {e(label)}</h2>
      <div class="scroll"><table class="tbl"><thead><tr><th>Address</th><th class="num">Bd / Ba</th><th class="num">Price</th><th class="num">Closed</th></tr></thead>
      <tbody>{recent}</tbody></table></div>
    </div>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <div class="sec-head"><h2>{e(label)} Homes: Common Questions</h2></div>
    <div class="faq-list">
{faq_html}
    </div>
  </div>
</section>

{contact_footer}

{jsonld}

<nav class="bottom-nav" aria-label="Jump to section">
  <a href="#map-section"><svg viewBox="0 0 24 24"><path d="M12 21s7-7.1 7-12a7 7 0 0 0-14 0c0 4.9 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>Map</a>
  <a href="#neighborhoods"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>Areas</a>
  <a href="#schools"><svg viewBox="0 0 24 24"><path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/></svg>Schools</a>
  <a href="#contact"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>Contact</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')"><svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>Menu</a>
</nav>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="/assets/basemap.js"></script>
<script>
(function(){{
  var D={mapdata}, C='{color}', sel=null;
  function esc(s){{return String(s).replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}});}}
  var map=L.map('arMap',{{scrollWheelZoom:false,zoomSnap:0.5}});
  // outlines are white over satellite and the area color over the street map
  var LN='#ffffff', BM=CVBase(map);
  var area=L.polygon(D.area,{{color:LN,weight:2.5,dashArray:'6 5',fill:false,interactive:false}}).addTo(map);
  var card=document.getElementById('mcard');
  var layers=D.nb.map(function(o){{
    var l=L.polygon(o.p,{{color:LN,weight:1.2,fillColor:C,fillOpacity:.32}}).addTo(map);
    l.bindTooltip(o.n,{{sticky:true,direction:'top'}});
    l.on('click',function(ev){{L.DomEvent.stopPropagation(ev);pick(o,l);}});
    return l;}});
  function pick(o,l){{
    if(sel)sel.setStyle({{weight:1.2,color:LN,fillOpacity:.32}});sel=l;l.setStyle({{weight:3,color:'#101418',fillOpacity:.6}});
    card.innerHTML='<button type="button" class="x" aria-label="Close">&times;</button><h3>'+esc(o.n)+'</h3><div class="mc-m">'+(o.s?(o.m?'12-mo median '+o.m+' ('+o.k+' sold)':'No sales in the last 12 months')+'<br>'+o.s+' sold in 5 yrs: '+o.r:'No recent single-family sales')+'</div>'
      +(o.u?'<a href="'+o.u+'">Neighborhood guide &rarr;</a>':'<a href="#contact">Ask about '+esc(o.n)+'</a>');
    card.classList.add('show');card.querySelector('.x').onclick=function(){{card.classList.remove('show');l.setStyle({{weight:1.2,color:LN,fillOpacity:.32}});sel=null;}};
  }}
  map.on('click',function(){{card.classList.remove('show');if(sel){{sel.setStyle({{weight:1.2,color:LN,fillOpacity:.32}});sel=null;}}}});
  CVBase.bind(BM,document.querySelector('.ar-map .map-views'),function(k){{LN=k==='sat'?'#ffffff':C;area.setStyle({{color:LN}});
    layers.forEach(function(l){{if(l!==sel)l.setStyle({{color:LN}});}});}});
  function fit(){{map.invalidateSize();map.fitBounds(area.getBounds(),{{padding:[12,12]}});}}
  fit();window.addEventListener('load',fit);
}})();
</script>
{hide_js}
</body>
</html>
'''
    left = re.findall(r"\{\{\w+\}\}", page)
    if left:
        raise SystemExit(f"unfilled placeholders: {sorted(set(left))}")
    dest = os.path.join(ROOT, path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(page)
    print(f"wrote {path}: {len(five)} sales in 5 yrs, {len(comms)} neighborhoods, {len(page)//1024} KB")


if __name__ == "__main__":
    shapes = area_shapes()
    _, hub_comms, _ = load_hub()
    rows = load_sales()
    for k in sys.argv[1:] or [k for k in AREA_LABELS if k in shapes]:
        if k not in shapes:
            raise SystemExit(f"no boundary for {k} in tools/kml/carmel-valley-areas.kml")
        build(k, shapes, hub_comms, rows)
