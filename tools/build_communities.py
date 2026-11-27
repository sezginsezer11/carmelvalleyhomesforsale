#!/usr/bin/env python3
"""Build every community page from one shared template.

    tools/community-template.html      the page design (shared by all communities)
    tools/communities/<slug>.json      one data file per community
    -> /<path>/index.html               the generated page

Change the design once in the template, run this script, and every community
page picks it up:

    python3 tools/build_communities.py            # build all communities
    python3 tools/build_communities.py arborlake  # build one

Then run tools/build_llm_files.py so the Markdown copies, llms files and
sitemap stay in sync. Stdlib only.
"""
import html
import json
import os
import re
import sys
import datetime
import statistics
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SITE = "https://carmelvalleyhomesforsale.com"

FACT_ICONS = {
    "price": '<path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "hoa": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    "sqft": '<path d="M3 3h7v7H3zM14 14h7v7h-7z"/><path d="M10 3 21 14"/>',
    "units": '<path d="M3 21V9l6-4 6 4v12"/><path d="M15 21V11l6 2v8z"/>',
    "built": '<rect x="3" y="4" width="18" height="17" rx="1"/><path d="M3 9h18M8 2v4M16 2v4"/>',
    "mello": '<circle cx="12" cy="12" r="9"/><path d="M8 8l8 8"/>',
    "tax": '<circle cx="7" cy="7" r="3"/><circle cx="17" cy="17" r="3"/><path d="M18 6 6 18"/>',
    "time": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 3.5"/>',
}
AMENITY_ICONS = {
    "lake": '<path d="M2 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0M2 13c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/><path d="M12 9V3M9.5 5.5 12 3l2.5 2.5"/>',
    "pool": '<path d="M2 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/><path d="M8 15V5a2 2 0 0 1 4 0M16 15V5a2 2 0 0 0-4 0M8 9h8"/>',
    "gym": '<path d="M6 7v10M18 7v10M3 9v6M21 9v6M6 12h12"/>',
    "tennis": '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6c3.5 3.5 3.5 9.3 0 12.8M18.4 5.6c-3.5 3.5-3.5 9.3 0 12.8"/>',
    "trees": '<path d="M12 22V12"/><path d="M7 12a5 5 0 1 1 10 0z"/><path d="M4 22h16"/>',
    "carport": '<path d="M3 10 12 4l9 6"/><path d="M5 10v10M19 10v10M3 20h18"/><rect x="8" y="13" width="8" height="4" rx="1"/>',
    "garage": '<path d="M3 21V9l9-6 9 6v12"/><path d="M7 21v-8h10v8M7 16h10"/>',
    "clubhouse": '<path d="M3 21h18M5 21V10l7-5 7 5v11"/><path d="M10 21v-5h4v5"/>',
    "bbq": '<path d="M5 9h14a7 7 0 0 1-14 0z"/><path d="M8 16l-2 5M16 16l2 5M9 3c0 1.5 1 2 1 3.5M13 3c0 1.5 1 2 1 3.5"/>',
    "water": '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
    "path": '<path d="M4 20c4-1 4-6 8-7s4-6 8-7"/><circle cx="4" cy="20" r="1.5"/><circle cx="20" cy="6" r="1.5"/>',
}
ANALYSIS_TAB = ('      <button type="button" role="tab" id="tab-analysis" aria-controls="analysis" aria-selected="false" tabindex="-1">'
                '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
                '<path d="M14 3v6h6M8 13h8M8 17h5"/></svg>Analysis</button>')


def svg(d, attrs=' viewBox="0 0 24 24" aria-hidden="true"'):
    return f'<svg{attrs}>{d}</svg>'


