"""Pip's Morning — a flat cartoon made only of solid ovals and blocks.

Pip, a round little bird, sleeps through the night in a nest, wakes with the
sunrise, chases a falling apple down the hill, eats it, and flies off toward
the sun.

Flat style means no outlines: every shape is a block of solid colour. Solid
shapes (``Scene.oval`` / ``Scene.block``) are drawn at twice the vertical
detail of text — each terminal cell holds two square pixels — so circles look
round and things slide up and down smoothly.

The same engine ideas as everywhere else do the animating:

- Pip is a dozen parts ("pip/body", "pip/wing", "pip/eye", ...) drawn around
  one position, so they travel together as one character.
- Squash and stretch is just a size change: Pip's body gets wide and short
  before a jump, tall and thin when stretching, and the engine eases between.
- A blink is the eye turning from an oval into a thin block and back.
- Day breaking is colour: the sky, hills and grass are the same nodes all
  along, and their colours blend from night to dawn to day.

    python examples/flat_cartoon.py
    python examples/flat_cartoon.py --at 12 --color    # one frame, in colour
"""

from dataclasses import dataclass, field

import codimate_tui as ct

W, H = 72, 20
GROUND = 17.0  # top of the grass

# Flat palette (day colours; night is mixed in by `shade`).
NIGHT = (22, 26, 56)
SKY = [(22, 26, 56), (238, 152, 122), (130, 198, 238)]  # night, dawn, day
LIGHT = [0.0, 0.55, 1.0]
SUN = [(230, 110, 60), (246, 142, 72), (255, 214, 92)]
SUN_Y = [18.0, 11.5, 2.0]
HILL_FAR, HILL_NEAR, GRASS = (122, 188, 128), (98, 166, 104), (86, 150, 82)
TRUNK, LEAVES, LEAVES_LIT, NEST = (122, 82, 56), (58, 132, 82), (74, 154, 94), (150, 104, 64)
CLOUD = (250, 250, 252)
BODY, BELLY, WING, BEAK = (252, 204, 72), (255, 238, 186), (238, 158, 58), (238, 108, 62)
INK, BLUSH, APPLE = (44, 36, 52), (246, 136, 136), (214, 58, 58)
PETALS = [(246, 130, 170), (255, 255, 255), (186, 140, 240), (255, 196, 80), (246, 130, 170)]
FLOWER_X = [24, 42, 48, 57, 64]
STARS = [(3, 1), (12, 3.5), (21, 0.5), (29, 2.5), (36, 1), (44, 4), (49, 0.5), (62, 2), (68, 5)]


def shade(color, light):
    """``color`` as seen in ``light`` (0 = night, 1 = full day)."""
    return ct.mix(ct.mix(color, NIGHT, 0.7), color, light)


@dataclass
class Pip:
    x: float = 8.0  # centre of the body
    feet: float = 10.5  # y of the bottom of the body
    k: float = 1.0  # overall size (shrinks as Pip flies away)
    sx: float = 1.0  # squash and stretch: width ...
    sy: float = 1.0  # ... and height multipliers
    eye: str = "shut"  # open / shut / happy
    wing: str = "down"  # down / up
    blush: bool = False


@dataclass
class State:
    sky: int = 0  # 0 night, 1 dawn, 2 day
    tick: int = 0
    pip: Pip = field(default_factory=Pip)
    zs: int = 0  # how many sleepy z's are showing
    thought: bool = False
    apple_x: float = 21.0
    apple_bottom: float = 12.5
    apple_sx: float = 1.0
    apple_sy: float = 1.0
    bites: int = 0  # 4 = all gone
    flowers: bool = False
    sparkles: int = 0
    the_end: bool = False


