#!/usr/bin/env python3
"""One top menu for every page on the site.

Homes for Sale ▾ · Neighborhoods ▾ · Homes by School ▾ · Contact

Each drop-down lists the site's own pages: area pages and the luxury page,
community pages (NEIGHBORHOOD_PAGES in make_neighborhood.py, so a new
community page joins the menu once it is added there) and the school pages.
On desktop the lists open on hover; inside the phone Menu they open with the
arrow button. The "Also in Carmel Valley" groups below stay as they are.

build_llm_files.py runs this next to bottom_nav.py, so the normal build
order applies it automatically. It can also run on its own:

    python3 tools/top_nav.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_neighborhood import AREA_LABELS, AREA_PAGES, NEIGHBORHOOD_PAGES, SCHOOL_PAGES, HUB, SCHOOLS_HUB  # noqa: E402
from bottom_nav import pages, ROOT  # noqa: E402

LUXURY = "/carmel-valley-luxury-homes-for-sale/"
TEMPLATE = os.path.join(ROOT, "tools", "community-template.html")

CHEVRON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>'


def groups():
    areas = sorted(((AREA_LABELS[k], p) for k, p in AREA_PAGES.items()), key=lambda x: x[0])
    return [
        ("Homes for Sale", "/", "All single-family homes",
         areas + [("Luxury homes $3M+", LUXURY)]),
        ("Neighborhoods", HUB, "Neighborhoods map",
         sorted(NEIGHBORHOOD_PAGES.items())),
        ("Homes by School", SCHOOLS_HUB, "Schools map",
         [(n.replace(" Elementary", " Elementary area"), p) for n, p in SCHOOL_PAGES.items()]),
    ]


def nav_links(here):
    cur = ' aria-current="page"'
    out = []
    for i, (label, top, all_label, items) in enumerate(groups()):
        pid = f"dd{i + 1}"
        links = [f'<a href="{top}" class="dd-all"{cur if here == top else ""}>{all_label}</a>']
        links += [f'<a href="{p}"{cur if here == p else ""}>{n}</a>' for n, p in items]
        out.append(
            f'<div class="dd"><div class="dd-top"><a href="{top}">{label}</a>'
            f'<button type="button" class="dd-btn" aria-expanded="false" aria-controls="{pid}" '
            f'aria-label="Show {label.lower()} pages">{CHEVRON}</button></div>'
            f'<div class="dd-panel" id="{pid}">' + "".join(links) + "</div></div>")
    out.append('<a href="#contact" class="nav-cta">Contact</a>')
    return "\n      " + "\n      ".join(out)


CSS = """<style id="tn-style">
  .primary-nav .dd{position:relative;display:flex;align-items:center}
  .dd-top{display:flex;align-items:center}
  .dd-btn{background:none;border:0;margin-left:-10px;padding:9px 8px 9px 2px;color:#37404a;cursor:pointer;display:flex;align-items:center;border-radius:7px}
  .dd-btn svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2.2;transition:transform .2s}
  .dd-panel{display:none;position:absolute;top:100%;left:0;min-width:270px;background:var(--white);border:1px solid var(--line);border-radius:10px;box-shadow:0 16px 32px rgba(16,20,24,.12);padding:6px;z-index:60}
  .dd:hover .dd-panel,.dd:focus-within .dd-panel,.dd.open .dd-panel{display:block}
  .dd:hover .dd-btn svg,.dd.open .dd-btn svg{transform:rotate(180deg)}
  .primary-nav .dd-panel a{display:block;padding:9px 12px;white-space:nowrap}
  .primary-nav .dd-panel a.dd-all{color:var(--lake);font-weight:600;border-bottom:1px solid var(--mist);border-radius:7px 7px 0 0;margin-bottom:4px}
  .primary-nav .dd-panel a[aria-current]{color:var(--lake);font-weight:600;background:var(--paper)}
  @media(max-width:1080px){
    .primary-nav .dd{display:block;width:100%}
    .dd-top{width:100%;border-bottom:1px solid var(--mist)}
    .primary-nav .dd-top>a{flex:1;border-bottom:0}
    .dd-btn{margin:0;padding:0 28px;align-self:stretch;border-left:1px solid var(--mist);border-radius:0}
    .dd-btn svg{width:18px;height:18px}
    .dd:hover .dd-btn svg{transform:none}
    .dd.open .dd-btn svg{transform:rotate(180deg)}
    .dd .dd-panel,.dd:hover .dd-panel,.dd:focus-within .dd-panel{display:none;position:static;min-width:0;border:0;border-radius:0;box-shadow:none;padding:0;background:var(--paper)}
    .dd.open .dd-panel{display:block}
    .primary-nav .dd-panel a{padding:13px 28px 13px 44px;font-size:14px;white-space:normal;border-bottom:1px solid var(--mist);border-radius:0;margin:0}
  }
</style>"""

JS = """<script id="tn-script">
(function(){var dds=document.querySelectorAll('#pnav .dd');
  function shut(x){dds.forEach(function(d){if(d!==x){d.classList.remove('open');d.querySelector('.dd-btn').setAttribute('aria-expanded','false');}});}
  dds.forEach(function(d){var b=d.querySelector('.dd-btn');
    b.addEventListener('click',function(e){e.preventDefault();var o=!d.classList.contains('open');shut(d);
      d.classList.toggle('open',o);b.setAttribute('aria-expanded',o?'true':'false');});});
  document.addEventListener('click',function(e){if(!e.target.closest('#pnav .dd'))shut(null);});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')shut(null);});})();
</script>"""

NAV_RE = re.compile(r'(<nav class="primary-nav" id="pnav">)(.*?)(\n\s*<div class="nav-group">)', re.S)
OLD_RE = re.compile(r'\n?<style id="tn-style">.*?</style>|\n?<script id="tn-script">.*?</script>', re.S)


def apply(path, here):
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    if not NAV_RE.search(s):
        return False
    s2 = OLD_RE.sub("", s)
    s2 = NAV_RE.sub(lambda m: m.group(1) + nav_links(here) + m.group(3), s2, count=1)
    s2 = s2.replace("</head>", CSS + "\n</head>", 1)
    i = s2.rfind("</body>")
    s2 = s2[:i] + JS + "\n" + s2[i:]
    if s2 != s:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(s2)
        return True
    return False


def main():
    if apply(TEMPLATE, None):
        print("top menu: tools/community-template.html")
    for p in pages():
        rel = "/" + os.path.relpath(os.path.dirname(p), ROOT).replace(os.sep, "/") + "/"
        rel = "/" if rel == "/./" else rel
        if apply(p, rel):
            print("top menu:", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
