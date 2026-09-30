"""Build every static SVG in assets/ from one set of tokens.

    pip install fonttools uharfbuzz
    python tools/build_assets.py

Each asset is emitted twice — `-dark.svg` and `-light.svg` — and the README
picks one per viewer with <picture> and prefers-color-scheme, which GitHub maps
to the viewer's GitHub theme. The contribution telemetry is not built here; it
is rebuilt every six hours by .github/workflows/telemetry.yml (see tools/telemetry.py).
"""

from __future__ import annotations

import math
import os
import random

import fonts
from svgkit import (
    HERE,
    PALETTES,
    Typesetter,
    corner_brackets,
    document,
    ellipse_arclength_samples,
    fmt,
    glow_filter,
    keyframes,
    write,
)

ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")

DISPLAY = fonts.display(weight=800, width=118)
MONO = fonts.mono(weight=500)
MONO_BOLD = fonts.mono(weight=700)


def emit(folder: str, stem: str, build) -> None:
    for mode, pal in PALETTES.items():
        write(os.path.join(ASSETS, folder, f"{stem}-{mode}.svg"), build(pal))


def hair(p, alpha=None, width=1):
    a = p["hair_a"] if alpha is None else alpha
    return f'stroke="{p["hair"]}" stroke-opacity="{fmt(a)}" stroke-width="{fmt(width)}"'


# ==========================================================================
# HERO — the name, and the signal rail beneath it
#
# The name is the only large thing on the page and nothing moves across it.
# Motion lives on the rail below: one packet, one pulse.
# ==========================================================================


def hero(p) -> str:
    W, H = 1000, 212
    ts = Typesetter()
    name = DISPLAY.shape("SAGAR TAILOR")
    tracking = 0.035
    size = 100 * 900 / ts.measure(DISPLAY, name, 100, tracking)
    cap = size * DISPLAY.cap_height / DISPLAY.upm
    top = 26
    base = top + cap
    rail = base + 38
    x0, x1 = 50, 950

    name_fill = "url(#nameInk)" if p["glow"] else p["ink_hi"]
    name_svg, _ = ts.run(DISPLAY, name, W / 2, base, size, name_fill, anchor="middle", tracking=tracking)

    lab = 11.5
    left, _ = ts.text(MONO, "00 — SURFACE", x0, rail + 27, lab, p["ink_low"], tracking=0.14)
    right, _ = ts.text(MONO, "@SLAZYVERSE", x1, rail + 27, lab, p["ink_low"], anchor="end", tracking=0.14)

    ticks = []
    for i, x in enumerate(range(x0 + 25, x1, 25)):
        h = 5 if i % 4 == 3 else 2.5
        ticks.append(f"M{x} {fmt(rail - h)}V{fmt(rail)}")
    tick_path = f'<path d="{"".join(ticks)}" fill="none" {hair(p, p["hair_a"] * 0.9)}/>'

    L = 110
    travel = x1 - x0 - L
    css = (
        ".pk{animation:pk 7s cubic-bezier(.65,0,.35,1) infinite}"
        + keyframes(
            "pk",
            [
                (0, "transform:translateX(0);opacity:0"),
                (6, "opacity:1"),
                (70, "opacity:1"),
                (78, f"transform:translateX({travel}px);opacity:0"),
                (100, f"transform:translateX({travel}px);opacity:0"),
            ],
        )
        + ".pl{animation:pl 7s ease-out infinite;transform-box:fill-box;transform-origin:center}"
        + keyframes(
            "pl",
            [
                (0, "transform:scale(1);opacity:.7"),
                (22, "transform:scale(4.2);opacity:0"),
                (100, "transform:scale(4.2);opacity:0"),
            ],
        )
    )

    defs = ts.defs() + (
        '<linearGradient id="pkg" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity="0"/>'
        f'<stop offset=".8" stop-color="{p["cyan"]}" stop-opacity=".9"/>'
        f'<stop offset="1" stop-color="{p["cyan_soft"]}"/></linearGradient>'
    )
    glow = ""
    if p["glow"]:
        defs += (
            '<linearGradient id="nameInk" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c4d0e0"/>'
            "</linearGradient>"
            '<radialGradient id="halo" cx=".5" cy=".5" r=".5">'
            f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity=".13"/>'
            f'<stop offset=".55" stop-color="{p["blue"]}" stop-opacity=".05"/>'
            f'<stop offset="1" stop-color="{p["blue"]}" stop-opacity="0"/></radialGradient>'
            + glow_filter("bloom", 2.2)
        )
        glow = f'<ellipse cx="{W/2}" cy="{fmt(top + cap/2)}" rx="470" ry="{fmt(cap*1.35)}" fill="url(#halo)"/>'

    bloom = ' filter="url(#bloom)"' if p["glow"] else ""
    body = (
        glow
        + name_svg
        + f'<line x1="{x0}" y1="{fmt(rail)}" x2="{x1}" y2="{fmt(rail)}" {hair(p)}/>'
        + tick_path
        + f'<g class="pk"><rect x="{x0}" y="{fmt(rail - 1)}" width="{L}" height="2" fill="url(#pkg)"{bloom}/></g>'
        + f'<circle class="pl" cx="{x0}" cy="{fmt(rail)}" r="3" fill="none" stroke="{p["cyan"]}" stroke-width="1"/>'
        + f'<circle cx="{x0}" cy="{fmt(rail)}" r="3" fill="{p["cyan"]}"/>'
        + f'<path d="M{x1} {fmt(rail - 3.5)}l3.5 3.5l-3.5 3.5l-3.5 -3.5z" fill="{p["ink_low"]}"/>'
        + left
        + right
    )
    return document(W, H, body, title="Sagar Tailor", css=css, defs=defs)


# ==========================================================================
# HEADLINE — a terminal line that types, holds, and deletes
#
# Every glyph owns a keyframe track for its own visibility. That is more CSS
# than a clip-path wipe, but it is the version that behaves the same in every
# browser, and with reduced motion the first phrase simply stands.
# ==========================================================================

PHRASES = [
    "builds the layer underneath",
    "concurrency · real-time state · async apis",
    "satellite data → pipelines → platforms",
    "observe → model → engineer → validate",
]


def headline(p) -> str:
    W, H = 640, 44
    size = 17
    adv = MONO.shape("a")[0][1] * size / MONO.upm
    ts = Typesetter()

    type_dt, del_dt, hold, gap = 0.075, 0.03, 2.4, 0.45
    spans, t = [], 0.6
    for ph in PHRASES:
        n = len(ph)
        t_typed = t + n * type_dt
        t_del = t_typed + hold
        t_gone = t_del + n * del_dt
        spans.append((t, t_typed, t_del, t_gone))
        t = t_gone + gap
    T = t

    prompt, pw = ts.text(MONO_BOLD, "›", 0, 0, size, p["cyan"])
    widest = max(len(ph) for ph in PHRASES) * adv
    x_start = (W - (pw + 12 + widest)) / 2
    tx = x_start + pw + 12
    base = H / 2 + size * 0.36
    prompt, _ = ts.text(MONO_BOLD, "›", x_start, base, size, p["cyan"])

    pct = lambda s: 100 * s / T  # noqa: E731
    css, runs = [], []
    for pi, (ph, (t0, t1, t2, t3)) in enumerate(zip(PHRASES, spans)):
        n = len(ph)
        for i in range(n):
            on = t0 + (i + 1) * type_dt
            off = t2 + (n - i) * del_dt
            name = f"p{pi}c{i}"
            css.append(
                f".{name}{{opacity:{1 if pi == 0 else 0};animation:{name} {T:.2f}s step-end infinite}}"
                + keyframes(name, [(0, "opacity:0"), (pct(on), "opacity:1"), (pct(off), "opacity:0"), (100, "opacity:0")])
            )
        run, _ = ts.text(MONO, ph, tx, base, size, p["ink"] if pi else p["ink_hi"], glyph_cls=lambda i, pi=pi: f"p{pi}c{i}")
        runs.append(run)

    # The cursor rides the end of whatever has been typed so far.
    stops = [(0, "transform:translateX(0)")]
    for ph, (t0, t1, t2, t3) in zip(PHRASES, spans):
        n = len(ph)
        for i in range(n):
            stops.append((pct(t0 + (i + 1) * type_dt), f"transform:translateX({fmt((i + 1) * adv)}px)"))
        for i in range(n):
            stops.append((pct(t2 + (i + 1) * del_dt), f"transform:translateX({fmt((n - 1 - i) * adv)}px)"))
    css.append(f".cur{{transform:translateX({fmt(len(PHRASES[0]) * adv)}px);animation:cur {T:.2f}s step-end infinite}}" + keyframes("cur", stops))
    css.append(".blink{animation:blink 1.05s step-end infinite}" + keyframes("blink", [(0, "opacity:1"), (50, "opacity:0")]))

    cursor = (
        f'<g class="cur"><rect class="blink" x="{fmt(tx + 1)}" y="{fmt(base - size * 0.78)}"'
        f' width="{fmt(adv * 0.62)}" height="{fmt(size * 0.98)}" fill="{p["cyan"]}" opacity=".9"/></g>'
    )
    body = prompt + "".join(runs) + cursor
    return document(W, H, body, title="builds the layer underneath", css="".join(css), defs=ts.defs())


