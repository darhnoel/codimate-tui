"""codimate-tui — explain an algorithm as an animation that plays in the terminal.

    import codimate_tui as ct

    tr = ct.Tracer(state)
    ... your algorithm, calling tr.emit("push", state, say="...") ...

    def view(frame):
        s = ct.Scene()
        s.rect(("tok", i), x, y, 3, 3).label("(").fill("blue")
        return s

    ct.explain(tr, view, motion=[ct.Rule("tok/*", arc=2)]).play()
"""

from .explain import Event, Explanation, Frame, Rule, Timing, Tracer, explain
from .scene import PALETTE, Node, Scene, font_file, measure, mix, rgb, row

__all__ = [
    "PALETTE",
    "Event",
    "Explanation",
    "Frame",
    "Node",
    "Rule",
    "Scene",
    "Timing",
    "Tracer",
    "explain",
    "font_file",
    "measure",
    "mix",
    "rgb",
    "row",
]