def plain(s):
    """HTML snippet -> plain text (for meta and JSON-LD)."""
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def render_facts(c):
    out = []
    for f in c["facts"]:
        icon = svg(FACT_ICONS.get(f["icon"], FACT_ICONS["price"]), ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"')
        out.append(f'    <div class="fact">{icon}<div class="num">{f["value"]}</div><div class="lbl">{f["label"]}</div></div>')
    return "\n".join(out)


def render_schools(c):
    return "\n".join(
        f'        <li>\n          <div class="s-level">{s["level"]}</div>\n          <div class="s-name">{s["name"]}</div>\n'
        f'          <div class="s-district">{s["district"]}</div>\n        </li>' for s in c["schools"])


def render_nearby(c):
    return "\n".join(f'        <li><span>{p}</span><span>{d}</span></li>' for p, d in c["nearby"])


def render_glance_cards(c):
    out = []
    for g in c["glance"]["cards"]:
        b = g["beds"]
        out.append(f'''      <div class="glance-card" data-beds="{b}">
        <div class="gc-head"><h3>{b} Bedroom</h3><div class="gc-count" id="g{b}-count">{g["count"]}</div></div>
        <div class="glance-row"><span class="gr-lbl">Size</span><span class="gr-val" id="g{b}-size">{g["size"]}</span></div>
        <div class="glance-row"><span class="gr-lbl">Sold for</span><span class="gr-val" id="g{b}-range">{g["range"]}</span></div>
        <div class="glance-row"><span class="gr-lbl">Most recent sale</span><span class="gr-val" id="g{b}-latest">{g.get("latest", "")}</span></div>
      </div>''')
    return "\n".join(out)


def render_glance_after(c):
    link = ' See the <a href="#analysis">full breakdown</a>.' if c.get("analysis") else ' See the <a href="#sold-data">price history</a>.'
    return f'<p class="glance-lede" style="margin-top:14px;margin-bottom:0"><span id="g-ratio">{c["glance"]["ratio"]}</span>{link}</p>'


def render_life(c):
    L = c["life"]
    reasons = "\n".join(f'      <li><strong>{t}</strong> {d}</li>' for t, d in L["reasons"])
    return f'''    <h2>Life at {c["name"]}</h2>
    <p class="lead">{L["lead"]}</p>
    <h3 class="life-sub">Why buyers choose {c["name"]}</h3>
    <ul class="reasons">
{reasons}
    </ul>'''


HOA_FILE = os.path.join(TOOLS, "hoa.json")
MELLO_TEXT = {"yes": "Yes", "no": "No", "some": "Some homes"}


def hoa_db():
    with open(HOA_FILE, encoding="utf-8") as f:
        d = json.load(f)
    d.pop("_about", None)
    return d


def hoa_info(name, c=None):
    """HOA facts for a community: tools/hoa.json, overridden by the page's own "hoa" block."""
    h = dict(hoa_db().get(name, {}))
    if c and isinstance(c.get("hoa"), dict):
        h.update(c["hoa"])
    h.setdefault("status", "confirm")
    return h


def hoa_fee_text(h):
    lo, hi = h.get("fee_low"), h.get("fee_high")
    if not lo:
        return ""
    return f"${lo:,}" + (f"&ndash;${hi:,}" if hi and hi != lo else "")


def hoa_short(name):
    """One line for nearby cards: 'HOA $435&ndash;$443/mo', 'No HOA' or ''."""
    h = hoa_info(name)
    if h["status"] == "no":
        return "No HOA"
    if h["status"] == "yes" and h.get("fee_low"):
        return f"HOA {hoa_fee_text(h)}/mo"
    return ""


def hoa_fact(c):
    h = hoa_info(c["name"], c)
    if h["status"] == "yes":
        return {"icon": "hoa", "value": (hoa_fee_text(h) + "/mo") if h.get("fee_low") else "Yes", "label": "HOA"}
    if h["status"] == "no":
        return {"icon": "hoa", "value": "None", "label": "HOA"}
    return {"icon": "hoa", "value": "Confirm", "label": "HOA"}


def mello_fact(c):
    m = hoa_info(c["name"], c).get("mello")
    return {"icon": "mello", "value": MELLO_TEXT.get(m, "Check tax bill"), "label": "Mello-Roos"}


def render_hoa(c, near_names):
    """HOA box on every community page: says plainly whether there is an HOA, the monthly fee,
    Mello-Roos, what the dues cover, and how the fee compares with nearby communities."""
    n, h = c["name"], hoa_info(c["name"], c)
    st = h["status"]
    if st == "yes":
        amt = f'{hoa_fee_text(h)}<span>/month</span>' if h.get("fee_low") else 'Yes'
        text = f'<strong>Yes, {n} has an HOA.</strong> {h.get("note", "")}'
        intro = h.get("intro") or "What owners pay each month, and what it covers."
    elif st == "no":
        amt = 'No HOA'
        text = f'<strong>No, {n} has no homeowners association</strong>, so there are no monthly HOA dues. {h.get("note", "")}'
        intro = "No monthly dues here, which is worth knowing when you compare it with nearby communities."
    else:
        amt = 'Confirm'
        text = (f'<strong>HOA dues for {n} are being confirmed.</strong> The listing and the seller&rsquo;s HOA documents '
                f'show the exact monthly amount. Ask me and I&rsquo;ll check it for the home you like.')
        intro = "Whether there is an HOA, what it costs, and Mello-Roos."
    if h.get("mello") in MELLO_TEXT:
        mello_line = f'<p class="hoa-also"><strong>Mello-Roos:</strong> {MELLO_TEXT[h["mello"]]}. {h.get("mello_note", "")}</p>'
    else:
        mello_line = ('<p class="hoa-also"><strong>Mello-Roos:</strong> check the property tax bill for the home; '
                      'special taxes (CFDs) show up as separate lines and can differ from street to street.</p>')
    left = ""
    if h.get("amenities"):
        amen = "\n".join(f'          <li>{svg(AMENITY_ICONS.get(i, AMENITY_ICONS["trees"]))}<span>{t}</span></li>'
                         for i, t in h["amenities"])
        left += ('        <h3 class="hoa-h">What the HOA includes</h3>\n        <ul class="amen-grid">\n'
                 + amen + '\n        </ul>\n')
    if h.get("also"):
        left += f'        <p class="hoa-also"><strong>Also covered:</strong> {h["also"]}</p>\n'
    left += "        " + mello_line + "\n"
    # compare bars: this community plus nearby ones with a known fee (or no HOA)
    rows = [(n, h, True)] + [(x, hoa_info(x), False) for x in near_names if x != n]
    rows = [r for r in rows if r[1]["status"] == "no" or (r[1]["status"] == "yes" and r[1].get("fee_low"))]
    compare = ""
    if len(rows) >= 2 and any(r[2] for r in rows):
        def top_fee(hh):
            return hh.get("fee_high") or hh.get("fee_low") or 0
        top = max(top_fee(hh) for _, hh, _ in rows) or 1
        rows.sort(key=lambda r: -top_fee(r[1]))
        bars = []
        for x, hh, this in rows:
            fee = "No HOA" if hh["status"] == "no" else f'{hoa_fee_text(hh)}/mo'
            cls = "hoa-bar-row this-community" if this else "hoa-bar-row"
            bars.append(f'        <div class="{cls}">\n'
                        f'          <div class="hoa-bar-label"><span>{x}</span><span class="amt">{fee}</span></div>\n'
                        f'          <div class="hoa-bar-track"><div class="hoa-bar-fill" style="width:{round(100 * top_fee(hh) / top)}%"></div></div>\n'
                        f'        </div>')
        compare = ('      <div class="hoa-compare">\n        <h3>How the Monthly Dues Compare</h3>\n' + "\n".join(bars)
                   + '\n        <p style="margin-top:20px;font-size:13.5px;color:var(--label)">Nearby communities with a known fee, '
                     'from recent MLS listings. Confirm the current amount with the HOA.</p>\n      </div>\n')
    src = f' <span class="data-stamp">Source: {h["source"]}.</span>' if h.get("source") else ""
    solo = "" if compare else " solo"
    return (f'<section class="hoa" id="cost">\n  <div class="wrap">\n    <div class="sec-head">\n'
            f'      <div class="eyebrow">HOA &amp; Mello-Roos</div>\n      <h2>Does {n} Have an HOA?</h2>\n      <p>{intro}</p>\n    </div>\n'
            f'    <div class="hoa-fee">\n      <div class="hf-amt">{amt}</div>\n      <div class="hf-text">{text}{src}</div>\n    </div>\n'
            f'    <div class="hoa-grid{solo}">\n      <div>\n{left}      </div>\n{compare}    </div>\n  </div>\n</section>')


# ---------- price by home size ----------
BANDS = [(0, 3000), (3000, 4000), (4000, 5000), (5000, 6000), (6000, 7000), (7000, 10 ** 9)]


def size_clusters(rows):
    """Group sales into floor-plan tiers: sizes within ~100-130 sq ft of each other are one plan."""
    s = sorted((r for r in rows if r.get("living_area")), key=lambda r: r["living_area"])
    out = []
    for r in s:
        if (out and r["living_area"] - out[-1][-1]["living_area"] <= max(100, out[-1][-1]["living_area"] * 0.025)
                and r["living_area"] - out[-1][0]["living_area"] <= max(200, out[-1][0]["living_area"] * 0.05)):  # one plan, not a drift
            out[-1].append(r)
        else:
            out.append([r])
    return out


def size_groups(c, rows):
    """[(label, sub, rows newest first)] and the mode used: 'tiers' (floor plans) or 'bands' (custom homes)."""
    mode = c.get("glance", {}).get("mode", "auto")
    sized = [r for r in rows if r.get("living_area")]
    if not sized:
        return "bands", []
    cl = [g for g in size_clusters(sized) if len(g) >= 2]
    covered = sum(len(g) for g in cl) / len(sized)
    if mode == "auto":
        mode = "tiers" if 2 <= len(cl) <= 8 and covered >= 0.7 else "bands"
    groups = []
    if mode == "tiers":
        # keep the plans with the most recent activity (up to 6), shown smallest to largest
        def activity(g):
            return (sum(1 for r in g if r["_d"] >= years_ago(2)), sum(1 for r in g if r["_d"] >= years_ago(5)), len(g))
        cl = [g for g in cl if any(r["_d"] >= years_ago(5) for r in g)]
        cl = sorted(sorted(cl, key=activity, reverse=True)[:6], key=lambda g: g[0]["living_area"])
        for g in cl:
            sizes = [r["living_area"] for r in g]
            mid = round(statistics.median(sizes) / 50) * 50
            beds = statistics.mode([r["beds_total"] for r in g if r.get("beds_total")] or [0])
            rng = f"{min(sizes):,}&ndash;{max(sizes):,} sq ft" if max(sizes) > min(sizes) else f"{min(sizes):,} sq ft"
            groups.append((f"About {mid:,} sq ft", rng + (f" &middot; usually {beds} bed" if beds else ""),
                           sorted(g, key=lambda r: r["_d"], reverse=True)))
    else:
        for lo, hi in BANDS:
            g = [r for r in sized if lo <= r["living_area"] < hi]
            if not g:
                continue
            lbl = f"Under {hi:,} sq ft" if lo == 0 else f"{lo:,}+ sq ft" if hi > 10 ** 8 else f"{lo:,}&ndash;{hi:,} sq ft"
            beds = sorted({r["beds_total"] for r in g if r.get("beds_total")})
            sub = (f"{beds[0]}&ndash;{beds[-1]} bed" if len(beds) > 1 else f"{beds[0]} bed") if beds else ""
            groups.append((lbl, sub, sorted(g, key=lambda r: r["_d"], reverse=True)))
    return mode, groups


def pick_recent(g):
    """2-4 most recent sales in the last 2 years; if fewer than 2, up to 2 from the last 5 years."""
    two = [r for r in g if r["_d"] >= years_ago(2)][:4]
    if len(two) >= 2:
        return two, "last 2 years"
    five = [r for r in g if r["_d"] >= years_ago(5)][:2]
    return five, "last 5 years"


def render_size_cards(c, rows):
    mode, groups = size_groups(c, rows)
    cards, faq_bits = [], []
    for lbl, sub, g in groups:
        recent, window = pick_recent(g)
        if not recent:
            continue
        prices = [r["close_price"] for r in recent]
        psf = [r["close_price"] / r["living_area"] for r in recent if r.get("living_area")]
        lis = "".join(
            f'<li><span class="ts-p">{money(r["close_price"])}</span><span class="ts-m">{r["living_area"]:,} sq ft &middot; '
            f'{r.get("beds_total") or "&mdash;"} bd &middot; {MONTHS[r["_d"].month - 1]} {r["_d"].year}</span></li>' for r in recent)
        rng = f"{k(min(prices))}&ndash;{k(max(prices))}" if max(prices) > min(prices) else k(min(prices))
        cards.append(f'''      <div class="glance-card tier">
        <div class="gc-head"><h3>{lbl}</h3><div class="gc-count">{sub}</div></div>
        <div class="glance-row"><span class="gr-lbl">Sold for</span><span class="gr-val">{rng}</span></div>
        <div class="glance-row"><span class="gr-lbl">Per sq ft</span><span class="gr-val">about {money(statistics.median(psf))}</span></div>
        <ul class="tier-sales" aria-label="Most recent sales, {lbl.replace("&ndash;", "-")}">{lis}</ul>
        <p class="tier-note">{len(recent)} most recent sale{"s" if len(recent) != 1 else ""}, {window}</p>
      </div>''')
        faq_bits.append(f"{plain(lbl).replace('About ', 'about ')} ({rng.replace('&ndash;', ' to ')})")
    return mode, "\n".join(cards), len(cards), faq_bits


def render_similar(c):
    out = []
    for k in c["similar"]["cards"]:
        if k.get("img"):
            img = f'<div class="cmp-img"><img src="{k["img"]}" alt="{k["alt"]}" loading="lazy"></div>'
        else:
            img = f'<div class="cmp-img ph" aria-hidden="true">{k["name"]}</div>'
        out.append(f'''        <a class="cmp-card" href="{k["href"]}">
          {img}
          <div class="cmp-body">
            <h3>{k["name"]}</h3>
            <div class="cmp-meta">{k["meta"]}</div>
            <p>{k["desc"]}</p>
            <span class="cmp-go">{k["cta"]} &rarr;</span>
          </div>
        </a>''')
    return "\n".join(out)


def render_analysis_panel(c):
    a = c.get("analysis")
    if not a:
        return ""
    tk = "\n".join(f'        <li><strong>{t}</strong> {d}</li>' for t, d in a["takeaways"])
    return f'''    <div class="px-panel" role="tabpanel" id="analysis" aria-labelledby="tab-analysis" hidden>
      <h3 class="px-h">{a["title"]}</h3>
      <p class="data-stamp">{a["stamp"]}</p>
      <ul class="takeaways">
{tk}
      </ul>
      <details class="px-more">
        <summary><span class="cl-closed">Read the full analysis <span class="cl-icon">+</span></span><span class="cl-open">Hide the full analysis <span class="cl-icon">&ndash;</span></span></summary>
        <div class="analysis-body">
{a["body_html"]}
        </div>
      </details>
    </div>'''


def render_fit(items):
    return "\n".join(f'          <li><h4>{h}</h4><p>{p}</p></li>' for h, p in items)


def render_faq(c):
    out = []
    for f in c["faq"]:
        out.append(f'      <details>\n        <summary>{f["q"]}</summary>\n        {f["a"]}\n      </details>')
    return "\n".join(out)


def faq_answer_text(a):
    # ordered lists become "item; item" for the schema text
    a = re.sub(r"</li>\s*<li>", "; ", a)
    return plain(a)


def render_jsonld(c):
    url = SITE + c["path"]
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": c["parent_name"], "item": SITE + c["parent_url"]},
        {"@type": "ListItem", "position": 3, "name": c["name"], "item": url}]}
    agent = {"@context": "https://schema.org", "@type": "RealEstateAgent", "name": "Sez Sezer",
             "image": SITE + "/images/sez-sezer-carmel-valley-realtor.jpg", "url": url, "mainEntityOfPage": url,
             "telephone": "+1-858-436-6585", "email": "sez@carmelvalley.com", "priceRange": "$$$",
             "description": c["seo"]["jsonld_description"],
             "address": {"@type": "PostalAddress", "streetAddress": "12750 High Bluff Drive", "addressLocality": "San Diego",
                         "addressRegion": "CA", "postalCode": "92130", "addressCountry": "US"},
             "areaServed": {"@type": "Place", "name": f'{c["name"]}, Carmel Valley, San Diego, CA',
                            "geo": {"@type": "GeoCoordinates", "latitude": c["geo"]["lat"], "longitude": c["geo"]["lng"]}},
             "memberOf": {"@type": "Organization", "name": "Keller Williams Realty"}}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": plain(f["q"]), "acceptedAnswer": {"@type": "Answer", "text": faq_answer_text(f["a"])}}
        for f in c["faq"]]}
    blocks = [json.dumps(x, ensure_ascii=False, indent=2) for x in (crumbs, agent, faq)]
    return "\n".join(f'<script type="application/ld+json">\n{b}\n</script>' for b in blocks)