# ==========================================================================
# LINK CHIPS — fixed-height, so they stay legible when the page narrows
#
# A chip is a link, and GitHub cannot keep a <picture> inside an <a>: its
# renderer wraps every <img> in a link of its own, the nested anchor is
# invalid, and the parser splits the <picture> open — the theme switch and the
# link both break. So each chip is one plain linked <img> that carries both
# palettes itself, switched by prefers-color-scheme inside the SVG, on a
# ground of its own so it stays legible even where that guess is wrong.
# ==========================================================================


def chip(index: str, label: str, primary: bool) -> str:
    H, size, pad = 36, 12, 16
    ts = Typesetter()
    D, Lt = PALETTES["dark"], PALETTES["light"]
    _, iw = ts.text(MONO, index, 0, 0, size, D["ink_low"])
    lab_w = ts.measure(MONO_BOLD, MONO_BOLD.shape(label), size, 0.16)
    arrow_w = MONO.shape("a")[0][1] * size / MONO.upm
    W = pad + iw + 12 + lab_w + 12 + arrow_w + pad
    base = H / 2 + size * 0.36
    idx, _ = ts.text(MONO, index, pad, base, size, D["ink_low"], cls="ix")
    lab, _ = ts.text(MONO_BOLD, label, pad + iw + 12, base, size, D["ink_hi"], tracking=0.16, cls="lb")
    arr, _ = ts.text(MONO, "↗", W - pad - arrow_w, base, size, D["ink_mid"], cls="ar")

    def theme(pal):
        accent = pal["cyan"] if primary else None
        border = (
            f"stroke:{pal['cyan']};stroke-opacity:.6"
            if primary
            else f"stroke:{pal['hair']};stroke-opacity:{fmt(pal['hair_a'] * 1.6)}"
        )
        return (
            f".bg{{fill:{pal['fill']};{border}}}"
            f".ix{{fill:{accent or pal['ink_low']}}}.lb{{fill:{pal['ink_hi']}}}"
            f".ar{{fill:{accent or pal['ink_mid']}}}.sc{{stop-color:{pal['cyan']}}}"
        )

    css = theme(D) + "@media (prefers-color-scheme: light){" + theme(Lt) + "}"
    sweep, defs = "", ts.defs()
    if primary:
        css += ".sw{animation:sw 5.5s cubic-bezier(.65,0,.35,1) infinite}" + keyframes(
            "sw",
            [(0, "transform:translateX(-40px);opacity:0"), (8, "opacity:1"),
             (40, f"transform:translateX({fmt(W)}px);opacity:0"), (100, f"transform:translateX({fmt(W)}px);opacity:0")],
        )
        sweep = f'<g class="sw"><rect x="0" y="{H - 1.5}" width="40" height="1.5" fill="url(#sg)"/></g>'
        defs += (
            '<linearGradient id="sg" x1="0" x2="1"><stop class="sc" offset="0" stop-opacity="0"/>'
            '<stop class="sc" offset="1"/></linearGradient>'
        )
    body = f'<rect class="bg" x=".5" y=".5" width="{fmt(W - 1)}" height="{H - 1}" rx="2"/>' + idx + lab + arr + sweep
    return document(W, H, body, title=label.title(), css=css, defs=defs)


# ==========================================================================
# DIVIDERS
#
# Two families on one baseline. A stratum divider opens each of the four
# chapters and carries the depth gauge — the README descends the same four
# layers the portfolio does. A section divider separates sections inside a
# chapter: textless, one motif each, never taller than 24 units.
# ==========================================================================

STRATA = [
    ("00", "SURFACE", "what software looks like from outside"),
    ("01", "INTERFACE", "where behaviour becomes visible"),
    ("02", "ENGINE", "where the work is actually done"),
    ("03", "SUBSTRATE", "bedrock. facts, no ornament"),
]


def packet_gradient(p, gid="pg"):
    return (
        f'<linearGradient id="{gid}" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity="0"/>'
        f'<stop offset=".85" stop-color="{p["cyan"]}" stop-opacity=".95"/>'
        f'<stop offset="1" stop-color="{p["cyan_soft"]}"/></linearGradient>'
    )


def faded_line_gradient(p, W, gid="fl", edge=0.14):
    a = fmt(p["hair_a"])
    return (
        f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" x2="{W}" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{p["hair"]}" stop-opacity="0"/>'
        f'<stop offset="{edge}" stop-color="{p["hair"]}" stop-opacity="{a}"/>'
        f'<stop offset="{1 - edge}" stop-color="{p["hair"]}" stop-opacity="{a}"/>'
        f'<stop offset="1" stop-color="{p["hair"]}" stop-opacity="0"/></linearGradient>'
    )


def travel_css(cls, dist, dur, start=0.0, delay=0.0, fade=True):
    stops = [(0, f"transform:translateX({fmt(start)}px);opacity:0")]
    if fade:
        stops += [(8, "opacity:1"), (62, "opacity:1")]
    stops += [
        (70, f"transform:translateX({fmt(start + dist)}px);opacity:0"),
        (100, f"transform:translateX({fmt(start + dist)}px);opacity:0"),
    ]
    d = f" {delay}s" if delay else ""
    return f".{cls}{{animation:{cls} {dur}s cubic-bezier(.65,0,.35,1){d} infinite}}" + keyframes(cls, stops)


def stratum(depth: int):
    index, name, gloss = STRATA[depth]

    def build(p) -> str:
        W, H = 1000, 40
        y = 20
        ts = Typesetter()
        size = 11.5
        idx, iw = ts.text(MONO_BOLD, index, 0, y + 4, size, p["cyan"], tracking=0.1)
        lab, lw = ts.text(MONO_BOLD, name, iw + 12, y + 4, size, p["ink_hi"], tracking=0.22)
        gl, gw = ts.text(MONO, gloss, iw + 12 + lw + 18, y + 4, size, p["ink_low"], tracking=0.02)
        x_line0 = iw + 12 + lw + 18 + gw + 20
        gauge_w = 4 * 9 + 3 * 5
        x_line1 = W - gauge_w - 20

        cells = []
        for i in range(4):
            gx = W - gauge_w + i * 14
            if i < depth:
                cells.append(f'<rect x="{gx}" y="{y - 4.5}" width="9" height="9" rx="1" fill="{p["cyan"]}" opacity=".45"/>')
            elif i == depth:
                cells.append(f'<rect class="now" x="{gx}" y="{y - 4.5}" width="9" height="9" rx="1" fill="{p["cyan"]}"/>')
            else:
                cells.append(
                    f'<rect x="{gx + .5}" y="{y - 4}" width="8" height="8" rx="1" fill="none" {hair(p, p["hair_a"] * 1.8)}/>'
                )
        L = 90
        css = travel_css("pk", x_line1 - x_line0 - L, 6.5) + ".now{animation:now 2.4s ease-in-out infinite}" + keyframes(
            "now", [(0, "opacity:1"), (50, "opacity:.35"), (100, "opacity:1")]
        )
        bloom = ' filter="url(#bl)"' if p["glow"] else ""
        defs = ts.defs() + packet_gradient(p) + (glow_filter("bl", 1.6) if p["glow"] else "")
        body = (
            idx + lab + gl
            + f'<line x1="{fmt(x_line0)}" y1="{y}" x2="{fmt(x_line1)}" y2="{y}" {hair(p)}/>'
            + f'<g class="pk"><rect x="{fmt(x_line0)}" y="{y - 1}" width="{L}" height="2" fill="url(#pg)"{bloom}/></g>'
            + "".join(cells)
        )
        return document(W, H, body, title=f"{index} {name.title()} — {gloss}", css=css, defs=defs)

    return build


def divider_signal(p) -> str:
    W, H, y = 1000, 24, 12
    L = 120
    nodes = [250, 500, 750]
    dur = 6.0
    css = travel_css("pk", W - L - 40, dur, start=20, fade=True)
    # Each node flashes as the packet's head crosses it.
    for i, nx in enumerate(nodes):
        head_at = (nx - 20 - L) / (W - L - 40)  # fraction of the travel
        t = 8 + head_at * (62 - 8) + 4
        css += f".n{i}{{animation:n{i} {dur}s linear infinite}}" + keyframes(
            f"n{i}",
            [(0, "opacity:.35"), (max(t - 2, 0.1), "opacity:.35"), (t, "opacity:1"), (t + 10, "opacity:.35"), (100, "opacity:.35")],
        )
    bloom = ' filter="url(#bl)"' if p["glow"] else ""
    body = f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="url(#fl)" stroke-width="1"/>'
    body += f'<g class="pk"><rect x="0" y="{y - 1}" width="{L}" height="2" fill="url(#pg)"{bloom}/></g>'
    for i, nx in enumerate(nodes):
        body += f'<rect class="n{i}" x="{nx - 3}" y="{y - 3}" width="6" height="6" transform="rotate(45 {nx} {y})" fill="{p["cyan"]}"/>'
    defs = packet_gradient(p) + faded_line_gradient(p, W) + (glow_filter("bl", 1.6) if p["glow"] else "")
    return document(W, H, body, title="divider", css=css, defs=defs)


