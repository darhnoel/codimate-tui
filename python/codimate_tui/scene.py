"""What one moment looks like: named boxes and text on a grid of terminal cells.

The name of a node is its identity. Between two moments, nodes are paired by
name and whatever differs becomes movement — so a name that follows a *thing*
makes it travel, and a name that follows a *place* makes it change in place.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
from typing import Any, Optional, Union

Color = Union[str, "tuple[int, int, int]"]
Name = Union[str, int, "tuple[Any, ...]"]

PALETTE: "dict[str, tuple[int, int, int]]" = {
    "bg": (22, 24, 30),
    "fg": (220, 223, 228),
    "muted": (92, 99, 112),
    "dim": (44, 48, 58),
    "blue": (66, 135, 245),
    "orange": (240, 150, 50),
    "green": (80, 200, 120),
    "red": (230, 80, 80),
    "yellow": (235, 200, 80),
    "purple": (170, 110, 230),
}


def rgb(color: Color) -> "tuple[int, int, int]":
    """A palette name (``"blue"``), ``"#rrggbb"``, or an ``(r, g, b)`` tuple."""
    if isinstance(color, tuple):
        if len(color) != 3 or not all(isinstance(c, int) and 0 <= c <= 255 for c in color):
            raise ValueError(f"colour {color!r} must be three ints from 0 to 255")
        return color
    if isinstance(color, str):
        if color in PALETTE:
            return PALETTE[color]
        if color.startswith("#") and len(color) == 7:
            try:
                return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
            except ValueError:
                pass
    names = ", ".join(PALETTE)
    raise ValueError(f"unknown colour {color!r}: use one of {names}, '#rrggbb', or (r, g, b)")


def mix(a: Color, b: Color, t: float) -> "tuple[int, int, int]":
    """The colour ``t`` of the way from ``a`` to ``b`` (``t`` clamped to 0..1)."""
    t = min(max(t, 0.0), 1.0)
    ca, cb = rgb(a), rgb(b)
    return tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))  # type: ignore[return-value]


def row(n: int, w: float, gap: float, canvas_w: float) -> "list[float]":
    """X positions for ``n`` items ``w`` wide with ``gap`` between, centred on the canvas."""
    if n <= 0:
        return []
    total = n * w + (n - 1) * gap
    x0 = (canvas_w - total) // 2
    return [x0 + i * (w + gap) for i in range(n)]


def _has_khmer(text: str) -> bool:
    return any("\u1780" <= ch <= "\u17ff" or "\u19e0" <= ch <= "\u19ff" for ch in text)


@functools.lru_cache(maxsize=None)
def font_file(font: str) -> str:
    """A font file path for ``font``: either a path already, or a fontconfig name
    such as ``"Noto Sans Khmer:bold"`` (looked up with ``fc-match``)."""
    if os.path.isfile(font):
        return font
    if "/" in font or font.lower().endswith((".ttf", ".otf", ".ttc")):
        raise ValueError(f"font file {font!r} not found")
    if shutil.which("fc-match") is None:
        raise ValueError(f"font {font!r}: not a file, and fc-match isn't available to look it up")
    found = subprocess.run(
        ["fc-match", "-f", "%{family}\n%{file}", font], capture_output=True, text=True, check=False
    ).stdout.split("\n")
    family, path = (found + ["", ""])[:2]
    # fc-match always answers with *some* font; only accept the one asked for
    # (generic names like "sans-serif" stand for whatever the system prefers).
    wanted = font.split(":")[0].strip().lower()
    generic = wanted in ("sans-serif", "sans", "serif", "monospace", "mono")
    families = [f.strip().lower() for f in family.split(",")]
    if not path or not os.path.isfile(path) or not (generic or wanted in families):
        raise ValueError(f"font {font!r} not found (closest installed match: {family or 'none'})")
    return path


Fonts = Union[str, "list[str]", "tuple[str, ...]"]


def default_fonts(text: str) -> "list[str]":
    """Bold Noto Sans Khmer and bold sans-serif, Khmer first when the text has
    Khmer in it (the first font sets the line's size and baseline)."""
    khmer, latin = "Noto Sans Khmer:bold", "sans-serif:bold"
    return [khmer, latin] if _has_khmer(text) else [latin, khmer]


def _font_files(text: str, font: "Optional[Fonts]") -> "list[str]":
    fonts = default_fonts(text) if font is None else [font] if isinstance(font, str) else list(font)
    if not fonts:
        raise ValueError("a title needs at least one font")
    return [font_file(f) for f in fonts]


def measure(text: Any, size: float = 6, font: "Optional[Fonts]" = None) -> float:
    """How many cells wide ``text`` is as a :meth:`Scene.title` of this size and
    font — for laying titles out side by side."""
    from . import _codimate_tui

    text = str(text)
    return _codimate_tui.measure(_font_files(text, font), text, float(size))


def _name(name: Name) -> str:
    # ("tok", 3) -> "tok/3": tuples make place- or thing-keyed names easy to build.
    if isinstance(name, tuple):
        return "/".join(str(p) for p in name)
    return str(name)


class Node:
    """A handle on one node; every method returns the handle so calls chain."""

    __slots__ = ("_d",)

    def __init__(self, d: "dict[str, Any]") -> None:
        self._d = d

    def fg(self, color: Color) -> "Node":
        self._d["fg"] = rgb(color)
        return self

    def fill(self, color: Color) -> "Node":
        self._d["fill"] = rgb(color)
        return self

    def bold(self, on: bool = True) -> "Node":
        self._d["bold"] = bool(on)
        return self

    def opacity(self, value: float) -> "Node":
        self._d["opacity"] = min(max(float(value), 0.0), 1.0)
        return self

    def z(self, value: int) -> "Node":
        """Higher draws on top. Moving nodes are lifted above still ones anyway."""
        self._d["z"] = int(value)
        return self

    def label(self, value: Any) -> "Node":
        """A box's centred label, or a text node's text."""
        self._d["text"] = str(value)
        return self


class Scene:
    """One still picture. Coordinates are terminal cells; (0, 0) is top-left."""

    def __init__(self) -> None:
        self._nodes: "dict[str, dict[str, Any]]" = {}

    def rect(self, name: Name, x: float, y: float, w: float, h: float) -> Node:
        """A diagram box. At least 2×2 gets a rounded border; smaller is solid."""
        return self._add(name, "box", x, y, w, h, "")

    def block(self, name: Name, x: float, y: float, w: float, h: float) -> Node:
        """A solid rectangle with no outline, coloured by ``fill`` (or ``fg``).

        Solid shapes have twice the vertical detail: ``y`` and ``h`` count in
        half cells (``y=2.5`` starts halfway down row 2), so a cell holds two
        square pixels — the building block of flat, cartoon-style pictures.
        """
        return self._add(name, "block", x, y, w, h, "")

    def oval(self, name: Name, x: float, y: float, w: float, h: float) -> Node:
        """A solid ellipse filling the ``w`` × ``h`` rectangle at (``x``, ``y``).

        Same half-cell detail as :meth:`block`. A cell is about twice as tall as
        it is wide, so a circle is ``w`` = 2 × ``h`` (e.g. ``oval(n, x, y, 8, 4)``).
        """
        return self._add(name, "oval", x, y, w, h, "")

    def text(self, name: Name, x: float, y: float, text: Any) -> Node:
        """One line of text (single-width characters only)."""
        return self._add(name, "text", x, y, 0.0, 0.0, str(text))

    def title(
        self, name: Name, x: float, y: float, text: Any, size: float = 6, font: "Optional[Fonts]" = None
    ) -> Node:
        """Big text drawn as pixels, ``size`` cells tall, **centred on** ``x``.

        The text is shaped with a real font, so scripts the terminal may get wrong
        (Khmer stacks consonants and reorders vowels) come out right. ``font`` is a
        file path or a fontconfig name like ``"Noto Sans Khmer:bold"``, or a list
        of them: each letter uses the first font that has it, so mixed Khmer and
        English works. By default: bold Noto Sans Khmer plus bold sans-serif.

        ``fg`` colours it; add ``fill`` for a left-to-right gradient from ``fg``
        to ``fill``. Fades blend with whatever is underneath.
        """
        text = str(text)
        node = self._add(name, "title", x, y, 0.0, size, text)
        node._d["font"] = _font_files(text, font)
        return node

    def _add(self, name: Name, kind: str, x: float, y: float, w: float, h: float, text: str) -> Node:
        key = _name(name)
        if key in self._nodes:
            raise ValueError(
                f"duplicate node name {key!r} in one Scene: names are identity and must be unique"
            )
        d = {
            "name": key,
            "kind": kind,
            "x": float(x),
            "y": float(y),
            "w": float(w),
            "h": float(h),
            "text": text,
            "fg": PALETTE["fg"],
            "fill": None,
            "bold": False,
            "opacity": 1.0,
            "z": 0,
            "font": None,
        }
        self._nodes[key] = d
        return Node(d)

    def _payload(self) -> "list[dict[str, Any]]":
        return list(self._nodes.values())
