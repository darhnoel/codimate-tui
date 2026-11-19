"""Introducing codimate-tui: a short launch deck that plays in the terminal.

Eight slides. Step through them like slides with ↑/↓ (one beat at a time),
or press space to let the deck run; f hides the player around the picture.

    python examples/intro.py
    python examples/intro.py --at 20 --color    # print one frame, in colour
    python examples/intro.py --list             # print the timeline

Made to look right in macOS Terminal, which draws only some of the block
characters cleanly:

- Shapes and titles use half blocks (``pixels="half"``): every pixel is the
  top or bottom half of a cell, drawn with ``▀`` alone. Quadrant and sextant
  blocks show as missing-glyph boxes there.
- Shapes are solid ``block``s, not outlined ``rect``s, whose line-drawing
  borders leave gaps between rows. Text sits on solid colour.
- Text is plain: no symbols a terminal might fall back to an emoji for, and
  Khmer only as a pixel title, which is shaped from a real font.
- Titles use fonts every Mac ships with, so nothing needs installing.

Every piece is drawn in every moment, and what differs between two moments
becomes motion: a piece waits a little low and invisible, rises into place on
its turn, then drifts up and fades when its slide is done.
"""

from dataclasses import dataclass, field

import codimate_tui as ct

W, H = 88, 22
BG = ct.PALETTE["bg"]  # the player's own background; fades mix toward it
WHITE, GREY, DIM = (240, 240, 245), (150, 152, 164), (70, 74, 88)
ORANGE, PINK, VIOLET = (255, 166, 64), (255, 94, 120), (170, 100, 255)
BLUE, TEAL, LIME = (90, 140, 255), (64, 214, 200), (214, 236, 90)
SUNSET, BERRY, OCEAN, LIMEY = (ORANGE, PINK), (PINK, VIOLET), (BLUE, TEAL), (TEAL, LIME)
SWEEP = [SUNSET, BERRY, OCEAN, LIMEY, SUNSET]
CARD = ct.mix(BG, WHITE, 0.07)  # a panel a shade lighter than the stage



def pick(*fonts: str) -> "str | None":
    """The first of ``fonts`` this machine has (a file, or a fontconfig name),
    or None for the library's own default."""
    for font in fonts:
        try:
            ct.font_file(font)
            return font
        except ValueError:
            pass
    return None


# Fonts for the pixel titles. The name is set in DIN Condensed Bold, which every
# Mac has: its upright strokes land on whole pixels, so it stays sharp at half
# blocks' coarse size. Khmer uses Noto Sans Khmer Bold where it's installed,
# else the Mac's own Khmer MN.
MAC = "/System/Library/Fonts/Supplemental/"
LOGO = pick(MAC + "DIN Condensed Bold.ttf")
LOGO_SIZE = 10 if LOGO else 7  # the default bold sans is much wider
KHMER = pick("Noto Sans Khmer:bold", MAC + "Khmer MN.ttc")

WAIT, SHOWN, GONE = 0, 1, 2
RISE = 2.0

REASONS = ["It's where code already lives.", "Nothing to render: it plays live.",
           "Pause, scrub and step through every beat."]
CODE = ['tr.emit("push", state, say="Push it.")',
        's.block(("tok", i), x, y, 3, 2).fill("orange")',
        "ct.explain(tr, view).play()"]
CODE_SAYS = ["Record a moment, with what to say.", "Draw the moment as named shapes.",
             "Play it. The engine animates the rest."]
SETUP = ["git clone https://github.com/darhnoel/codimate-tui",
         "cd codimate-tui && maturin develop --release",
         "python examples/intro.py"]
SETUP_SAYS = ["Clone it.", "Build the Rust engine.", "Play this deck."]
BARS = [5, 2, 4, 6, 1, 3]  # the demo's values, sorted live


@dataclass
class State:
    phase: "dict[str, int]" = field(default_factory=dict)
    token: float = 0.0  # 0 at Python's card .. 1 at Rust's
    order: "list[int]" = field(default_factory=lambda: list(BARS))
    hot: "tuple[int, int]" = (-1, -1)  # the two bars being compared
    sweep: int = 0
    underline: float = 0.0