def story() -> ct.Tracer:
    st = State()
    p = st.pip
    tr = ct.Tracer(st)
    caption = ""

    def beat(name: str, say: "str | None" = None) -> None:
        nonlocal caption
        caption = caption if say is None else say
        st.tick += 1
        tr.emit(name, st, say=caption)

    def squash(sx: float, sy: float) -> None:
        p.sx, p.sy = sx, sy

    # Night.
    for z in (1, 2, 3):
        st.zs = z
        beat("snore", "Night on the hill. Pip is fast asleep.")
    st.zs = 0
    st.sky = 1
    beat("dawn", "The sky warms up...")
    st.sky = 2
    beat("sunrise", "...and the sun climbs over the hills.")
    st.flowers = True
    beat("bloom", "The flowers open.")

    # Waking up.
    p.eye = "open"
    beat("wake", "Pip wakes up.")
    squash(0.85, 1.3)
    p.wing = "up"
    beat("stretch", "A big stretch...")
    squash(1, 1)
    p.wing = "down"
    beat("settle", "")
    p.eye = "shut"
    beat("blink")
    p.eye = "open"
    beat("blink")
    st.thought = True
    beat("hungry", "Pip is hungry. Breakfast?")

    # Up to the apple.
    st.thought = False
    squash(1.25, 0.7)
    beat("crouch", "Ready...")
    p.x, p.feet = 13, 5.5
    squash(0.85, 1.2)
    p.wing = "up"
    beat("hop", "Hop!")
    p.x, p.feet = 18, 6.5
    squash(1.25, 0.75)
    p.wing = "down"
    beat("land")
    squash(1, 1)
    beat("settle")
    for shake in (0.6, -0.6, 0.6, 0.0):
        p.feet = 7.0 if shake else 6.5
        st.apple_x = 21 + shake
        beat("peck", "Pip taps the branch.")
        p.feet = 6.5
    beat("settle")

    # The apple falls, bounces and rolls (shorter steps = slowing down; longer =
    # speeding up: the apple moves at constant speed within each step).
    st.apple_bottom = 14.0
    beat("fall", "The apple drops!")
    st.apple_bottom = GROUND
    st.apple_sx, st.apple_sy = 1.4, 0.6
    beat("fall")
    st.apple_bottom = GROUND - 2.0
    st.apple_sx, st.apple_sy = 0.9, 1.15
    beat("bounce", "Boing.")
    st.apple_bottom = GROUND
    st.apple_sx, st.apple_sy = 1.2, 0.8
    beat("bounce")
    st.apple_sx, st.apple_sy = 1.0, 1.0
    for x in (27, 31, 33.5, 34.5):
        st.apple_x = x
        beat("roll", "It rolls away down the hill.")

    # Pip flutters down after it.
    start, end = (18.0, 6.5), (30.0, GROUND)
    flaps = 6
    for i in range(1, flaps + 1):
        f = i / flaps
        p.x = start[0] + (end[0] - start[0]) * f
        p.feet = start[1] + (end[1] - start[1]) * f - (0 if i == flaps else 1.0)
        p.wing = "up" if i % 2 else "down"
        beat("flap", "Pip flutters after it.")
    p.feet = GROUND
    p.wing = "down"
    squash(1.3, 0.7)
    beat("land", "")
    squash(1, 1)
    beat("settle")

    # Breakfast.
    for _ in range(4):
        st.bites += 1
        p.eye = "happy"
        squash(1.05, 0.92)
        beat("munch", "Munch.")
        squash(1, 1)
        p.eye = "open"
        beat("chew")
    p.eye, p.blush = "happy", True
    for n in (1, 2, 1):
        st.sparkles = n
        beat("yum", "Yum!")
    st.sparkles = 0

    # Off toward the sun.
    p.eye = "open"
    squash(1.3, 0.7)
    beat("crouch", "Off for the day, toward the sun.")
    squash(1, 1)
    for i in range(8):
        p.wing = "up" if i % 2 == 0 else "down"
        p.x += 3.5
        p.feet -= 1.6
        p.k *= 0.86
        beat("fly")
    st.the_end = True
    beat("the end", "")
    return tr