def divider_wave(p) -> str:
    W, H, y = 1000, 24, 12
    span, period, amp = 300, 30, 5.5
    x0 = (W - span) / 2
    # A path longer than the window by one period, shifted by exactly one
    # period per cycle, so the loop has no seam.
    pts = []
    n = int((span + period) / 2) + 1
    for i in range(n):
        x = x0 - period + i * 2
        pts.append(f"{fmt(x)} {fmt(y + amp * math.sin(2 * math.pi * (x - x0) / period))}")
    wave = "M" + " L".join(pts)
    css = ".wv{animation:wv 1.6s linear infinite}" + keyframes(
        "wv", [(0, "transform:translateX(0)"), (100, f"transform:translateX({period}px)")]
    )
    mask = (
        f'<linearGradient id="env" gradientUnits="userSpaceOnUse" x1="{fmt(x0)}" x2="{fmt(x0 + span)}">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
        f'<rect x="{fmt(x0)}" y="0" width="{span}" height="{H}" fill="url(#env)"/></mask>'
    )
    body = (
        f'<line x1="0" y1="{y}" x2="{fmt(x0 + 8)}" y2="{y}" stroke="url(#fl)"/>'
        f'<line x1="{fmt(x0 + span - 8)}" y1="{y}" x2="{W}" y2="{y}" stroke="url(#fl)"/>'
        f'<g mask="url(#m)"><path class="wv" d="{wave}" fill="none" stroke="{p["cyan"]}" stroke-width="1.4"'
        f' stroke-linejoin="round"/></g>'
    )
    defs = faded_line_gradient(p, W) + mask
    return document(W, H, body, title="divider", css=css, defs=defs)


def divider_scan(p) -> str:
    W, H, y = 1000, 24, 12
    dots = "".join(f"M{x} {y}h1.2" for x in range(40, W - 39, 8))
    L = 160
    css = travel_css("sc", W - L, 7.5, start=0)
    body = (
        f'<path d="{dots}" stroke="{p["ink_low"]}" stroke-opacity=".55" stroke-width="1.2"/>'
        f'<g class="sc"><rect x="0" y="{y - 5}" width="{L}" height="10" fill="url(#sg)"/>'
        f'<rect x="{L - 2}" y="{y - 6}" width="1.5" height="12" fill="{p["cyan"]}"/></g>'
    )
    defs = (
        '<linearGradient id="sg" x1="0" x2="1"><stop offset="0" stop-color="{c}" stop-opacity="0"/>'
        '<stop offset="1" stop-color="{c}" stop-opacity=".22"/></linearGradient>'.format(c=p["cyan"])
    )
    return document(W, H, body, title="divider", css=css, defs=defs)


def divider_pulse(p) -> str:
    W, H, y = 1000, 24, 12
    cx = W / 2
    css = (
        ".rg{transform-box:fill-box;transform-origin:center;animation:rg 3.2s ease-out infinite}"
        ".rg2{animation-delay:1.6s}"
        + keyframes("rg", [(0, "transform:scale(1);opacity:.8"), (70, "transform:scale(3.4);opacity:0"), (100, "transform:scale(3.4);opacity:0")])
        + ".ar{transform-box:fill-box;animation:ar 3.2s cubic-bezier(.16,1,.3,1) infinite}"
        + ".arl{transform-origin:right center}.arr{transform-origin:left center}"
        + keyframes("ar", [(0, "transform:scaleX(0);opacity:1"), (55, "transform:scaleX(1);opacity:0"), (100, "transform:scaleX(1);opacity:0")])
    )
    body = (
        f'<line x1="0" y1="{y}" x2="{fmt(cx - 14)}" y2="{y}" stroke="url(#fl)"/>'
        f'<line x1="{fmt(cx + 14)}" y1="{y}" x2="{W}" y2="{y}" stroke="url(#fl)"/>'
        f'<rect class="ar arl" x="{fmt(cx - 214)}" y="{y - .75}" width="200" height="1.5" fill="url(#gl)"/>'
        f'<rect class="ar arr" x="{fmt(cx + 14)}" y="{y - .75}" width="200" height="1.5" fill="url(#gr)"/>'
        f'<circle class="rg" cx="{fmt(cx)}" cy="{y}" r="3" fill="none" stroke="{p["cyan"]}"/>'
        f'<circle class="rg rg2" cx="{fmt(cx)}" cy="{y}" r="3" fill="none" stroke="{p["cyan"]}"/>'
        f'<circle cx="{fmt(cx)}" cy="{y}" r="3" fill="{p["cyan"]}"/>'
    )
    defs = faded_line_gradient(p, W) + (
        '<linearGradient id="gl" x1="1" x2="0"><stop offset="0" stop-color="{c}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="gr" x1="0" x2="1"><stop offset="0" stop-color="{c}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>'
    ).format(c=p["cyan"])
    return document(W, H, body, title="divider", css=css, defs=defs)