API = "https://www.sellmyhomesforcash.com/api/public/sold-listings?community={}&zip=92130&limit=500"
SFR = "Single Family Residence"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_sales(c):
    """Closed sales for the community (deduped), or None if the feed is unreachable.
    Same rules as the page's own script: first row per group_key wins."""
    try:
        url = API.format(urllib.request.quote(c["api_community"]))
        with urllib.request.urlopen(url, timeout=25) as r:
            d = json.load(r)
    except Exception as e:  # build still works with the JSON fallback values
        print(f"  ! sales feed unavailable ({e}); using fallback values")
        return None
    seen, rows = set(), []
    for r in d.get("rows", []):
        if r.get("group_key") in seen:
            continue
        seen.add(r.get("group_key"))
        if r.get("close_price") is not None and r.get("close_date") and r.get("property_sub_type") == SFR:
            r["_d"] = datetime.date.fromisoformat(r["close_date"][:10])
            rows.append(r)
    rows.sort(key=lambda r: r["_d"], reverse=True)
    return rows


def years_ago(n):
    t = datetime.date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:  # Feb 29
        return t.replace(year=t.year - n, day=28)


def money(n):
    return "${:,.0f}".format(n)


def k(n):
    return "${:g}M".format(round(n / 1e6, 1)) if n >= 1e6 else "${}K".format(round(n / 1000))


