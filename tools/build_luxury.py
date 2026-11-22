#!/usr/bin/env python3
"""Build /carmel-valley-luxury-homes-for-sale/ exactly as the SEO plan specifies.

    python3 tools/build_luxury.py

Plan: ~/seo-plan/plans/carmelvalleyhomesforsale.com.md (priority 1, Price spoke).
Luxury here means a single-family sale of $3 million or more (the plan's long-tail
"carmel valley homes over 3 million"). Every price figure uses the last 12 months of
sales; the year before is used only to say which way the market moved.
Shell (CSS, masthead, contact, footer) comes from tools/community-template.html. Stdlib only.
"""
import collections
import datetime
import html
import json
import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from sold_data import load_sales, AREA_LABELS  # noqa: E402
from schools import _inside, elementary_for  # noqa: E402
from make_neighborhood import NEIGHBORHOOD_PAGES, SCHOOL_PAGES  # noqa: E402
from build_area import area_shapes, area_path, years_ago, short, money, med, span, fmt_date  # noqa: E402

SITE = "https://carmelvalleyhomesforsale.com"
PATH = "/carmel-valley-luxury-homes-for-sale/"
FLOOR = 3_000_000
AREA_PAGES = {"phr", "th", "tdm", "dmm", "cch", "n", "s"}  # areas that have their own page
TITLE = "Carmel Valley Luxury Homes for Sale"
H1 = "Luxury Homes for Sale in Carmel Valley"
DESC = ("Luxury homes for sale in Carmel Valley, San Diego, with the neighborhoods where they sit "
        "and recent top sales, from luxury agent Sez Sezer.")
RS = ("https://sezsezer.realscout.com/homesearch/map?ptype=SFR&amp;geo_type=zipcode&amp;geo_id=92130"
      "&amp;for_sale=1&amp;for_rent=0")
e = html.escape


def pct(a, b):
    return round(100 * a / b) if b else 0


