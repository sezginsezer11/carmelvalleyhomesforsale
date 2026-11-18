#!/usr/bin/env python3
"""Build the schools hub: /carmel-valley-schools/.

    python3 tools/build_schools_hub.py

Full-screen map of the Del Mar Union elementary attendance areas in Carmel Valley (one color per
school), with the same pull-up list and map card as the neighborhoods hub (tools/explorer.py).
Tapping a school opens its card: See homes / School guide on its school page.
Run after tools/build_school.py; tools/build_llm_files.py applies the shared bottom menu. Stdlib only.
"""
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
from sold_data import load_sales  # noqa: E402
from schools import school_boundary, share_in, _inside, sduhsd_zones, DMUSD, DMUSD_URL, SDUHSD_URL  # noqa: E402
from make_neighborhood import SCHOOL_PAGES, SCHOOLS_HUB as PATH  # noqa: E402
from build_communities_hub import load as load_communities  # noqa: E402
from explorer import explorer  # noqa: E402
from fetch_sbsd import simplify_ring  # noqa: E402

SITE = "https://carmelvalleyhomesforsale.com"
SBSD_URL = "https://www.schoolsitelocator.com/apps/solanabeach/"
# Carmel Valley schools in Del Mar Union SD (Del Mar Heights Elementary serves Del Mar, not 92130)
SCHOOLS = [
    ("Sage Canyon Elementary", "#0b5c8c"),
    ("Pacific Sky Elementary", "#e0691c"),
    ("Ocean Air Elementary", "#d0346f"),
    ("Ashley Falls Elementary", "#0d8f84"),
    ("Sycamore Ridge Elementary", "#7a4ce0"),
    ("Torrey Hills Elementary", "#c27a0e"),
    ("Carmel Del Mar Elementary", "#3f9a2a"),
]
SBSD_COLORS = {"Solana Ranch Elementary": "#0891b2", "Solana Highlands Elementary": "#b91c1c",
               "Solana Santa Fe Elementary": "#8a8a00", "Carmel Creek Elementary": "#475569"}
SDUHSD_YEAR = "2015\u201316"  # TODO: replace with the current San Dieguito map (PowerSchool locator) when available
MIDDLE = {"Carmel Valley Middle": "#0b5c8c", "Pacific Trails Middle": "#e0691c", "Earl Warren Middle": "#0d8f84"}
HIGH = {"Torrey Pines High": "#7a4ce0"}
DISTRICTS = {"mid": ("Middle schools", "San Dieguito Union HSD"),
             "high": ("High school", "San Dieguito Union HSD"),
             "dmusd": ("Del Mar Union School District", "Del Mar Union SD"),
             "sbsd": ("Solana Beach School District", "Solana Beach SD")}
e = html.escape


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:
        return t.replace(year=t.year - n, day=28)


def short(n):
    return "${}M".format(("%.2f" % (n / 1e6 + 1e-9)).rstrip("0").rstrip(".")) if n >= 1e6 else "${:,.0f}K".format(n / 1e3)


def label_point(rings, frame=None, n=40):
    """A point well inside the largest ring, for the map label (bounding-box centers can fall outside)."""
    from schools import _inside
    r = max(rings, key=lambda r: abs(sum(r[k][1] * r[k - 1][0] - r[k - 1][1] * r[k][0] for k in range(len(r)))))  # largest by area
    la0, la1 = min(p[0] for p in r), max(p[0] for p in r)
    lo0, lo1 = min(p[1] for p in r), max(p[1] for p in r)
    best, bd = None, -1
    for i in range(n):
        for j in range(n):
            la, lo = la0 + (i + .5) * (la1 - la0) / n, lo0 + (j + .5) * (lo1 - lo0) / n
            if frame and not (frame[0][0] < la < frame[1][0] and frame[0][1] < lo < frame[1][1]):
                continue
            if _inside(lo, la, [(q[1], q[0]) for q in r]):
                d = min((la - q[0]) ** 2 + (lo - q[1]) ** 2 for q in r[::3])
                if d > bd:
                    best, bd = [round(la, 5), round(lo, 5)], d
    return best


