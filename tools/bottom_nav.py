#!/usr/bin/env python3
"""One phone bottom menu for every page on the site.

Homes for sale · Neighborhoods · Schools · Call · Menu

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
from make_neighborhood import SCHOOL_PAGES, AREA_PAGES, HUB  # noqa: E402
from sold_data import AREA_LABELS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE = "tel:+18584366585"
# area order for the Schools list (west to east, roughly)
AREA_ORDER = ["n", "s", "th", "cch", "dmm", "tdm", "phr"]

ICONS = {
    "homes": '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h5"/><circle cx="16" cy="16" r="3.2"/><path d="m18.4 18.4 2.6 2.6"/></svg>',
    "hoods": '<svg viewBox="0 0 24 24"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>',
    "schools": '<svg viewBox="0 0 24 24"><path d="M2 9l10-5 10 5-10 5L2 9z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/></svg>',
    "call": '<svg viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
}

CSS = """<style id="bn-style">
  @media(max-width:760px){
    .bottom-nav a,.bottom-nav button.bn-btn{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
      gap:2px;padding:5px 1px;color:#8b909a;font:600 9.5px/1.1 var(--sans,system-ui);text-align:center;white-space:nowrap;
      background:none;border:0;cursor:pointer}
    .bottom-nav button.bn-btn svg{width:19px;height:19px;stroke:currentColor;fill:none;stroke-width:1.8}
    .bottom-nav .is-here,.bottom-nav button.bn-btn[aria-expanded="true"]{color:var(--lake,#0b5c8c)}
    .bn-sheet{position:fixed;top:0;left:0;right:0;bottom:calc(55px + env(safe-area-inset-bottom));z-index:69;background:rgba(16,20,24,.35)}
    .bn-sheet[hidden]{display:none}
    .bn-panel{position:absolute;left:0;right:0;bottom:0;background:#fff;border-radius:16px 16px 0 0;
      padding:16px 16px 14px;box-shadow:0 -4px 18px rgba(0,0,0,.18);max-height:80vh;overflow-y:auto}
    .bn-panel h2{font-size:17px;font-weight:800;margin:0 0 10px;display:flex;justify-content:space-between;align-items:center}
    .bn-panel h2 button{border:0;background:none;font-size:22px;line-height:1;color:#8b909a;cursor:pointer;padding:2px 6px}
    .bn-panel .bn-lbl{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8b909a;margin:14px 0 4px}
    .bottom-nav .bn-panel a{display:block;flex:none;text-align:left;white-space:normal;padding:11px 2px;border-top:1px solid #e6e8eb;
      font:600 15px/1.3 var(--sans,system-ui);color:#101418}
    .bottom-nav .bn-panel a span{display:block;font-size:12.5px;font-weight:500;color:#6b7280;margin-top:1px}
  }
</style>"""

JS = """<script id="bn-script">
(function(){
  var b=document.getElementById('bnSchoolsBtn'),s=document.getElementById('bnSchools');if(!b||!s)return;
  var n=b.closest('.bottom-nav');
  // while the list is open, lift the menu above page maps and panels
  function set(o){s.hidden=!o;b.setAttribute('aria-expanded',o?'true':'false');n.style.zIndex=o?'1200':'';}
  b.addEventListener('click',function(){set(s.hidden);});
  s.addEventListener('click',function(e){if(e.target===s||e.target.closest('[data-x]')||e.target.closest('a'))set(false);});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')set(false);});
})();
</script>"""


def nav(page_path, has_embed):
    e = html.escape
    here_hub = page_path == HUB
    here_school = page_path in SCHOOL_PAGES.values()
    # the listings search opens full screen: on this page if it has one, otherwise from the home page
    homes = "#expand-map" if has_embed else "/#expand-map"
    school_links = "".join(
        f'<a href="{u}">{e(n)}<span>Homes in its attendance area</span></a>' for n, u in SCHOOL_PAGES.items())
    area_links = "".join(
        f'<a href="{AREA_PAGES[k]}#schools">{e(AREA_LABELS[k])}</a>' for k in AREA_ORDER if k in AREA_PAGES)
    return f"""<nav class="bottom-nav" aria-label="Site menu">
  <a href="{homes}">{ICONS["homes"]}Homes for sale</a>
  <a href="{HUB}"{' class="is-here" aria-current="page"' if here_hub else ''}>{ICONS["hoods"]}Neighborhoods</a>
  <button type="button" class="bn-btn{' is-here' if here_school else ''}" id="bnSchoolsBtn" aria-controls="bnSchools" aria-expanded="false">{ICONS["schools"]}Schools</button>
  <a href="{PHONE}">{ICONS["call"]}Call</a>
  <a href="#" class="bn-menu" onclick="event.preventDefault();window.__showMasthead&&window.__showMasthead();document.getElementById('pnav').classList.toggle('open')">{ICONS["menu"]}Menu</a>
  <div class="bn-sheet" id="bnSchools" hidden>
    <div class="bn-panel" role="dialog" aria-label="Carmel Valley schools">
      <h2>Carmel Valley Schools <button type="button" data-x aria-label="Close">&times;</button></h2>
      <div class="bn-lbl">School pages</div>
      {school_links}
      <div class="bn-lbl">Assigned schools by area</div>
      {area_links}
    </div>
  </div>
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
    s2 = NAV_RE.sub(lambda m: nav(rel, 'class="rs-embed' in s2), s2, count=1)
    s2 = s2.replace("</head>", CSS + "\n</head>", 1).replace("</body>", JS + "\n</body>", 1)
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
