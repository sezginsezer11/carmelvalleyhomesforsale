#!/usr/bin/env python3
"""Build the home page (/index.html) from live single-family sales.

    python3 tools/build_home.py

Shell (CSS, masthead, contact block, footer, scroll script) comes from
tools/community-template.html so the look stays in sync with every other page.
Numbers come from tools/sold_data.py (single-family only). Run
tools/build_llm_files.py afterwards. Stdlib only.
"""
import datetime
import html
import json
import os
import re
import statistics

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
import sys
sys.path.insert(0, TOOLS)
from sold_data import load_sales, area_of, AREA_LABELS  # noqa: E402

SITE = "https://carmelvalleyhomesforsale.com"
e = html.escape

# Pages that exist (or are being built in this first batch). Chips and links only point here.
LINKS = {
    "hub": "/carmel-valley-neighborhoods/",
    "phr": "/pacific-highlands-ranch-homes-for-sale/",
}
from make_neighborhood import AREA_PAGES  # noqa: E402
BANDS = [("Under $2M", 0, 2e6, None), ("$2M to $3M", 2e6, 3e6, None),
         ("$3M to $4M", 3e6, 4e6, None), ("$4M and up", 4e6, float("inf"), None)]


def money(n):
    return "${:,.0f}".format(n)


def short(n):
    if n >= 1e6:
        return "${}M".format(("%.2f" % (n / 1e6 + 1e-9)).rstrip("0").rstrip("."))
    return "${:,.0f}K".format(n / 1e3)


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:
        return t.replace(year=t.year - n, day=28)