def main():
    _, comms, tpl = load_communities()
    sales = [r for r in load_sales() if r.get("lat") is not None]
    sbsd = json.load(open(os.path.join(TOOLS, "sbsd_zones.json"), encoding="utf-8"))["zones"]
    # (district key, school, color, Leaflet rings, grade note)
    # frame Carmel Valley (its neighborhoods), not the whole of every district
    cp = [q for c in comms for r in c["p"] for q in r]
    frame = [[min(q[0] for q in cp), min(q[1] for q in cp)], [max(q[0] for q in cp), max(q[1] for q in cp)]]
    ll = lambda rings: [[[round(y, 5), round(x, 5)] for x, y in simplify_ring([(round(x, 6), round(y, 6)) for x, y in r], 0.00004)] for r in rings]
    # (district key, school, color, Leaflet rings, note, level)
    entries = [("dmusd", n, c, school_boundary(n), "") for n, c in SCHOOLS]
    entries += [("sbsd", z["name"], SBSD_COLORS.get(z["name"], "#64748b"), z["rings"], z.get("note", "")) for z in sbsd]
    entries = [x + ("el",) for x in entries]
    entries += [("mid", n, MIDDLE[n], ll(r), f"{SDUHSD_YEAR} map", "mi") for n, r in sduhsd_zones("Middle School") if n in MIDDLE]
    entries += [("high", n, HIGH[n], ll(r), "Canyon Crest Academy and San Dieguito Academy by lottery", "hi") for n, r in sduhsd_zones("High School") if n in HIGH]

    zones, rows, all_hoods = [], {k: [] for k in DISTRICTS}, set()
    for dk, name, color, rings, grades, lvl in entries:
        bnd = [[(q[1], q[0]) for q in r] for r in rings]
        rs = [r for r in sales if any(_inside(r["lng"], r["lat"], b) for b in bnd)]
        five = [r["close_price"] for r in rs if r["_d"] >= years_ago(5)]
        t12 = [r["close_price"] for r in rs if r["_d"] >= years_ago(1)]
        med = statistics.median(t12) if t12 else None
        hoods = sorted(c["n"] for c in comms if share_in(c["p"], bnd) >= 0.3)
        if lvl == "el":
            all_hoods.update(hoods)
        page = SCHOOL_PAGES.get(name)
        meta = " &middot; ".join(x for x in [f"{len(hoods)} neighborhoods", f"median {short(med)}" if med else "", grades] if x)
        zones.append({"n": name, "sub": dk, "c": color, "p": rings, "note": meta,
                      "r5": f"{short(min(five))}&ndash;{short(max(five))}" if five else None,
                      "x": DISTRICTS[dk][1] + " \u00b7 " + (f"{SDUHSD_YEAR} map" if lvl != "el" else f"{len(hoods)} neighborhoods" if hoods else "Carmel Valley"),
                      "v": lvl,
                      "hu": page + "#listings" if page else "", "gu": page if page else "", "gl": "School guide",
                      "l": re.sub(r" (Elementary|Middle|High)$", "", name), "lp": label_point(rings, frame)})
        name_html = f'<a href="{page}">{e(name)}</a>' if page else e(name)
        rows[dk].append(f'<tr><td class="nm"><span class="dot" style="--ac:{color}"></span> {name_html}</td>'
                        f'<td class="num">{len(hoods)}</td><td class="num">{short(med) if med else "&mdash;"}</td>'
                        f'<td class="num">{len(t12)}</td></tr>'
                        f'<tr class="sub"><td colspan="4">{e(", ".join(hoods[:8]))}{", and more" if len(hoods) > 8 else ""}</td></tr>')
    table = "".join(f'<tr class="dh"><th colspan="4">{DISTRICTS[k][0]}</th></tr>' + "".join(rows[k]) for k in ("dmusd", "sbsd", "mid", "high") if rows[k])

    # frame Carmel Valley (its neighborhoods), not the whole of every district
    LV = {"dmusd": "el", "sbsd": "el", "mid": "mi", "high": "hi"}
    groups = [(k, DISTRICTS[k][0], [z for z in zones if z["sub"] == k], LV[k]) for k in ("dmusd", "sbsd", "mid", "high")]
    groups = [g for g in groups if g[2]]
    x = explorer(zones, groups, {"dmusd": "#0b5c8c", "sbsd": "#0891b2", "mid": "#e0691c", "high": "#7a4ce0"}, SCHOOL_PAGES, {}, list_title="Carmel Valley Schools",
                 hint="Carmel Valley school attendance areas. Pick Elementary, Middle or High on the map, open a district, then tap a school to see its area.",
                 map_aria="Map of Carmel Valley elementary school attendance areas",
                 map_note=f"Elementary areas from the {DMUSD} map and the Solana Beach School District school locator; middle and high school areas "
                          f"from the {SDUHSD_YEAR} San Dieguito Union HSD map (middle-school areas overlap in it). "
                          f"Boundaries change, so confirm any address with the district.",
                 label_zoom=11, frame=frame, levels=[("el", "Elementary"), ("mi", "Middle"), ("hi", "High")])

    n_hoods = len(all_hoods)
    faqs = [
        ("Which elementary school serves my Carmel Valley address?",
         f"Most of western and central Carmel Valley is in the {DMUSD}: Sage Canyon, Pacific Sky, Ocean Air, Ashley Falls, Sycamore Ridge, "
         "Torrey Hills and Carmel Del Mar elementary schools. Much of Pacific Highlands Ranch and Torrey Highlands is in Solana Beach School District "
         "(Solana Ranch, Solana Highlands, Solana Santa Fe, and Carmel Creek with Solana Pacific). Boundaries can split a neighborhood, so check the exact address with the district locator."),
        ("What middle and high school do Carmel Valley homes go to?",
         "Carmel Valley is in San Dieguito Union High School District. Middle school is Carmel Valley Middle or Pacific Trails Middle depending on the address. "
         "The assigned high school is Torrey Pines High, and Canyon Crest Academy and San Dieguito Academy are open by lottery."),
        ("Do homes cost more in some school areas?",
         "Yes. Prices follow home size, age and lot as much as the school, but each school page shows the 12-month median and what houses inside "
         "that boundary sold for, so you can compare like for like."),
        ("How do I search for homes in one school area?",
         "Tap the school on the map, then See homes. Each school page lists the neighborhoods inside the boundary and recent sales. "
         "Call or email Sez Sezer for listings inside a specific boundary, including homes not yet on the market."),
    ]
    faq_html = "\n".join(f'      <details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Carmel Valley Schools", "item": SITE + PATH}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
    ]
    jsonld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    css = re.search(r"<style>(.*?)</style>", tpl, re.S).group(1)
    masthead = tpl[tpl.index("<!-- ============ PRIMARY NAVIGATION"):tpl.index("</header>") + len("</header>")]
    contact_footer = tpl[tpl.index("<!-- ============ CONTACT BLOCK"):tpl.index("</footer>") + len("</footer>")]
    contact_footer = contact_footer.replace("Thinking About {{name}}?", "Shopping by School Area?").replace(
        "{{contact_lead}}", "Tell me which school you want and your budget, and I&rsquo;ll send you every home that comes up inside that boundary, including ones that haven&rsquo;t hit the market yet.")
    hide_js = tpl[tpl.rindex("<script>"):tpl.rindex("</script>") + len("</script>")]

    title = "Carmel Valley Schools Map: Homes by Elementary School Area"
    desc = "Map of Carmel Valley elementary school attendance areas, with the neighborhoods in each and what homes sell for. San Diego 92130."
    assert len(desc) <= 160, len(desc)

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
{x["css"]}
  /* ============ SCHOOLS HUB ============ */
  .hub-intro{{padding:18px 0 4px}}
  .hub-bar{{display:flex;align-items:baseline;justify-content:space-between;gap:6px 16px;flex-wrap:wrap}}
  .hub-bar h1{{font-size:clamp(21px,2.4vw,27px);font-weight:800;letter-spacing:-.015em;line-height:1.2}}
  .hub-bar h1 span{{font-weight:500;color:var(--label);font-size:.62em;letter-spacing:0;margin-left:6px;white-space:nowrap}}
  .hub-stats{{font-size:13.5px;font-weight:600;color:var(--label)}}
  .h3{{font-size:20px;font-weight:800;margin-bottom:10px}}
  .note{{font-size:13px;color:var(--label);margin-top:10px}}
  .tbl{{width:100%;border-collapse:collapse;font-size:15px}}
  .tbl th{{text-align:left;font-size:12.5px;color:var(--label);font-weight:600;padding:0 8px 8px;border-bottom:1px solid var(--line)}}
  .tbl td{{padding:11px 8px 2px;vertical-align:top}}
  .tbl tr.sub td{{padding:0 8px 11px 26px;font-size:13px;color:var(--label);border-bottom:1px solid var(--mist)}}
  .tbl .num,.tbl th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  .tbl .nm{{font-weight:700}}
  .tbl tr.dh th{{padding:18px 8px 6px;font-size:13px;color:var(--lake);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--line)}}
  .path{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}
  .path div{{border:1px solid var(--line);border-radius:12px;padding:14px}}
  .path .lv{{font-size:12px;font-weight:700;color:var(--lake);text-transform:uppercase;letter-spacing:.04em}}
  .path .sn{{font-size:16px;font-weight:700;margin-top:4px}}
  .path .sd{{font-size:13px;color:var(--label);margin-top:2px}}
  @media(max-width:760px){{
    .hub-intro{{padding:12px 0 2px}}
    .hub-bar h1 span{{display:block;margin:2px 0 0}}
    .path{{grid-template-columns:minmax(0,1fr)}}
    .tbl{{font-size:14px}}
    .tbl td{{padding:10px 5px 2px}}
    .tbl tr.sub td{{padding:0 5px 10px 22px}}
  }}
