#!/usr/bin/env python3
"""One phone bottom menu for every page on the site.

Homes for sale · Neighborhoods · Schools · Home prices · Menu

Each page builder still writes its own <nav class="bottom-nav">; this script
swaps it for the shared one. build_llm_files.py runs it first, so the normal
build order applies it automatically. It can also run on its own:

    python3 tools/bottom_nav.py
"""
import glob
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_neighborhood import SCHOOL_PAGES, HUB, SCHOOLS_HUB  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE = "tel:+18584366585"

ICONS = {
    "homes": '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h5"/><circle cx="16" cy="16" r="3.2"/><path d="m18.4 18.4 2.6 2.6"/></svg>',
    "hoods": '<svg viewBox="0 0 24 24"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>',
    "schools": '<svg viewBox="0 0 24 24"><path d="M2 9l10-5 10 5-10 5L2 9z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/></svg>',
    "prices": '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
    "call": '<svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
}

CSS = """<style id="bn-style">
  @media(max-width:760px){
    .bottom-nav a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
      gap:2px;padding:5px 1px;color:var(--label,#5b6470);font:600 9.5px/1.1 var(--sans,system-ui);text-align:center;white-space:nowrap}
    .bottom-nav .is-here{color:var(--lake,#0b5c8c)}
  }
</style>"""

# the Menu panel closes when the visitor taps anywhere outside it, or follows a link in it
JS = """<script id="bn-script">
(function(){var n=document.getElementById('pnav');if(!n)return;
  function shut(){n.classList.remove('open');}
  document.addEventListener('click',function(e){if(!n.classList.contains('open'))return;
    if(e.target.closest('.bn-menu'))return;if(n.contains(e.target)&&!e.target.closest('a'))return;shut();},true);
  document.addEventListener('keydown',function(e){if(e.key==='Escape')shut();});})();
</script>"""


def nav(page_path, has_embed, prices):
    here_hub = page_path == HUB
    here_school = page_path == SCHOOLS_HUB or page_path in SCHOOL_PAGES.values()
    # the listings search opens full screen: on this page if it has one, otherwise from the home page
    homes = "#expand-map" if has_embed else "/#expand-map"
    here = ' class="is-here" aria-current="page"'
    return f"""<nav class="bottom-nav" aria-label="Site menu">
  <a href="{homes}">{ICONS["homes"]}Homes for sale</a>
  <a href="{HUB}"{here if here_hub else ''}>{ICONS["hoods"]}Neighborhoods</a>
  <a href="{SCHOOLS_HUB}"{here if here_school else ''}>{ICONS["schools"]}Schools</a>
  <a href="{prices}">{ICONS["prices"]}Home prices</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')">{ICONS["menu"]}Menu</a>
</nav>"""


NAV_RE = re.compile(r'<nav class="bottom-nav".*?</nav>', re.S)
OLD_RE = re.compile(r'\n?<style id="bn-style">.*?</style>|\n?<script id="bn-script">.*?</script>', re.S)


def pages():
    out = []
    for f in [os.path.join(ROOT, "index.html")] + sorted(glob.glob(os.path.join(ROOT, "*", "index.html"))):
        rel = os.path.relpath(f, ROOT)
        if rel.split(os.sep)[0] in ("tools", "assets", "images", "node_modules"):
            continue
        out.append(f)
    return out


def apply(path):
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    if not NAV_RE.search(s):
        return False
    rel = "/" + os.path.relpath(os.path.dirname(path), ROOT).replace(os.sep, "/") + "/"
    rel = "/" if rel == "/./" else rel
    s2 = OLD_RE.sub("", s)
    # Home prices: this page's prices section, or the site-wide one on the home page
    prices = "#prices" if 'id="prices"' in s2 else "#sold-data" if 'id="sold-data"' in s2 else "/#prices"
    s2 = NAV_RE.sub(lambda m: nav(rel, 'class="rs-embed' in s2, prices), s2, count=1)
    s2 = s2.replace("</head>", CSS + "\n</head>", 1)
    i = s2.rfind("</body>")
    s2 = s2[:i] + JS + "\n" + s2[i:]
    if s2 != s:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(s2)
        return True
    return False


def main():
    for p in pages():
        if apply(p):
            print("bottom menu:", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