def fmt_date(d):
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def glance_from_sales(c, rows):
    five = [r for r in rows if r["_d"] >= years_ago(1)]  # what homes sell for: last 12 months only
    cards = []
    for card in c["glance"]["cards"]:
        b = card["beds"]
        g = [r for r in five if r.get("beds_total") == b]
        if not g:
            cards.append(card)
            continue
        prices = [r["close_price"] for r in g]
        sizes = [r["living_area"] for r in g if r.get("living_area")]
        lo, hi = (min(sizes), max(sizes)) if sizes else (0, 0)
        cards.append({
            "beds": b,
            "count": f"{len(g)} sale{'s' if len(g) != 1 else ''} &middot; 12 mo",
            "size": (f"{lo:,}&ndash;{hi:,} sq ft" if hi > lo else f"{lo:,} sq ft") if sizes else card["size"],
            "latest": f'{money(g[0]["close_price"])} &middot; {MONTHS[g[0]["_d"].month - 1]} {g[0]["_d"].year}',
            "range": f"{k(min(prices))}&ndash;{k(max(prices))}" if max(prices) > min(prices) else k(min(prices)),
        })
    return cards


def stats(rows):
    t12 = [r for r in rows if r["_d"] >= years_ago(1)]
    five = [r for r in rows if r["_d"] >= years_ago(5)]
    def med(rs):
        return statistics.median([r["close_price"] for r in rs]) if rs else None
    def psf(rs):
        v = [r["close_price"] / r["living_area"] for r in rs if r.get("living_area")]
        return sum(v) / len(v) if v else None  # average, like the Overview tab
    return {"t12": t12, "five": five, "t12_median": med(t12), "t12_psf": psf(t12),
            "latest": rows[0] if rows else None}


