"""Font handling for the asset build. Needs fontTools and uharfbuzz.

The typefaces are the portfolio's own — Archivo for display, JetBrains Mono for
anything machine-derived — fetched from slazyverse/portfolio so the two sites
cannot drift apart. Both are SIL Open Font License 1.1.

Only the build needs this module. The telemetry workflow reads the glyph table
this module writes to tools/glyphs/, so CI never installs a font library.
"""

from __future__ import annotations

import io
import os
import urllib.request

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from svgkit import HERE, GlyphTable

CACHE = os.path.join(HERE, ".cache")
SOURCE = "https://raw.githubusercontent.com/slazyverse/portfolio/main/public/fonts/{}"

# Characters the telemetry job may need to draw. Kept explicit so the JSON
# table stays small and reviewable.
MONO_CHARSET = (
    "".join(chr(c) for c in range(32, 127)) + "·→↗↘—–●◆■□▸×≤≥±µ²•"
)


def _fetch(filename: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, filename)
    if not os.path.exists(path):
        with urllib.request.urlopen(SOURCE.format(filename), timeout=60) as r:
            data = r.read()
        with open(path, "wb") as fh:
            fh.write(data)
    return path


def _path(glyphset, name) -> str:
    pen = SVGPathPen(glyphset, ntos=lambda v: str(round(v)))
    glyphset[name].draw(pen)
    return pen.getCommands()


class ShapedFont:
    """A variable font pinned to one instance and shaped with HarfBuzz.

    Presents the same interface as GlyphTable, so a Typesetter can set either.
    """

    def __init__(self, filename: str, axes: dict, name: str, features=None):
        vf = TTFont(_fetch(filename))
        self.ttf = instancer.instantiateVariableFont(vf, axes)
        buf = io.BytesIO()
        self.ttf.save(buf)
        self.hb_font = hb.Font(hb.Face(buf.getvalue()))
        self.glyphset = self.ttf.getGlyphSet()
        self.order = self.ttf.getGlyphOrder()
        self.name = name
        self.upm = self.ttf["head"].unitsPerEm
        self.cap_height = self.ttf["OS/2"].sCapHeight
        self.features = features or {"kern": True, "liga": False, "calt": False}
        self.glyphs: dict = {}
        self.cmap = {}

    def _glyph(self, gid: int) -> str:
        key = self.order[gid]
        if key not in self.glyphs:
            adv = self.ttf["hmtx"][key][0]
            self.glyphs[key] = (adv, _path(self.glyphset, key))
        return key

    def shape(self, text: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, self.features)
        out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            key = self._glyph(info.codepoint)
            out.append((key, pos.x_advance, pos.x_offset))
        return out

    def to_table(self, charset: str, name: str) -> GlyphTable:
        """Freeze a per-character table (monospace faces only)."""
        cmap = self.ttf.getBestCmap()
        glyphs = {}
        for ch in charset:
            gname = cmap.get(ord(ch))
            if gname is None:
                continue
            glyphs[ch] = (self.ttf["hmtx"][gname][0], _path(self.glyphset, gname))
        return GlyphTable(name, self.upm, self.cap_height, glyphs, {c: c for c in glyphs})


def display(weight=800, width=112) -> ShapedFont:
    return ShapedFont("Archivo.ttf", {"wght": weight, "wdth": width}, f"ar{weight}{width}")


def mono(weight=500) -> ShapedFont:
    return ShapedFont("JetBrainsMono.ttf", {"wght": weight}, f"jb{weight}")
