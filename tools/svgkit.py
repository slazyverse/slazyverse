"""Shared primitives for the profile's generated SVG assets.

Standard library only: the contribution-telemetry workflow imports this module
on a bare GitHub runner without installing anything.

Two rules hold for every asset built on top of it:

* Text is drawn as outlined glyphs, never as <text>. An SVG loaded through an
  <img> tag cannot fetch web fonts, so live text would fall back to whatever
  the viewer's system has. Outlines render identically everywhere.
* Motion is CSS, never script. GitHub serves README images as <img>, which
  runs CSS animations but no JavaScript. Every animated asset's un-animated
  state is also a complete picture, so a first frame is never half-drawn.
  Motion deliberately does not stop for prefers-reduced-motion: Windows sets
  that flag whenever "Animation effects" is off, which on many machines is a
  performance default rather than an accessibility choice, and the profile's
  owner wants the motion seen. The motion is slow, small and never flashes.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
GLYPH_DIR = os.path.join(HERE, "glyphs")

# --------------------------------------------------------------------------
# Design tokens. One restrained palette, two grounds.
#
# ink    — text, from primary to metadata
# hair   — the structural line; there are no shadows or heavy borders
# cyan   — the signal: anything moving, live or "this is the subject"
# blue   — the machine talking about itself: structure, secondary data
# violet — used sparingly, for a state change (a deadlock, a highlight)
# --------------------------------------------------------------------------

PALETTES = {
    "dark": {
        "ink_hi": "#e9eef6",
        "ink": "#c3ccd9",
        "ink_mid": "#98a5b7",
        "ink_low": "#7c8899",
        "hair": "#e8edf4",
        "hair_a": 0.12,
        "fill": "#0d1117",
        "cyan": "#45d7ff",
        "cyan_soft": "#a8f0ff",
        "blue": "#58a6ff",
        "violet": "#a78bfa",
        "glow": True,
    },
    "light": {
        "ink_hi": "#1f2328",
        "ink": "#2f363d",
        "ink_mid": "#59636e",
        "ink_low": "#6e7781",
        "hair": "#1f2328",
        "hair_a": 0.16,
        "fill": "#ffffff",
        "cyan": "#0a7ea4",
        "cyan_soft": "#0e7490",
        "blue": "#0969da",
        "violet": "#8250df",
        "glow": False,
    },
}



def fmt(v: float) -> str:
    """Compact number formatting for SVG attributes."""
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# Glyph tables and text runs
# --------------------------------------------------------------------------


@dataclass
class GlyphTable:
    """A font reduced to what an SVG needs: advances and outline paths.

    Paths are in font units with y pointing up; a run flips them with a
    negative y-scale, so the table never needs to be rewritten per size.
    """

    name: str
    upm: int
    cap_height: int
    glyphs: dict  # key -> (advance, path d)
    cmap: dict = field(default_factory=dict)  # char -> key

    @classmethod
    def load(cls, name: str) -> "GlyphTable":
        with open(os.path.join(GLYPH_DIR, f"{name}.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        glyphs = {k: (v[0], v[1]) for k, v in raw["glyphs"].items()}
        return cls(name, raw["upm"], raw["capHeight"], glyphs, {c: c for c in glyphs})

    def dump(self, path: str) -> None:
        payload = {
            "upm": self.upm,
            "capHeight": self.cap_height,
            "glyphs": {k: [a, d] for k, (a, d) in sorted(self.glyphs.items())},
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")

    def shape(self, text: str):
        """Map characters straight to glyphs — correct for a monospace face."""
        out = []
        for ch in text:
            key = self.cmap.get(ch) or self.cmap.get("?")
            adv, _ = self.glyphs[key]
            out.append((key, adv, 0))
        return out


class Typesetter:
    """Collects the glyphs an SVG uses and emits each outline once.

    A run is a <g> transformed to the requested size, holding one <use> per
    glyph; the outline lives in <defs>. Repeated letters cost a few bytes.
    """

    def __init__(self):
        self._defs: dict[str, str] = {}
        self._ids: dict[tuple, str] = {}

    def _ref(self, table, key) -> str:
        ident = (table.name, key)
        if ident not in self._ids:
            gid = f"{table.name[:2]}{len(self._ids):x}"
            self._ids[ident] = gid
            d = table.glyphs[key][1]
            self._defs[gid] = f'<path id="{gid}" d="{d}"/>' if d else ""
        return self._ids[ident]

    def measure(self, table, shaped, size, tracking=0.0) -> float:
        units = sum(adv for _, adv, _ in shaped)
        return units * size / table.upm + tracking * size * max(len(shaped) - 1, 0)

    def run(
        self,
        table,
        shaped,
        x,
        y,
        size,
        fill,
        anchor="start",
        tracking=0.0,
        opacity=None,
        cls=None,
        glyph_cls=None,
        attrs="",
    ):
        """Place a shaped run with its baseline at (x, y).

        `tracking` is extra space per glyph in em. `glyph_cls(i)` may return a
        class for the i-th glyph, which is how typing effects address letters.
        Returns (svg, width).
        """
        width = self.measure(table, shaped, size, tracking)
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        s = size / table.upm
        track_units = tracking * table.upm
        parts, pen = [], 0.0
        for i, (key, adv, xoff) in enumerate(shaped):
            gid = self._ref(table, key)
            if self._defs[gid]:
                c = glyph_cls(i) if glyph_cls else None
                ca = f' class="{c}"' if c else ""
                parts.append(f'<use href="#{gid}" x="{fmt(pen + xoff)}"{ca}/>')
            pen += adv + track_units
        op = f' opacity="{fmt(opacity)}"' if opacity is not None else ""
        cl = f' class="{cls}"' if cls else ""
        svg = (
            f'<g transform="translate({fmt(x)} {fmt(y)}) scale({s:.5f} {-s:.5f})"'
            f' fill="{fill}"{op}{cl}{attrs}>{"".join(parts)}</g>'
        )
        return svg, width

    def text(self, table, text, x, y, size, fill, **kw):
        return self.run(table, table.shape(text), x, y, size, fill, **kw)

    def defs(self) -> str:
        return "".join(v for v in self._defs.values() if v)


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


def document(width, height, body, *, title, css="", defs=""):
    style = f"<style>{css}</style>" if css else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" height="{fmt(height)}"'
        f' viewBox="0 0 {fmt(width)} {fmt(height)}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{style}<defs>{defs}</defs>{body}</svg>\n"
    )


def write(path: str, svg: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)


def glow_filter(fid: str, std: float) -> str:
    """A soft bloom: the source blurred and laid under itself."""
    return (
        f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%">'
        f'<feGaussianBlur stdDeviation="{fmt(std)}" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        f"</filter>"
    )


def keyframes(name: str, stops) -> str:
    """stops: iterable of (percent, css declarations)."""
    body = "".join(f"{fmt(p)}%{{{decl}}}" for p, decl in stops)
    return f"@keyframes {name}{{{body}}}"


def corner_brackets(x, y, w, h, color, alpha, length=12, stroke=1):
    """The portfolio's panel device: four corner marks instead of a box."""
    L = length
    d = (
        f"M{fmt(x)} {fmt(y + L)}V{fmt(y)}H{fmt(x + L)}"
        f"M{fmt(x + w - L)} {fmt(y)}H{fmt(x + w)}V{fmt(y + L)}"
        f"M{fmt(x + w)} {fmt(y + h - L)}V{fmt(y + h)}H{fmt(x + w - L)}"
        f"M{fmt(x + L)} {fmt(y + h)}H{fmt(x)}V{fmt(y + h - L)}"
    )
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="{fmt(alpha)}"'
        f' stroke-width="{fmt(stroke)}"/>'
    )


def ellipse_arclength_samples(cx, cy, a, b, n, start=0.0):
    """Points on an ellipse spaced evenly by arc length, not by angle.

    Anything that travels an orbit at constant speed — a vehicle, and the
    light trail drawn by a dash offset — has to agree on arc length, or the
    two drift apart at the ends of the ellipse where curvature is highest.
    Returns [(x, y, theta)] of length n, plus the total perimeter.
    """
    fine = 4096
    thetas = [start + 2 * math.pi * i / fine for i in range(fine + 1)]
    pts = [(cx + a * math.cos(t), cy + b * math.sin(t)) for t in thetas]
    cum = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
    total = cum[-1]
    out, j = [], 0
    for i in range(n):
        target = total * i / n
        while cum[j + 1] < target:
            j += 1
        f = (target - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        t = thetas[j] + f * (thetas[j + 1] - thetas[j])
        out.append((cx + a * math.cos(t), cy + b * math.sin(t), t))
    return out, total