def render_sales_summary(c, st):
    if not st or not st["five"]:
        return ""
    n = c["name"]
    parts = []
    if st["t12"]:
        parts.append(f'In the last 12 months, {len(st["t12"])} {n} home{"s" if len(st["t12"]) != 1 else ""} sold, '
                     f'at a median of {money(st["t12_median"])}' + (f' ({money(st["t12_psf"])}/sq ft)' if st["t12_psf"] else '') + '.')
    else:
        parts.append(f'No {n} homes sold in the last 12 months.')
    p12 = [r["close_price"] for r in st["t12"]]
    if p12:
        parts.append(f'They sold for between {money(min(p12))} and {money(max(p12))}.')
    if st["latest"]:
        r = st["latest"]
        desc = f'{r.get("beds_total")}-bedroom' + (f', {r["living_area"]:,} sq ft' if r.get("living_area") else "")
        parts.append(f'The most recent sale was a {desc} home that closed at {money(r["close_price"])} on {fmt_date(r["_d"])}.')
    return f'<p class="px-summary">{" ".join(parts)} <span class="data-stamp">MLS closed sales as of {fmt_date(datetime.date.today())}.</span></p>'


def short_addr(a):
    return re.sub(r"\bCourt\b", "Ct", re.sub(r"\bRoad\b", "Rd", a or ""))


