#!/usr/bin/env python3
"""Build the single-family neighborhoods hub: /carmel-valley-neighborhoods/.

    python3 tools/build_communities_hub.py

Inputs
- tools/atlas_data.json          boundaries, areas, home counts (from tools/build_atlas.py)
- tools/sold_data.py             single-family closed sales (MLS type decides; "(a)" communities left out)
- tools/community-template.html  site CSS, masthead, contact block and footer (so the look stays in sync)
A map community is shown when it isn't a condo "(a)" community and at least half of its
MLS sales are "Single Family Residence" (no sales yet: the map's own home type decides).
Run tools/build_atlas.py first when the map changes, and tools/build_llm_files.py after. Stdlib only.
"""
import datetime
import html
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from sold_data import load_raw, load_sales, is_condo_community, SFR  # noqa: E402

PATH = "/carmel-valley-neighborhoods/"
OUT = os.path.join(ROOT, "carmel-valley-neighborhoods", "index.html")
SITE = "https://carmelvalleyhomesforsale.com"
COLORS = {"n": "#0d8f84", "s": "#0b5c8c", "cch": "#c27a0e", "phr": "#e0691c", "tdm": "#3f9a2a",
          "th": "#d0346f", "dmm": "#7a4ce0", "rp": "#64748b"}
SHORT = {"n": "North of Del Mar Hts Rd", "s": "South of Del Mar Hts Rd"}

e = html.escape


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# Pages on this site, by map name or area key.
from make_neighborhood import NEIGHBORHOOD_PAGES as PAGES  # noqa: E402
from make_neighborhood import AREA_PAGES  # noqa: E402
AREA_TEXT = {
    "n": "Established 1980s and 1990s neighborhoods north of Del Mar Heights Road, close to the beach, Torrey Pines and the I-5 / SR-56 interchange.",
    "s": "The original heart of Carmel Valley: mature trees, parks and walking paths, with homes from the late 1980s and 1990s close to Del Mar Highlands Town Center.",
    "cch": "Larger 1990s and early-2000s homes on bigger lots in the hills of Carmel Country Highlands, many with five or more bedrooms.",
    "phr": "Carmel Valley's newest homes, built from the 2000s onward, east of the SR-56. Many neighborhoods pay Mello-Roos on top of property tax.",
    "tdm": "Newer homes in Torrey Highlands, at the eastern edge of Carmel Valley near the SR-56 and Del Sur.",
    "th": "A self-contained valley south of the SR-56 with its own parks and shopping, and homes from the late 1990s and 2000s.",
    "dmm": "Estate homes on large lots next to the Del Mar Mesa preserve, with horse trails and a rural feel.",
    "rp": "A gated community of large custom and semi-custom estates in the hills.",
}


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:
        return t.replace(year=t.year - n, day=28)


def short(n):
    return "${}M".format(("%.2f" % (n / 1e6 + 1e-9)).rstrip("0").rstrip(".")) if n >= 1e6 else "${:,.0f}K".format(n / 1e3)


def load():
    data = json.load(open(os.path.join(ROOT, "tools", "atlas_data.json"), encoding="utf-8"))
    tpl = open(os.path.join(ROOT, "tools", "community-template.html"), encoding="utf-8").read()
    # MLS mix per community (every property type), to decide which map communities are single-family
    mix, seen = {}, set()
    for r in load_raw():
        if r.get("group_key") in seen:
            continue
        seen.add(r.get("group_key"))
        m = mix.setdefault((r.get("community_name") or "").strip().lower(), [0, 0])
        m[1] += 1
        m[0] += r.get("property_sub_type") == SFR
    five = years_ago(5)
    sales = {}
    for r in load_sales():
        if r["_d"] >= five:
            sales.setdefault((r.get("community_name") or "").strip().lower(), []).append(r)
    comms = []
    for c in data["c"]:
        s, tot = mix.get(c["n"].lower(), (0, 0))
        if is_condo_community(c["n"]) or (s / tot < 0.5 if tot else c["cat"] != "sfr"):
            continue
        p = sales.get(c["n"].lower(), [])
        # 5 years = what homes sold for (range); medians only from the last 12 months
        pr = [r["close_price"] for r in p]
        p12 = [r["close_price"] for r in p if r["_d"] >= years_ago(1)]
        c["n5"], c["n12"], c["med12"] = len(p), len(p12), (statistics.median(p12) if p12 else None)
        c["r5"] = (f"{short(min(pr))}&ndash;{short(max(pr))}" if max(pr) > min(pr) else short(pr[0])) if pr else None
        comms.append(c)
    return data, comms, tpl