def divider_orbit(p) -> str:
    W, H, y = 1000, 24, 12
    cx, a, b = W / 2, 64, 8
    n = 48
    pts, _ = ellipse_arclength_samples(cx, y, a, b, n)
    dur = 5.0

    def orbit_css(cls, phase):
        stops = []
        for i in range(n + 1):
            x, yy, _t = pts[(i + phase) % n]
            behind = yy < y
            stops.append((100 * i / n, f"transform:translate({fmt(x - cx)}px,{fmt(yy - y)}px);opacity:{'.35' if behind else '1'}"))
        return f".{cls}{{animation:{cls} {dur}s linear infinite}}" + keyframes(cls, stops)

    css = orbit_css("o1", 0) + orbit_css("o2", n // 2)
    body = (
        f'<line x1="0" y1="{y}" x2="{fmt(cx - a - 16)}" y2="{y}" stroke="url(#fl)"/>'
        f'<line x1="{fmt(cx + a + 16)}" y1="{y}" x2="{W}" y2="{y}" stroke="url(#fl)"/>'
        f'<ellipse cx="{fmt(cx)}" cy="{y}" rx="{a}" ry="{b}" fill="none" {hair(p, p["hair_a"] * 1.6)}/>'
        f'<circle cx="{fmt(cx)}" cy="{y}" r="2.5" fill="{p["ink_mid"]}"/>'
        f'<circle class="o1" cx="{fmt(cx)}" cy="{y}" r="2.6" fill="{p["cyan"]}"/>'
        f'<circle class="o2" cx="{fmt(cx)}" cy="{y}" r="1.8" fill="{p["blue"]}"/>'
    )
    return document(W, H, body, title="divider", css=css, defs=faded_line_gradient(p, W))


# ==========================================================================
# SYSTEM CORE — the motion piece
#
# The four strata stacked as a core, a request descending through them, and
# a vehicle in orbit around the outside. The metaphor is the whole profile in
# one frame: the interface moves around the system; the system is underneath.
#
# Depth is faked honestly. Everything that orbits is drawn twice — once
# behind the core, once in front — and each copy is clipped to its half of
# the ellipse, so it passes behind the core without any timing trickery.
# ==========================================================================

VEHICLE = {
    # A low hover-craft in side profile, facing +x, origin under its centre.
    "body": "M-33 -.8L-31.6 -5.2L-28 -5.8C-20 -8.2 -12 -11.2 -3 -12C7 -12.6 15 -10.4 21 -6.6"
    "C27 -5 31 -3.4 34 -1.2L33 1C20 2.4 -20 2.4 -31 1.4Z",
    "glass": "M-14.5 -9.3C-6 -11.1 6 -11.2 14.2 -7.6L4 -6.4C-2 -6.3 -8.5 -6.8 -14.5 -7.4Z",
    "strip": "M-26 -2.2H27",
    "pods": "M-24 2.6h9M14 2.6h9",
}


def vehicle(p) -> str:
    body_fill = "#0e1520" if p["glow"] else "#f6f8fa"
    rim = p["cyan_soft"] if p["glow"] else p["ink_hi"]
    hover = (
        f'<ellipse cx="0" cy="6" rx="24" ry="2.4" fill="{p["cyan"]}" opacity=".55" filter="url(#hv)"/>'
        if p["glow"]
        else f'<ellipse cx="0" cy="6.5" rx="22" ry="1.6" fill="{p["cyan"]}" opacity=".35"/>'
    )
    return (
        hover
        + f'<path d="{VEHICLE["body"]}" fill="{body_fill}" stroke="{rim}" stroke-width=".9" stroke-linejoin="round"/>'
        + f'<path d="{VEHICLE["glass"]}" fill="{p["cyan"]}" fill-opacity=".28" stroke="{p["cyan"]}" stroke-opacity=".6" stroke-width=".6"/>'
        + f'<path d="{VEHICLE["strip"]}" stroke="{p["cyan"]}" stroke-width=".9"/>'
        + f'<path d="{VEHICLE["pods"]}" stroke="{p["cyan_soft"] if p["glow"] else p["cyan"]}" stroke-width="1.6" stroke-linecap="round" opacity=".8"/>'
        + f'<rect x="-32.6" y="-4" width="1.6" height="4.2" fill="{p["violet"]}"/>'
        + f'<path d="M28.6 -2.1L32.3 -.9" stroke="{p["cyan_soft"]}" stroke-width="1.1" stroke-linecap="round"/>'
    )


def orbit_track(cx, cy, a, b, n, reverse=False):
    pts, total = ellipse_arclength_samples(cx, cy, a, b, n)
    if reverse:
        pts = [pts[0]] + pts[:0:-1]
    return pts, total


def orbit_keyframes(cls_pos, cls_yaw, pts, cy, b, dur, yaw=True, depth=(0.82, 1.32), fade=(0.5, 1.0)):
    n = len(pts)
    pos, rot = [], []
    for i in range(n + 1):
        x, y, _ = pts[i % n]
        nx, ny, _ = pts[(i + 1) % n]
        px, py, _ = pts[(i - 1) % n]
        vx, vy = nx - px, ny - py
        k = (y - (cy - b)) / (2 * b)  # 0 at the back of the orbit, 1 at the front
        ds = depth[0] + (depth[1] - depth[0]) * k
        op = fade[0] + (fade[1] - fade[0]) * k
        pct = 100 * i / n
        pos.append((pct, f"transform:translate({fmt(x)}px,{fmt(y)}px)"))
        if yaw:
            sx = vx / max(math.hypot(vx, vy), 1e-9)
            sx = math.copysign(max(abs(sx), 0.16), sx)
            rot.append((pct, f"transform:scale({sx * ds:.3f},{ds:.3f});opacity:{op:.2f}"))
        else:
            rot.append((pct, f"transform:scale({ds:.3f});opacity:{op:.2f}"))
    css = f".{cls_pos}{{animation:{cls_pos} {dur}s linear infinite}}" + keyframes(cls_pos, pos)
    css += f".{cls_yaw}{{animation:{cls_yaw} {dur}s linear infinite}}" + keyframes(cls_yaw, rot)
    return css


def system_core(p) -> str:
    W, H = 1000, 396
    cx, cy = 500, 200
    ts = Typesetter()
    rnd = random.Random(7)
    css = []
    defs = []
    g = p["glow"]
    if g:
        defs.append(glow_filter("bl", 2.4))
        defs.append('<filter id="hv" x="-50%" y="-300%" width="200%" height="700%"><feGaussianBlur stdDeviation="2.6"/></filter>')
        defs.append(
            '<radialGradient id="coreGlow" cx=".5" cy=".5" r=".5">'
            f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity=".30"/>'
            f'<stop offset=".45" stop-color="{p["blue"]}" stop-opacity=".08"/>'
            f'<stop offset="1" stop-color="{p["blue"]}" stop-opacity="0"/></radialGradient>'
        )

    # --- Orbits -------------------------------------------------------------
    oa, ob, ocy = 340, 64, cy + 34
    ia, ib, icy = 205, 38, cy + 8
    N, dur = 120, 16.0
    outer, outer_len = orbit_track(cx, ocy, oa, ob, N, reverse=True)
    inner, inner_len = orbit_track(cx, icy, ia, ib, 72)

    def half_clip(cid, y, front):
        y0, h = (y, H - y) if front else (0, y)
        return f'<clipPath id="{cid}"><rect x="0" y="{fmt(y0)}" width="{W}" height="{fmt(h)}"/></clipPath>'

    defs += [half_clip("ob", ocy, False), half_clip("of", ocy, True), half_clip("ib", icy, False), half_clip("if", icy, True)]

    trail = 260
    fine, _ = orbit_track(cx, ocy, oa, ob, 360, reverse=True)
    orbit_d = "M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y, _ in fine) + "Z"
    css.append(
        f".tr{{stroke-dasharray:{trail} {fmt(outer_len - trail)};animation:tr {dur}s linear infinite}}"
        + keyframes("tr", [(0, f"stroke-dashoffset:{trail}"), (100, f"stroke-dashoffset:{fmt(trail - outer_len)}")])
    )
    defs.append(
        f'<linearGradient id="trg" gradientUnits="userSpaceOnUse" x1="{cx - oa}" x2="{cx + oa}">'
        f'<stop offset="0" stop-color="{p["blue"]}"/><stop offset=".5" stop-color="{p["cyan"]}"/>'
        f'<stop offset="1" stop-color="{p["blue"]}"/></linearGradient>'
    )
    css.append(orbit_keyframes("cp", "cy", outer, ocy, ob, dur))
    css.append(orbit_keyframes("sp", "sy", inner, icy, ib, 11.0, yaw=False, depth=(0.8, 1.1), fade=(0.45, 1.0)))
    css.append(
        ".rot{animation:rot 24s linear infinite}"
        + keyframes("rot", [(0, "stroke-dashoffset:0"), (100, f"stroke-dashoffset:{fmt(-inner_len)}")])
    )

    def orbit_layer(front: bool) -> str:
        clip_o, clip_i = ("of", "if") if front else ("ob", "ib")
        a_ring = p["hair_a"] * (2.2 if front else 1.2)
        out = f'<g clip-path="url(#{clip_i})">'
        out += (
            f'<ellipse class="rot" cx="{cx}" cy="{icy}" rx="{ia}" ry="{ib}" fill="none" stroke="{p["blue"]}"'
            f' stroke-opacity="{fmt(0.45 if front else 0.25)}" stroke-dasharray="2 7"/>'
        )
        out += f'<g class="sp"><g class="sy"><circle r="3" fill="{p["blue"]}"/><circle r="6" fill="none" stroke="{p["blue"]}" stroke-opacity=".4"/></g></g>'
        out += "</g>"
        out += f'<g clip-path="url(#{clip_o})">'
        out += f'<ellipse cx="{cx}" cy="{ocy}" rx="{oa}" ry="{ob}" fill="none" stroke="{p["hair"]}" stroke-opacity="{fmt(a_ring)}"/>'
        bloom = ' filter="url(#bl)"' if g else ""
        out += f'<path class="tr" d="{orbit_d}" fill="none" stroke="url(#trg)" stroke-width="1.6" stroke-linecap="round"{bloom} opacity="{".55" if not front else "1"}"/>'
        out += f'<g class="cp"><g class="cy">{vehicle(p)}</g></g>'
        out += "</g>"
        return out

    # --- Core: four strata --------------------------------------------------
    levels = [cy - 66, cy - 22, cy + 22, cy + 66]
    ra, rb = 78, 16
    top, bottom = cy - 128, cy + 116
    fall = 4.2
    css.append(
        ".rq{animation:rq 6s cubic-bezier(.45,0,.55,1) infinite}"
        + keyframes(
            "rq",
            [(0, "transform:translateY(0);opacity:0"), (6, "opacity:1"), (100 * fall / 6 - 4, "opacity:1"),
             (100 * fall / 6, f"transform:translateY({bottom - top}px);opacity:0"), (100, f"transform:translateY({bottom - top}px);opacity:0")],
        )
    )
    discs = []
    for i, ly in enumerate(levels):
        frac = (ly - top) / (bottom - top)
        # Ease-in-out timing: solve for when the packet reaches this level.
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            e = mid * mid * (3 - 2 * mid)
            lo, hi = (mid, hi) if e < frac else (lo, mid)
        t = 100 * (lo * fall) / 6
        css.append(
            f".d{i}{{animation:d{i} 6s linear infinite}}"
            + keyframes(f"d{i}", [(0, "stroke-opacity:.35"), (max(t - 1.5, 0.1), "stroke-opacity:.35"), (t, "stroke-opacity:1"), (t + 12, "stroke-opacity:.35"), (100, "stroke-opacity:.35")])
        )
        shade = [0.05, 0.08, 0.12, 0.18][i]
        col = p["cyan"] if i == 3 else p["blue"]
        discs.append(
            f'<ellipse cx="{cx}" cy="{ly}" rx="{ra}" ry="{rb}" fill="{col}" fill-opacity="{shade}"/>'
            f'<ellipse class="d{i}" cx="{cx}" cy="{ly}" rx="{ra}" ry="{rb}" fill="none" stroke="{col}" stroke-width="1.1"/>'
        )
        num, _ = ts.text(MONO, STRATA[i][0], cx + ra + 12, ly + 4, 11, p["ink_low"])
        discs.append(num)
    # Side walls of the column, so the four discs read as one solid.
    walls = f'<path d="M{cx - ra} {levels[0]}V{levels[-1]}M{cx + ra} {levels[0]}V{levels[-1]}" {hair(p, p["hair_a"] * 1.4)}/>'
    core_glow = f'<ellipse class="cg" cx="{cx}" cy="{levels[-1]}" rx="150" ry="46" fill="url(#coreGlow)"/>' if g else ""
    css.append(".cg{animation:cg 5s ease-in-out infinite}" + keyframes("cg", [(0, "opacity:.7"), (50, "opacity:1"), (100, "opacity:.7")]))
    axis = f'<line x1="{cx}" y1="{top}" x2="{cx}" y2="{bottom}" stroke="{p["hair"]}" stroke-opacity="{fmt(p["hair_a"] * 1.3)}" stroke-dasharray="1 4"/>'
    request = (
        f'<g class="rq"><rect x="{cx - 1}" y="{top - 26}" width="2" height="26" fill="url(#rqg)"/>'
        f'<circle cx="{cx}" cy="{top}" r="2.6" fill="{p["cyan_soft"]}"{" filter=" + chr(34) + "url(#bl)" + chr(34) if g else ""}/></g>'
    )
    defs.append(
        '<linearGradient id="rqg" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity="0"/><stop offset="1" stop-color="{p["cyan"]}"/></linearGradient>'
    )

    # --- Particles ----------------------------------------------------------
    parts = []
    k = 0
    while len(parts) < 30:
        x, y = rnd.uniform(40, W - 40), rnd.uniform(40, H - 30)
        if abs(x - cx) < ra + 30 and top - 20 < y < bottom + 20:
            continue
        dx, dy = rnd.uniform(-18, 18), rnd.uniform(-22, -6)
        d, delay = rnd.uniform(7, 13), rnd.uniform(0, 12)
        r = rnd.choice([0.7, 0.9, 1.1, 1.4])
        col = rnd.choice([p["ink_mid"], p["ink_mid"], p["cyan"], p["blue"]])
        name = f"q{k}"
        css.append(
            f".{name}{{animation:{name} {d:.1f}s ease-in-out -{delay:.1f}s infinite}}"
            + keyframes(name, [(0, "transform:translate(0,0);opacity:0"), (30, "opacity:.8"), (70, "opacity:.8"), (100, f"transform:translate({dx:.1f}px,{dy:.1f}px);opacity:0")])
        )
        parts.append(f'<circle class="{name}" cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}"/>')
        k += 1

    # --- Frame --------------------------------------------------------------
    cap, _ = ts.text(MONO, "FIG. 01 — ONE REQUEST, ALL THE WAY DOWN", 28, 34, 11, p["ink_low"], tracking=0.1)
    tag, _ = ts.text(MONO_BOLD, "SYSTEM CORE", W - 28, 34, 11, p["ink_mid"], anchor="end", tracking=0.22)
    legend, _ = ts.text(
        MONO, "00 SURFACE · 01 INTERFACE · 02 ENGINE · 03 SUBSTRATE", 28, H - 22, 11, p["ink_low"], tracking=0.06
    )
    tail, _ = ts.text(MONO, "the interface orbits · the system is underneath", W - 28, H - 22, 11, p["ink_low"], anchor="end")
    frame = corner_brackets(12, 12, W - 24, H - 24, p["hair"], p["hair_a"] * 2.2, length=14)

    body = (
        frame + cap + tag
        + "".join(parts)
        + core_glow
        + orbit_layer(front=False)
        + axis
        + walls
        + "".join(discs)
        + request
        + orbit_layer(front=True)
        + legend + tail
    )
    return document(W, H, body, title="System core", css="".join(css), defs=ts.defs() + "".join(defs))


# ==========================================================================
# PROJECT FIGURES
#
# Each one animates something the repository actually does. The deadlockd
# figure replays the CIRCULAR_WAIT scenario from backend/engine/scenarios.go;
# its victim is P0 because ResolveDeadlock takes the first process in the
# cycle that DetectDeadlock's DFS returns ([P0 P2 P1 P0]) when allocations
# tie. The AKASH figure is an attribution diagram: which layers are mine.
# ==========================================================================


def timeline(name, T, stops, prop="opacity", base=None, ease="linear"):
    """Keyframes for one property from (seconds, value) pairs."""
    kf = [(100 * t / T, f"{prop}:{v}") for t, v in stops]
    if kf[0][0] > 0:
        kf.insert(0, (0, kf[0][1]))
    if kf[-1][0] < 100:
        kf.append((100, kf[-1][1]))
    b = f"{prop}:{base};" if base is not None else ""
    return f".{name}{{{b}animation:{name} {T}s {ease} infinite}}" + keyframes(name, kf)


def arrow_line(x0, y0, x1, y1, r0, r1):
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    return (x0 + ux * r0, y0 + uy * r0, x1 - ux * r1, y1 - uy * r1, ux, uy)


def arrowhead(x, y, ux, uy, size=6):
    px, py = -uy, ux
    a = (x, y)
    b = (x - ux * size + px * size * 0.5, y - uy * size + py * size * 0.5)
    c = (x - ux * size - px * size * 0.5, y - uy * size - py * size * 0.5)
    return f"M{fmt(a[0])} {fmt(a[1])}L{fmt(b[0])} {fmt(b[1])}L{fmt(c[0])} {fmt(c[1])}Z"


def project_deadlockd(p) -> str:
    W, H, T = 1000, 260, 14.0
    ts = Typesetter()
    css = []
    gx, gy, R = 250, 132, 92
    ang = {"P0": -90, "R1": -30, "P1": 30, "R2": 90, "P2": 150, "R0": 210}
    pos = {k: (gx + R * math.cos(math.radians(a)), gy + R * math.sin(math.radians(a))) for k, a in ang.items()}
    rad = 17

    def edge(cls, a, b, dashed, color, width=1.3, base_op=None):
        x0, y0, x1, y1, ux, uy = arrow_line(*pos[a], *pos[b], rad + 3, rad + 5)
        dash = ' stroke-dasharray="4 4"' if dashed else ""
        op = f' opacity="{base_op}"' if base_op is not None else ""
        return (
            f'<g class="{cls}"{op}><line x1="{fmt(x0)}" y1="{fmt(y0)}" x2="{fmt(x1)}" y2="{fmt(y1)}"'
            f' stroke="{color}" stroke-width="{width}"{dash}/>'
            f'<path d="{arrowhead(x1, y1, ux, uy)}" fill="{color}"/></g>'
        )

    # Timeline (seconds): load → requests → unsafe → detect → deadlock →
    # terminate P0 → grant P2's request → safe → hold → reset.
    t_req = [1.2, 2.2, 3.2]
    t_unsafe, t_detect, t_dead, t_kill, t_grant, t_safe, t_end = 4.4, 5.4, 7.2, 8.6, 9.6, 10.4, 13.2

    held = [("R0", "P0", "h0"), ("R1", "P1", "h1"), ("R2", "P2", "h2")]
    reqs = [("P0", "R1", "q0"), ("P1", "R2", "q1"), ("P2", "R0", "q2")]
    edges = []
    for a, b, c in held:
        edges.append(edge(c, a, b, False, p["ink_mid"]))
    for (a, b, c), t in zip(reqs, t_req):
        edges.append(edge(c, a, b, True, p["ink_mid"]))
        if c == "q1":
            css.append(timeline(c, T, [(t - 0.01, 0), (t, 1), (t_end, 1), (t_end + 0.4, 0)], base=1, ease="step-end"))
    # The violet overlay is the cycle itself, lit once DetectDeadlock returns.
    cyc = []
    order = ["P0", "R1", "P1", "R2", "P2", "R0", "P0"]
    for a, b in zip(order, order[1:]):
        cyc.append(edge("cy", a, b, False, p["violet"], width=2))
    css.append(timeline("cy", T, [(t_dead - 0.01, 0), (t_dead, 1), (t_kill, 1), (t_kill + 0.5, 0)], base=0))
    css.append(timeline("h0", T, [(t_kill, 1), (t_kill + 0.5, 0.0), (t_end, 0), (t_end + 0.4, 1)], base=1))
    css.append(timeline("q0", T, [(t_req[0] - 0.01, 0), (t_req[0], 1), (t_kill, 1), (t_kill + 0.5, 0)], base=1))
    css.append(timeline("q2", T, [(t_req[2] - 0.01, 0), (t_req[2], 1), (t_grant, 1), (t_grant + 0.3, 0)], base=1))
    # Granted: the request edge P2→R0 becomes the assignment edge R0→P2.
    edges.append(edge("gr", "R0", "P2", False, p["cyan"], width=1.6))
    css.append(timeline("gr", T, [(t_grant, 0), (t_grant + 0.4, 1), (t_end, 1), (t_end + 0.4, 0)], base=0))

    # A token walking the cycle — DetectDeadlock's DFS, made visible.
    walk = []
    seg_t = (t_dead - t_detect) / 6
    for i, k in enumerate(order):
        x, y = pos[k]
        walk.append((t_detect + i * seg_t, f"transform:translate({fmt(x)}px,{fmt(y)}px)"))
    kf = [(0, walk[0][1])] + [(100 * t / T, v) for t, v in walk] + [(100, walk[-1][1])]
    css.append(".tk{animation:tk %ss linear infinite}" % T + keyframes("tk", kf))
    css.append(timeline("tko", T, [(t_detect - 0.01, 0), (t_detect, 1), (t_dead, 1), (t_dead + 0.2, 0)], base=0, ease="step-end"))

    nodes = []
    for k, (x, y) in pos.items():
        if k.startswith("P"):
            cls = ' class="p0"' if k == "P0" else ""
            nodes.append(
                f'<g{cls}><circle cx="{fmt(x)}" cy="{fmt(y)}" r="{rad}" fill="{p["cyan"]}" fill-opacity=".07"'
                f' stroke="{p["cyan"]}" stroke-width="1.3"/></g>'
            )
        else:
            nodes.append(
                f'<rect x="{fmt(x - 15)}" y="{fmt(y - 15)}" width="30" height="30" rx="2" fill="{p["blue"]}"'
                f' fill-opacity=".07" stroke="{p["blue"]}" stroke-width="1.3"/>'
                f'<circle cx="{fmt(x + 9)}" cy="{fmt(y - 9)}" r="1.8" fill="{p["blue"]}"/>'
            )
        lab, _ = ts.text(MONO_BOLD, k, x, y + 4.2, 12, p["ink_hi"], anchor="middle")
        nodes.append(f'<g class="p0"><g>{lab}</g></g>' if k == "P0" else lab)
    css.append(timeline("p0", T, [(t_kill, 1), (t_kill + 0.5, 0.25), (t_end, 0.25), (t_end + 0.4, 1)], base=1))

    # --- Log panel ----------------------------------------------------------
    lx, ly0, lh = 520, 70, 27
    size = 12.5
    lines = [
        (0.3, "›", "LOAD_SCENARIO", "CIRCULAR_WAIT", "ink"),
        (t_unsafe, " ", "IsSafeState", "false", "ink"),
        (t_dead, " ", "DetectDeadlock", "P0 → P1 → P2 → P0", "violet"),
        (t_kill, " ", "ResolveDeadlock", "terminate P0", "ink"),
        (t_safe, " ", "IsSafeState", "true  [P2 P1]", "cyan"),
    ]
    log = []
    for i, (t, mark, fn, val, tone) in enumerate(lines):
        y = ly0 + i * lh
        m, _ = ts.text(MONO_BOLD, mark, lx, y, size, p["cyan"])
        f, _ = ts.text(MONO, fn, lx + 18, y, size, p["ink_mid"])
        v, _ = ts.text(MONO_BOLD if tone != "ink" else MONO, val, lx + 18 + 16 * 7.8, y, size, p[tone] if tone != "ink" else p["ink_hi"])
        c = f"l{i}"
        log.append(f'<g class="{c}">{m}{f}{v}</g>')
        css.append(timeline(c, T, [(t - 0.01, 0), (t, 1), (t_end, 1), (t_end + 0.4, 0)], base=1, ease="step-end"))

    head, _ = ts.text(MONO, "SIMULATION LOG", lx, 36, 11, p["ink_low"], tracking=0.18)
    chips = []
    states = [("RUNNING", 0, t_unsafe, "ink_mid"), ("UNSAFE", t_unsafe, t_dead, "ink_hi"), ("DEADLOCK", t_dead, t_kill, "violet"),
              ("RECOVERING", t_kill, t_safe, "ink_hi"), ("SAFE", t_safe, T, "cyan")]
    for i, (label, a, b, tone) in enumerate(states):
        c = f"s{i}"
        t_txt, tw = ts.text(MONO_BOLD, label, W - 40, 36, 11, p[tone], anchor="end", tracking=0.16)
        dot = f'<circle cx="{fmt(W - 40 - tw - 12)}" cy="32" r="3.2" fill="{p[tone]}"/>'
        chips.append(f'<g class="{c}">{dot}{t_txt}</g>')
        css.append(timeline(c, T, [(0, 0), (a, 1), (b, 0)] if a > 0 else [(0, 1), (b, 0)], base=1 if label == "SAFE" else 0, ease="step-end"))

    rule = f'<line x1="{lx}" y1="48" x2="{W - 40}" y2="48" {hair(p)}/>'
    foot, _ = ts.text(MONO, "backend/engine · banker.go · detection.go · recovery.go", lx, H - 26, 11, p["ink_low"])
    frame = corner_brackets(12, 12, W - 24, H - 24, p["hair"], p["hair_a"] * 2.2)
    token = f'<g class="tk"><g class="tko"><circle r="4" fill="{p["violet"]}"/><circle r="8" fill="none" stroke="{p["violet"]}" stroke-opacity=".5"/></g></g>'
    body = frame + "".join(edges) + "".join(cyc) + "".join(nodes) + token + head + rule + "".join(chips) + "".join(log) + foot
    return document(W, H, body, title="deadlockd — CIRCULAR_WAIT scenario", css="".join(css), defs=ts.defs())


def akash_field(i, j):
    """A fixed, smooth field for the illustrative grid — plumes, not data."""
    v = 0.0
    for cx, cy, s, w in [(3.5, 2.5, 1.9, 1.0), (10.5, 5.5, 2.4, 0.85), (6.5, 7.5, 1.6, 0.6), (13, 1.5, 1.4, 0.5)]:
        v += w * math.exp(-((i - cx) ** 2 + (j - cy) ** 2) / (2 * s * s))
    return min(v, 1.0)


def project_akash(p) -> str:
    W, H, T = 1000, 260, 10.0
    ts = Typesetter()
    css = []
    # --- Left: a swath sweeping the analysis grid ------------------------------
    cols, rows, cell, gap = 16, 9, 13, 3
    gx0, gy0 = 44, 74
    gw = cols * (cell + gap) - gap
    cells = []
    sweep_t0, sweep_t1 = 0.6, 6.6
    for i in range(cols):
        for j in range(rows):
            v = akash_field(i, j)
            x, y = gx0 + i * (cell + gap), gy0 + j * (cell + gap)
            col = p["violet"] if v > 0.72 else p["cyan"] if v > 0.38 else p["blue"]
            lit = 0.2 + 0.8 * v
            t_hit = sweep_t0 + (sweep_t1 - sweep_t0) * ((i + j * 0.35) / (cols + rows * 0.35))
            level = min(3, int(v * 4))
            cells.append(
                f'<rect class="lv{level}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1.5" fill="{col}"'
                f' style="animation-delay:{t_hit:.2f}s"/>'
            )
    for level in range(4):
        lit = 0.22 + 0.26 * level
        css.append(
            f".lv{level}{{opacity:.06;animation:lv{level} {T}s linear infinite backwards}}"
            + keyframes(
                f"lv{level}",
                [(0, "opacity:.06"), (2.5, f"opacity:{min(lit + .2, 1):.2f}"), (12, f"opacity:{lit:.2f}"),
                 (78, f"opacity:{lit:.2f}"), (86, "opacity:.06"), (100, "opacity:.06")],
            )
        )
    outline = "".join(
        f"M{gx0 + i * (cell + gap) + .5} {gy0 + j * (cell + gap) + .5}h{cell - 1}v{cell - 1}h{1 - cell}z"
        for i in range(cols) for j in range(rows)
    )
    grid_bg = f'<path d="{outline}" fill="none" {hair(p, p["hair_a"] * 0.9)}/>'
    # The satellite crosses on a slanted ground track, dragging its swath.
    sw = 34
    track_y = gy0 - 26
    sat = (
        f'<rect x="-5" y="-3.5" width="10" height="7" rx="1" fill="{p["ink_hi"]}"/>'
        f'<rect x="-19" y="-2.5" width="11" height="5" fill="none" stroke="{p["cyan"]}" stroke-width="1"/>'
        f'<rect x="8" y="-2.5" width="11" height="5" fill="none" stroke="{p["cyan"]}" stroke-width="1"/>'
        f'<path d="M-8 0H-5M5 0H8" stroke="{p["ink_hi"]}"/>'
    )
    swath = (
        f'<polygon points="0,6 {-sw/2},{fmt(gy0 + rows * (cell + gap) - track_y)} {sw/2},{fmt(gy0 + rows * (cell + gap) - track_y)}" fill="url(#swg)"/>'
    )
    travel = gw + 60
    css.append(timeline("sat", T, [(sweep_t0 - .4, "translateX(0px)"), (sweep_t1 + .6, f"translateX({travel}px)")], prop="transform", ease="linear"))
    css.append(timeline("sato", T, [(0, 0), (sweep_t0 - .2, 1), (sweep_t1 + .3, 1), (sweep_t1 + .8, 0)], base=1))
    defs = (
        '<linearGradient id="swg" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity=".35"/>'
        f'<stop offset="1" stop-color="{p["cyan"]}" stop-opacity="0"/></linearGradient>'
    )
    satg = f'<g transform="translate({gx0 - 30} {track_y})"><g class="sat"><g class="sato">{swath}{sat}</g></g></g>'
    cap, _ = ts.text(MONO, "ANALYSIS GRID · ILLUSTRATIVE", gx0, H - 28, 11, p["ink_low"], tracking=0.12)
    lab_t, _ = ts.text(MONO, "SENTINEL-5P / TROPOMI", gx0, 36, 11, p["ink_low"], tracking=0.12)

    # --- Right: the layers, and whose they are ---------------------------------
    rx0, rx1 = 356, W - 36
    rows_spec = [
        ("OBSERVE", "TROPOMI · MODIS AOD · ERA5 · CPCB · OpenAQ", False),
        ("MODEL", "feature lineage · collocation · baseline models", False),
        ("SERVE", "FastAPI · async SQLAlchemy · PostGIS · structlog", True),
        ("SEE", "Streamlit · Folium · map, forecast & report pages", True),
    ]
    ry0, rh, rgap = 40, 34, 8
    layer = []
    for k, (name, desc, mine) in enumerate(rows_spec):
        y = ry0 + k * (rh + rgap)
        stroke = f'stroke="{p["cyan"]}" stroke-opacity=".55"' if mine else f'stroke="{p["hair"]}" stroke-opacity="{fmt(p["hair_a"] * 1.3)}"'
        fill = f'fill="{p["cyan"]}" fill-opacity=".06"' if mine else 'fill="none"'
        layer.append(f'<rect x="{rx0}" y="{y}" width="{rx1 - rx0}" height="{rh}" rx="2" {fill} {stroke}/>')
        if mine:
            layer.append(f'<rect x="{rx0}" y="{y}" width="3" height="{rh}" fill="{p["cyan"]}"/>')
        idx, _ = ts.text(MONO, f"L{k}", rx0 + 16, y + rh / 2 + 4.3, 12, p["cyan"] if mine else p["ink_low"])
        nm, _ = ts.text(MONO_BOLD, name, rx0 + 48, y + rh / 2 + 4.3, 12, p["ink_hi"] if mine else p["ink_mid"], tracking=0.14)
        ds, _ = ts.text(MONO, desc, rx0 + 150, y + rh / 2 + 4.3, 12, p["ink"] if mine else p["ink_low"])
        layer += [idx, nm, ds]
    # Packets fall through the layers: data in at the top, a map at the bottom.
    ax = rx1 - 22
    fall_top, fall_bot = ry0 + 10, ry0 + 3 * (rh + rgap) + rh - 10
    for n in range(3):
        c = f"f{n}"
        css.append(
            f".{c}{{animation:{c} 3.6s cubic-bezier(.45,0,.55,1) {-1.2 * n:.1f}s infinite}}"
            + keyframes(c, [(0, "transform:translateY(0);opacity:0"), (12, "opacity:1"), (82, "opacity:1"), (100, f"transform:translateY({fmt(fall_bot - fall_top)}px);opacity:0")])
        )
        layer.append(f'<rect class="{c}" x="{ax - 3}" y="{fall_top - 3}" width="6" height="6" transform-origin="{ax} {fall_top}" fill="{p["cyan"]}"/>')
    rail = f'<line x1="{ax}" y1="{fall_top}" x2="{ax}" y2="{fall_bot}" stroke="{p["hair"]}" stroke-opacity="{fmt(p["hair_a"] * 1.4)}" stroke-dasharray="1 4"/>'
    y_mine = ry0 + 2 * (rh + rgap)
    brk_x = rx0 - 12
    brk = (
        f'<path d="M{brk_x + 6} {y_mine}H{brk_x}V{y_mine + 2 * rh + rgap}H{brk_x + 6}" fill="none" stroke="{p["cyan"]}" stroke-width="1.2"/>'
    )
    mine_lab, mw = ts.text(MONO_BOLD, "MY LAYER", rx0, H - 28, 11, p["cyan"], tracking=0.16)
    team_lab, _ = ts.text(MONO, "L0–L1  TEAMMATES", rx1, H - 28, 11, p["ink_low"], anchor="end", tracking=0.08)
    mine_rest, _ = ts.text(MONO, "L2–L3  PLATFORM + DASHBOARD", rx0 + mw + 14, H - 28, 11, p["ink_mid"], tracking=0.08)
    frame = corner_brackets(12, 12, W - 24, H - 24, p["hair"], p["hair_a"] * 2.2)
    body = frame + lab_t + grid_bg + "".join(cells) + satg + cap + "".join(layer) + rail + brk + mine_lab + mine_rest + team_lab
    return document(W, H, body, title="AKASH — satellite AQI platform, layer attribution", css="".join(css), defs=ts.defs() + defs)


def project_portfolio(p) -> str:
    W, H, P = 1000, 260, 10.0
    ts = Typesetter()
    css = []
    cx, cy = 430, 132
    base_w, base_h = 330, 150
    planes = [
        ("00", "SURFACE", "P1 requests R0 ×1  →  GRANTED"),
        ("01", "INTERFACE", '{ "type": "REQUEST", "pid": 1 }'),
        ("02", "ENGINE", "IsSafeState(state)?  →  commit"),
        ("03", "SUBSTRATE", "state.Mu.Lock() … Unlock()"),
    ]
    # A camera dollies through four planes. z falls linearly; apparent size is
    # 1/z. Planes fade in slowly and clear out fast — a plane you have just
    # passed is huge and in front of everything, so it has to leave quickly.
    samples = 40
    z0, z1 = 3.4, 0.62

    def plane_kf(name):
        stops = []
        for i in range(samples + 1):
            f = i / samples
            z = z0 + (z1 - z0) * f
            s = 1 / z
            if s < 0.55:
                op = max(0.0, (s - 1 / z0) / (0.55 - 1 / z0)) * 0.8
            elif s <= 1.05:
                op = 0.8 + 0.2 * (s - 0.55) / 0.5
            else:
                op = max(0.0, 1 - (s - 1.05) / 0.3)
            stops.append((100 * f, f"transform:scale({s:.3f});opacity:{op:.2f}"))
        return keyframes(name, stops)

    css.append(plane_kf("dv"))
    groups = []
    for k, (idx, name, snip) in enumerate(planes):
        x, y = cx - base_w / 2, cy - base_h / 2
        a, _ = ts.text(MONO_BOLD, idx, x + 14, y + 24, 12, p["cyan"])
        n, _ = ts.text(MONO_BOLD, name, x + 40, y + 24, 12, p["ink_hi"], tracking=0.18)
        s, _ = ts.text(MONO, snip, x + 14, y + base_h - 20, 12, p["ink"])
        g = (
            f'<g class="pl pl{k}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{base_w}" height="{base_h}" rx="2"'
            f' fill="{p["cyan"]}" fill-opacity=".025" stroke="{p["cyan"] if k != 3 else p["violet"]}" stroke-opacity=".6"/>'
            f'<path d="M{fmt(x)} {fmt(y + 36)}H{fmt(x + base_w)}" {hair(p)}/>{a}{n}{s}</g>'
        )
        groups.append(g)
        css.append(f".pl{k}{{animation:dv {P}s linear {-(P / 4) * (3 - k):.2f}s infinite}}")
    css.append(f".pl{{transform-box:view-box;transform-origin:{cx}px {cy}px}}")

    # Crosshair at the vanishing point, and faint perspective rays.
    rays = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{fmt(cx + dx)}" y2="{fmt(cy + dy)}" {hair(p, p["hair_a"] * .7)}/>'
        for dx, dy in [(-400, -130), (400, -130), (-400, 130), (400, 130)]
    )
    cross = (
        f'<path d="M{cx - 6} {cy}H{cx + 6}M{cx} {cy - 6}V{cy + 6}" stroke="{p["ink_low"]}"/>'
    )
    # Depth readout on the right, stepping with whichever plane is nearest.
    rx = 830
    rail = []
    lab, _ = ts.text(MONO, "DEPTH", rx, 52, 11, p["ink_low"], tracking=0.2)
    rail.append(lab)
    for k, (idx, name, _) in enumerate(planes):
        y = 80 + k * 38
        rail.append(f'<line x1="{rx}" y1="{y}" x2="{rx + 10}" y2="{y}" {hair(p, p["hair_a"] * 2)}/>')
        t, _ = ts.text(MONO, f"{idx} {name}", rx + 20, y + 4, 11, p["ink_low"], tracking=0.1)
        rail.append(t)
        th, _ = ts.text(MONO_BOLD, f"{idx} {name}", rx + 20, y + 4, 11, p["ink_hi"], tracking=0.1)
        c = f"dp{k}"
        rail.append(f'<g class="{c}"><rect x="{rx - 1}" y="{y - 1.5}" width="12" height="3" fill="{p["cyan"]}"/>{th}</g>')
        # Plane k is nearest the camera for the quarter-cycle centred on the
        # moment its scale crosses 1 (z = 1).
        f_one = (z0 - 1) / (z0 - z1)
        centre = (f_one - (3 - k) / 4) % 1
        on, off = (centre - 0.125) % 1 * P, (centre + 0.125) % 1 * P
        if on < off:
            kf = [(0, "opacity:0"), (100 * on / P, "opacity:1"), (100 * off / P, "opacity:0"), (100, "opacity:0")]
        else:
            kf = [(0, "opacity:1"), (100 * off / P, "opacity:0"), (100 * on / P, "opacity:1"), (100, "opacity:1")]
        css.append(f".{c}{{opacity:{1 if k == 0 else 0};animation:{c} {P}s step-end infinite}}" + keyframes(c, kf))
    rail.append(f'<line x1="{rx + 5}" y1="80" x2="{rx + 5}" y2="{80 + 3 * 38}" {hair(p)}/>')
    note, _ = ts.text(MONO, "one real request, surface to substrate", 36, H - 26, 11, p["ink_low"])
    tag, _ = ts.text(MONO, "WEBGL · SCROLL-DRIVEN", W - 36, H - 26, 11, p["ink_low"], anchor="end", tracking=0.14)
    clip = f'<clipPath id="win"><rect x="24" y="24" width="{rx - 60}" height="{H - 70}"/></clipPath>'
    frame = corner_brackets(12, 12, W - 24, H - 24, p["hair"], p["hair_a"] * 2.2)
    body = frame + f'<g clip-path="url(#win)">{rays}{"".join(groups)}{cross}</g>' + "".join(rail) + note + tag
    return document(W, H, body, title="Portfolio — the descent", css="".join(css), defs=ts.defs() + clip)