def render_sold_static(rows):
    """Same markup the page's script builds, so search engines see real sales."""
    if not rows:
        return '<div class="sold-state">Loading recent sales&hellip;</div>'
    beds = sorted({r["beds_total"] for r in rows if r.get("beds_total")})
    out = []
    for b in beds:
        g = [r for r in rows if r.get("beds_total") == b][:8]
        trs = "".join(
            f'<tr><td class="addr">{html.escape(short_addr(r.get("address")))}</td>'
            f'<td class="num">{r.get("beds_total", "&mdash;")} / {r.get("baths_total", "&mdash;")}</td>'
            f'<td class="num">{("{:,}".format(r["living_area"]) if r.get("living_area") else "&mdash;")}</td>'
            f'<td class="num">{r.get("year_built") or "&mdash;"}</td>'
            f'<td class="price">{money(r["close_price"])}</td>'
            f'<td class="num">{fmt_date(r["_d"])}</td></tr>' for r in g)
        out.append(f'<div class="sold-group"><div class="sold-group-head"><h3>{b} Bedroom</h3><span class="cnt">{len(g)} most recent</span></div>'
                   f'<div class="sold-table-wrap"><table class="sold-table"><thead><tr><th>Address</th><th>Beds / Baths</th><th>Sq Ft</th>'
                   f'<th>Year Built</th><th>Sold Price</th><th>Close Date</th></tr></thead><tbody>{trs}</tbody></table></div></div>')
    return "".join(out)


def render_seller(c, st):
    n = c["name"]
    med = money(st["t12_median"]) if st and st["t12_median"] else "&mdash;"
    psf = money(st["t12_psf"]) if st and st["t12_psf"] else "&mdash;"
    cnt = (f'{len(st["t12"])} sale{"s" if len(st["t12"]) != 1 else ""}') if st and st["t12"] else "&mdash;"
    return f'''<!-- ============ SELLER: WHAT'S IT WORTH ============ -->
<section class="seller" id="sell">
  <div class="wrap">
    <div class="sec-head">
      <div class="eyebrow">Thinking of Selling?</div>
      <h2>What's Your {n} Home Worth?</h2>
    </div>
    <div class="seller-grid">
      <div class="seller-tile"><div class="sv" id="sv-median">{med}</div><div class="sl">Median sale price, last 12 months</div></div>
      <div class="seller-tile"><div class="sv" id="sv-psf">{psf}</div><div class="sl">Average price per sq ft, last 12 months</div></div>
      <div class="seller-tile"><div class="sv" id="sv-count">{cnt}</div><div class="sl">Closed in the last 12 months</div></div>
    </div>
    <p class="seller-copy">{c.get("seller_copy") or f"Your home's value depends on its size, lot, floor plan, view and updates, not just the community median. I track every {n} sale and can tell you what yours would likely sell for today, with the comps to back it up."}</p>
    <div class="seller-cta">
      <a class="solid" href="#contact">Get my {n} home value</a>
      <a class="line" href="tel:+18584366585">Call Sez &middot; (858) 436-6585</a>
    </div>
  </div>
</section>'''