def med(rs, f=lambda r: r["close_price"]):
    v = [f(r) for r in rs]
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def main():
    rows = load_sales()
    t12 = [r for r in rows if r["_d"] >= years_ago(1)]
    today = datetime.date.today()
    stamp = f'{today.strftime("%B")} {today.day}, {today.year}'
    m12 = med(t12)
    psf = med([r for r in t12 if r.get("living_area")], lambda r: r["close_price"] / r["living_area"])
    dom = med([r for r in t12 if r.get("days_on_market") is not None], lambda r: r["days_on_market"])
    u2 = [r for r in t12 if r["close_price"] < 2e6]

    # ---------- price bands ----------
    bands = []
    for label, lo, hi, href in BANDS:
        g = [r for r in t12 if lo <= r["close_price"] < hi]
        share = round(100 * len(g) / len(t12)) if t12 else 0
        body = (f'<div class="pb-top"><h3>{label}</h3><span class="pb-n">{len(g)} sold</span></div>'
                f'<div class="pb-bar"><i style="width:{max(share, 3)}%"></i></div>'
                f'<div class="pb-meta">{share}% of sales &middot; median {short(med(g)) if g else "&mdash;"}</div>'
                + (f'<span class="pb-go">See homes {label[0].lower() + label[1:]} &rarr;</span>' if href else ""))
        bands.append(f'<a class="pb" href="{href}">{body}</a>' if href else f'<div class="pb">{body}</div>')

    # ---------- areas ----------
    areas = []
    for k, label in AREA_LABELS.items():
        g = [r for r in t12 if area_of(r.get("community_name")) == k]
        if not g:
            continue
        href = AREA_PAGES.get(k)
        cta = f'<a class="ar-go" href="{href}">Area guide &rarr;</a>' if href else ""
        areas.append((len(g), f'<tr><td><span class="ar-name">{e(label)}</span>{cta}</td>'
                               f'<td class="num">{len(g)}</td><td class="num">{short(med(g))}</td></tr>'))
    areas_html = "\n".join(h for _, h in areas)

    # ---------- FAQ ----------
    top = max(((k, l, [r for r in t12 if area_of(r.get("community_name")) == k]) for k, l in AREA_LABELS.items()),
              key=lambda x: len(x[2]))
    priciest = max(((l, med(g)) for k, l in AREA_LABELS.items()
                    if len(g := [r for r in t12 if area_of(r.get("community_name")) == k]) >= 5), key=lambda x: x[1])
    faqs = [
        ("What is the median price of a single-family home in Carmel Valley?",
         f"{money(m12)}, based on {len(t12)} single-family homes that closed in the last 12 months in ZIP 92130 "
         f"(about {money(psf)} per square foot). Condos and townhomes are not included."),
        ("Can you still buy a house in Carmel Valley for under $2 million?",
         f"Yes, but there are few of them. {len(u2)} of {len(t12)} single-family sales in the last 12 months closed under $2M, "
         "mostly smaller or older homes and newer homes on compact lots. They tend to sell quickly, so set up alerts and be ready to act."),
        ("How fast do Carmel Valley houses sell?",
         f"The median single-family home sold in {round(dom)} days on market over the last 12 months. "
         "Well-priced homes in popular school areas often go under contract in the first week."),
        ("Which part of Carmel Valley has the most home sales?",
         f"{top[1]} had the most single-family sales in the last 12 months ({len(top[2])}). "
         f"Among areas with at least five sales, {priciest[0]} had the highest median at {money(priciest[1])}."),
        ("Is this site for condos and townhomes too?",
         'No. This site covers single-family homes only. For condos and townhomes, including HOA fees and Mello-Roos, see '
         '<a href="https://carmelvalleycondos.com">Carmel Valley condos and townhomes</a>. For every property type in one search, see '
         '<a href="https://carmelvalley.com">all Carmel Valley listings</a>.'),
    ]
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{a if "<a " in a else e(a)}</p></details>' for q, a in faqs)

    # ---------- JSON-LD ----------
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": "Carmel Valley Homes for Sale", "url": SITE + "/"},
        {"@context": "https://schema.org", "@type": "RealEstateAgent", "name": "Sez Sezer", "url": SITE + "/",
         "image": SITE + "/images/sez-sezer-carmel-valley-realtor.jpg", "telephone": "+1-858-436-6585",
         "description": "Single-family homes for sale in Carmel Valley, San Diego, CA 92130.",
         "address": {"@type": "PostalAddress", "streetAddress": "12750 High Bluff Drive", "addressLocality": "San Diego",
                     "addressRegion": "CA", "postalCode": "92130", "addressCountry": "US"},
         "areaServed": {"@type": "Place", "name": "Carmel Valley, San Diego, CA 92130"},
         "memberOf": {"@type": "Organization", "name": "Keller Williams Realty"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}} for q, a in faqs]},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    # ---------- shell from the community template ----------
    tpl = open(os.path.join(TOOLS, "community-template.html"), encoding="utf-8").read()
    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", "Looking for a House in Carmel Valley?").replace(
        "{{contact_lead}}", "Tell me your budget, school area and must-haves (pool, single-story, yard, commute) and I&rsquo;ll send you the homes that fit, including ones that haven&rsquo;t hit the market yet.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    title = "Carmel Valley Homes for Sale | Single-Family Houses, San Diego 92130"
    desc = (f"Single-family homes for sale in Carmel Valley, San Diego 92130. Median {short(m12)} over the last 12 months. "
            "Search by price, neighborhood and school area.")
    assert len(desc) <= 160, len(desc)

    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Carmel Valley Homes for Sale">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}/">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="{SITE}/index.md">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" media="print" onload="this.media='all'">