</style>
{x["head_js"]}
</head>
<body>

{masthead}

<nav class="breadcrumb" aria-label="Breadcrumb">
  <div class="wrap"><a href="/">Home</a><span class="sep">/</span><span class="current">Carmel Valley Schools</span></div>
</nav>

<section class="hub-intro">
  <div class="wrap hub-bar">
    <h1>Carmel Valley Schools <span>Homes by school area</span></h1>
    <p class="hub-stats">{sum(z["v"] == "el" for z in zones)} elementary schools &middot; {n_hoods} neighborhoods</p>
  </div>
</section>

{x["html"]}

<section id="schools-list" style="padding-top:28px">
  <div class="wrap">
    <h2 class="h3">Schools at a glance</h2>
    <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>School</th><th class="num">Neighborhoods</th><th class="num">Median, 12 mo</th><th class="num">Sold, 12 mo</th></tr></thead>
    <tbody>{table}</tbody></table></div>
    <p class="note">Single-family homes inside each attendance boundary. Confirm any address with <a href="{DMUSD_URL}" target="_blank" rel="noopener">{DMUSD}</a> or the <a href="{SBSD_URL}" target="_blank" rel="noopener">Solana Beach SD locator</a>.</p>
  </div>
</section>

<section id="solana-beach" style="padding-top:20px">
  <div class="wrap">
    <h2 class="h3">Two elementary school districts</h2>
    <p>Western and central Carmel Valley is in the {DMUSD}. Much of Pacific Highlands Ranch, Torrey Highlands and some neighborhoods north of
    Del Mar Heights Road are in Solana Beach School District: Solana Ranch, Solana Highlands, Solana Santa Fe, and Carmel Creek (K&ndash;3) with
    Solana Pacific for grades 4&ndash;6. Both send students on to San Dieguito Union High School District. Look up an exact address with
    <a href="{DMUSD_URL}" target="_blank" rel="noopener">{DMUSD}</a> or the <a href="{SBSD_URL}" target="_blank" rel="noopener">Solana Beach SD school locator</a>.</p>
  </div>
