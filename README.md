# codimate-tui

Explain an algorithm as an animation that plays **in the terminal**.

You write the algorithm as ordinary Python and say what each step looks like.
codimate-tui works out the motion and the timing, and gives you a player you can
pause, scrub and step through.

```python
import codimate_tui as ct

tr = ct.Tracer(state)
# ... your algorithm, calling after each step worth showing:
tr.emit("push", state, say="'(' opens something. Push it.")

def view(frame):                       # one moment -> one picture
    s = ct.Scene()
    s.rect(("tok", i), x, y, 3, 3).label("(").fill("orange")
    return s

ct.explain(tr, view, motion=[ct.Rule("tok/*", arc=2)]).play()
```

## Setup

Python authors; Rust does the per-frame work. Build once (needs a Rust toolchain):

```bash
python3 -m venv .venv && .venv/bin/pip install maturin pytest
.venv/bin/maturin develop --release
```

Run an example in a truecolor terminal at least ~90×24:

```bash
.venv/bin/python examples/brackets.py              # BRACKETS="([)]" shows a failure
.venv/bin/python examples/binary_search.py
.venv/bin/python examples/flood_fill.py
.venv/bin/python examples/cartoon.py               # not an algorithm: Bit builds a bridge
.venv/bin/python examples/rooftop_run.py           # a tiny game loop: platformer with a camera
.venv/bin/python examples/flat_cartoon.py          # flat style: Pip's morning, all solid shapes
.venv/bin/python examples/keynote.py               # keynote-style big text, Khmer + English
```

Every explainer script also understands:

```bash
python my_explainer.py --list                # the timeline
python my_explainer.py --at 5.85             # one frame as plain text
python my_explainer.py --at 5.85 --color     # one frame in colour (needed for solid shapes)
```

## Shapes

| shape | call | looks like |
|---|---|---|
| box | `s.rect(name, x, y, w, h)` | a diagram box with a rounded border |
| block | `s.block(name, x, y, w, h)` | a solid rectangle, no outline |
| oval | `s.oval(name, x, y, w, h)` | a solid ellipse, no outline |
| text | `s.text(name, x, y, "hi")` | one line of text, drawn by the terminal |
| title | `s.title(name, x, y, "ខ្មែរ", size=12)` | big text drawn as pixels, centred on `x` |

Blocks, ovals and titles are drawn as pixels, several per terminal cell, so
`x`, `y`, `w` and `h` can be fractions of a cell (`y=2.5`). A cell is about twice as tall as it is wide, so a
circle is twice as wide as it is tall: `s.oval("sun", 50, 2, 10, 5)`.

### How fine the pixels are

| `pixels=` | pixels per cell | characters | works in |
|---|---|---|---|
| `"sextant"` (default) | 2 × 3 | `🬀🬂🬎…` | VS Code, kitty, WezTerm, foot, most recent terminals |
| `"quad"` | 2 × 2 | `▚▞▙…` | almost everywhere |
| `"half"` | 1 × 2 | `▀` | everywhere |

**Sharper still: fit to the terminal.** With `ct.explain(..., fit=True)` (or
`--fit`), the picture scales to fill the player instead of staying at its
canvas size: twice the terminal, twice the pixels each way. Shrink the terminal
font (Ctrl+– in VS Code) for more cells, and press `f` for full screen. Use it
for pictures made of shapes and titles; terminal text can't grow, so diagrams
with text labels are better left at their own size. The keynote and flat cartoon
examples fit by default.

Set it with `ct.explain(..., pixels="quad")`, or try it without editing code:
`python my_explainer.py --pixels quad`. A cell can still show only two colours,
so where three colours meet in one cell, the closest two win.

## Khmer and other complex scripts

A terminal draws text one cell at a time, and many terminals get scripts like
Khmer wrong: `ស្តី` stacks one consonant under another, and `េ` is typed after
its consonant but drawn before it. Getting that right is called *shaping*.

| | `s.text(...)` | `s.title(...)` |
|---|---|---|
| who draws it | your terminal's font | the engine, as pixels |
| shaping | as good as your terminal | always right (rustybuzz, a Rust port of HarfBuzz) |
| size | normal terminal text | any size; Khmer reads well from about `size=10` |

`s.text` keeps each visible letter group together (`ស្តី` is four code points
but one group), so a terminal that can shape Khmer gets what it needs.

`s.title` takes `font=` as a file path or a fontconfig name, or a list of them:
each letter uses the first font that has it, so `"អក្សរខ្មែរ ក្នុង Terminal"`
mixes Khmer and English in one title. The default is bold Noto Sans Khmer plus
bold sans-serif. `ct.measure(text, size)` gives a title's width, for layout.
Give `fill` as well as `fg` for a left-to-right colour gradient.

**Player keys:** `space` play/pause · `←/→` scrub · `↑/↓` previous/next event ·
`r` restart · `+/-` speed · `f` full screen · `q` or `Ctrl+C` quit

## The four pieces

| piece     | what you write                                   |
|-----------|--------------------------------------------------|
| algorithm | your code, calling `tr.emit(name, state, say=…)` |
| view      | `def view(frame) -> Scene`: what one moment looks like |
| motion    | `ct.Rule("tok/*", arc=2)`: how matching nodes travel; `pace="linear"` for things that never stop (game loops, cameras) |
| timing    | `ct.Timing(events={"push": 0.8})`: seconds per event |

## The one decision: what a name follows

Nodes are paired between moments **by name**; whatever differs becomes movement.

- A name that follows the **thing** (`("tok", i)`, `"ptr/lo"`) makes it travel:
  the bracket hops into the stack, the pointer slides.
- A name that follows the **place** (`("cell", i)`, `("cell", r, c)`) makes it
  change in place: the cell recolours, the grid lights up wave by wave.

## How it's split

```
python/codimate_tui/        what authors use: Tracer, Scene, Timing, Rule, explain
crates/codimate-tui-py/     the bridge: Python's lists → engine values, nothing else
crates/codimate-tui-core/   the engine: motion, timeline, render, player (no Python)
```

Python runs the view **once per event** and hands every Scene over in **one call**.
The bridge reads Python's lists directly into Rust values: no file, no text
format, nothing crossing back and forth per frame. The engine then answers one
pure question, *what does the screen look like at this second?*, so scrubbing
is instant.

## Tests

```bash
cargo test                      # engine
.venv/bin/pytest python/tests   # authoring surface + round trip through the engine
```
