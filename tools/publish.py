#!/usr/bin/env python3
"""Hold finished community pages back and release them on a schedule.

Each tools/communities/<slug>.json may carry "publish_on": "YYYY-MM-DD".
Until that date the page is a draft:
  - build_communities.py writes it to _drafts/<path>/index.html (never deployed:
    _drafts/ is in .assetsignore) with a noindex tag, for previewing;
  - it is left out of NEIGHBORHOOD_PAGES, so no menu item, hub/area/school link,
    nearby card, llms entry or sitemap URL points to it.
On or after the date, the next full build (tools/build_all.py) publishes it at its
real URL and links it everywhere. Nothing goes live until that build is pushed.

    python3 tools/publish.py                          # show the schedule
    python3 tools/publish.py plan a b c --start 2026-11-30 --every 2,3
                                                      # give pages publish dates
Stdlib only.
"""
import datetime
import glob
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
DRAFTS = os.path.join(ROOT, "_drafts")


def communities():
    out = []
    for f in sorted(glob.glob(os.path.join(TOOLS, "communities", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            c = json.load(fh)
        c["_file"] = f
        out.append(c)
    return out


def is_live(c, today=None):
    d = c.get("publish_on")
    return not d or datetime.date.fromisoformat(d) <= (today or datetime.date.today())


def live_pages():
    """name -> path for community pages that are published (or due today)."""
    return {c["name"]: c["path"] for c in communities() if is_live(c)}


def show():
    today = datetime.date.today()
    rows = sorted(communities(), key=lambda c: c.get("publish_on") or "")
    for c in rows:
        state = "live" if is_live(c, today) else "draft"
        print(f'{c.get("publish_on") or "—":<11} {state:<6} {c["path"]}')


def plan(slugs, start, every):
    d = datetime.date.fromisoformat(start)
    steps = [int(x) for x in every.split(",")]
    for i, s in enumerate(slugs):
        f = os.path.join(TOOLS, "communities", s + ".json")
        with open(f, encoding="utf-8") as fh:
            c = json.load(fh)
        c["publish_on"] = d.isoformat()
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(c, fh, indent=1, ensure_ascii=False)
        print(f"{s}: {d.isoformat()}")
        d += datetime.timedelta(days=steps[i % len(steps)])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "plan":
        start = a[a.index("--start") + 1]
        every = a[a.index("--every") + 1] if "--every" in a else "2,3"
        slugs = [x for x in a[1:] if not x.startswith("--") and x not in (start, every)]
        plan(slugs, start, every)
    else:
        show()