</section>

<section id="middle-high" style="padding-top:20px">
  <div class="wrap">
    <h2 class="h3">Middle and high schools</h2>
    <div class="path">
      <div><div class="lv">Middle</div><div class="sn">Carmel Valley Middle or Pacific Trails Middle</div><div class="sd">Depends on the address</div></div>
      <div><div class="lv">High</div><div class="sn">Torrey Pines High</div><div class="sd">The assigned high school for Carmel Valley</div></div>
      <div><div class="lv">By lottery</div><div class="sn">Canyon Crest Academy</div><div class="sd">and San Dieguito Academy</div></div>
    </div>
    <p class="note">All in San Dieguito Union High School District. Confirm with <a href="{SDUHSD_URL}" target="_blank" rel="noopener">SDUHSD boundary maps</a>.</p>
  </div>
</section>

<section class="faq" id="faq">
  <div class="wrap">
    <div class="sec-head"><h2>Carmel Valley Schools: Common Questions</h2></div>
    <div class="faq-list">
{faq_html}
    </div>
  </div>
</section>

{contact_footer}

{jsonld}

<nav class="bottom-nav" aria-label="Site menu"></nav>

{x["js"]}
{hide_js}
</body>
</html>
'''
    left = re.findall(r"\{\{\w+\}\}", page)
    if left:
        raise SystemExit(f"unfilled placeholders: {sorted(set(left))}")
    out = os.path.join(ROOT, PATH.strip("/"), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(page)
    print(f"wrote {PATH}: {len(zones)} schools, {n_hoods} neighborhoods, {len(page)//1024} KB")


if __name__ == "__main__":
    main()
