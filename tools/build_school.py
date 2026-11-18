#!/usr/bin/env python3
"""Build a school-area page: single-family homes inside one elementary attendance area.

    python3 tools/build_school.py "Sage Canyon Elementary"

Sales are matched to the school by their map location (tools/schools.py), so the
numbers cover exactly the homes inside the attendance boundary. Shell (CSS, masthead,
contact, footer) comes from tools/community-template.html. Stdlib only.
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
from sold_data import size_cards, load_sales  # noqa: E402
from schools import elementary_for, school_boundary, share_inside, DMUSD, DMUSD_URL, SDUHSD_URL  # noqa: E402
from make_neighborhood import NEIGHBORHOOD_PAGES, SCHOOL_PAGES, AREA_PAGES, slug  # noqa: E402
from build_communities_hub import load as load_communities, COLORS  # noqa: E402
from explorer import explorer  # noqa: E402

SITE = "https://carmelvalleyhomesforsale.com"
e = html.escape


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


def build(school):
    path = SCHOOL_PAGES[school]
    short_name = school.replace(" Elementary", "")
    rows = [r for r in load_sales() if elementary_for(r.get("lat"), r.get("lng")) == school]
    all5 = [r for r in load_sales() if r["_d"] >= years_ago(5)]
    five = [r for r in rows if r["_d"] >= years_ago(5)]
    t12 = [r for r in rows if r["_d"] >= years_ago(1)]
    if len(five) < 10:
        raise SystemExit(f"{school}: only {len(five)} sales in 5 years")
    if not t12:
        raise SystemExit(f"{school}: no sales in the last 12 months")
    # Medians, $/sq ft and days on market use the last 12 months; 5 years is only for sales history.
    cv12 = [r for r in all5 if r["_d"] >= years_ago(1)]
    m12, cv_m12 = med([r["close_price"] for r in t12]), med([r["close_price"] for r in cv12])
    psf = med([r["close_price"] / r["living_area"] for r in t12 if r.get("living_area")])
    dom = med([r.get("days_on_market") for r in t12])
    # map: the attendance boundary, and the mapped single-family neighborhoods inside it
    # (at least 30% of a neighborhood's area; boundaries split a few of them)
    data, comms, _ = load_communities()
    inside = []
    for c in comms:
        sh = share_inside(c["p"], school)
        if sh >= 0.3:
            inside.append(dict(c, note="" if sh >= 0.8 else "Partly in this area"))
    groups = [(k, l, sorted((c for c in inside if c.get("sub") == k), key=lambda c: c["n"])) for k, l in data["subs"]]
    groups = [g for g in groups if g[2]]
    map_homes = sum(c.get("homes") or 0 for c in inside)
    x = explorer(inside, groups, COLORS, NEIGHBORHOOD_PAGES, AREA_PAGES, list_title=f"{short_name} neighborhoods",
                 hint=f"The single-family neighborhoods inside the {e(school)} attendance boundary, grouped by area. Tap one to find it on the map.",
                 map_aria=f"Map of the {school} attendance boundary and the neighborhoods inside it",
                 map_note=f"Dashed line: the {e(school)} attendance boundary from the {DMUSD} map. Neighborhood outlines are approximate. "
                          f"Boundaries change, so confirm any address with <a href=\"{DMUSD_URL}\" target=\"_blank\" rel=\"noopener\">the district</a>.",
                 zone=school_boundary(school))
    today = datetime.date.today()
    stamp = f'{today.strftime("%B")} {today.day}, {today.year}'

    # neighborhoods inside the area (by where their sales are)
    groups = collections.defaultdict(list)
    for r in five:
        groups[(r.get("community_name") or "").strip()].append(r)
    unnamed = len(groups.pop("", []))
    nbh = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    nb_rows = []
    for n, g in nbh:
        link = NEIGHBORHOOD_PAGES.get(n)
        name_html = f'<a href="{link}">{e(n)}</a>' if link else e(n)
        nb_rows.append(f'<tr><td class="nm">{name_html}</td><td class="num">{len(g)}</td>'
                       f'<td class="num">{span([r["close_price"] for r in g])}</td></tr>')

    # price by home size
    bed_cards = size_cards(five, span, short)

    recent = "".join(
        f'<tr><td class="addr">{e(r.get("address") or "")}<span>{e(r.get("community_name") or "")}</span></td>'
        f'<td class="num">{r.get("beds_total") or "&mdash;"} / {r.get("baths_total") or "&mdash;"}</td>'
        f'<td class="num">{("{:,}".format(r["living_area"]) if r.get("living_area") else "&mdash;")}</td>'
        f'<td class="num price">{money(r["close_price"])}</td><td class="num">{fmt_date(r["_d"])}</td></tr>' for r in rows[:10])

    biggest = nbh[0][0] if nbh else ""
    faqs = [
        (f"How much does a house in the {school} area cost?",
         (f"In the last 12 months, {len(t12)} single-family homes in the {school} attendance area sold at a median of {money(m12)} "
          f"(about {money(psf)} per sq ft), versus {money(cv_m12)} for all Carmel Valley houses. " if t12 else
          f"No single-family homes in the {school} attendance area sold in the last 12 months. ")
         + f"Over the last 5 years, {len(five)} sold for between {money(min(r['close_price'] for r in five))} and {money(max(r['close_price'] for r in five))}."),
        (f"Which neighborhoods are in the {school} area?",
         f"Based on where homes have sold, the area includes {', '.join(n for n, _ in nbh[:8])}"
         + (", and more" if len(nbh) > 8 else "") + f". {biggest} has had the most sales. Boundaries can split a neighborhood, so check the exact address."),
        (f"What middle and high school go with {school}?",
         "High school is Torrey Pines High (San Dieguito Union HSD); Canyon Crest Academy and San Dieguito Academy are available by lottery. "
         "Middle school depends on the address, so confirm it with San Dieguito Union HSD."),
        (f"How do I confirm a home is in the {school} boundary?",
         f"Use the {DMUSD} school locator with the exact address before you make an offer. Boundaries change, and this map is for research only."),
        (f"How fast do homes sell in the {school} area?",
         f"Over the last 12 months, the median home sold in {round(dom)} days on market. Homes in sought-after school areas often go under contract in the first week."),
    ]
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": f"{school} Area Homes", "item": SITE + path}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    tpl = open(os.path.join(TOOLS, "community-template.html"), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", f"Looking in the {short_name} Area?").replace(
        "{{contact_lead}}", f"Tell me your budget and must-haves and I&rsquo;ll send you every home that comes up inside the {school} boundary, including ones that haven&rsquo;t hit the market yet.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    title = f"Homes for Sale in the {school} Area | Carmel Valley 92130"
    desc = f"Carmel Valley houses in the {school} attendance area: 12-month median {short(m12)}, neighborhoods in the boundary, sold prices and a map."
    assert len(desc) <= 160, len(desc)

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
{x["css"]}
  /* ============ SCHOOL AREA ============ */
  .hub-intro{{padding:18px 0 4px}}
  .hub-bar{{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap}}
  .hub-bar h1{{font-size:clamp(21px,2.4vw,27px);font-weight:800;letter-spacing:-.015em;line-height:1.2}}
  .hub-bar h1 span{{font-weight:500;color:var(--label);font-size:.62em;letter-spacing:0;margin-left:6px;white-space:nowrap}}
  .hub-stats{{font-size:13.5px;font-weight:600;color:var(--label)}}
  .note{{font-size:13px;color:var(--label);margin-top:10px}}
  .two{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;align-items:start}}
  .tbl{{width:100%;border-collapse:collapse;font-size:15px}}
  .tbl th{{text-align:left;font-size:12.5px;color:var(--label);font-weight:600;padding:0 8px 8px;border-bottom:1px solid var(--line)}}
  .tbl td{{padding:11px 8px;border-bottom:1px solid var(--mist);vertical-align:top}}
  .tbl .num,.tbl th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .tbl .nm{{font-weight:700}}
  .tbl .addr{{font-weight:600}}
  .tbl .addr span{{display:block;font-weight:400;font-size:12.5px;color:var(--label)}}
  .tbl .price{{font-weight:700}}
  .bcs{{display:grid;gap:10px}}
  .bc{{border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
  .bc-h{{display:flex;justify-content:space-between;align-items:baseline}}
  .bc h3{{font-size:15.5px;font-weight:700}}
  .bc-bar{{height:6px;background:#e6f0f6;border-radius:3px;margin:8px 0 6px}}
  .bc-bar i{{display:block;height:6px;background:var(--lake);border-radius:3px}}
  .bc-m{{font-size:13px;color:var(--label)}}
  .path{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
  .path div{{border:1px solid var(--line);border-radius:12px;padding:14px}}
  .path .lv{{font-size:12px;font-weight:700;color:var(--lake);text-transform:uppercase;letter-spacing:.04em}}
  .path .sn{{font-size:16px;font-weight:700;margin-top:4px}}
  .path .sd{{font-size:13px;color:var(--label);margin-top:2px}}
  .h3{{font-size:18px;font-weight:800;margin-bottom:10px}}
  .scroll{{overflow-x:auto}}
  @media(max-width:760px){{
    .two{{grid-template-columns:minmax(0,1fr)}}
    .path{{grid-template-columns:minmax(0,1fr)}}
    .tbl{{font-size:13.5px}}
    .tbl td{{padding:10px 5px}}
    .hub-intro{{padding:12px 0 2px}}
    .hub-bar h1 span{{display:block;margin:2px 0 0}}
  }}
</style>
{x["head_js"]}
</head>
<body>

{masthead}

<nav class="breadcrumb" aria-label="Breadcrumb">
  <div class="wrap"><a href="/">Home</a><span class="sep">/</span><span class="current">{e(school)} Area</span></div>
</nav>

<section class="hub-intro">
  <div class="wrap hub-bar">
    <h1>{e(school)} Homes for Sale <span>{DMUSD}</span></h1>
    <p class="hub-stats">{len(inside)} neighborhoods{f" &middot; {map_homes:,}+ homes" if map_homes else ""} &middot; median {short(m12)}</p>
  </div>
</section>

{x["html"]}

<section class="facts" style="padding-top:20px">
  <div class="wrap facts-grid">
    <div class="fact"><div class="num">{short(m12)}</div><div class="lbl">Median sale, last 12 mo</div></div>
    <div class="fact"><div class="num">{len(t12)}</div><div class="lbl">Sold, last 12 mo</div></div>
    <div class="fact"><div class="num">{money(psf)}</div><div class="lbl">Per sq ft, last 12 mo</div></div>
    <div class="fact"><div class="num">{round(dom)} days</div><div class="lbl">On market, last 12 mo</div></div>
  </div>
</section>

<section class="listings" id="listings" style="padding-top:12px;padding-bottom:16px">
  <div class="wrap">
    <div class="listings-head"><h2 class="listings-title">Carmel Valley houses for sale now</h2><span class="listings-tag">Live MLS</span></div>
    <p class="note" style="margin:-6px 0 12px">This search shows all of 92130. Ask me which listings are inside the {e(short_name)} boundary.</p>
    <div class="rs-embed" style="max-width:1100px;margin:0 auto">
      <iframe data-src="https://sezsezer.realscout.com/homesearch/map?ptype=SFR&amp;geo_type=zipcode&amp;geo_id=92130&amp;for_sale=1&amp;for_rent=0" title="Carmel Valley Single-Family Homes for Sale"></iframe>
    </div>
  </div>
</section>

<section id="neighborhoods">
  <div class="wrap two">
    <div>
      <h2 class="h3">Where homes sold in the {e(short_name)} area</h2>
      <table class="tbl"><thead><tr><th>Neighborhood</th><th class="num">Sales, 5 yrs</th><th class="num">Sold for, 5 yrs</th></tr></thead>
      <tbody>{"".join(nb_rows)}</tbody></table>
      <p class="note">From where homes sold in the last 5 years.{f" {unnamed} more sales had no neighborhood name." if unnamed else ""}</p>
    </div>
    <div id="prices">
      <h2 class="h3">Prices by home size</h2>
      <div class="bcs">{bed_cards}</div>
      <p class="note">What single-family homes inside the boundary sold for over the last 5 years. As of {stamp}.</p>
    </div>
  </div>
</section>

<section id="sold" style="padding-top:8px">
  <div class="wrap">
    <h2 class="h3">Recently sold in the {e(short_name)} area</h2>
    <div class="scroll"><table class="tbl"><thead><tr><th>Address</th><th class="num">Bd / Ba</th><th class="num">Sq ft</th><th class="num">Price</th><th class="num">Closed</th></tr></thead>
    <tbody>{recent}</tbody></table></div>
  </div>
</section>

<section id="schools" style="padding-top:8px">
  <div class="wrap">
    <h2 class="h3">School path</h2>
    <div class="path">
      <div><div class="lv">Elementary</div><div class="sn">{e(school)}</div><div class="sd">{DMUSD}</div></div>
      <div><div class="lv">Middle</div><div class="sn">Confirm by address</div><div class="sd">San Dieguito Union HSD</div></div>
      <div><div class="lv">High</div><div class="sn">Torrey Pines High</div><div class="sd">Canyon Crest Academy and San Dieguito Academy by lottery</div></div>
    </div>
    <p class="note">Confirm middle and high school with <a href="{SDUHSD_URL}" target="_blank" rel="noopener">San Dieguito Union HSD</a>.</p>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <div class="sec-head"><h2>{e(school)} Area Homes: Common Questions</h2></div>
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
  <a href="#sold"><svg viewBox="0 0 24 24"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>Sold</a>
  <a href="#contact"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>Contact</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')"><svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>Menu</a>
</nav>

{x["js"]}
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
    print(f"wrote {path}: {len(five)} sales in 5 yrs, {len(nbh)} neighborhoods, {len(page)//1024} KB")


if __name__ == "__main__":
    for s in sys.argv[1:] or list(SCHOOL_PAGES):
        build(s)
