"""Breadth-first flood fill on a grid, one wave per event.

Identity choice: cells are named by *place* (("cell", r, c)). Nothing travels —
the wave is pure colour and label change, which is exactly what BFS looks like.

    python examples/flood_fill.py
"""

from dataclasses import dataclass

import codimate_tui as ct

MAP = [
    "S.........",
    "....#.....",
    "....#..##.",
    "..###.....",
    "......#...",
    "..#...#...",
]


@dataclass
class State:
    walls: list
    dist: dict  # (r, c) -> steps from S
    wave: int = 0


def fill() -> ct.Tracer:
    walls = [[ch == "#" for ch in line] for line in MAP]
    rows, cols = len(walls), len(walls[0])
    st = State(walls, dist={(0, 0): 0})
    tr = ct.Tracer(st)

    frontier = [(0, 0)]
    while True:
        nxt = []
        for r, c in frontier:
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= nr < rows and 0 <= nc < cols and not walls[nr][nc] and (nr, nc) not in st.dist:
                    st.dist[(nr, nc)] = st.dist[(r, c)] + 1
                    nxt.append((nr, nc))
        if not nxt:
            break
        st.wave += 1
        tr.emit("wave", st, say=f"Wave {st.wave}: {len(nxt)} new cell(s), each exactly {st.wave} step(s) from S.")
        frontier = nxt

    tr.emit("done", st, say=f"No new cells. {len(st.dist)} reachable; every number is a shortest distance.")
    return tr


CW, CH = 5, 2


def view(f: ct.Frame) -> ct.Scene:
    st = f.state
    s = ct.Scene()
    xs = ct.row(len(st.walls[0]), CW, 1, 62)

    for r, line in enumerate(st.walls):
        y = 1 + r * (CH + 1)
        for c, wall in enumerate(line):
            cell = s.rect(("cell", r, c), xs[c], y, CW, CH)
            d = st.dist.get((r, c))
            if wall:
                cell.fill("muted")
            elif d is None:
                cell.fill("dim")
            else:
                # The newest wave is bright; older waves cool from blue to purple.
                color = "orange" if d == st.wave and d > 0 else ct.mix("blue", "purple", d / 12)
                cell.fill(color).fg("bg").label("S" if d == 0 else d).bold()
    return s


if __name__ == "__main__":
    ct.explain(
        fill(),
        view,
        title="flood fill (BFS)",
        canvas=(62, 18),
        timing=ct.Timing(events={"wave": 0.6}),
    ).play()