# ==========================================================================
# FOOTER — the bottom of the descent
# ==========================================================================


def footer(p) -> str:
    W, H = 1000, 150
    ts = Typesetter()
    css = []
    x0, x1 = 60, 940
    ys = [26, 44, 62, 80]
    lines = []
    for i, y in enumerate(ys):
        dash = ["2 10", "6 14", "14 18", "28 12"][i]
        speed = [22, 30, 42, 60][i]
        period = sum(float(v) for v in dash.split())
        c = f"s{i}"
        css.append(
            f".{c}{{animation:{c} {speed}s linear infinite}}"
            + keyframes(c, [(0, "stroke-dashoffset:0"), (100, f"stroke-dashoffset:{fmt(-period * 12)}")])
        )
        op = p["hair_a"] * (1.4 + 0.5 * i)
        lines.append(
            f'<line class="{c}" x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="url(#ff)" stroke-width="{1 + 0.25 * i}"'
            f' stroke-dasharray="{dash}" style="stroke-opacity:{min(op * 4, 1):.2f}"/>'
        )
        lab, _ = ts.text(MONO, f"0{i}", x0 - 14, y + 3.8, 10, p["ink_low"], anchor="end")
        lines.append(lab)
    cx = W / 2
    drop = ys[-1] - 4
    css.append(
        ".dr{animation:dr 4.8s cubic-bezier(.55,0,.8,.4) infinite}"
        + keyframes("dr", [(0, "transform:translateY(0);opacity:0"), (8, "opacity:1"), (50, f"transform:translateY({drop}px);opacity:1"), (54, f"transform:translateY({drop}px);opacity:0"), (100, f"transform:translateY({drop}px);opacity:0")])
    )
    css.append(
        ".rp{transform-box:fill-box;transform-origin:center;animation:rp 4.8s ease-out infinite}"
        + keyframes("rp", [(0, "transform:scale(.2);opacity:0"), (50, "transform:scale(.2);opacity:0"), (52, "transform:scale(.3);opacity:.9"), (92, "transform:scale(1);opacity:0"), (100, "transform:scale(1);opacity:0")])
    )
    glow = ' filter="url(#bl)"' if p["glow"] else ""
    packet = (
        f'<g class="dr"><rect x="{cx - 1}" y="-18" width="2" height="22" fill="url(#dg)"/>'
        f'<circle cx="{cx}" cy="4" r="2.6" fill="{p["cyan_soft"]}"{glow}/></g>'
    )
    ripple = f'<ellipse class="rp" cx="{cx}" cy="{ys[-1]}" rx="120" ry="9" fill="none" stroke="{p["cyan"]}" stroke-width="1.2"/>'

    name = DISPLAY.shape("SAGAR TAILOR")
    nm_size = 17
    nw = ts.measure(DISPLAY, name, nm_size, 0.06)
    tail = "  ·  BUILDS THE LAYER UNDERNEATH"
    tw = ts.measure(MONO, MONO.shape(tail), 11.5, 0.12)
    start = cx - (nw + tw) / 2
    nm, _ = ts.run(DISPLAY, name, start, 122, nm_size, p["ink_hi"], tracking=0.06)
    tl, _ = ts.text(MONO, tail, start + nw, 121.5, 11.5, p["ink_low"], tracking=0.12)
    css.append(".cr{animation:cr 1.05s step-end infinite}" + keyframes("cr", [(0, "opacity:1"), (50, "opacity:0")]))
    cursor = f'<rect class="cr" x="{fmt(start + nw + tw + 8)}" y="110" width="7" height="13" fill="{p["cyan"]}"/>'

    defs = (
        f'<linearGradient id="ff" gradientUnits="userSpaceOnUse" x1="{x0}" x2="{x1}">'
        f'<stop offset="0" stop-color="{p["blue"]}" stop-opacity="0"/><stop offset=".2" stop-color="{p["blue"]}"/>'
        f'<stop offset=".5" stop-color="{p["cyan"]}"/><stop offset=".8" stop-color="{p["blue"]}"/>'
        f'<stop offset="1" stop-color="{p["blue"]}" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="dg" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{p["cyan"]}" stop-opacity="0"/><stop offset="1" stop-color="{p["cyan"]}"/></linearGradient>'
        + (glow_filter("bl", 2) if p["glow"] else "")
    )
    body = "".join(lines) + ripple + packet + nm + tl + cursor
    return document(W, H, body, title="Sagar Tailor — builds the layer underneath", css="".join(css), defs=ts.defs() + defs)


