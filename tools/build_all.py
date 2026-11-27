#!/usr/bin/env python3
"""Rebuild the whole site in the right order. Run it on a release day so pages whose
"publish_on" date has arrived go live and get linked everywhere (see tools/publish.py):

    python3 tools/build_all.py
    python3 tools/publish.py        # check what is live and what is still a draft

Then review and push; nothing is public until the push.
"""
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ORDER = ["build_communities", "build_communities_hub", "build_school", "build_schools_hub", "build_area",
         "build_luxury", "build_home", "build_llm_files"]  # llm files last: menus, .md copies, sitemap

for step in ORDER:
    print(f"== {step}")
    r = subprocess.run([sys.executable, os.path.join(TOOLS, step + ".py")], cwd=os.path.dirname(TOOLS))
    if r.returncode:
        sys.exit(f"{step} failed")