def main():
    data, comms, tpl = load()
    areas = [(k, l) for k, l in data["subs"]]
    pages, ext, photos, atext = PAGES, {}, {}, AREA_TEXT
    groups = [(k, l, sorted((c for c in comms if c.get("sub") == k), key=lambda c: c["n"])) for k, l in areas]
    groups = [g for g in groups if g[2]]
    total_homes = sum(c.get("homes") or 0 for c in comms)
    homes_floor = f"{total_homes // 100 * 100:,}"  # some communities have no count, so show "5,700+"

    def link(c):
        return pages.get(c["n"]) or ext.get(c["n"])

    # ---------- area accordion (left column; static, crawlable) ----------
    sec = []
    for k, label, cs in groups:
        homes = sum(c.get("homes") or 0 for c in cs)
        rows = []
        for c in cs:
            u = link(c)
            meta = " &middot; ".join(x for x in [f'{c["homes"]} homes' if c.get("homes") else "",
                                                  f'sold {c["r5"]}' if c.get("r5") else ""] if x) or "Single-family homes"
            go = ""
            if c["n"] in pages:
                go = f'<a class="nr-go" href="{u}">Guide<span class="sr"> to {e(c["n"])}</span> &rarr;</a>'
            elif u:
                go = f'<a class="nr-go" href="{u}">Homes<span class="sr"> in {e(c["n"])}</span> &rarr;</a>'
            rows.append(f'<li class="nr"><button type="button" class="nr-pick" data-n="{e(c["n"])}">'
                        f'<span class="nr-name">{e(c["n"])}</span><span class="nr-meta">{meta}</span></button>{go}</li>')
        stats = f'{len(cs)} neighborhood{"" if len(cs) == 1 else "s"}' + (f" &middot; {homes:,} homes" if homes else "")
        guide = f' <a href="{AREA_PAGES[k]}">{e(label)} guide &rarr;</a>' if k in AREA_PAGES else ""
        sec.append(f'''<details class="ax" id="area-{slug(label)}" data-a="{k}" style="--ac:{COLORS.get(k, "#64748b")}">
  <summary><span class="dot"></span><span class="ax-name">{e(label)}</span><span class="ax-n">{len(cs)}</span><svg class="ax-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></summary>
  <div class="ax-body">
    <p class="ax-text">{e(atext.get(k, ""))}{guide}</p>
    <p class="ax-stats">{stats}</p>
    <ul class="nr-list">{"".join(rows)}</ul>
  </div>
</details>''')

    # ---------- FAQ ----------
    biggest = max(groups, key=lambda g: len(g[2]))
    n_big = len(biggest[2])
    largest = sorted((c for c in comms if c.get("homes")), key=lambda c: -c["homes"])[:3]
    priced = [c for c in comms if c.get("med12") and c["n12"] >= 3]
    lo, hi = min(priced, key=lambda c: c["med12"]), max(priced, key=lambda c: c["med12"])
    faqs = [
        ("How many single-family neighborhoods are in Carmel Valley?",
         f"This map shows {len(comms)} single-family neighborhoods in Carmel Valley (San Diego, 92130), with more than "
         f"{homes_floor} homes between them. They are spread across {len(groups)} areas, and {n_big} of them are in {biggest[1]}."),
        ("Which Carmel Valley neighborhoods have the lowest and highest home prices?",
         f"Among neighborhoods with at least three house sales in the last 12 months, {lo['n']} had the lowest median ({short(lo['med12'])}) "
         f"and {hi['n']} the highest ({short(hi['med12'])}). Lot size, home age and school area explain most of the gap."),
        ("What are the largest single-family neighborhoods in Carmel Valley?",
         "By number of homes, the largest are " + ", ".join(f"{c['n']} ({c['homes']} homes)" for c in largest) +
         ". Bigger neighborhoods have more sales each year, which makes prices easier to compare."),
        ("Where are the newest houses in Carmel Valley?",
         "Pacific Highlands Ranch, east of the SR-56, was built out from the 2000s onward and still has some of the newest homes. "
         "Many of its neighborhoods pay Mello-Roos on top of property tax, so compare the full yearly cost."),
        ("How do I see what is for sale in a specific neighborhood?",
         "Tap the neighborhood on the map or its card below. Where there is a guide, it shows live listings, recent sales and schools. "
         "For any other neighborhood, call or email Sez Sezer for current listings and recent sales."),
    ]
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)

    # ---------- JSON-LD ----------
    ld = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Carmel Valley Single-Family Neighborhoods",
         "url": SITE + PATH, "about": {"@type": "Place", "name": "Carmel Valley, San Diego, CA 92130"},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(comms), "itemListElement": [
             dict({"@type": "ListItem", "position": i + 1, "name": c["n"]},
                  **({"url": SITE + pages[c["n"]]} if c["n"] in pages else {}))
             for i, c in enumerate(c for _, _, cs in groups for c in cs)]}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Carmel Valley Neighborhoods", "item": SITE + PATH}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    # ---------- map data ----------
    mdata = {"c": [{"n": c["n"], "a": c["sub"], "h": c.get("homes"), "u": link(c), "g": c["n"] in pages, "m": c.get("r5"), "p": c["p"]} for c in comms],
             "areas": {k: [l, COLORS.get(k)] for k, l, _ in groups}}

    # ---------- shell from the community template ----------
    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", "Not Sure Which Neighborhood Fits?").replace(
        "{{contact_lead}}", "Tell me what matters to you (budget, school area, lot size, single-story, commute) and I&rsquo;ll point you to the neighborhoods that fit, with current listings and recent sales for each.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    title = "Carmel Valley Neighborhoods Map: Single-Family Homes by Area"
    desc = f"Map of {len(comms)} Carmel Valley single-family neighborhoods by area, with home counts and what homes sold for. San Diego 92130."
    assert len(desc) <= 155, len(desc)

    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{PATH}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Carmel Valley Homes for Sale">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}{PATH}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="{SITE}{PATH}index.md">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap" media="print" onload="this.media='all'">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>{css}
  /* ============ COMMUNITIES HUB ============ */
  .sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
  .hub-intro{{padding:18px 0 4px}}
  .hub-bar{{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap}}
  .hub-bar h1{{font-size:clamp(21px,2.4vw,27px);font-weight:800;letter-spacing:-.015em;line-height:1.2}}
  .hub-bar h1 span{{font-weight:500;color:var(--label);font-size:.62em;letter-spacing:0;margin-left:6px;white-space:nowrap}}
  .hub-stats{{font-size:13.5px;font-weight:600;color:var(--label)}}
  .map-sec{{padding:12px 0 8px}}
  .chips{{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-bottom:14px}}
  .chip{{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);background:var(--white);color:var(--ink);font-size:13.5px;font-weight:600;padding:7px 12px;border-radius:100px;cursor:pointer}}
  .chip:hover{{border-color:var(--ac);color:var(--ink)}}
  .chip b{{color:var(--label);font-weight:600}}
  .chip.on{{background:var(--ac);border-color:var(--ac);color:#fff}}
  .chip.on b{{color:rgba(255,255,255,.85)}}
  .chip.on .dot{{background:#fff}}
  .dot{{width:10px;height:10px;border-radius:50%;background:var(--ac);flex:none;display:inline-block}}
  .map-box{{position:relative;z-index:0;isolation:isolate;max-width:1100px;margin:0 auto;border:1px solid var(--line);border-radius:14px;overflow:hidden}}
  #map{{height:min(64vh,560px);background:#e8ecef}}
  .map-views{{position:absolute;top:10px;right:10px;z-index:500;display:flex;background:#fff;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.18);overflow:hidden}}
  .map-views button{{border:0;background:#fff;font:600 12.5px var(--sans);padding:7px 11px;cursor:pointer;color:#37404a}}
  .map-views button[aria-pressed="true"]{{background:var(--lake);color:#fff}}
  .map-card{{position:absolute;left:10px;bottom:10px;z-index:500;background:#fff;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.18);padding:14px 16px;max-width:300px;display:none}}
  .map-card.show{{display:block}}
  .map-card h3{{font-size:17px;font-weight:800;margin-right:22px}}
  .map-card .mc-area{{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--label);margin-top:4px}}
  .map-card .mc-homes{{font-size:14px;margin-top:6px}}
  .map-card a.mc-go{{display:inline-block;margin-top:10px;background:var(--lake);color:#fff;font-weight:600;font-size:13.5px;padding:8px 14px;border-radius:7px}}
  .map-card .mc-x{{position:absolute;top:8px;right:10px;border:0;background:none;font-size:20px;line-height:1;color:var(--label);cursor:pointer}}
  .map-note{{text-align:center;font-size:13px;color:var(--label);margin-top:10px}}
  .leaflet-container{{font-family:var(--sans)}}
  .leaflet-control-attribution{{font-size:9.5px!important}}
  .leaflet-tooltip.lbl{{background:none;border:0;box-shadow:none;padding:0;color:#101418;font-weight:700;font-size:11.5px;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 2px #fff;white-space:nowrap}}
  .leaflet-tooltip.lbl::before{{display:none}}
  .sat .leaflet-tooltip.lbl{{color:#fff;text-shadow:0 0 3px #000,0 0 3px #000,0 0 2px #000}}
  /* explorer: area list left, sticky map right (stacked on phones) */
  .xp{{display:grid;grid-template-columns:minmax(0,1fr);gap:14px}}
  .xp-map{{order:-1}}
  .xp-list h2{{font-size:20px;font-weight:800;letter-spacing:-.01em}}
  .xp-list .xp-hint{{font-size:14px;color:var(--label);margin:4px 0 12px}}
  .ax{{border:1px solid var(--line);border-left:4px solid var(--ac);border-radius:10px;background:var(--white);margin-bottom:8px;overflow:hidden}}
  .ax summary{{list-style:none;display:flex;align-items:center;gap:10px;padding:13px 14px;cursor:pointer;font-weight:700;font-size:16px}}
  .ax summary::-webkit-details-marker{{display:none}}
  .ax summary:hover{{background:var(--paper)}}
  .ax-name{{flex:1;min-width:0}}
  .ax-n{{font-size:13px;font-weight:600;color:var(--label);background:var(--paper);border-radius:100px;padding:2px 9px}}
  .ax-chev{{width:18px;height:18px;fill:none;stroke:var(--label);stroke-width:2;transition:transform .2s}}
  .ax[open] .ax-chev{{transform:rotate(180deg)}}
  .ax[open] summary{{border-bottom:1px solid var(--line)}}
  .ax-body{{padding:12px 14px 6px}}
  .ax-text{{font-size:14.5px;color:#333a42;line-height:1.5}}
  .ax-stats{{font-size:13px;font-weight:600;color:var(--label);margin:8px 0 6px}}
  .nr-list{{list-style:none}}
  .nr{{display:flex;align-items:center;gap:8px;border-top:1px solid var(--line)}}
  .nr-pick{{flex:1;min-width:0;text-align:left;border:0;background:none;padding:10px 4px;cursor:pointer;font:inherit;color:var(--ink);display:flex;flex-direction:column;gap:1px;border-radius:6px}}
  .nr-name{{font-weight:700;font-size:15px}}
  .nr-meta{{font-size:13px;color:var(--label)}}
  .nr-pick:hover .nr-name,.nr.on .nr-name{{color:var(--lake)}}
  .nr.on{{background:#eef5fa}}
  .nr-go{{flex:none;font-size:13px;font-weight:700;color:var(--lake);padding:6px 6px;white-space:nowrap}}
  .xp .map-box{{max-width:none}}
  .sh-grab,.sh-btn{{display:none}}
  @media(max-width:979px){{
    .map-sec{{padding:6px 0 0}}
    .xp{{position:relative;display:block;height:calc(100svh - 64px);min-height:440px;padding:0}}
    .xp-map{{position:absolute;inset:0}}
    .xp .map-box{{height:100%;border-radius:0}}
    .xp #map{{height:100%}}
    .xp .map-note{{display:none}}
    .xp .map-card{{top:46px;bottom:auto;left:10px;right:10px;max-width:none}}
    .xp-list{{position:absolute;left:0;right:0;bottom:0;z-index:600;height:150px;display:flex;flex-direction:column;
      background:var(--white);border-radius:16px 16px 12px 12px;box-shadow:0 -4px 18px rgba(0,0,0,.18);transition:height .25s ease}}
    .xp-list.dragging{{transition:none}}
    .sh-head{{position:relative;flex:none;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:16px 14px 10px;touch-action:none;cursor:grab;-webkit-user-select:none;user-select:none}}
    .sh-grab{{display:block;position:absolute;top:6px;left:50%;width:38px;height:5px;margin-left:-19px;border-radius:3px;background:#c9cfd6}}
    .sh-head h2{{font-size:17px}}
    .sh-btn{{display:block;border:1px solid var(--line);background:var(--white);border-radius:100px;font:600 13px var(--sans);color:var(--lake);padding:6px 12px;cursor:pointer}}
    .sh-body{{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:0 12px 12px}}
    .xp-list .xp-hint{{display:none}}
    .xp .leaflet-control-zoom{{display:none}}
  }}
  @media(min-width:980px){{
    .xp{{grid-template-columns:minmax(0,400px) minmax(0,1fr);gap:24px;align-items:start}}
    .xp-map{{order:0;position:sticky;top:76px}}
    .xp #map{{height:calc(100vh - 150px);min-height:460px;max-height:820px}}
  }}
  .areas-wrap{{padding:32px 0 8px}}
  .area{{padding:28px 0}}
  .area + .area{{border-top:1px solid var(--line)}}
  .area-head{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}}
  .area-head h3{{display:flex;align-items:center;gap:10px;font-size:clamp(20px,2.6vw,26px);font-weight:800;letter-spacing:-.01em}}
  .area-head .dot{{width:14px;height:14px}}
  .area-stats{{font-size:14px;color:var(--label);font-weight:600}}
  .area-text{{margin:8px 0 18px;color:#333a42;font-size:15.5px;max-width:820px}}
  .cc-grid{{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}}
  .cc{{position:relative;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--white);display:flex;flex-direction:column}}
  .cc img,.cc-ph{{width:100%;aspect-ratio:16/10;object-fit:cover}}
  .cc-ph{{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,var(--paper),var(--mist));color:var(--ac);font:700 34px var(--serif);border-bottom:3px solid var(--ac)}}
  .cc-body{{padding:12px 14px 14px;display:flex;flex-direction:column;gap:4px;flex:1}}
  .cc:not(:has(img)){{border-left:4px solid var(--ac)}}
  .cc h4{{font-size:16px;font-weight:800}}
  .cc-meta{{font-size:13.5px;color:var(--label)}}
  .cc-cta{{font-size:13.5px;font-weight:700;color:var(--lake);margin-top:auto;padding-top:4px}}
  .cc-link{{position:absolute;inset:0;z-index:1}}
  .cc:has(.cc-link):hover{{border-color:var(--lake);box-shadow:0 4px 14px rgba(20,86,232,.12)}}
  .cc-map{{position:relative;z-index:2;align-self:flex-start;border:0;background:none;padding:0;font:600 12.5px var(--sans);color:var(--label);text-decoration:underline;cursor:pointer}}
  .cc-map:hover{{color:var(--lake)}}
  @media(max-width:760px){{
    .hub-intro{{padding:12px 0 2px}}
    .hub-bar h1 span{{display:block;margin:2px 0 0}}
    .map-card{{padding:12px 14px}}
    .map-card a.mc-go{{margin-top:8px;padding:7px 12px}}
    #map{{height:58vh}}
    .chips{{flex-wrap:nowrap;overflow-x:auto;justify-content:flex-start;padding:0 2px 4px;scrollbar-width:none}}
    .chips::-webkit-scrollbar{{display:none}}
    .chip{{white-space:nowrap}}
    .map-box{{border-radius:10px}}
    .map-card{{right:10px;max-width:none}}
    .cc-grid{{grid-template-columns:1fr 1fr;gap:10px}}
    .cc h4{{font-size:14.5px}}
    .cc-body{{padding:10px 10px 12px}}
    .area{{padding:22px 0}}
  }}
</style>
</head>
<body>

{masthead}

<nav class="breadcrumb" aria-label="Breadcrumb">
  <div class="wrap"><a href="/">Home</a><span class="sep">/</span><span class="current">Carmel Valley Neighborhoods</span></div>
</nav>

<section class="hub-intro">
  <div class="wrap hub-bar">
    <h1>Carmel Valley Neighborhoods <span>Single-family homes by area</span></h1>
    <p class="hub-stats">{len(comms)} neighborhoods &middot; {homes_floor}+ homes &middot; {len(groups)} areas</p>
  </div>
</section>

<section class="map-sec" id="map-section">
  <div class="wrap xp">
    <div class="xp-list" id="areas">
      <div class="sh-head" id="shHead"><span class="sh-grab" aria-hidden="true"></span>
        <h2>Neighborhoods by Area</h2>
        <button type="button" class="sh-btn" id="shBtn" aria-controls="areas" aria-expanded="false">Show list</button>
      </div>
      <div class="sh-body">
      <p class="xp-hint">Every single-family neighborhood in Carmel Valley, grouped by area. Open an area to see its neighborhoods, how many homes each has and what houses there sold for, then tap one to find it on the map.</p>
{chr(10).join(sec)}
      </div>
    </div>
    <div class="xp-map">
      <div class="map-box">
        <div id="map" class="sat" role="region" aria-label="Map of Carmel Valley single-family neighborhoods"></div>
        <div class="map-views" role="group" aria-label="Map view"><button type="button" data-b="sat" aria-pressed="true">Satellite</button><button type="button" data-b="map" aria-pressed="false">Map</button></div>
        <div class="map-card" id="mcard" aria-live="polite"></div>
      </div>
      <p class="map-note">Boundaries are approximate. Home counts are from the California Title Company community chart. Price ranges are what single-family homes sold for over the last 5 years.</p>
    </div>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <div class="sec-head"><h2>Carmel Valley Neighborhoods: Common Questions</h2></div>
    <div class="faq-list">
{faq_html}
    </div>
  </div>
</section>

{contact_footer}

{jsonld}

<nav class="bottom-nav" aria-label="Jump to section">
  <a href="#map-section"><svg viewBox="0 0 24 24"><path d="M12 21s7-7.1 7-12a7 7 0 0 0-14 0c0 4.9 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>Map</a>
  <a href="#areas"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>Areas</a>
  <a href="#faq"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.8-2.5 2-2.5 4"/><circle cx="12" cy="16.5" r=".6"/></svg>FAQ</a>
  <a href="#contact"><svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>Contact</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')"><svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>Menu</a>
</nav>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="/assets/basemap.js"></script>
<script>
var HUB={json.dumps(mdata, separators=(",", ":"))};
(function(){{
  var C=HUB.c, A=HUB.areas, sel=-1, area=null;
  var wide=window.matchMedia('(min-width:980px)');
  var XP=document.querySelector('.xp'), SH=document.getElementById('areas');
  // keep the area being shown clear of the pull-up panel on phones
  function pad(p){{return wide.matches?{{padding:[p,p]}}:{{paddingTopLeft:[p,p+30],paddingBottomRight:[p,SH.offsetHeight+p]}};}}
  function esc(s){{return String(s).replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}});}}
  var map=L.map('map',{{scrollWheelZoom:false,zoomSnap:0.5}}).setView([32.94,-117.22],13);
  var cur='sat', BM=CVBase(map);
  CVBase.bind(BM,document.querySelector('.map-views'),function(k){{cur=k;
    document.getElementById('map').classList.toggle('sat',k==='sat');style();}});
  var layers=C.map(function(o,i){{var l=L.polygon(o.p,{{weight:1.5}}).addTo(map);
    l.on('click',function(e){{L.DomEvent.stopPropagation(e);pick(i,false);}});
    l.bindTooltip(o.n,{{sticky:true,direction:'top'}});return l;}});
  var all=L.latLngBounds([]);layers.forEach(function(l){{all.extend(l.getBounds());}});
  function fitAll(){{map.invalidateSize();map.fitBounds(all,pad(16));}}
  var touched=false;map.getContainer().addEventListener('pointerdown',function(){{touched=true;}});
  fitAll();window.addEventListener('load',fitAll);
  var rt;window.addEventListener('resize',function(){{clearTimeout(rt);rt=setTimeout(function(){{if(!touched&&!area&&sel<0)fitAll();else map.invalidateSize();}},150);}});
  var lbl=L.layerGroup().addTo(map);
  function style(){{var sat=cur==='sat';layers.forEach(function(l,i){{var o=C[i],c=A[o.a][1],dim=area&&o.a!==area,on=i===sel;
    l.setStyle({{color:on?'#101418':(sat?'#fff':c),weight:on?3:1.5,fillColor:c,fillOpacity:dim?0.06:(on?0.75:(sat?0.45:0.38)),opacity:dim?0.3:1}});}});}}
  function labels(){{lbl.clearLayers();if(map.getZoom()<15)return;var b=map.getBounds();
    C.forEach(function(o,i){{if(area&&o.a!==area)return;var c=layers[i].getBounds().getCenter();if(!b.contains(c))return;
      lbl.addLayer(L.tooltip({{permanent:true,direction:'center',className:'lbl',interactive:false}}).setLatLng(c).setContent(esc(o.n)));}});}}
  map.on('zoomend moveend',labels);
  var card=document.getElementById('mcard');
  function pick(i,zoom){{touched=true;sel=i;var o=C[i];style();
    var go=o.u?'<a class="mc-go" href="'+o.u+'">'+(o.g?'Community guide &rarr;':'See homes &rarr;')+'</a>':'<a class="mc-go" href="#contact">Ask about '+esc(o.n)+'</a>';
    card.innerHTML='<button type="button" class="mc-x" aria-label="Close">&times;</button><h3>'+esc(o.n)+'</h3><div class="mc-area"><span class="dot" style="--ac:'+A[o.a][1]+'"></span>'+esc(A[o.a][0])+'</div>'+(o.h||o.m?'<div class="mc-homes">'+(o.h?'<b>'+o.h+'</b> homes':'')+(o.h&&o.m?' &middot; ':'')+(o.m?'sold <b>'+o.m+'</b> (5 yrs)':'')+'</div>':'')+go;
    card.classList.add('show');card.querySelector('.mc-x').onclick=function(){{card.classList.remove('show');sel=-1;style();}};
    if(zoom)map.flyToBounds(layers[i].getBounds(),Object.assign({{maxZoom:16,duration:.6}},pad(40)));}}
  map.on('click',function(){{card.classList.remove('show');sel=-1;style();}});
  var AX=Array.prototype.slice.call(document.querySelectorAll('.ax')), quiet=false;
  var PICKS=Array.prototype.slice.call(document.querySelectorAll('.nr-pick'));
  function rowFor(i){{for(var k=0;k<PICKS.length;k++)if(PICKS[k].dataset.n===C[i].n)return PICKS[k];return null;}}
  function mark(i){{document.querySelectorAll('.nr.on').forEach(function(r){{r.classList.remove('on');}});
    var b=i>=0&&rowFor(i);if(b)b.parentNode.classList.add('on');return b;}}
  function setArea(k,fly){{touched=true;area=k;card.classList.remove('show');sel=-1;mark(-1);style();labels();
    if(fly){{var b=L.latLngBounds([]);layers.forEach(function(l,i){{if(!area||C[i].a===area)b.extend(l.getBounds());}});
      map.flyToBounds(b,Object.assign({{duration:.6}},pad(20)));}}}}
  AX.forEach(function(d){{d.addEventListener('toggle',function(){{
    if(quiet)return;
    if(d.open){{quiet=true;AX.forEach(function(o){{if(o!==d)o.open=false;}});quiet=false;setArea(d.dataset.a,true);}}
    else if(area===d.dataset.a){{setArea(null,false);fitAll();}}}});}});
  // map click on a neighborhood: open its area in the list and highlight the row
  var pick0=pick;pick=function(i,zoom){{
    var d=document.querySelector('.ax[data-a="'+C[i].a+'"]');
    if(d&&!d.open){{quiet=true;AX.forEach(function(o){{o.open=o===d;}});quiet=false;area=C[i].a;labels();}}
    pick0(i,zoom);var b=mark(i);
    if(b&&!zoom&&wide.matches)b.scrollIntoView({{block:'nearest',behavior:'smooth'}});}};
  document.querySelectorAll('.nr-pick').forEach(function(b){{
    var i=C.findIndex(function(o){{return o.n===b.dataset.n;}});if(i<0)return;
    b.addEventListener('click',function(){{if(!wide.matches)snap('peek');pick(i,true);}});
    b.addEventListener('mouseenter',function(){{if(sel<0){{layers[i].setStyle({{color:'#101418',weight:3,fillOpacity:.7}});}}}});
    b.addEventListener('mouseleave',function(){{if(sel<0)style();}});}});
  map.on('click',function(){{mark(-1);}});
  // ---- phone pull-up panel: peek / half / full ----
  var head=document.getElementById('shHead'), btn=document.getElementById('shBtn'), state='peek';
  function off(){{return wide.matches?0:Math.max(0,Math.round(XP.getBoundingClientRect().top));}}
  function hts(){{var H=XP.clientHeight-off();return {{peek:150,half:Math.round(H*.55),full:H-8}};}}
  function snap(st){{if(wide.matches){{SH.style.height='';return;}}state=st;SH.style.height=hts()[st]+'px';
    btn.textContent=st==='full'?'Show map':'Show list';btn.setAttribute('aria-expanded',st==='peek'?'false':'true');}}
  btn.addEventListener('click',function(e){{e.stopPropagation();snap(state==='full'?'peek':'full');}});
  var y0=null,h0=0,moved=false,dragDown=0;
  head.addEventListener('pointerdown',function(e){{if(wide.matches||e.target===btn)return;y0=e.clientY;h0=SH.offsetHeight;moved=false;
    SH.classList.add('dragging');head.setPointerCapture(e.pointerId);}});
  head.addEventListener('pointermove',function(e){{if(y0===null)return;var dy=y0-e.clientY;if(Math.abs(dy)>4)moved=true;dragDown=-dy;
    var t=hts();SH.style.height=Math.max(t.peek,Math.min(t.full,h0+dy))+'px';}});
  function end(){{if(y0===null)return;y0=null;SH.classList.remove('dragging');var t=hts(),h=SH.offsetHeight;
    if(!moved){{snap(state==='peek'?'half':state==='half'?'full':'peek');return;}}
    if(state==='peek'&&h0-h<=0&&dragDown>50){{snap('peek');toTitle();return;}}
    var best='peek';['peek','half','full'].forEach(function(k){{if(Math.abs(t[k]-h)<Math.abs(t[best]-h))best=k;}});snap(best);}}
  head.addEventListener('pointerup',end);head.addEventListener('pointercancel',end);
  // opening an area raises the panel halfway so its neighborhoods show with the map above
  var body=SH.querySelector('.sh-body');
  function toTop(el){{body.scrollTo({{top:Math.max(0,el.offsetTop-body.offsetTop-4),behavior:'smooth'}});}}
  AX.forEach(function(d){{d.addEventListener('toggle',function(){{if(!d.open||wide.matches)return;
    if(state==='peek'&&!quiet)snap('half');setTimeout(function(){{toTop(d);}},30);}});}});
  wide.addEventListener&&wide.addEventListener('change',function(){{snap(wide.matches?state:'peek');map.invalidateSize();}});
  // phones: the map fills the screen between the title and the bottom menu
  function fit(){{if(wide.matches){{XP.style.height='';return;}}var nav=document.querySelector('.bottom-nav');
    var top=XP.getBoundingClientRect().top+window.scrollY,nh=nav?nav.offsetHeight:0;
    XP.style.height=Math.max(440,window.innerHeight-nh)+'px';map.invalidateSize();}}
  // phones: the title scrolls away and the map takes the whole screen.
  // Touching the map or the list, or a scroll that stops part-way, settles the page on the map.
  function xpTop(){{return XP.getBoundingClientRect().top+window.scrollY;}}
  function toMap(){{if(wide.matches)return;var t=xpTop();if(window.scrollY<t-2)window.scrollTo({{top:t,behavior:'smooth'}});}}
  function toTitle(){{if(wide.matches)return;if(window.__showMasthead)window.__showMasthead();window.scrollTo({{top:0,behavior:'smooth'}});}}
  map.getContainer().addEventListener('pointerdown',toMap);
  head.addEventListener('pointerdown',function(){{if(state!=='peek')toMap();}});
  AX.forEach(function(d){{d.addEventListener('toggle',function(){{if(d.open)toMap();}});}});
  // until the page settles on the map, keep the panel in view above the bottom menu
  function lift(){{SH.style.bottom=off()+'px';if(state==='full')SH.style.height=hts().full+'px';}}
  lift();
  var lastY=window.scrollY,down=true,se;
  window.addEventListener('scroll',function(){{lift();var y=window.scrollY;if(y!==lastY)down=y>lastY;lastY=y;
    clearTimeout(se);se=setTimeout(function(){{if(wide.matches)return;var t=xpTop(),y=window.scrollY;
      if(y>4&&y<t-2)(down?toMap:toTitle)();}},140);}},{{passive:true}});
  fit();window.addEventListener('resize',function(){{fit();snap(state);}});
  snap('peek');
  // open the area named in the URL (#area-...)
  var h=location.hash&&document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if(h&&h.classList.contains('ax'))h.open=true;
  style();
}})();
</script>
<script>
(function(){{
  var links=Array.prototype.slice.call(document.querySelectorAll('.bottom-nav a[href^="#"]')).filter(function(a){{return a.getAttribute('href').length>1&&document.getElementById(a.getAttribute('href').slice(1));}});
  if(!links.length||!('IntersectionObserver' in window))return;
  var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(!e.isIntersecting)return;
    links.forEach(function(a){{a.classList.toggle('active',a.getAttribute('href')==='#'+e.target.id);}});}});}},{{rootMargin:'-45% 0px -50% 0px'}});
  links.forEach(function(a){{io.observe(document.getElementById(a.getAttribute('href').slice(1)));}});
}})();
</script>
{hide_js}
</body>
</html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(page)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(comms)} communities, {total_homes:,} homes, {len(groups)} areas, {len(page)//1024} KB")


if __name__ == "__main__":
    main()