def story() -> ct.Tracer:
    st = State()
    tr = ct.Tracer(st)

    def beat(event: str, say: str, **phases: int) -> None:
        st.phase.update(phases)
        tr.emit(event, st, say=say)

    def gone(*keys: str) -> "dict[str, int]":
        return {k: GONE for k in keys}

    # 1. The title
    beat("title", "codimate-tui: animations that play in your terminal.", logo=SHOWN)
    beat("hold", "codimate-tui: animations that play in your terminal.", tagline=SHOWN)
    beat("next", "", **gone("logo", "tagline"))

    # 2. Why the terminal?
    beat("slide", "Why the terminal?", why=SHOWN)
    for i, reason in enumerate(REASONS):
        beat("point", reason, **{f"why{i}": SHOWN})
    beat("next", "", **gone("why", *(f"why{i}" for i in range(len(REASONS)))))

    # 3. How it works: Python writes the story, Rust moves and draws it
    beat("slide", "You write the story in Python.", how=SHOWN, py=SHOWN)
    beat("point", "A Rust engine handles the motion, timing and drawing.", rs=SHOWN, wire=SHOWN)
    for token in (1.0, 0.0):  # there and back
        st.token = token
        beat("send", "Each moment you describe goes to the engine, which eases between them.")
    beat("next", "", **gone("how", "py", "rs", "wire"))

    # 4. A live demo: bubble sort, every comparison a beat
    beat("slide", "A live demo: bubble sort, one comparison per beat.", demo=SHOWN, bars=SHOWN)
    order = st.order
    for end in range(len(order) - 1, 0, -1):
        for i in range(end):
            st.hot = (order[i], order[i + 1])
            if order[i] > order[i + 1]:
                order[i], order[i + 1] = order[i + 1], order[i]
                beat("swap", f"{st.hot[0]} is bigger than {st.hot[1]}: swap them.")
            else:
                beat("compare", f"{st.hot[0]} is smaller than {st.hot[1]}: leave them.")
    st.hot = (-1, -1)
    beat("done", "Sorted. Every frame between the beats is made by the engine.")
    beat("next", "", **gone("demo", "bars"))

    # 5. The code
    beat("slide", "That demo is a few lines of Python.", code=SHOWN, editor=SHOWN)
    for i, say in enumerate(CODE_SAYS):
        beat("line", say, **{f"code{i}": SHOWN})
    beat("next", "", **gone("code", "editor", *(f"code{i}" for i in range(len(CODE)))))

    # 6. Khmer, too (said in English: the caption is terminal text)
    beat("slide", "Khmer too, shaped properly and drawn as pixels.", khmer=SHOWN)
    for i in range(1, len(SWEEP)):
        st.sweep = i
        beat("sweep", "Real text shaping: stacked consonants, vowels in the right place.",
             **({"shaping": SHOWN} if i == 1 else {}))
    beat("next", "", **gone("khmer", "shaping"))

    # 7. Try it
    beat("slide", "Try it.", try_=SHOWN, shell=SHOWN)
    for i, say in enumerate(SETUP_SAYS):
        beat("line", say, **{f"setup{i}": SHOWN})
    beat("next", "", **gone("try_", "shell", *(f"setup{i}" for i in range(len(SETUP)))))

    # 8. The closing card
    beat("brand", "", brand=SHOWN, link=SHOWN)
    st.underline = 1.0
    beat("underline", "github.com/darhnoel/codimate-tui")
    return tr


