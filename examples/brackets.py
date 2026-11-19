"""Balanced brackets with a stack.

Identity choice: every bracket is named by *thing* (("tok", i)) for its whole
life, so an opener hops from the input into the stack, and back home when its
partner closes it.

    python examples/brackets.py
    BRACKETS="([)]" python examples/brackets.py
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import codimate_tui as ct

PARTNER = {")": "(", "]": "[", "}": "{"}


@dataclass
class State:
    tokens: str
    cursor: Optional[int] = None
    stack: list = field(default_factory=list)
    matched: set = field(default_factory=set)
    bad: Optional[int] = None
    verdict: Optional[bool] = None


def check(text: str) -> ct.Tracer:
    st = State(tokens=text)
    tr = ct.Tracer(st)

    for i, c in enumerate(text):
        st.cursor = i
        if c in "([{":
            st.stack.append(i)
            tr.emit("push", st, say=f"'{c}' opens something. Push it and wait for its partner.")
            continue
        if st.stack and text[st.stack[-1]] == PARTNER.get(c):
            top = st.stack.pop()
            st.matched |= {top, i}
            tr.emit("match", st, say=f"'{c}' closes the '{text[top]}' on top of the stack. Pop it.")
        else:
            st.bad, st.verdict = i, False
            tr.emit("mismatch", st, say=f"'{c}' doesn't close what's on top of the stack. Unbalanced.")
            return tr

    st.cursor = None
    st.verdict = not st.stack
    tr.emit("verdict", st, say="Input used up and the stack is empty: balanced."
            if st.verdict else "Input used up but openers are still waiting: unbalanced.")
    return tr


TOK = 3
INPUT_X, INPUT_Y = 3, 3
STACK_X, STACK_Y, STACK_H = 44, 3, 13


def view(f: ct.Frame) -> ct.Scene:
    st = f.state
    s = ct.Scene()

    s.text("label/input", INPUT_X, INPUT_Y - 2, "input").fg("muted")
    s.text("label/stack", STACK_X + 1, STACK_Y - 1, "stack").fg("muted")
    s.rect("stack", STACK_X, STACK_Y, TOK + 4, STACK_H).fg("muted")

    for i, c in enumerate(st.tokens):
        if i in st.stack:
            depth = st.stack.index(i)  # the stack grows upward from the bottom
            x, y = STACK_X + 2, STACK_Y + STACK_H - 1 - TOK * (depth + 1)
        else:
            x, y = INPUT_X + i * (TOK + 1), INPUT_Y

        if st.bad == i:
            fill, fg = "red", "bg"
        elif i in st.matched:
            fill, fg = "green", "bg"
        elif i in st.stack:
            fill, fg = "orange", "bg"
        elif st.cursor is not None and i < st.cursor:
            fill, fg = "dim", "muted"
        else:
            fill, fg = "blue", "fg"
        s.rect(("tok", i), x, y, TOK, TOK).label(c).fill(fill).fg(fg).bold().z(2)

    if st.cursor is not None:
        s.text("cursor", INPUT_X + st.cursor * (TOK + 1) + 1, INPUT_Y + TOK, "↑").fg("yellow").bold()

    if st.verdict is not None:
        msg, color = ("balanced ✓", "green") if st.verdict else ("unbalanced ✗", "red")
        s.text("verdict", INPUT_X, INPUT_Y + 7, msg).fg(color).bold()
    return s


if __name__ == "__main__":
    text = os.environ.get("BRACKETS", "([]{()})")
    ct.explain(
        check(text),
        view,
        title=f"balanced brackets: {text}",
        canvas=(58, 17),
        motion=[ct.Rule("tok/*", arc=2)],
        timing=ct.Timing(events={"push": 0.8, "match": 1.1}),
    ).play()
