"""Keynote — big, smooth, keynote-style text animation, in Khmer and English.

Black stage, big bold words that rise into place and fade, colour that sweeps
across the letters, a word that zooms in. All the text is drawn as pixels by
the engine (``Scene.title``), shaped with a real font, so Khmer comes out right
in any terminal: stacked consonants (ស្តី), vowels that sit before their
consonant (េ in លោ), marks above and below.

How the effects are made — no special engine support, just the usual rule that
what differs between two moments becomes motion:

- **Rise and fade in**: every piece of text is drawn in every moment. Before
  its turn it waits a little lower and invisible; on its turn it is in place
  and visible; afterwards it drifts up and fades out. The engine eases between.
- **Colour sweep**: a title's ``fg`` and ``fill`` are the two ends of a
  left-to-right gradient; changing them each beat makes the colour flow.
- **Zoom**: a title's ``size`` animates like any other number.

    python examples/keynote.py
    python examples/keynote.py --at 9 --color    # one frame, in colour
"""

from dataclasses import dataclass, field

import codimate_tui as ct

W, H = 88, 22
BLACK, WHITE, GREY = (0, 0, 0), (255, 255, 255), (140, 140, 150)

# Gradient stops: each pair is (left colour, right colour).
SUNSET = [(255, 166, 64), (255, 94, 120)]
BERRY = [(255, 94, 120), (170, 100, 255)]
OCEAN = [(90, 140, 255), (64, 214, 200)]
LIME = [(64, 214, 160), (214, 236, 90)]
SWEEP = [SUNSET, BERRY, OCEAN, LIME, SUNSET]

WAIT, SHOWN, GONE = 0, 1, 2  # where a piece of text is in its life
RISE = 2.0  # how far text travels as it enters and leaves, in cells

WORDS = ["តូច", "លឿន", "ស្អាត"]  # small, fast, beautiful
WORD_SIZE = 13


@dataclass
class State:
    phase: "dict[str, int]" = field(default_factory=dict)
    hello_small: bool = False
    zoom: float = 5.0  # size of the big "ខ្មែរ"
    sweep: int = 0  # which gradient the big word shows
    underline: float = 0.0  # 0..1, how far the closing line has drawn


def story() -> ct.Tracer:
    st = State()
    tr = ct.Tracer(st)

    def beat(name: str, say: str, **phases: int) -> None:
        st.phase.update(phases)
        tr.emit(name, st, say=say)

    beat("hello", "សួស្តី — hello, shaped by rustybuzz: ស and ត stack, ួ and ី attach.", hello=SHOWN)
    beat("hold", "សួស្តី — hello, shaped by rustybuzz: ស and ត stack, ួ and ី attach.")
    st.hello_small = True
    beat("make room", "It makes room for the English...", english=SHOWN)
    beat("hold", "...one title can mix scripts: each letter uses the first font that has it.")
    beat("clear", "", hello=GONE, english=GONE)

    for i, _ in enumerate(WORDS):
        leaving = {f"word{i - 1}": GONE} if i else {}
        beat("word", "Small. Fast. Beautiful. Each word takes the stage alone.", **{f"word{i}": SHOWN}, **leaving)
        beat("hold", "Small. Fast. Beautiful. Each word takes the stage alone.")
    beat("clear", "", **{f"word{len(WORDS) - 1}": GONE})

    beat("appear", "ខ្មែរ — Khmer.", khmer=SHOWN)
    st.zoom = 15.0
    beat("zoom", "Sizes animate too.")
    for i in range(1, len(SWEEP)):
        st.sweep = i
        beat("sweep", "Colour flows across the letters." if i < 3 else "អក្សរខ្មែរ ក្នុង Terminal — Khmer script, in the terminal.",
             **({"tagline": SHOWN} if i == 3 else {}))
    beat("clear", "", khmer=GONE, tagline=GONE)

    beat("brand", "", brand=SHOWN)
    st.underline = 1.0
    beat("underline", "")
    return tr


def view(frame: ct.Frame) -> ct.Scene:
    st: State = frame.state
    s = ct.Scene()
    s.block("stage", 0, 0, W, H).fill(BLACK)

    def title(name, x, y, text, size, colors=(WHITE, WHITE)):
        """Draw a title wherever it is in its life: waiting below, shown, or gone above."""
        phase = st.phase.get(name, WAIT)
        dy = {WAIT: RISE, SHOWN: 0.0, GONE: -RISE}[phase]
        node = s.title(name, x, y + dy, text, size).fg(colors[0]).fill(colors[1])
        node.opacity(1.0 if phase == SHOWN else 0.0)
        return node

    # Hello.
    if st.hello_small:
        title("hello", W / 2, 1.5, "សួស្តី", 11)
    else:
        title("hello", W / 2, (H - 14) / 2, "សួស្តី", 14)
    title("english", W / 2, 14, "Hello, terminal.", 5, (GREY, GREY))

    # Small. Fast. Beautiful. — one at a time, centre stage.
    for i, word in enumerate(WORDS):
        title(f"word{i}", W / 2, (H - WORD_SIZE) / 2, word, WORD_SIZE, SWEEP[i + 1])

    # ខ្មែរ zooms in, colour sweeping; the tagline joins underneath.
    top = (H - st.zoom) / 2 - (3.5 if st.phase.get("tagline") == SHOWN else 0)
    title("khmer", W / 2, top, "ខ្មែរ", st.zoom, SWEEP[st.sweep])
    title("tagline", W / 2, 15.5, "អក្សរខ្មែរ ក្នុង Terminal", 5.5, (GREY, WHITE))

    # Closing card: the name, and a gradient line drawing itself underneath.
    title("brand", W / 2, 6, "codimate-tui", 7)
    # One block whose width animates, so the line grows out from the middle.
    line_w = ct.measure("codimate-tui", 7) * st.underline
    s.block("underline", (W - line_w) / 2, 15, line_w, 0.5).fill(SUNSET[1]).opacity(st.underline)
    return s


if __name__ == "__main__":
    ct.explain(
        story(),
        view,
        title="Keynote",
        fit=True,  # made of shapes and titles only, so it can grow with the terminal
        canvas=(W, H),
        timing=ct.Timing(
            default=0.9,
            events={"hold": 1.4, "clear": 0.7, "word": 0.6, "zoom": 1.4, "sweep": 0.9, "underline": 1.2},
            opening=0.8,
            closing=3.0,
        ),
    ).play()