def draw_pip(s: ct.Scene, p: Pip, light: float) -> None:
    c = lambda color: shade(color, light)  # noqa: E731
    k = p.k
    bw, bh = 8 * k * p.sx, 4 * k * p.sy
    bx, by = p.x - bw / 2, p.feet - bh
    for i, fx in enumerate((0.35, 0.6)):
        s.block(("pip", "foot", i), bx + bw * fx, p.feet - 0.5, max(1, k), 1).fill(c(BEAK)).z(69)
    s.oval(("pip", "tail"), bx - 1.5 * k, by + bh * 0.2, 3 * k, 1.5 * k).fill(c(WING)).z(70)
    s.oval(("pip", "body"), bx, by, bw, bh).fill(c(BODY)).z(71)
    s.oval(("pip", "belly"), bx + bw * 0.3, by + bh * 0.5, bw * 0.5, bh * 0.45).fill(c(BELLY)).z(72)
    if p.wing == "up":  # raised behind the back, peeking out above it
        s.oval(("pip", "wing"), bx - bw * 0.05, by - bh * 0.4, bw * 0.4, bh * 0.75).fill(c(WING)).z(70)
    else:  # folded against the side
        s.oval(("pip", "wing"), bx + bw * 0.1, by + bh * 0.42, bw * 0.45, bh * 0.4).fill(c(WING)).z(73)
    ex, ey = bx + bw * 0.6, by + bh * 0.22
    if p.eye == "open":
        s.oval(("pip", "eye"), ex, ey, 2 * k, 1 * k).fill(c(INK)).z(74)
        if k > 0.6:
            s.block(("pip", "shine"), ex, ey, 1, 0.5).fill(c((255, 255, 255))).z(75)
    else:  # shut is a line low in the eye; happy is a line higher up
        s.block(("pip", "eye"), ex, ey + (0.5 if p.eye == "shut" else 0), 2 * k, 0.5).fill(c(INK)).z(74)
    s.oval(("pip", "beak"), bx + bw - 1.2 * k, by + bh * 0.4, 3 * k, 1.5 * k).fill(c(BEAK)).z(74)
    if p.blush:
        s.oval(("pip", "blush"), ex - 1.0 * k, ey + 1.5 * k, 2 * k, 0.5).fill(c(BLUSH)).z(74)


def cloud(s: ct.Scene, i: int, x: float, y: float, light: float) -> None:
    color = shade(CLOUD, light)
    s.oval(("cloud", i, 0), x, y + 1, 11, 2.5).fill(color).z(30)
    s.oval(("cloud", i, 1), x + 2, y, 5, 2.5).fill(color).z(30)
    s.oval(("cloud", i, 2), x + 5, y + 0.5, 5, 2).fill(color).z(30)


