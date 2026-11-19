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
.venv/bin/python examples/keynote.py
```

Other examples are in [examples/](examples/).

**Keys:** `space` play/pause · `←/→` scrub · `↑/↓` event · `r` restart · `+/-` speed · `f` full screen · `q` quit

## Tests

```bash
cargo test && .venv/bin/pytest python/tests
```
