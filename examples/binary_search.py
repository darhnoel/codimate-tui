"""Binary search: halve the range until the target turns up.

Identity choices: cells are named by *place* (("cell", i)) — they never move,
only change colour. Pointers are named by *thing* ("ptr/lo") — they slide.

    python examples/binary_search.py
"""

from dataclasses import dataclass
from typing import Optional

import codimate_tui as ct


@dataclass
class State:
    values: list
    target: int
    lo: int
    hi: int
    mid: Optional[int] = None
    found: Optional[int] = None


def search(values: list, target: int) -> ct.Tracer:
    st = State(values, target, lo=0, hi=len(values) - 1)
    tr = ct.Tracer(st)

    while st.lo <= st.hi:
        mid = (st.lo + st.hi) // 2
        v = values[mid]
        st.mid = mid
        tr.emit("probe", st, say=f"Look in the middle of what's left: index {mid} holds {v}.")

        if v == target:
            st.found = mid
            tr.emit("found", st, say=f"{v} is the target. Found at index {mid}.")
            return tr
        if v < target:
            st.lo = mid + 1
            tr.emit("go right", st, say=f"{v} < {target}, so everything left of it is out. Drop that half.")
        else:
            st.hi = mid - 1
            tr.emit("go left", st, say=f"{v} > {target}, so everything right of it is out. Drop that half.")

    tr.emit("missing", st, say=f"Nothing left to search: {target} isn't here.")
    return tr


W, CELL_W, ROW_Y = 64, 5, 5


def view(f: ct.Frame) -> ct.Scene:
    st = f.state
    s = ct.Scene()
    xs = ct.row(len(st.values), CELL_W, 1, W)

    s.text("target", xs[0], 1, f"target = {st.target}").fg("yellow").bold()

    for i, (v, x) in enumerate(zip(st.values, xs)):
        if st.found == i:
            fill, fg = "green", "bg"
        elif st.mid == i:
            fill, fg = "orange", "bg"
        elif st.lo <= i <= st.hi:
            fill, fg = "blue", "fg"
        else:
            fill, fg = "dim", "muted"
        s.rect(("cell", i), x, ROW_Y, CELL_W, 3).label(v).fill(fill).fg(fg).bold()
        s.text(("idx", i), x + 2, ROW_Y + 3, i).fg("muted")

    def at(i: int) -> float:
        return xs[min(max(i, 0), len(xs) - 1)]

    # Pointers follow the *thing*, so moving `lo` slides it rather than fading.
    if st.mid is not None:
        s.text("ptr/mid", xs[st.mid] + 1, ROW_Y - 2, "mid").fg("orange").bold()
        s.text("ptr/mid-arrow", xs[st.mid] + 2, ROW_Y - 1, "↓").fg("orange")
    if st.lo <= st.hi:
        s.text("ptr/lo", at(st.lo) + 1, ROW_Y + 4, "↑lo")
        s.text("ptr/hi", at(st.hi) + 1, ROW_Y + 5, "↑hi")

    left = max(st.hi - st.lo + 1, 0)
    s.text("remaining", xs[0], ROW_Y + 7, f"{left} candidate(s) left").fg("muted")
    return s


if __name__ == "__main__":
    ct.explain(
        search([2, 5, 8, 12, 16, 23, 38, 56, 72, 91], 23),
        view,
        title="binary search",
        canvas=(W, 14),
        timing=ct.Timing(events={"probe": 0.8, "found": 1.0}),
    ).play()