def view(frame: ct.Frame) -> ct.Scene:
    st: State = frame.state
    light = LIGHT[st.sky]
    s = ct.Scene()

    s.block("sky", 0, 0, W, H).fill(SKY[st.sky]).z(0)
    if st.sky < 2:
        for i, (x, y) in enumerate(STARS):
            twinkle = 1.0 if (i + st.tick) % 3 else 0.45
            s.block(("star", i), x, y, 1, 0.5).fill((255, 246, 210)).opacity(
                twinkle * (1.0 if st.sky == 0 else 0.35)
            ).z(10)
    s.oval("sun", 52, SUN_Y[st.sky], 10, 5).fill(SUN[st.sky]).z(20)
    drift = st.tick * 0.7
    cloud(s, 0, 62 - drift, 2.5, light)
    cloud(s, 1, 30 - drift, 5.0, light)

    s.oval("hill/far", -12, 10, 54, 16).fill(shade(HILL_FAR, light)).z(40)
    s.oval("hill/near", 28, 11.5, 62, 14).fill(shade(HILL_NEAR, light)).z(41)
    s.block("grass", 0, GROUND, W, H - GROUND).fill(shade(GRASS, light)).z(45)

    for i, x in enumerate(FLOWER_X):
        if st.flowers:
            s.oval(("flower", i), x, GROUND - 2.5, 4, 2).fill(shade(PETALS[i], light)).z(46)
            s.block(("flower", i, "eye"), x + 1.5, GROUND - 2, 1, 1).fill(shade((255, 214, 92), light)).z(47)
        else:  # a closed green bud
            s.oval(("flower", i), x + 1, GROUND - 1.5, 2, 1).fill(shade(LEAVES_LIT, light)).z(46)
        s.block(("flower", i, "stem"), x + 1.5, GROUND - 0.5, 1, 0.5).fill(shade(LEAVES, light)).z(45)

    # The tree.
    s.block("tree/trunk", 15, 11, 3, GROUND - 11 + 0.5).fill(shade(TRUNK, light)).z(50)
    s.oval("tree/leaves", 5, 6, 22, 7).fill(shade(LEAVES, light)).z(51)
    s.oval("tree/leaves/lit", 8, 6.5, 13, 3.5).fill(shade(LEAVES_LIT, light)).z(52)
    s.oval("tree/leaf", 22.5, 10.5, 2, 1).fill(shade(LEAVES_LIT, light)).z(53)
    s.oval("nest", 3, 9.5, 10, 2.5).fill(shade(NEST, light)).z(80)

    if st.bites < 4:
        aw = 4 * st.apple_sx * (1 - st.bites / 4)
        ah = 2 * st.apple_sy
        s.oval("apple", st.apple_x + (4 - aw) / 2, st.apple_bottom - ah, aw, ah).fill(
            shade(APPLE, light)
        ).z(60)

    draw_pip(s, st.pip, light)

    for i in range(st.zs):
        s.text(("zz", i), 13 + 2 * i, 7 - 1.5 * i, "z" if i < 2 else "Z").fg((236, 236, 255)).bold().z(90)
    if st.thought:
        for i, (x, y, w, h) in enumerate([(12, 6.5, 2, 1), (14, 5, 3, 1.5), (16, 0.5, 11, 4.5)]):
            s.oval(("thought", i), x, y, w, h).fill((255, 255, 255)).z(90)
        s.oval("thought/apple", 20, 1.75, 3, 2).fill(APPLE).z(91)
        s.oval("thought/leaf", 22.5, 1.5, 2, 1).fill(LEAVES_LIT).z(92)
    spots = {1: [(26, 13), (35, 12), (29, 11)], 2: [(25, 12), (36, 13.5), (31, 10.5)]}
    for i, (x, y) in enumerate(spots.get(st.sparkles, [])):
        s.text(("sparkle", i), x, y, "*").fg((255, 236, 120)).bold().z(95)
    if st.the_end:
        s.text("the end", W // 2 - 3, 9, "the end").fg(INK).bold().z(100)
    return s


if __name__ == "__main__":
    ct.explain(
        story(),
        view,
        title="Pip's Morning",
        fit=True,  # made of shapes and titles only, so it can grow with the terminal
        canvas=(W, H),
        motion=[ct.Rule("cloud/*", pace="linear"), ct.Rule("apple", pace="linear")],
        timing=ct.Timing(
            default=0.6,
            events={
                "snore": 1.0,
                "dawn": 1.8,
                "sunrise": 2.0,
                "bloom": 0.9,
                "wake": 0.5,
                "stretch": 0.7,
                "settle": 0.3,
                "blink": 0.12,
                "hungry": 1.6,
                "crouch": 0.35,
                "hop": 0.35,
                "land": 0.2,
                "peck": 0.12,
                "fall": 0.25,
                "bounce": 0.25,
                "roll": 0.3,
                "flap": 0.3,
                "munch": 0.35,
                "chew": 0.25,
                "yum": 0.5,
                "fly": 0.35,
            },
            opening=1.2,
            closing=3.0,
        ),
    ).play()
