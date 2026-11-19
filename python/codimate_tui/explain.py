"""From an algorithm run to something you can play.

Four pieces, each in one place:

    algorithm   your code, calling tracer.emit(name, state) after each step
    view        a function from one moment (Frame) to one Scene
    motion      Rule("tok/*", arc=2) — how matching nodes travel
    timing      Timing(events={"push": 0.8}) — seconds per event

The view runs once per event, not once per frame; the Rust engine does every
frame. Everything is handed over in one call.
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar

from .scene import Scene

S = TypeVar("S")


PIXELS = ("sextant", "quad", "half")
"""How finely solid shapes and titles are drawn, finest first: pixels per cell
2×3 (sextant blocks), 2×2 (quadrant blocks) or 1×2 (half blocks). Finer needs a
terminal that draws the characters; half works everywhere."""


@dataclass(frozen=True)
class Event:
    name: str
    caption: str = ""


@dataclass(frozen=True)
class Frame(Generic[S]):
    """One moment handed to the view: the state, and the event that produced it
    (``None`` for the starting state)."""

    state: S
    event: Optional[Event]


class Tracer(Generic[S]):
    """Records your algorithm. Call :meth:`emit` *after* changing your data; the
    tracer keeps its own copy, so later changes don't rewrite history."""

    def __init__(self, state: S) -> None:
        self.initial: S = copy.deepcopy(state)
        self.steps: "list[tuple[Event, S]]" = []

    def emit(self, name: str, state: S, *, say: str = "") -> None:
        """Record that ``name`` just happened. ``say`` is the caption shown while
        it plays."""
        self.steps.append((Event(name, say), copy.deepcopy(state)))


@dataclass
class Timing:
    """Seconds per event, by name. ``opening`` and ``closing`` hold on the first
    and last pictures."""

    default: float = 0.7
    events: "dict[str, float] | None" = None
    opening: float = 0.8
    closing: float = 1.5

    def for_event(self, name: str) -> float:
        return (self.events or {}).get(name, self.default)


@dataclass(frozen=True)
class Rule:
    """How nodes whose name matches ``pattern`` (``*`` = anything) move. First
    match wins. A rule never makes a still node move.

    ``arc``   travel on a hop ``arc`` cells high instead of a straight line.
    ``pace``  ``"smooth"`` (default) eases in and out, so things settle at every
              event. ``"linear"`` keeps constant speed — for things mid-journey at
              every event, like a game loop or a scrolling camera.
    """

    pattern: str
    arc: Optional[float] = None
    pace: str = "smooth"

    def __post_init__(self) -> None:
        if self.pace not in ("smooth", "linear"):
            raise ValueError(f"pace must be 'smooth' or 'linear', got {self.pace!r}")

    def _payload(self) -> "dict[str, Any]":
        arc = None if self.arc is None else float(self.arc)
        return {"pattern": self.pattern, "arc": arc, "pace": self.pace}