# ==========================================================================
# TOOLKIT STRIP — recognisable logos, served from this repository
#
# The icons are skill-icons (MIT, github.com/tandpfun/skill-icons), fetched
# once at build time and committed, so the README depends on no third-party
# image service at view time. The list is the "shipped" tier of the toolkit.
# ==========================================================================

TOOLKIT = "go,py,ts,fastapi,postgres,docker,githubactions,nextjs,react,threejs,tailwind,linux"


def toolkit_strip() -> None:
    import urllib.parse
    import urllib.request

    for mode in PALETTES:
        query = urllib.parse.urlencode({"i": TOOLKIT, "theme": mode})
        req = urllib.request.Request(f"https://skillicons.dev/icons?{query}", headers={"User-Agent": "Mozilla/5.0 (profile-build)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            svg = r.read().decode("utf-8")
        if "<script" in svg or "http://" in svg.replace("http://www.w3.org", ""):
            raise SystemExit("unexpected content in the toolkit strip")
        write(os.path.join(ASSETS, "toolkit", f"icons-{mode}.svg"), svg.strip() + "\n")


def main() -> None:
    toolkit_strip()
    # The telemetry workflow draws its text from these tables, so it never
    # needs a font library on the runner.
    for font, weight in ((MONO, 500), (MONO_BOLD, 700)):
        name = f"jetbrains-mono-{weight}"
        font.to_table(fonts.MONO_CHARSET, name).dump(os.path.join(HERE, "glyphs", f"{name}.json"))
    emit("footer", "footer", footer)
    emit("projects", "deadlockd", project_deadlockd)
    emit("projects", "akash", project_akash)
    emit("projects", "portfolio", project_portfolio)
    emit("system", "core", system_core)
    emit("hero", "name", hero)
    emit("hero", "headline", headline)
    for stem, index, label, primary in (
        ("github", "01", "GITHUB", False),
        ("portfolio", "02", "PORTFOLIO", True),
        ("linkedin", "03", "LINKEDIN", False),
    ):
        write(os.path.join(ASSETS, "links", f"{stem}.svg"), chip(index, label, primary))
    for depth, (index, name, _) in enumerate(STRATA):
        emit("dividers", f"stratum-{index}-{name.lower()}", stratum(depth))
    emit("dividers", "signal", divider_signal)
    emit("dividers", "wave", divider_wave)
    emit("dividers", "scan", divider_scan)
    emit("dividers", "pulse", divider_pulse)
    emit("dividers", "orbit", divider_orbit)


if __name__ == "__main__":
    main()
