"""Fail if the README points at anything that does not exist.

    python tools/check_readme.py            # assets + external links
    python tools/check_readme.py --offline  # assets only

Standard library only. Checks, in order:

* every asset the README references on `main` exists in this checkout, and
  every SVG under assets/ parses and declares an intrinsic width and height
  (GitHub sizes an <img> from those, so a missing one renders at 300×150);
* no <picture> sits inside a link — GitHub's renderer splits that open;
* every external link and image answers with a success status.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_MAIN = "https://raw.githubusercontent.com/slazyverse/slazyverse/main/"

# LinkedIn answers every unauthenticated client with HTTP 999; a failure there
# says nothing about the link, so it is checked for shape only.
BOT_WALLED = ("linkedin.com",)


def urls(readme: str) -> set[str]:
    found = set(re.findall(r'(?:href|src)="([^"]+)"', readme))
    for srcset in re.findall(r'srcset="([^"]+)"', readme):
        found.update(part.strip().split(" ")[0] for part in srcset.split(", "))
    found.update(re.findall(r"\]\((https?://[^)\s]+)\)", readme))
    return {u.replace("&amp;", "&") for u in found}


def check_assets(refs: set[str]) -> list[str]:
    errors = []
    for u in sorted(refs):
        if u.startswith(RAW_MAIN):
            path = os.path.join(ROOT, u[len(RAW_MAIN):])
            if not os.path.isfile(path):
                errors.append(f"missing asset: {u}")
    for folder, _, files in os.walk(os.path.join(ROOT, "assets")):
        for name in files:
            if not name.endswith(".svg"):
                continue
            path = os.path.join(folder, name)
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError as exc:
                errors.append(f"malformed SVG {path}: {exc}")
                continue
            if not (root.get("width") and root.get("height")):
                errors.append(f"SVG without intrinsic size: {path}")
    return errors


def check_structure(readme: str) -> list[str]:
    if re.search(r"<a\b[^>]*>\s*<picture>", readme):
        return ["a <picture> is wrapped in a link; GitHub will break both"]
    return []


def status(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (readme-check)", "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def check_links(refs: set[str]) -> list[str]:
    errors = []
    for u in sorted(refs):
        if not u.startswith("http") or u.startswith(RAW_MAIN):
            continue
        if any(host in u for host in BOT_WALLED):
            continue
        code = status(u.split("#")[0])
        mark = "ok " if code < 400 else "ERR"
        print(f"  {mark} {code} {u}")
        if code >= 400:
            errors.append(f"{code} {u}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    refs = urls(readme)
    errors = check_assets(refs) + check_structure(readme)
    if not args.offline:
        errors += check_links(refs)
    for e in errors:
        print(f"::error::{e}")
    print(f"{len(refs)} references checked, {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
