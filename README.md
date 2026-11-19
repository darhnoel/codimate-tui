# codimate-tui

Explain an algorithm as an animation that plays in the terminal.
Write it in Python; a Rust engine handles the motion, timing and drawing.

```python
import codimate_tui as ct

tr = ct.Tracer(state)
tr.emit("push", state, say="'(' opens something. Push it.")

def view(frame):
    s = ct.Scene()
    s.rect(("tok", i), x, y, 3, 3).label("(").fill("orange")
    return s

ct.explain(tr, view, motion=[ct.Rule("tok/*", arc=2)]).play()
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install maturin pytest
.venv/bin/maturin develop --release
.venv/bin/python examples/intro.py
```

[examples/intro.py](examples/intro.py) is a short deck that introduces codimate-tui.
It draws with half blocks (`pixels="half"`), which every terminal shows cleanly,
macOS Terminal included. The finer `quad` and `sextant` modes need a terminal
that draws those blocks itself, such as Ghostty, kitty or WezTerm.

**Keys:** `space` play/pause · `←/→` scrub · `↑/↓` event · `r` restart · `+/-` speed · `f` full screen · `q` quit

## Tests

```bash
cargo test && .venv/bin/pytest python/tests
```