def auto_similar(c, live):
    """Nearby-community cards from the neighborhood map: closest communities first, linking to their
    own page when it is published, else to their area guide. Returns (cards, neighbor names)."""
    sys.path.insert(0, TOOLS)
    from sold_data import load_sales, AREA_LABELS
    from make_neighborhood import AREA_PAGES, HUB
    with open(os.path.join(TOOLS, "atlas_data.json"), encoding="utf-8") as f:
        comms = json.load(f)["c"]
    me = next((x for x in comms if x["n"].lower() == c["name"].lower()), None)
    if not me:
        return c["similar"]["cards"], [k["name"] for k in c["similar"]["cards"]]
    sales = load_sales()
    names, cards = [], []
    for j, miles in me.get("nb", []):
        x = comms[j]
        if x.get("cat") not in (None, "sfr"):
            continue
        names.append(x["n"])
        g = [r for r in sales if (r.get("community_name") or "").strip().lower() == x["n"].lower() and r["_d"] >= years_ago(5)]
        if len(g) < 3:
            continue
        g12 = [r for r in g if r["_d"] >= years_ago(1)]
        area = AREA_LABELS.get(x["sub"], "Carmel Valley")
        sizes = sorted(r["living_area"] for r in g if r.get("living_area"))
        yb = sorted(r["year_built"] for r in g if r.get("year_built"))
        bits = [b for b in (hoa_short(x["n"]),
                            f'12-mo median {k(statistics.median([r["close_price"] for r in g12]))}' if g12 else f"{len(g)} sales in 5 yrs") if b]
        where = "Next door" if miles < 0.05 else f"{miles:.1f} miles away"
        desc = f"{where} in {area}." + (f" Homes about {sizes[0]:,}&ndash;{sizes[-1]:,} sq ft" if sizes else "") + \
               (f", built {yb[0]}&ndash;{yb[-1]}." if yb and yb[-1] > yb[0] else f", built {yb[0]}." if yb else ".")
        if x["n"] in live:
            href, cta = live[x["n"]], f'{x["n"]} homes'
        else:
            href, cta = AREA_PAGES.get(x["sub"], HUB), f"{area} guide"
        cards.append({"href": href, "img": "", "alt": "", "name": x["n"], "meta": " &middot; ".join(bits), "desc": desc, "cta": cta})
        if len(cards) == 6:
            break
    return cards, names


def auto_faq(c, mode, size_bits):
    """Questions every community page answers: HOA, Mello-Roos and home sizes."""
    n, h = c["name"], hoa_info(c["name"], c)
    if h["status"] == "yes":
        a = f"<p>Yes. {n} has a homeowners association" + (f", and recent listings show dues of {plain(hoa_fee_text(h))} a month" if h.get("fee_low") else "") + \
            f". {plain(h.get('note', '')) if not h.get('fee_low') else ''}Confirm the current amount in the HOA documents before you write an offer.</p>"
    elif h["status"] == "no":
        a = f"<p>No. {n} has no homeowners association, so there are no monthly HOA dues.</p>"
    else:
        a = f"<p>The listing for each {n} home shows whether it pays HOA dues and how much. Ask me and I'll confirm it for the home you're considering.</p>"
    m = h.get("mello")
    mt = {"yes": f"Yes. Homes in {n} are in a Mello-Roos district (CFD), which appears as a special tax on the property tax bill.",
          "some": f"Some {n} homes list a Mello-Roos (CFD) assessment. It shows on the property tax bill, so check the bill for the home you like.",
          "no": f"No Mello-Roos has been reported for {n}."}.get(m, f"Check the property tax bill for the {n} home you like: Mello-Roos and other special taxes (CFDs) appear as separate lines.")
    out = [{"q": f"Does {n} have an HOA?", "a": a},
           {"q": f"Is there Mello-Roos in {n}?", "a": f"<p>{mt} Ask the title company for the exact amount during escrow.</p>"}]
    if size_bits:
        how = "Homes here come in a few floor-plan sizes" if mode == "tiers" else "Homes here vary a lot in size"
        out.append({"q": f"How big are homes in {n}, and what do they sell for?",
                    "a": f"<p>{how}: {'; '.join(size_bits)}. These ranges use the most recent sales of each size; see the size cards on this page.</p>"})
    have = {plain(f["q"]).lower() for f in c["faq"]}
    return [f for f in out if plain(f["q"]).lower() not in have]


