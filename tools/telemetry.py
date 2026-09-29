"""Render the contribution telemetry figure from the live contribution calendar.

    GITHUB_TOKEN=... python tools/telemetry.py --user slazyverse --out dist

Standard library only, so the workflow needs no install step. Writes
contribution-telemetry-dark.svg and contribution-telemetry-light.svg.

Every number in the figure is read from GitHub's contribution calendar at build
time; nothing is estimated, smoothed into a claim, or carried over by hand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svgkit import (  # noqa: E402
    PALETTES,
    GlyphTable,
    Typesetter,
    corner_brackets,
    document,
    fmt,
    glow_filter,
    keyframes,
    write,
)

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-telemetry"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def stats(days):
    active = [d for d in days if d["contributionCount"] > 0]
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    busiest = max(days, key=lambda d: d["contributionCount"]) if days else None
    return len(active), longest, busiest


def render(cal: dict, p: dict, mono: GlyphTable, bold: GlyphTable, today: str) -> str:
    W, H = 1000, 292
    ts = Typesetter()
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    n_weeks = len(weeks)
    cell, gap = 11, 4
    step = cell + gap
    gx0 = (W - (n_weeks * step - gap)) / 2
    gy0 = 72
    grid_w = n_weeks * step - gap
    scan_t0, scan_t1, T = 0.8, 7.8, 10.0
    css, marks, dots = [], [], []

    def hit_time(x):
        return scan_t0 + (scan_t1 - scan_t0) * (x - gx0) / grid_w

    ramp = {1: (p["blue"], 0.55), 2: (p["cyan"], 0.6), 3: (p["cyan"], 0.85), 4: (p["cyan_soft"], 1.0)}
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = dt.date.fromisoformat(d["date"]).isoweekday() % 7  # Sunday = 0
            x, y = gx0 + wi * step, gy0 + wd * step
            lvl = LEVEL.get(d["contributionLevel"], 0)
            if lvl == 0:
                dots.append(f"M{fmt(x + cell / 2 - .6)} {fmt(y + cell / 2)}h1.2")
            else:
                col, op = ramp[lvl]
                marks.append(
                    f'<rect class="k{lvl}" x="{fmt(x)}" y="{fmt(y)}" width="{cell}" height="{cell}" rx="2" fill="{col}"'
                    f' style="animation-delay:{hit_time(x + cell / 2):.2f}s"/>'
                )
    for lvl, (_, op) in ramp.items():
        # Each lit cell flares as the scan crosses it, then settles.
        css.append(
            f".k{lvl}{{opacity:{op};transform-box:fill-box;transform-origin:center;"
            f"animation:k{lvl} {T}s ease-out infinite backwards}}"
            + keyframes(f"k{lvl}", [(0, f"opacity:{op * .45:.2f};transform:scale(1)"), (2, "opacity:1;transform:scale(1.35)"),
                                    (12, f"opacity:{op};transform:scale(1)"), (100, f"opacity:{op * .45:.2f};transform:scale(1)")])
        )

    # Month labels where a new month starts.
    months, last = [], None
    for wi, w in enumerate(weeks):
        first = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        m = first.strftime("%b").upper()
        if m != last and wi < n_weeks - 2:
            if wi > 0 or first.day <= 7:
                lab, _ = ts.text(mono, m, gx0 + wi * step, gy0 - 12, 10, p["ink_low"], tracking=0.1)
                months.append(lab)
            last = m

    # The scan beam.
    grid_h = 7 * step - gap
    beam = (
        f'<g class="bm"><rect x="-70" y="{gy0 - 4}" width="70" height="{grid_h + 8}" fill="url(#bg)"/>'
        f'<rect x="-1" y="{gy0 - 6}" width="1.5" height="{grid_h + 12}" fill="{p["cyan"]}"/></g>'
    )
    css.append(
        ".bm{animation:bm %ss linear infinite}" % T
        + keyframes("bm", [(0, f"transform:translateX({fmt(gx0)}px);opacity:0"), (100 * (scan_t0 - .3) / T, f"transform:translateX({fmt(gx0)}px);opacity:0"),
                           (100 * scan_t0 / T, f"transform:translateX({fmt(gx0)}px);opacity:1"), (100 * scan_t1 / T, f"transform:translateX({fmt(gx0 + grid_w)}px);opacity:1"),
                           (100 * (scan_t1 + .4) / T, f"transform:translateX({fmt(gx0 + grid_w)}px);opacity:0"), (100, f"transform:translateX({fmt(gx0 + grid_w)}px);opacity:0")])
    )

    # Weekly totals as a trace under the grid, with a point riding it in step
    # with the beam.
    totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    peak = max(max(totals), 1)
    ty0, th = gy0 + grid_h + 58, 36
    pts = [(gx0 + i * step + cell / 2, ty0 - th * (t / peak)) for i, t in enumerate(totals)]
    trace = "M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y in pts)
    area = trace + f" L{fmt(pts[-1][0])} {ty0} L{fmt(pts[0][0])} {ty0}Z"
    ride = [(0, f"transform:translate({fmt(pts[0][0])}px,{fmt(pts[0][1])}px);opacity:0")]
    for x, y in pts:
        ride.append((100 * hit_time(x) / T, f"transform:translate({fmt(x)}px,{fmt(y)}px);opacity:1"))
    ride.append((100 * (scan_t1 + .4) / T, f"transform:translate({fmt(pts[-1][0])}px,{fmt(pts[-1][1])}px);opacity:0"))
    ride.append((100, f"transform:translate({fmt(pts[-1][0])}px,{fmt(pts[-1][1])}px);opacity:0"))
    css.append(".rd{animation:rd %ss linear infinite}" % T + keyframes("rd", ride))
    glow = ' filter="url(#gl)"' if p["glow"] else ""
    rider = f'<g class="rd"><circle r="3" fill="{p["cyan_soft"]}"{glow}/></g>'

    active, longest, busiest = stats(days)
    head_l, _ = ts.text(bold, "CONTRIBUTION SIGNAL", 36, 38, 11, p["ink_mid"], tracking=0.22)
    head_r, _ = ts.text(mono, f"{cal['totalContributions']} contributions · last 12 months", W - 36, 38, 11, p["ink_low"], anchor="end", tracking=0.04)
    parts = [
        ("ACTIVE DAYS", str(active)),
        ("LONGEST STREAK", f"{longest} d"),
        ("BUSIEST DAY", f"{busiest['contributionCount']}" if busiest else "0"),
        ("UPDATED", today),
    ]
    x = 36
    foot = []
    for label, value in parts:
        lab, lw = ts.text(mono, label, x, H - 30, 10.5, p["ink_low"], tracking=0.14)
        val, vw = ts.text(bold, value, x + lw + 8, H - 30, 10.5, p["ink_hi"], tracking=0.04)
        foot += [lab, val]
        x += lw + 8 + vw + 28
    wk, _ = ts.text(mono, "WEEKLY", gx0 - 12, ty0 - 2, 10, p["ink_low"], anchor="end", tracking=0.1)

    defs = (
        '<linearGradient id="bg" x1="0" x2="1"><stop offset="0" stop-color="{c}" stop-opacity="0"/>'
        '<stop offset="1" stop-color="{c}" stop-opacity=".16"/></linearGradient>'
        '<linearGradient id="ag" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{c}" stop-opacity=".18"/>'
        '<stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>'
    ).format(c=p["cyan"]) + (glow_filter("gl", 2) if p["glow"] else "")
    body = (
        corner_brackets(12, 12, W - 24, H - 24, p["hair"], p["hair_a"] * 2.2)
        + head_l + head_r + "".join(months)
        + f'<path d="{"".join(dots)}" stroke="{p["ink_low"]}" stroke-opacity=".5" stroke-width="1.2"/>'
        + "".join(marks)
        + beam
        + f'<line x1="{fmt(gx0)}" y1="{ty0}" x2="{fmt(gx0 + grid_w)}" y2="{ty0}" stroke="{p["hair"]}" stroke-opacity="{fmt(p["hair_a"])}"/>'
        + f'<path d="{area}" fill="url(#ag)"/>'
        + f'<path d="{trace}" fill="none" stroke="{p["cyan"]}" stroke-opacity=".7" stroke-width="1.2" stroke-linejoin="round"/>'
        + rider + wk
        + "".join(foot)
    )
    title = f"{cal['totalContributions']} contributions in the last 12 months"
    return document(W, H, body, title=title, css="".join(css), defs=ts.defs() + defs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--calendar", help="read a saved calendar JSON instead of calling the API")
    args = ap.parse_args()

    if args.calendar:
        with open(args.calendar, encoding="utf-8") as fh:
            raw = json.load(fh)
        cal = raw.get("data", {}).get("user", {}).get("contributionsCollection", {}).get("contributionCalendar", raw)
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is required")
        cal = fetch(args.user, token)

    mono = GlyphTable.load("jetbrains-mono-500")
    bold = GlyphTable.load("jetbrains-mono-700")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    for mode, pal in PALETTES.items():
        write(os.path.join(args.out, f"contribution-telemetry-{mode}.svg"), render(cal, pal, mono, bold, today))
    print(f"{cal['totalContributions']} contributions rendered to {args.out}")


if __name__ == "__main__":
    main()