<link rel="stylesheet" href="/assets/rs-embed.css?v=3">
<script src="/assets/rs-embed.js?v=3" defer></script>
<style>{css}
  /* ============ HOME ============ */
  .home-hero{{padding:40px 0 20px;background:#f2f7fa;border-bottom:1px solid var(--line)}}
  .home-hero .wrap{{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:36px;align-items:center}}
  .home-hero .eyebrow{{display:inline-block;font-size:12.5px;color:var(--lake);background:#e0edf4;padding:5px 12px;border-radius:6px;font-weight:700;margin-bottom:14px}}
  .home-hero h1{{font-size:clamp(30px,4.6vw,48px);font-weight:800;line-height:1.08;letter-spacing:-.025em}}
  .home-hero .lead{{font-size:17px;color:#3f4852;margin-top:14px;max-width:560px}}
  .quick{{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}}
  .quick a{{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid #cddbe4;color:var(--ink);font-size:14px;font-weight:600;padding:9px 14px;border-radius:100px}}
  .quick a:hover{{border-color:var(--lake);color:var(--lake)}}
  .quick a.primary{{background:var(--lake);border-color:var(--lake);color:#fff}}
  .kpi-card{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px 22px}}
  .kpi-card h2{{font-size:14px;font-weight:700;color:var(--label);margin-bottom:12px}}
  .kpi-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px 18px}}
  .kpi-grid .v{{font-size:26px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}
  .kpi-grid .l{{font-size:13px;color:var(--label)}}
  .kpi-card .stamp{{font-size:12px;color:var(--label);margin-top:14px;border-top:1px solid var(--mist);padding-top:10px}}
  .bands{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}}
  .pb{{display:flex;flex-direction:column;gap:8px;border:1px solid var(--line);border-radius:14px;padding:18px;color:var(--ink);background:#fff}}
  a.pb:hover{{border-color:var(--lake);box-shadow:0 4px 14px rgba(11,92,140,.12);color:var(--ink)}}
  .pb-top{{display:flex;justify-content:space-between;align-items:baseline;gap:8px}}
  .pb h3{{font-size:17px;font-weight:800}}
  .pb-n{{font-size:13px;color:var(--label);font-weight:600;white-space:nowrap}}
  .pb-bar{{height:6px;background:#e6f0f6;border-radius:3px}}
  .pb-bar i{{display:block;height:6px;background:var(--lake);border-radius:3px}}
  .pb-meta{{font-size:13.5px;color:var(--label)}}
  .pb-go{{font-size:13.5px;font-weight:700;color:var(--lake);margin-top:auto}}
  .areas-tbl{{width:100%;border-collapse:collapse;max-width:860px;margin:0 auto;font-size:15px}}
  .areas-tbl th{{text-align:left;font-size:12.5px;color:var(--label);font-weight:600;padding:0 10px 10px;border-bottom:1px solid var(--line)}}
  .areas-tbl td{{padding:14px 10px;border-bottom:1px solid var(--mist)}}
  .areas-tbl .num,.areas-tbl th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .ar-name{{font-weight:700}}
  .ar-go{{display:block;font-size:13px;font-weight:600;margin-top:2px}}
  .tbl-note{{text-align:center;font-size:13px;color:var(--label);margin-top:14px}}
  .tbl-note a{{font-weight:600}}
  .network{{background:var(--paper)}}
  .net-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:860px;margin:0 auto}}
  .net{{display:block;background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;color:var(--ink)}}
  .net:hover{{border-color:var(--lake);color:var(--ink)}}
  .net h3{{font-size:17px;font-weight:800}}
  .net p{{font-size:14.5px;color:var(--label);margin-top:4px}}
  .net span{{display:inline-block;margin-top:10px;font-size:14px;font-weight:700;color:var(--lake)}}
  @media(max-width:900px){{.bands{{grid-template-columns:1fr 1fr}}}}
  @media(max-width:760px){{
    .home-hero{{padding:22px 0 18px}}
    .home-hero .wrap{{grid-template-columns:minmax(0,1fr);gap:18px}}
    .home-hero .lead{{font-size:15px}}
    .quick{{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin-right:-16px;padding-right:16px}}
    .quick::-webkit-scrollbar{{display:none}}
    .quick a{{white-space:nowrap;font-size:13.5px;padding:8px 12px}}
    .kpi-card{{padding:16px}}
    .kpi-grid .v{{font-size:21px}}
    .bands{{gap:10px}}
    .pb{{padding:14px}}
    .pb h3{{font-size:15px}}
    .areas-tbl{{font-size:14px}}
    .areas-tbl td{{padding:12px 6px}}
    .net-grid{{grid-template-columns:1fr}}
  }}
</style>
</head>
<body>

{masthead}

<section class="home-hero" style="padding-left:0;padding-right:0">
  <div class="wrap">
    <div>
      <span class="eyebrow">Carmel Valley &middot; San Diego 92130</span>
      <h1>Carmel Valley Homes for Sale</h1>
      <p class="lead">Single-family houses only, organized the way buyers search: by price, neighborhood and school area, with real sold prices for every one.</p>
      <nav class="quick" aria-label="Popular searches">
        <a class="primary" href="#listings">Homes for sale now</a>
        <a href="{LINKS["phr"]}">New homes in Pacific Highlands Ranch</a>
        <a href="{LINKS["hub"]}">All neighborhoods</a>
      </nav>
    </div>
    <div class="kpi-card">
      <h2>Carmel Valley houses, last 12 months</h2>
      <div class="kpi-grid">
        <div><div class="v">{short(m12)}</div><div class="l">Median sale price</div></div>
        <div><div class="v">{len(t12)}</div><div class="l">Homes sold</div></div>
        <div><div class="v">{money(psf)}</div><div class="l">Median per sq ft</div></div>
        <div><div class="v">{round(dom)} days</div><div class="l">Median on market</div></div>
      </div>
      <div class="stamp">Single-family closed sales, ZIP 92130, as of {stamp}.</div>
    </div>
  </div>
</section>

<section class="listings" id="listings" style="padding-top:28px;padding-bottom:16px">
  <div class="wrap">
    <div class="listings-head"><h2 class="listings-title">Carmel Valley houses for sale now</h2><span class="listings-tag">Live MLS</span></div>
    <div class="rs-embed" style="max-width:1100px;margin:0 auto">
      <iframe data-src="https://sezsezer.realscout.com/homesearch/map?ptype=SFR&amp;geo_type=zipcode&amp;geo_id=92130&amp;for_sale=1&amp;for_rent=0" title="Carmel Valley Single-Family Homes for Sale"></iframe>
    </div>
  </div>
</section>

<section id="prices">
  <div class="wrap">
    <div class="sec-head"><div class="eyebrow">By Price</div><h2>What a House Costs in Carmel Valley</h2>
      <p>How the last 12 months of single-family sales break down by price. Most homes sell between $2M and $3M.</p></div>
    <div class="bands">
      {"".join(bands)}
    </div>
  </div>
</section>

<section id="areas" style="padding-top:8px">
  <div class="wrap">
    <div class="sec-head"><div class="eyebrow">By Area</div><h2>Carmel Valley Neighborhoods by Price</h2>
      <p>Each part of Carmel Valley has its own age of homes, lot sizes and price range. Start with the area, then compare its neighborhoods.</p></div>
    <table class="areas-tbl">
      <thead><tr><th>Area</th><th class="num">Sold, 12 mo</th><th class="num">Median price</th></tr></thead>
      <tbody>
{areas_html}
      </tbody>
    </table>
    <p class="tbl-note">Sales without a neighborhood name are counted in the totals above but not in this table. <a href="{LINKS["hub"]}">See every neighborhood on the map &rarr;</a></p>
  </div>
</section>

<section class="network" id="more">
  <div class="wrap">
    <div class="sec-head"><h2>Looking for Something Else?</h2></div>
    <div class="net-grid">
      <a class="net" href="https://carmelvalleycondos.com"><h3>Carmel Valley condos and townhomes</h3><p>HOA fees, Mello-Roos, sold prices and community comparisons for attached homes.</p><span>Visit carmelvalleycondos.com &rarr;</span></a>
      <a class="net" href="https://carmelvalley.com"><h3>All Carmel Valley listings</h3><p>Every property type for sale in Carmel Valley in one search.</p><span>Visit carmelvalley.com &rarr;</span></a>
    </div>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <div class="sec-head"><h2>Buying a House in Carmel Valley: Common Questions</h2></div>
    <div class="faq-list">
{faq_html}
    </div>
  </div>
</section>

{contact_footer}

{jsonld}

<nav class="bottom-nav" aria-label="Jump to section">
  <a href="#expand-map"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>Find Homes</a>
  <a href="#prices"><svg viewBox="0 0 24 24"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>Prices</a>
  <a href="#areas"><svg viewBox="0 0 24 24"><path d="M12 21s7-7.1 7-12a7 7 0 0 0-14 0c0 4.9 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>Areas</a>
  <a href="#contact"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>Contact</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')"><svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>Menu</a>
</nav>
{hide_js}
</body>
</html>
'''
    left = re.findall(r"\{\{\w+\}\}", page)
    if left:
        raise SystemExit(f"unfilled placeholders: {sorted(set(left))}")
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(page)
    print(f"wrote index.html: {len(t12)} sales in last 12 months, median {money(m12)}, {len(page)//1024} KB")


if __name__ == "__main__":
    main()
