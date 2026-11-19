"""A tiny cartoon: Bit the robot meets a gap, has an idea, builds a bridge.

Not an algorithm this time — the "algorithm" is a story script, and every
event is a beat of the story. The same engine ideas do all the work:

- Bit is several text nodes ("bit/head", "bit/body", "bit/legs") drawn from one
  position, so they travel together as one character.
- Each plank is named by *thing* ("plank/2"), so it hops from the pile to its
  place in the gap on an arc.
- The face and legs are just text that switches mid-move, which reads as an
  expression change and a step.
- The speech bubble fades in when Bit talks and out when Bit stops.

    python examples/cartoon.py
"""

from dataclasses import dataclass

import codimate_tui as ct

W, H = 72, 18
GROUND_Y = 14
GAP_X, GAP_W = 30, 12
PLANK_W = 3
N_PLANKS = GAP_W // PLANK_W
WOOD = (150, 100, 60)
SKY_DOT = (60, 66, 84)


@dataclass
class State:
    x: float = 8  # Bit's left edge
    lift: float = 0  # how high Bit is off the ground (jumping)
    face: str = "[o_o]"
    arms: str = "/|#|\\"
    step: int = 0  # alternates the legs
    say: str = ""  # speech bubble text ("" = no bubble)
    idea: bool = False
    planks: int = 0  # planks laid in the gap
    cloud: float = 46
    party: bool = False


def story() -> ct.Tracer:
    st = State()
    tr = ct.Tracer(st)

    def beat(name: str, caption: str, **changes) -> None:
        for k, v in changes.items():
            setattr(st, k, v)
        st.cloud -= 1.5  # the sky keeps drifting, whatever Bit does
        tr.emit(name, st, say=caption)

    def walk(to: float, caption: str) -> None:
        while st.x < to:
            beat("walk", caption, x=min(st.x + 4, to), step=st.step + 1, say="")

    beat("hello", "Meet Bit.", face="[^_^]", say="hi!")
    beat("hum", "Bit is heading for the hills.", say="")
    walk(GAP_X - 6, "Bit is heading for the hills.")
    beat("uh oh", "Uh oh.", face="[O_O]", say="a gap!?")
    beat("think", "Bit thinks...", face="[-_-]", say="hmm...")
    beat("idea", "...and has an idea.", face="[^o^]", say="planks!", idea=True)
    beat("work", "Bit gets to work.", face="[>_<]", say="", idea=False)
    for i in range(N_PLANKS):
        beat("plank", f"Plank {i + 1} of {N_PLANKS}.", planks=i + 1)
    beat("test", "Bit checks the bridge.", face="[o_o]", say="safe?")
    walk(GAP_X + GAP_W + 4, "Across!")
    beat("jump", "Hooray!", face="[^O^]", arms="\\|#|/", lift=3, say="")
    beat("land", "Hooray!", lift=0)
    beat("ta-da", "The end.", face="[^_^]", say="ta-da!", party=True)
    return tr


# Deterministic confetti: (x, y, char, colour).
CONFETTI = [
    (6, 3, "*", "yellow"), (14, 6, "+", "red"), (22, 2, "*", "blue"), (31, 5, "o", "green"),
    (38, 2, "+", "purple"), (47, 7, "*", "orange"), (55, 3, "o", "red"), (63, 6, "*", "yellow"),
    (11, 9, "o", "purple"), (26, 8, "+", "orange"), (59, 9, "+", "blue"), (68, 2, "o", "green"),
]


def view(f: ct.Frame) -> ct.Scene:
    st = f.state
    s = ct.Scene()

    # Sky: a few fixed dots, a sun, a drifting cloud.
    for i, (x, y) in enumerate([(4, 1), (19, 4), (35, 1), (52, 5), (66, 8)]):
        s.text(("sky", i), x, y, ".").fg(SKY_DOT)
    sun = "yellow" if st.party else (200, 170, 70)
    s.text("sun/top", 62, 1, "\\ | /").fg(sun)
    s.text("sun/mid", 62, 2, "- O -" if not st.party else "- ^ -").fg(sun).bold()
    s.text("sun/bot", 62, 3, "/ | \\").fg(sun)
    s.text("cloud/top", st.cloud + 1, 3, ".--.").fg("muted")
    s.text("cloud/bot", st.cloud, 4, "(____)").fg("muted")

    # Ground, with a gap in it.
    for name, x0, x1 in (("left", 0, GAP_X), ("right", GAP_X + GAP_W, W)):
        s.rect(("grass", name), x0, GROUND_Y, x1 - x0, 1).fill("green")
        for d in range(3):  # 1-high strips stay borderless, so the dirt reads as solid
            s.rect(("dirt", name, d), x0, GROUND_Y + 1 + d, x1 - x0, 1).fill((70, 55, 40))
    s.text("gap", GAP_X + 3, GROUND_Y + 2, "~ ~ ~").fg("blue")

    # Planks: in the pile until laid, then in the gap. Named by *thing*, so each hops.
    for i in range(N_PLANKS):
        if i < st.planks:
            x, y = GAP_X + i * PLANK_W, GROUND_Y
        else:
            x, y = 1, GROUND_Y - 1 - (N_PLANKS - 1 - i)
        s.rect(("plank", i), x, y, PLANK_W, 1).fill(WOOD).fg((90, 60, 35)).label("=").z(1)

    # Bit: three lines drawn from one position, so they move as one character.
    top = GROUND_Y - 3 - st.lift
    legs = " / \\ " if st.step % 2 else " | | "
    s.text("bit/head", st.x, top, st.face).fg("fg").bold().z(3)
    s.text("bit/body", st.x, top + 1, st.arms).fg("blue").z(3)
    s.text("bit/legs", st.x, top + 2, legs).fg("muted").z(3)

    if st.idea:
        s.text("bit/idea", st.x + 2, top - 2, "*").fg("yellow").bold().z(3)
    if st.say:
        w = len(st.say) + 4
        s.rect("bubble", st.x + 5, top - 4, w, 3).label(st.say).fg("fg").z(4)
        s.text("bubble/tail", st.x + 5, top - 1, "/").fg("fg").z(4)

    if st.party:
        for i, (x, y, ch, color) in enumerate(CONFETTI):
            s.text(("confetti", i), x, y, ch).fg(color).bold()
    return s


if __name__ == "__main__":
    ct.explain(
        story(),
        view,
        title="Bit builds a bridge",
        canvas=(W, H),
        motion=[ct.Rule("plank/*", arc=4)],
        timing=ct.Timing(
            default=0.9,
            events={"walk": 0.45, "plank": 0.75, "jump": 0.45, "land": 0.4, "hello": 1.2, "ta-da": 2.0},
            closing=2.5,
        ),
    ).play()