def main():
    shapes = area_shapes()

    def area_of(r):
        if not r.get("lat"):
            return None
        for k, rings in shapes.items():
            if any(_inside(r["lng"], r["lat"], p) for p in rings):
                return k
        return None

    rows = load_sales()
    t12 = [r for r in rows if r["_d"] >= years_ago(1)]
    prev = [r for r in rows if years_ago(2) <= r["_d"] < years_ago(1)]  # only to show the direction
    lux = sorted([r for r in t12 if r["close_price"] >= FLOOR], key=lambda r: -r["close_price"])
    lux_prev = [r for r in prev if r["close_price"] >= FLOOR]
    if len(lux) < 10:
        raise SystemExit(f"only {len(lux)} sales of $3M+ in 12 months")
    m = med([r["close_price"] for r in lux])
    psf = med([r["close_price"] / r["living_area"] for r in lux if r.get("living_area")])
    dom = med([r.get("days_on_market") for r in lux])
    sqft = med([r["living_area"] for r in lux if r.get("living_area")])
    lot = med([r["lot_size_sqft"] for r in lux if r.get("lot_size_sqft")])
    beds = collections.Counter(r.get("beds_total") for r in lux if r.get("beds_total"))
    top_beds, top_beds_n = beds.most_common(1)[0]
    yb = sorted(r["year_built"] for r in lux if r.get("year_built"))
    over4 = sum(r["close_price"] >= 4e6 for r in lux)
    over5 = sum(r["close_price"] >= 5e6 for r in lux)
    share, share_prev = pct(len(lux), len(t12)), pct(len(lux_prev), len(prev))
    top = lux[0]
    today = datetime.date.today()
    stamp = f'{today.strftime("%B")} {today.day}, {today.year}'

    # ---------- where luxury homes sit: by area ----------
    by_area, all_area = collections.defaultdict(list), collections.Counter()
    for r in t12:
        all_area[area_of(r)] += 1
    for r in lux:
        by_area[area_of(r)].append(r["close_price"])
    areas = sorted(((k, v) for k, v in by_area.items() if k), key=lambda kv: (-len(kv[1]), kv[0]))
    area_rows = ""
    for k, p in areas:
        name = AREA_LABELS[k]
        link = f'<a href="{area_path(k)}">{e(name)}</a>' if k in AREA_PAGES else e(name)
        area_rows += (f'<tr><td class="nm">{link}<span>{pct(len(p), all_area[k])}% of its sales</span></td>'
                      f'<td class="num">{len(p)}</td><td class="num">{span(p)}</td></tr>')
    unmapped = len(by_area.get(None, []))
    dmm = by_area.get("dmm", [])
    # lot size and age of the $3M+ homes in each area (for the estates paragraph)
    lux_area = collections.defaultdict(list)
    for r in lux:
        lux_area[area_of(r)].append(r)
    def area_med(k, f):
        return med([r[f] for r in lux_area.get(k, []) if r.get(f)])
    dmm_lot, phr_lot, phr_yb = area_med("dmm", "lot_size_sqft"), area_med("phr", "lot_size_sqft"), area_med("phr", "year_built")

    # ---------- neighborhoods with the most $3M+ sales ----------
    by_hood = collections.defaultdict(list)
    for r in lux:
        n = (r.get("community_name") or "").strip()
        if n:
            by_hood[n].append(r)
    hoods = sorted(by_hood.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    hoods = [(n, g) for n, g in hoods if len(g) >= 2][:10]
    hood_cards = ""
    for n, g in hoods:
        p = [r["close_price"] for r in g]
        name = f'<a href="{NEIGHBORHOOD_PAGES[n]}">{e(n)}</a>' if n in NEIGHBORHOOD_PAGES else e(n)
        hood_cards += (f'<div class="bc"><div class="bc-h"><h3>{name}</h3><b>{span(p)}</b></div>'
                       f'<div class="bc-m">{len(g)} sales of $3M+ in the last 12 months &middot; median {short(med(p))}</div></div>')

    # ---------- recent top sales ----------
    top_rows = "".join(
        f'<tr><td class="addr">{e(r.get("address") or "")}<span>{e(r.get("community_name") or "")}</span></td>'
        f'<td class="num">{r.get("beds_total") or "&mdash;"} / {r.get("baths_total") or "&mdash;"}</td>'
        f'<td class="num">{("{:,}".format(r["living_area"]) if r.get("living_area") else "&mdash;")}</td>'
        f'<td class="num price">{money(r["close_price"])}</td><td class="num">{fmt_date(r["_d"])}</td></tr>' for r in lux[:10])

    # ---------- schools ----------
    elem = collections.Counter(elementary_for(r.get("lat"), r.get("lng")) for r in lux)
    elem.pop(None, None)
    def school_link(s):
        return f'<a href="{SCHOOL_PAGES[s]}">{e(s)}</a>' if s in SCHOOL_PAGES else e(s)
    school_items = "".join(f'<li><span>{school_link(s)}</span><span class="cnt">{n} of {len(lux)} sales</span></li>'
                           for s, n in elem.most_common())
    top_school, top_school_n = elem.most_common(1)[0] if elem else ("", 0)

    direction = ("up from" if share > share_prev else "down from" if share < share_prev else "the same as")
    top_area = AREA_LABELS[areas[0][0]] if areas else "Pacific Highlands Ranch"

    faqs = [
        ("What counts as a luxury home in Carmel Valley?",
         f"On this page, a luxury home is a single-family house that sells for $3 million or more. In the last 12 months "
         f"{len(lux)} of the {len(t12)} single-family sales in Carmel Valley (92130) reached that mark, about {share}% of them."),
        ("What is the most expensive home sold in Carmel Valley recently?",
         f"The top sale of the last 12 months closed at {money(top['close_price'])} in {fmt_date(top['_d'])}"
         + (f", a {top.get('beds_total')}-bedroom home" if top.get("beds_total") else "")
         + (f" of {top['living_area']:,} sq ft" if top.get("living_area") else "")
         + (f" in {top['community_name'].strip()}" if (top.get("community_name") or "").strip() else "") + "."),
        ("Which Carmel Valley neighborhoods have the most luxury homes?",
         f"By sales of $3M and up over the last 12 months, {top_area} led with {len(areas[0][1])}. "
         f"Every one of the {len(dmm)} Del Mar Mesa sales was over $3M. The neighborhoods with the most $3M+ sales were "
         + ", ".join(f"{n} ({len(g)})" for n, g in hoods[:4]) + "."),
        ("How fast do luxury homes sell in Carmel Valley?",
         f"Half of the $3M+ homes that sold in the last 12 months went under contract within {round(dom)} days on market. "
         "Compare a home with recent sales in its own neighborhood before you tour it."),
        ("What do Carmel Valley homes over $3 million cost per square foot?",
         f"The median was about {money(psf)} per sq ft over the last 12 months, for a median home of about {sqft:,.0f} sq ft."),
        ("Which schools serve Carmel Valley's luxury homes?",
         f"{top_school} served the most $3M+ sales ({top_school_n} of {len(lux)}). High school for most of Carmel Valley is "
         "Torrey Pines High in the San Dieguito Union High School District, with Canyon Crest Academy and San Dieguito Academy by lottery. "
         "School boundaries change, so confirm any address with the district."),
    ]
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)

    # ---------- JSON-LD ----------
    url = SITE + PATH
    ld = [
        {"@context": "https://schema.org", "@type": "WebPage", "name": TITLE, "url": url, "description": DESC,
         "isPartOf": {"@type": "WebSite", "name": "Carmel Valley Homes for Sale", "url": SITE + "/"},
         "dateModified": today.isoformat()},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Luxury homes", "item": url}]},
        {"@context": "https://schema.org", "@type": "ItemList", "name": "Where luxury homes sit in Carmel Valley",
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": AREA_LABELS[k], "url": SITE + area_path(k)}
                             for i, (k, _) in enumerate(a for a in areas if a[0] in AREA_PAGES)]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
        {"@context": "https://schema.org", "@type": "RealEstateAgent", "@id": "https://www.carmelvalley.com/sez-sezer-realtor/",
         "name": "Sez Sezer", "url": url, "image": SITE + "/images/sez-sezer-carmel-valley-realtor.jpg",
         "telephone": "+1-858-436-6585", "email": "sez@carmelvalley.com", "priceRange": "$$$",
         "description": "Luxury and single-family homes in Carmel Valley, San Diego. Keller Williams Realty, DRE #01988197.",
         "address": {"@type": "PostalAddress", "streetAddress": "12750 High Bluff Drive", "addressLocality": "San Diego",
                     "addressRegion": "CA", "postalCode": "92130", "addressCountry": "US"},
         "areaServed": {"@type": "Place", "name": "Carmel Valley, San Diego, CA 92130"},
         "memberOf": {"@type": "Organization", "name": "Keller Williams Realty"}},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    tpl = open(os.path.join(TOOLS, "community-template.html"), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", "Looking for a luxury home in Carmel Valley?").replace(
        "{{contact_lead}}", "Tell me the area, size and budget you have in mind and I&rsquo;ll send the $3M+ homes that fit, "
                            "including ones that haven&rsquo;t hit the market yet.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Carmel Valley Homes for Sale">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="{url}index.md">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" media="print" onload="this.media='all'">
<link rel="stylesheet" href="/assets/rs-embed.css?v=3">
<script src="/assets/rs-embed.js?v=3" defer></script>
<style>{css}
  /* ============ LUXURY PAGE ============ */
  .ar-hero{{padding:28px 0 8px}}
  .ar-hero .eyebrow{{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--lake);background:#e6f0f6;padding:5px 12px;border-radius:6px;font-weight:700;margin-bottom:12px}}
  .ar-hero h1{{font-size:clamp(28px,4.4vw,44px);font-weight:800;line-height:1.1;letter-spacing:-.02em;max-width:820px}}
  .ar-hero p{{font-size:16px;color:#3f4852;margin-top:12px;max-width:760px}}
  .prose{{max-width:760px}}
  .prose p{{font-size:16px;color:#2c333b;margin-top:10px}}
  .note{{font-size:13px;color:var(--label);margin-top:10px}}
  .two{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;align-items:start}}
  .tbl{{width:100%;border-collapse:collapse;font-size:15px}}
  .tbl th{{text-align:left;font-size:12.5px;color:var(--label);font-weight:600;padding:0 8px 8px;border-bottom:1px solid var(--line)}}
  .tbl td{{padding:11px 8px;border-bottom:1px solid var(--mist);vertical-align:top}}
  .tbl .num,.tbl th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .tbl .nm{{font-weight:700}}
  .tbl .nm span,.tbl .addr span{{display:block;font-weight:400;font-size:12.5px;color:var(--label)}}
  .tbl .addr{{font-weight:600}}
  .tbl .price{{font-weight:700}}
  .bcs{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
  .bc{{border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
  .bc-h{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
  .bc h3{{font-size:15.5px;font-weight:700}}
  .bc-m{{font-size:13px;color:var(--label);margin-top:4px}}
  .sch{{list-style:none;border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  .sch li{{display:flex;justify-content:space-between;gap:12px;padding:12px 14px;border-top:1px solid var(--mist);font-weight:600}}
  .sch li:first-child{{border-top:0}}
  .sch .cnt{{font-weight:500;color:var(--label);white-space:nowrap}}
  .h3{{font-size:18px;font-weight:800;margin-bottom:10px}}
  .scroll{{overflow-x:auto}}
  @media(max-width:760px){{
    .two,.bcs{{grid-template-columns:minmax(0,1fr)}}
    .tbl{{font-size:13.5px}}
    .tbl td{{padding:10px 5px}}
  }}
</style>
{jsonld}
</head>
<body>

{masthead}

<nav class="breadcrumb" aria-label="Breadcrumb">
  <div class="wrap"><a href="/">Home</a><span class="sep">/</span><span class="current">Luxury homes</span></div>
</nav>

<section class="ar-hero" style="padding-left:0;padding-right:0">
  <div class="wrap">
    <span class="eyebrow">Carmel Valley &middot; San Diego 92130 &middot; $3M and up</span>
    <h1>{e(H1)}</h1>
    <p>Carmel Valley luxury homes for sale are single-family houses of $3 million and up, from the newest homes in Pacific Highlands Ranch
      to the large lots of Del Mar Mesa. Here is where they sit, what the top homes sold for in the last 12 months and what to expect
      when you buy one.</p>
  </div>
</section>

<section class="facts" style="padding-top:12px">
  <div class="wrap facts-grid">
    <div class="fact"><div class="num">{len(lux)}</div><div class="lbl">Sold at $3M+, last 12 mo</div></div>
    <div class="fact"><div class="num">{short(m)}</div><div class="lbl">Median $3M+ sale, 12 mo</div></div>
    <div class="fact"><div class="num">{money(psf)}</div><div class="lbl">Per sq ft, 12 mo</div></div>
    <div class="fact"><div class="num">{round(dom)} days</div><div class="lbl">On market, 12 mo</div></div>
  </div>
</section>

<section class="listings" id="listings" style="padding-top:24px;padding-bottom:16px">
  <div class="wrap">
    <div class="listings-head"><h2 class="listings-title">Carmel Valley luxury listings</h2><span class="listings-tag">Live MLS</span></div>
    <p class="note" style="margin:-6px 0 12px">Live single-family listings in 92130. Set <b>Price Min</b> to $3,000,000 to see only luxury homes, or ask me for a saved $3M+ search.</p>
    <div class="rs-embed" style="max-width:1100px;margin:0 auto">
      <iframe data-src="{RS}" title="Carmel Valley luxury homes for sale"></iframe>
    </div>
  </div>
</section>

<section id="areas" style="padding-top:20px">
  <div class="wrap two">
    <div>
      <h2 class="h3">Where luxury homes sit in Carmel Valley, San Diego</h2>
      <table class="tbl"><thead><tr><th>Area</th><th class="num">$3M+ sold</th><th class="num">Price range</th></tr></thead>
      <tbody>{area_rows}</tbody></table>
      <p class="note">Single-family sales of $3 million or more in the last 12 months, and their share of each area&rsquo;s sales, as of {stamp}.{f" {unmapped} more were in parts of 92130 outside these areas." if unmapped else ""}</p>
    </div>
    <div>
      <h2 class="h3">Neighborhoods with the most $3M+ sales</h2>
      <div class="bcs" style="grid-template-columns:minmax(0,1fr)">{hood_cards}</div>
    </div>
  </div>
</section>

<section id="top-sales" style="padding-top:24px">
  <div class="wrap">
    <h2 class="h3">Most expensive homes sold in Carmel Valley, last 12 months</h2>
    <div class="scroll"><table class="tbl"><thead><tr><th>Address</th><th class="num">Bd / Ba</th><th class="num">Sq ft</th><th class="num">Price</th><th class="num">Closed</th></tr></thead>
    <tbody>{top_rows}</tbody></table></div>
    <p class="note">Closed single-family MLS sales in 92130. Information deemed reliable but not guaranteed.</p>
  </div>
</section>

<section id="market" style="padding-top:24px">
  <div class="wrap prose">
    <h2 class="h3">Carmel Valley homes over $3 million: the market now</h2>
    <p>In the last 12 months, {len(lux)} of {len(t12)} single-family homes in Carmel Valley sold for $3 million or more. That is about
      {share}% of all house sales, {direction} {share_prev}% in the 12 months before. {over4} sold for $4 million or more and {over5}
      for $5 million or more.</p>
    <p>The typical luxury home here has {top_beds} bedrooms ({top_beds_n} of the {len(lux)} sales), about {sqft:,.0f} sq ft of living space
      {f"and a lot of about {lot:,.0f} sq ft" if lot else ""}. They were built between {yb[0]} and {yb[-1]}, with a median year of
      {yb[len(yb) // 2]}.</p>
    <p>High end homes in Carmel Valley still move quickly: half of the $3M+ sales went under contract within {round(dom)} days on market.
      That leaves little time to decide, so compare a home with recent sales in its own neighborhood before you tour it.</p>
    <h2 class="h3" style="margin-top:22px">Carmel Valley estates for sale</h2>
    <p>For a larger lot, start with Del Mar Mesa: every one of its {len(dmm)} sales in the last 12 months was over $3 million
      {f"(median {short(med(dmm))})" if dmm else ""}{f", on lots of about {dmm_lot:,.0f} sq ft" if dmm_lot else ""}.
      Pacific Highlands Ranch had the most luxury sales, and its $3M+ homes are the newest{f" (median year built {phr_yb:.0f})" if phr_yb else ""}
      {f"on lots of about {phr_lot:,.0f} sq ft" if phr_lot else ""}.</p>
  </div>
</section>

<section id="schools" style="padding-top:24px">
  <div class="wrap two">
    <div>
      <h2 class="h3">Elementary schools for $3M+ homes</h2>
      <ul class="sch">{school_items}</ul>
      <p class="note">Attendance area of each $3M+ sale, last 12 months. Confirm any address with the school district.</p>
    </div>
    <div>
      <h2 class="h3">Buying a luxury home in Carmel Valley</h2>
      <p>Most $3M+ buyers here are choosing between a school area and a lot size. Compare the
        <a href="/sage-canyon-elementary-homes-for-sale/">Sage Canyon Elementary area</a>, which had the most luxury sales,
        with the larger lots of <a href="/del-mar-mesa-homes-for-sale/">Del Mar Mesa</a>, then see every neighborhood on the
        <a href="/carmel-valley-neighborhoods/">Carmel Valley neighborhoods map</a>.</p>
    </div>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <h2 class="h3">Carmel Valley luxury homes: common questions</h2>
    <div class="faq-list">
{faq_html}
    </div>
  </div>
</section>

{contact_footer}

<nav class="bottom-nav" aria-label="Jump to section">
  <a href="#listings">Listings</a>
</nav>

{hide_js}
</body>
</html>
'''
    out = os.path.join(ROOT, PATH.strip("/"))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    words = len(re.sub(r"<[^>]+>", " ", page[page.index("<body>"):page.index("<!-- ============ CONTACT BLOCK")]).split())
    print(f"wrote {PATH}: {len(lux)} sales of $3M+ in 12 months, {len(page) // 1024} KB, ~{words} words")


if __name__ == "__main__":
    main()