def view(frame: ct.Frame) -> ct.Scene:
    st: State = frame.state
    s = ct.Scene()

    def shift(key: str) -> "tuple[float, float]":
        """How far below its place a piece sits, and how visible it is."""
        phase = st.phase.get(key, WAIT)
        return {WAIT: RISE, SHOWN: 0.0, GONE: -RISE}[phase], 1.0 if phase == SHOWN else 0.0

    def title(name, y, text, size, colors=(WHITE, WHITE), font=LOGO, key=None):
        dy, op = shift(key or name)
        s.title(name, W / 2, y + dy, text, size, font=font).fg(colors[0]).fill(
            colors[1]).opacity(op)

    def line(name, x, y, text, color=WHITE, bold=False, key=None):
        dy, op = shift(key or name)
        s.text(name, x, y + dy, text).fg(color).bold(bold).opacity(op)

    def centred(name, y, text, color=WHITE, bold=False, key=None):
        line(name, (W - len(text)) / 2, y, text, color, bold, key)

    def card(name, x, y, w, h, color=CARD, key=None):
        dy, op = shift(key or name)
        s.block(name, x, y + dy, w, h).fill(color).opacity(op)

    def heading(name, text, colors, key=None):
        """A slide's heading in the terminal's own font, which stays crisp:
        bold spaced capitals over a coloured rule that grows from the middle."""
        spaced = " ".join(text.upper())
        centred(name, 3, spaced, colors[0], bold=True, key=key)
        dy, op = shift(key or name)
        width = (len(spaced) + 4) * op
        s.block((name, "rule"), (W - width) / 2, 4.5 + dy, width, 0.5).fill(
            colors[1]).opacity(op)

    def bullet(name, x, y, text, color):
        """A coloured dot and a line of text; the dot is a plain bullet, which
        every terminal font has."""
        line((name, "dot"), x, y, "•", color, key=name)
        line(name, x + 3, y, text)

    # 1. The title
    title("logo", 4, "codimate-tui", LOGO_SIZE, SUNSET)
    centred("tagline", 15, "Animations that play in your terminal.", GREY)

    # 2. Why the terminal?
    heading("why", "Why the terminal?", OCEAN)
    for i, reason in enumerate(REASONS):
        bullet(f"why{i}", 22, 9 + 3 * i, reason, OCEAN[i % 2])

    # 3. How it works: two solid cards and a wire, with a token travelling
    heading("how", "How it works", BERRY)
    card("py-card", 8, 9, 26, 8, ct.mix(BG, ORANGE, 0.16), key="py")
    line("py-name", 18, 11, "Python", ORANGE, bold=True, key="py")
    line("py-what", 11, 14, "you write the story", GREY, key="py")
    card("rs-card", 54, 9, 26, 8, ct.mix(BG, TEAL, 0.16), key="rs")
    line("rs-name", 65, 11, "Rust", TEAL, bold=True, key="rs")
    line("rs-what", 57, 14, "motion, timing, ink", GREY, key="rs")
    card("wire", 34, 12.5, 20, 0.5, DIM)
    dy, op = shift("wire")
    s.block("token", 35 + 16 * st.token, 12 + dy, 2, 1.5).fill(PINK).opacity(op)

    # 4. The demo: bars that sort themselves
    heading("demo", "Live demo", LIMEY)
    dy, op = shift("bars")
    for value in BARS:
        x = 22 + 8 * st.order.index(value)
        hot = value in st.hot
        h = 1.6 * value
        s.block(("bar", value), x, 19.5 - h + dy, 5, h).fill(PINK if hot else BLUE).opacity(op)
        s.text(("num", value), x + 2, 20 + dy, str(value)).fg(
            WHITE if hot else GREY).bold(hot).opacity(op)

    # 5. The code, on an editor panel
    heading("code", "The code", SUNSET)
    card("editor", 10, 8, 68, 11)
    for i, text in enumerate(CODE):
        line(f"code{i}", 14, 10 + 3 * i, text, [ORANGE, TEAL, LIME][i])

    # 6. Khmer, as a pixel title (the terminal itself can't stack the letters)
    title("khmer", 3, "អក្សរខ្មែរ", 11, SWEEP[st.sweep], font=KHMER)
    centred("shaping", 16, "Real text shaping, drawn as pixels.", GREY)

    # 7. Try it, on a shell panel
    heading("try", "Try it", OCEAN, key="try_")
    card("shell", 8, 8, 72, 11)
    for i, text in enumerate(SETUP):
        line((f"setup{i}", "prompt"), 12, 10 + 3 * i, "$", DIM, key=f"setup{i}")
        line(f"setup{i}", 14, 10 + 3 * i, text, WHITE if i < 2 else LIME)

    # 8. The closing card
    title("brand", 4, "codimate-tui", LOGO_SIZE)
    centred("link", 16, "github.com/darhnoel/codimate-tui", GREY)
    width = ct.measure("codimate-tui", LOGO_SIZE, font=LOGO) * st.underline
    s.block("underline", (W - width) / 2, 13, width, 0.5).fill(PINK).opacity(st.underline)
    return s


def deck() -> ct.Explanation:
    return ct.explain(
        story(),
        view,
        title="Introducing codimate-tui",
        fit=True,
        pixels="half",  # the blocks macOS Terminal draws cleanly
        canvas=(W, H),
        timing=ct.Timing(
            default=1.0,
            events={"title": 1.2, "hold": 2.2, "next": 0.6, "slide": 1.4,
                    "point": 2.0, "send": 1.2, "swap": 0.6, "compare": 0.5,
                    "done": 1.6, "line": 1.8, "sweep": 0.9, "brand": 1.0,
                    "underline": 1.4},
            opening=0.6,
            closing=3.0,
        ),
    )


if __name__ == "__main__":
    deck().play()