def build(slug):
    with open(os.path.join(TOOLS, "communities", slug + ".json"), encoding="utf-8") as f:
        c = json.load(f)
    with open(os.path.join(TOOLS, "community-template.html"), encoding="utf-8") as f:
        t = f.read()
    rows = fetch_sales(c)
    st = stats(rows) if rows else None
    from publish import is_live, live_pages
    live, draft = live_pages(), not is_live(c)
    if c["similar"].get("auto", True):
        c["similar"]["cards"], near = auto_similar(c, live)
    else:
        near = [x["name"] for x in c["similar"]["cards"]]
    # price cards: by home size (floor-plan tiers, or size bands for custom homes) unless the page asks for bedrooms
    by_size = c["glance"].get("mode", "auto") != "bedrooms" and rows
    if by_size:
        mode, glance_cards_html, glance_n, size_bits = render_size_cards(c, rows)
        if not glance_n:
            by_size = False
    if by_size:
        glance_h2 = f'What a {c["name"]} Home Costs by Size'
        glance_lede = (f'{c["name"]} homes come in a few floor-plan sizes. Each card shows the most recent sales of that size, so you can compare like with like.'
                       if mode == "tiers" else
                       f'{c["name"]} homes vary a lot, so sales are grouped by size. Each card shows the most recent sales in that size range.')
        glance_after = ""
        glance_stamp = f'Closed MLS sales: up to 4 most recent per size from the last 2 years (5 years when a size has fewer than 2 recent sales). As of {fmt_date(datetime.date.today())}.'
        glance_cta = "See Prices by Size"
        size_faq = size_bits
    else:
        if rows:
            c["glance"]["cards"] = glance_from_sales(c, rows)
        mode, size_faq = "bedrooms", []
        glance_h2, glance_lede = c["glance"]["h2"], c["glance"]["lede"]
        glance_cards_html, glance_n, glance_after = render_glance_cards(c), len(c["glance"]["cards"]), render_glance_after(c)
        glance_stamp, glance_cta = "Closed MLS sales, last 12 months.", "See Prices by Bedroom"
    icons = {f["icon"] for f in c["facts"]}
    if "hoa" not in icons:
        c["facts"].append(hoa_fact(c))
    if "mello" not in icons:
        c["facts"].append(mello_fact(c))
    c["faq"] = c["faq"] + auto_faq(c, mode, size_faq)
    v = {
        "name": c["name"], "name_json": json.dumps(c["name"]), "path": c["path"],
        "parent_name": c["parent_name"], "parent_url": c["parent_url"],
        "api_community": c["api_community"].replace(" ", "%20"),
        "seo_title": c["seo"]["title"], "seo_description": html.escape(c["seo"]["description"], quote=True),
        "hero_eyebrow": c["hero"]["eyebrow"], "h1": c["hero"]["h1"], "hero_lead": c["hero"]["lead"],
        "facts_html": render_facts(c),
        "loc_intro": c["location_intro"], "lat": c["geo"]["lat"], "lng": c["geo"]["lng"],
        "boundary_json": json.dumps(c["boundary"]),
        "schools_html": render_schools(c), "nearby_html": render_nearby(c),
        "glance_h2": glance_h2, "glance_lede": glance_lede, "glance_stamp": glance_stamp, "glance_cta": glance_cta,
        "glance_cards_html": glance_cards_html, "glance_n": glance_n, "glance_after_html": glance_after,
        "life_html": render_life(c), "hoa_html": render_hoa(c, near),
        "similar_h2": c["similar"]["h2"], "similar_intro": c["similar"]["intro"], "similar_aria": c["similar"]["h2"],
        "similar_cards_html": render_similar(c),
        "analysis_tab_html": ANALYSIS_TAB if c.get("analysis") else "",
        "analysis_panel_html": render_analysis_panel(c),
        "fit_good_html": render_fit(c["fit"]["good"]), "fit_weigh_html": render_fit(c["fit"]["weigh"]),
        "faq_h2": c["faq_h2"], "faq_html": render_faq(c),
        "contact_lead": c["contact_lead"], "jsonld_html": render_jsonld(c),
        "hero_img_html": (f'  <img class="page-hero-img" src="{c["hero"]["img"]}" alt="{html.escape(c["hero"]["alt"], quote=True)}" width="1200" height="800" fetchpriority="high">\n'
                          if c["hero"].get("img") else ""),
        "og_image_html": (f'<meta property="og:image" content="{SITE}{c["hero"]["img"]}">\n' if c["hero"].get("img") else ""),
        "sales_summary_html": render_sales_summary(c, st),
        "sold_static_html": render_sold_static(rows or []),
        "seller_html": render_seller(c, st),
    }
    missing = set(re.findall(r"\{\{(\w+)\}\}", t)) - set(v)
    if missing:
        raise SystemExit(f"{slug}: template needs {sorted(missing)}")
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: str(v[m.group(1)]), t)
    live_dest = os.path.join(ROOT, c["path"].strip("/"), "index.html")
    draft_dest = os.path.join(ROOT, "_drafts", c["path"].strip("/"), "index.html")
    if draft:  # not public yet: preview copy only, never deployed (_drafts/ is in .assetsignore)
        out = out.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
        dest = draft_dest
    else:
        dest = live_dest
        if os.path.exists(draft_dest):
            os.remove(draft_dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"built {c['path']}" + (f"  (draft until {c['publish_on']}: _drafts{c['path']})" if draft else ""))


def main(argv):
    slugs = argv or sorted(n[:-5] for n in os.listdir(os.path.join(TOOLS, "communities")) if n.endswith(".json"))
    for s in slugs:
        build(s)


if __name__ == "__main__":
    main(sys.argv[1:])
