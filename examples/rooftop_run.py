"""Rooftop Run: an original night-city platformer, played as an animation.

The "algorithm" is a real (tiny) game loop: gravity, landing checks, a simple
AI that decides when to jump, collisions with coins and drones. Every tick of the
loop is one event; the view draws the world through a scrolling camera.

What it shows off:

- pace="linear" — a game is mid-motion at every tick; easing each tick would
  make everything stop and start. Linear pacing makes it flow.
- a camera — the view subtracts the camera from world positions, and the canvas
  clips whatever is off-stage.
- parallax — the moon, skyline and rooftops scroll at different speeds.
- hit-pause — a stomp is just an event with a longer duration: instant slow-mo.

    python examples/rooftop_run.py
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import codimate_tui as ct

# --- the world (cells; y grows downward) -------------------------------------

W, H = 76, 22
BUILDINGS = [  # (left, width, roof row)
    (0, 34, 15),
    (40, 22, 13),
    (66, 18, 16),
    (112, 26, 13),
    (142, 8, 10),
    (154, 36, 14),
]
LEVEL_W = 190
ZIP = ((78, 6), (118, 8))  # zipline from (x, y) to (x, y)
DRONES = [(46, 9), (75, 8.7), (162, 6.3)]  # patrol centres, on Kip's jump arcs
COINS = [
    (12, 12), (16, 12), (20, 12),  # warm-up row
    (37, 9), (41, 8),  # over the first gap
    (50, 5), (56, 10),
    (90, 9), (100, 10), (110, 11),  # along the zipline
    (126, 10), (130, 10),
    (150, 5),  # leaving the tall roof
    (158, 3), (167, 2),
]
BEACON_X = 180
JUMP_AT = {52, 126, 160}  # extra hops the AI takes for coins and drones

# --- physics -------------------------------------------------------------------

RUN = 1.5  # cells per tick
GRAVITY = 0.35
JUMP = -2.1
BOUNCE = -1.5
ZIP_SPEED = 2.2
LOOK = 3  # how far ahead the AI looks for an edge


def roof_under(x: float) -> Optional[int]:
    for left, w, top in BUILDINGS:
        if left <= x < left + w:
            return top
    return None


def zip_y(x: float) -> float:
    (x0, y0), (x1, y1) = ZIP
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def drone_pos(i: int, tick: int) -> "tuple[float, float]":
    bx, by = DRONES[i]
    return bx + 3 * math.sin(tick * 0.2 + i * 2), by + 0.8 * math.sin(tick * 0.3 + i)


@dataclass
class State:
    tick: int = 0
    x: float = 4.0  # Kip's left edge (Kip is 3 cells wide; x + 1 is the middle)
    y: float = 14.0  # Kip's feet row
    vy: float = 0.0
    mode: str = "run"  # run | air | zip | done
    zipped: bool = False
    got: dict = field(default_factory=dict)  # coin index -> tick collected
    stomped: dict = field(default_factory=dict)  # drone index -> (x, y, tick)
    lit: bool = False
    burst: int = 0  # fireworks stage


def game() -> ct.Tracer:
    st = State()
    tr = ct.Tracer(st)

    def emit(name: str, say: str = "") -> None:
        tr.emit(name, st, say=say)

    emit("start", "Kip has a package to deliver across the rooftops.")
    while st.mode != "done":
        st.tick += 1
        events = []
        mid = st.x + 1

        if st.mode == "run":
            st.x += RUN
            mid = st.x + 1
            here, ahead = roof_under(mid), roof_under(mid + LOOK)
            crossed = any(st.x - RUN < j <= st.x for j in JUMP_AT)
            if here is None:
                st.mode, st.vy = "air", 0.0
            elif ahead is None or ahead < here or crossed:
                st.mode, st.vy = "air", JUMP
                events.append("jump")

        elif st.mode == "air":
            st.x += RUN
            mid = st.x + 1
            st.vy += GRAVITY
            new_y = st.y + st.vy
            for i in range(len(DRONES)):
                dx, dy = drone_pos(i, st.tick)
                if i not in st.stomped and st.vy > 0 and abs(mid - (dx + 2)) <= 2.5 and dy - 1.5 <= new_y <= dy + 1:
                    st.stomped[i] = (dx, dy, st.tick)
                    st.vy, new_y = BOUNCE, dy - 1
                    events.append("stomp")
            # Check the roof under this tick *and* the last one, so a fast fall
            # across a roof's edge still lands instead of slipping past it.
            top = roof_under(mid)
            if top is None:
                top = roof_under(mid - RUN)
            if st.vy > 0 and top is not None and st.y <= top - 1 <= new_y:
                st.y, st.vy, st.mode = top - 1, 0.0, "run"
                events.append("land")
            else:
                st.y = new_y
            (zx0, _), (zx1, _) = ZIP
            if not st.zipped and zx0 <= mid <= zx1 and abs((st.y - 2) - (zip_y(mid) + 1)) <= 1.5:
                st.mode, st.zipped = "zip", True
                events.append("zip")

        elif st.mode == "zip":
            st.x += ZIP_SPEED
            mid = st.x + 1
            if mid >= ZIP[1][0]:
                st.mode, st.vy = "air", 0.0
                events.append("let go")
            else:
                st.y = zip_y(mid) + 3  # hanging: hands on the line, feet 3 below

        if st.y > H + 2:
            raise RuntimeError(f"Kip fell at x={st.x:.1f}, tick {st.tick}: retune the level")

        for i, (cx, cy) in enumerate(COINS):
            if i not in st.got and st.x - 0.5 <= cx <= st.x + 2.5 and st.y - 2.5 <= cy <= st.y + 0.5:
                st.got[i] = st.tick
                events.append("coin")

        if st.mode == "run" and st.x + 1 >= BEACON_X - 4:
            st.mode = "done"

        if "stomp" in events:
            emit("stomp", f"Stomp! Drone {len(st.stomped)} of {len(DRONES)} down.")
        elif "zip" in events:
            emit("zip", "Grab the zipline!")
        elif "let go" in events:
            emit("let go", "Let go...")
        elif "coin" in events:
            emit("coin", f"Coin! {len(st.got)} of {len(COINS)}.")
        elif "jump" in events:
            emit("jump", "Jump!")
        elif "land" in events:
            emit("land", "")
        else:
            emit("run")

    st.lit = True
    emit("deliver", "Delivered. The beacon lights up.")
    for stage in (1, 2, 3):
        st.burst = stage
        st.tick += 1
        emit("burst", f"Rooftop Run complete: {len(st.got)} coins, {len(st.stomped)} drones.")
    return tr


# --- the view -------------------------------------------------------------------

def hashed(*parts: int) -> int:
    h = 2166136261
    for p in parts:
        h = ((h ^ (p & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h


STARS = [(hashed(i, 1) % 100, hashed(i, 2) % 9) for i in range(36)]
SKYLINE = []
_x = -4
while _x < LEVEL_W * 0.45 + W + 8:
    w = 6 + hashed(_x, 3) % 7
    SKYLINE.append((_x, w, 5 + hashed(_x, 4) % 7))
    _x += w + hashed(_x, 5) % 3

FIREWORK_DIRS = [(math.cos(a), math.sin(a)) for a in (i * math.tau / 14 for i in range(14))]


def view(f: ct.Frame) -> ct.Scene:
    st = f.state
    s = ct.Scene()
    cam = min(max(st.x - 22, 0), LEVEL_W - W)

    def on_stage(x: float, w: float = 1) -> bool:
        return x + w >= -10 and x <= W + 10

    # Far: stars and the moon barely move.
    for i, (sx, sy) in enumerate(STARS):
        x = sx - cam * 0.1
        if on_stage(x):
            twinkle = hashed(i, st.tick // 5) % 9 == 0
            s.text(("star", i), x, sy, "+" if twinkle else ".").fg("yellow" if twinkle else (90, 96, 130))
    mx = 58 - cam * 0.05
    for row, line in enumerate((" .-. ", "(   )", " '-' ")):
        s.text(("moon", row), mx, 1 + row, line).fg((225, 220, 180))

    # Middle: the skyline drifts at under half speed.
    for i, (x0, w, top) in enumerate(SKYLINE):
        x = x0 - cam * 0.45
        if on_stage(x, w):
            shade = (30, 34, 52)
            s.rect(("skyline", i), x, top, w, H - top + 1).fill(shade).fg(shade)

    # Near: rooftops, windows, zipline, beacon move with the camera.
    for b, (left, w, top) in enumerate(BUILDINGS):
        x = left - cam
        if not on_stage(x, w):
            continue
        s.rect(("bldg", b), x, top, w, H - top + 2).fill((52, 58, 78)).fg((96, 104, 132)).z(1)
        for col in range(left + 2, left + w - 3, 4):
            for row in range(top + 2, H, 2):
                h = hashed(b, col, row)
                lit = h % 3 == 0 or (h % 7 == 0 and (st.tick // 10 + h) % 2 == 0)
                color = (240, 200, 110) if lit else (40, 44, 60)
                s.rect(("win", b, col, row), col - cam, row, 2, 1).fill(color).z(2)

    (zx0, zy0), (zx1, zy1) = ZIP
    for xi in range(zx0, zx1 + 1):
        if on_stage(xi - cam):
            s.text(("zip", xi), xi - cam, round(zip_y(xi)), "-").fg("muted").z(2)
    for px, py, roof in ((zx0, zy0, roof_under(zx0)), (zx1, zy1, roof_under(zx1))):
        for row in range(py, roof):
            s.text(("pole", px, row), px - cam, row, "|").fg("muted").z(2)

    bx = BEACON_X - cam
    if on_stage(bx, 5):
        lamp = "yellow" if st.lit else "muted"
        s.text("beacon/lamp", bx + 1, 7, " * " if st.lit else " o ").fg(lamp).bold().z(3)
        if st.lit:
            s.text("beacon/rays", bx - 3, 7, "--     --").fg("yellow").z(3)
        for row, line in enumerate(("/|\\", "|=|", "|=|", "|=|", "/___\\")):
            s.text(("beacon", row), bx + (1 if row < 4 else 0), 8 + row, line).fg((150, 160, 190)).z(3)

    # Coins spin; a collected coin rises and fades on the tick it's taken.
    for i, (cx, cy) in enumerate(COINS):
        x = cx - cam
        got = st.got.get(i)
        if got is None and on_stage(x):
            face = "oO0O"[(st.tick + i) % 4]
            s.text(("coin", i), x, cy, face).fg("yellow").bold().z(4)
        elif got == st.tick:
            s.text(("coin", i), x, cy - 2, "o").fg("yellow").opacity(0).z(4)
            s.text(("plus", i), x - 1, cy - 1, "+1").fg("yellow").bold().z(4)

    # Drones patrol; a stomped drone squashes, drops and fades.
    for i in range(len(DRONES)):
        if i in st.stomped:
            sx, sy, when = st.stomped[i]
            age = st.tick - when
            if age > 8:
                continue
            x, y = sx - cam, sy + 0.25 * age * age
            s.text(("drone", i), x, y, "_x_x_").fg("red").opacity(1 - age / 8).z(4)
            s.text(("spark", i), x + 1, sy - 1 - age * 0.5, "* *").fg("orange").opacity(max(0, 1 - age / 4)).z(4)
        else:
            dx, dy = drone_pos(i, st.tick)
            if on_stage(dx - cam, 5):
                props = "-_o_-" if st.tick % 2 else "~_o_~"
                s.text(("drone", i), dx - cam, dy, props).fg("red").bold().z(4)

    # Kip: four nodes drawn from one position, so they move as one character.
    x, y = st.x - cam, st.y
    rising, falling = st.mode == "air" and st.vy < 0, st.mode == "air" and st.vy >= 0
    if st.mode in ("zip", "done"):
        head, body, legs = "\\o/", " | ", "/ \\"
    elif rising:
        head, body, legs = " o ", "\\|/", " ^ "
    elif falling:
        head, body, legs = " o ", "-|-", "/ \\"
    else:
        step = st.tick % 4
        head, body, legs = " o ", ("/|-", "-|\\")[step % 2], ("/ \\", " |\\", " | ", "/| ")[step]
    scarf = "~" if st.tick % 2 else "-"
    s.text("kip/scarf", x - 1 + (0.5 if st.mode == "done" else 0), y - 2, scarf).fg("orange").bold().z(6)
    s.text("kip/head", x, y - 2, head).fg("fg").bold().z(6)
    s.text("kip/body", x, y - 1, body).fg("blue").bold().z(6)
    s.text("kip/legs", x, y, legs).fg("fg").z(6)

    # Fireworks: particles start invisible at the lamp, then fly out and fall.
    if st.lit:
        lx, ly = bx + 2, 7
        reach = {0: 0, 1: 4, 2: 7, 3: 9}[st.burst]
        fade = {0: 0.0, 1: 1.0, 2: 0.7, 3: 0.0}[st.burst]
        drop = {0: 0, 1: 0, 2: 1, 3: 3}[st.burst]
        for i, (dx, dy) in enumerate(FIREWORK_DIRS):
            color = ("red", "yellow", "green", "purple", "blue")[i % 5]
            s.text(("spark", "fw", i), lx + dx * reach * 2, ly + dy * reach + drop, "*").fg(color).bold().opacity(fade).z(7)

    # HUD: fixed to the screen, not the world.
    s.text("hud", 1, 0, f"coins {len(st.got):>2}/{len(COINS)}   drones {len(st.stomped)}/{len(DRONES)}").fg("yellow").bold().z(8)
    return s


if __name__ == "__main__":
    ct.explain(
        game(),
        view,
        title="Rooftop Run",
        canvas=(W, H),
        motion=[ct.Rule("*", pace="linear")],
        timing=ct.Timing(
            default=0.085,
            events={"start": 1.0, "stomp": 0.3, "zip": 0.2, "deliver": 1.0, "burst": 0.5},
            opening=0.6,
            closing=2.5,
        ),
    ).play()