class Explanation:
    """A finished explanation, ready to :meth:`play`."""

    def __init__(
        self,
        scenes: "list[Scene]",
        events: "list[Event]",
        *,
        title: str,
        canvas: "tuple[int, int]",
        motion: "list[Rule]",
        timing: Timing,
        pixels: str = "sextant",
        fit: bool = False,
    ) -> None:
        if pixels not in PIXELS:
            raise ValueError(f"pixels must be one of {', '.join(PIXELS)}, got {pixels!r}")
        self.title = title
        self.canvas = canvas
        self.pixels = pixels
        self.fit = fit
        self.motion = motion
        # Holds are beats from a Scene to itself: no special case in the engine.
        self._scenes = [scenes[0], *scenes, scenes[-1]]
        self._beats = [{"name": "start", "caption": "", "duration": float(timing.opening)}]
        for e in events:
            self._beats.append(
                {"name": e.name, "caption": e.caption, "duration": float(timing.for_event(e.name))}
            )
        self._beats.append({"name": "end", "caption": "", "duration": float(timing.closing)})

    @property
    def duration(self) -> float:
        return sum(b["duration"] for b in self._beats)

    def timeline(self) -> "list[tuple[float, float, str, str]]":
        """Every beat as ``(start, duration, name, caption)``."""
        out, start = [], 0.0
        for b in self._beats:
            out.append((start, b["duration"], b["name"], b["caption"]))
            start += b["duration"]
        return out

    def frame(
        self, seconds: float, *, color: bool = False, pixels: Optional[str] = None, scale: float = 1.0
    ) -> str:
        """The picture at ``seconds`` as text, with its caption underneath. For
        checking a moment without opening the player. ``color=True`` adds 24-bit
        colour codes — needed to see solid shapes (``block``/``oval``)."""
        from . import _codimate_tui

        text, caption = _codimate_tui.frame_text(
            self._payload_scenes(),
            self._beats,
            self._payload_rules(),
            self.canvas,
            float(seconds),
            color,
            pixels or self.pixels,
            float(scale),
        )
        return f"{text}-- {seconds:.2f}s · {caption}\n"

    def play(self, start_at: float = 0.0) -> float:
        """Open the player in this terminal. Returns the time you quit at.

        Also reads the command line, so every explainer script gets these free:

            python my_explainer.py --list        # print the timeline
            python my_explainer.py --at 5.85     # print one frame as text
            python my_explainer.py --at 5.85 --color   # ... in colour
            python my_explainer.py --pixels quad       # coarser blocks, if your
                                                       # terminal lacks sextants
            python my_explainer.py --fit               # scale to fill the terminal
            python my_explainer.py --at 5.85 --color --scale 2   # one frame, twice as big
        """
        args = sys.argv[1:]
        pixels = self.pixels
        fit = self.fit or "--fit" in args
        args = [a for a in args if a != "--fit"]
        if "--pixels" in args:
            i = args.index("--pixels")
            if i + 1 >= len(args) or args[i + 1] not in PIXELS:
                raise SystemExit(f"usage: --pixels {{{'|'.join(PIXELS)}}}")
            pixels = args[i + 1]
            del args[i : i + 2]
        if args[:1] == ["--list"]:
            for start, dur, name, caption in self.timeline():
                print(f"{start:6.2f}s {dur:5.2f}s  {name:<10} {caption}")
            return 0.0
        if args[:1] == ["--at"]:
            if len(args) < 2:
                raise SystemExit("usage: --at <seconds>")
            seconds = float(args[1])
            scale = 1.0
            if "--scale" in args[2:]:
                k = args.index("--scale")
                try:
                    scale = float(args[k + 1])
                except (IndexError, ValueError):
                    raise SystemExit("usage: --scale <number>") from None
            print(self.frame(seconds, color="--color" in args[2:], pixels=pixels, scale=scale), end="")
            return seconds

        from . import _codimate_tui

        return _codimate_tui.play(
            self._payload_scenes(),
            self._beats,
            self._payload_rules(),
            self.title,
            self.canvas,
            float(start_at),
            pixels,
            fit,
        )

    def _payload_scenes(self) -> "list[list[dict[str, Any]]]":
        return [s._payload() for s in self._scenes]

    def _payload_rules(self) -> "list[dict[str, Any]]":
        return [r._payload() for r in self.motion]


def explain(
    trace: Tracer[S],
    view: Callable[[Frame[S]], Scene],
    *,
    title: str = "codimate-tui",
    canvas: "tuple[int, int]" = (60, 16),
    motion: Iterable[Rule] = (),
    timing: Optional[Timing] = None,
    pixels: str = "sextant",
    fit: bool = False,
) -> Explanation:
    """Run ``view`` once per recorded moment and combine everything into an
    :class:`Explanation`."""

    def draw(frame: Frame[S]) -> Scene:
        scene = view(frame)
        if not isinstance(scene, Scene):
            what = frame.event.name if frame.event else "the starting state"
            raise TypeError(f"view must return a Scene, got {type(scene).__name__} for {what}")
        return scene

    scenes = [draw(Frame(trace.initial, None))]
    scenes += [draw(Frame(state, event)) for event, state in trace.steps]
    return Explanation(
        scenes,
        [event for event, _ in trace.steps],
        title=title,
        canvas=canvas,
        motion=list(motion),
        timing=timing or Timing(),
        pixels=pixels,
        fit=fit,
    )
