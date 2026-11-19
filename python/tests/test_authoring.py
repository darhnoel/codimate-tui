import pytest

import codimate_tui as ct


def counter():
    n = [0]
    tr = ct.Tracer(n)
    n[0] += 1
    tr.emit("inc", n, say="one")
    n[0] += 1
    tr.emit("inc", n, say="two")
    return tr


def number_view(f):
    s = ct.Scene()
    s.text("n", f.state[0] * 5, 0, f.state[0])
    return s


def test_tracer_keeps_its_own_copy():
    tr = counter()
    assert tr.initial == [0]
    assert [state for _, state in tr.steps] == [[1], [2]]


def test_timeline_wraps_events_in_holds():
    ex = ct.explain(counter(), number_view, timing=ct.Timing(default=2, opening=1, closing=1))
    assert [(s, d, n) for s, d, n, _ in ex.timeline()] == [
        (0.0, 1.0, "start"),
        (1.0, 2.0, "inc"),
        (3.0, 2.0, "inc"),
        (5.0, 1.0, "end"),
    ]
    assert ex.duration == 6.0


def test_frames_round_trip_through_the_engine():
    ex = ct.explain(counter(), number_view, canvas=(12, 1), timing=ct.Timing(default=2, opening=1, closing=1))
    assert ex.frame(0) == "0\n-- 0.00s · \n"
    assert ex.frame(2) == "   1\n-- 2.00s · one\n"  # midpoint: x 0 → 5 is at 2.5, label switched
    # A boundary belongs to the beat that starts there: same picture, next caption.
    assert ex.frame(3) == "     1\n-- 3.00s · two\n"
    assert ex.frame(6) == "          2\n-- 6.00s · two\n"  # caption survives the closing hold


def test_moving_nodes_follow_their_rule():
    def view(f):
        s = ct.Scene()
        s.rect("b", f.state[0] * 6, 4, 3, 3).label("x")
        return s

    ex = ct.explain(counter(), view, canvas=(20, 8), motion=[ct.Rule("b", arc=4)],
                    timing=ct.Timing(default=2, opening=1, closing=1))
    lines = ex.frame(2).splitlines()  # halfway through the first hop: 4 cells up
    assert lines[0].strip() == "╭─╮"


def test_duplicate_names_fail_at_the_authors_line():
    s = ct.Scene()
    s.text(("tok", 1), 0, 0, "a")
    with pytest.raises(ValueError, match="duplicate node name 'tok/1'"):
        s.text("tok/1", 0, 0, "b")


def test_colours():
    assert ct.rgb("blue") == ct.PALETTE["blue"]
    assert ct.rgb("#ff8000") == (255, 128, 0)
    assert ct.mix((0, 0, 0), (100, 200, 50), 0.5) == (50, 100, 25)
    with pytest.raises(ValueError, match="unknown colour 'blu'"):
        ct.rgb("blu")


def test_view_must_return_a_scene():
    with pytest.raises(TypeError, match="view must return a Scene, got NoneType for the starting state"):
        ct.explain(counter(), lambda f: None)


def test_engine_rejects_unknown_kinds():
    ex = ct.explain(counter(), number_view)
    ex._scenes[1]._nodes["n"]["kind"] = "circle"
    with pytest.raises(ValueError, match="unknown kind `circle`"):
        ex.frame(0)


def test_linear_pace_moves_at_constant_speed():
    timing = ct.Timing(default=2, opening=1, closing=1)
    smooth = ct.explain(counter(), number_view, canvas=(12, 1), timing=timing)
    linear = ct.explain(counter(), number_view, canvas=(12, 1), timing=timing,
                        motion=[ct.Rule("*", pace="linear")])
    # A quarter of the way through the first move (x 0 -> 5).
    # The label still reads "0": text switches at the halfway point.
    assert smooth.frame(1.5).startswith("0\n")  # eased: barely started
    assert linear.frame(1.5).startswith(" 0\n")  # linear: 1.25 cells along


def test_unknown_pace_is_rejected():
    with pytest.raises(ValueError, match="pace must be 'smooth' or 'linear'"):
        ct.Rule("*", pace="bouncy")


def test_solid_shapes_draw_without_borders_and_show_in_colour():
    def view(frame):
        s = ct.Scene()
        s.oval("sun", 0, 0, 8, 4).fill("yellow")
        s.block("ground", 0, 4, 8, 1).fill("green")
        return s

    ex = ct.explain(counter(), view, canvas=(8, 5))
    plain = ex.frame(0, pixels="half")
    assert "╭" not in plain and "│" not in plain  # no outlines
    assert "▀" in plain  # the oval's curved edge uses half cells
    finer = ex.frame(0)  # sextants by default: 2 x 3 pixels per cell
    assert any(0x1FB00 <= ord(ch) <= 0x1FB3B for ch in finer)
    coloured = ex.frame(0, color=True)
    assert "48;2;235;200;80m" in coloured  # yellow
    assert "48;2;80;200;120m" in coloured  # green


def test_titles_measure_and_reject_unknown_fonts():
    assert ct.measure("ខ្មែរ", 6) > 0
    assert ct.measure("ខ្មែរ", 12) > ct.measure("ខ្មែរ", 6)
    with pytest.raises(ValueError, match="font file '/no/such/font.ttf' not found"):
        ct.Scene().title("t", 0, 0, "hi", font="/no/such/font.ttf")
    with pytest.raises(ValueError, match="font 'Nosuch Font:bold' not found"):
        ct.measure("hi", 6, font=["Nosuch Font:bold"])


def test_title_draws_khmer_as_pixels():
    def view(frame):
        s = ct.Scene()
        s.title("t", 20, 0, "សួស្តី", 6).fg("yellow")
        return s

    ex = ct.explain(counter(), view, canvas=(40, 8))
    assert "▀" in ex.frame(0, pixels="half")
    assert any(0x1FB00 <= ord(ch) <= 0x1FB3B for ch in ex.frame(0))


def test_pixels_setting_is_checked():
    with pytest.raises(ValueError, match="pixels must be one of"):
        ct.explain(counter(), number_view, pixels="tiny")


def intro_deck():
    import runpy
    from pathlib import Path

    path = Path(__file__).parents[2] / "examples" / "intro.py"
    return runpy.run_path(str(path))["deck"]()


def test_intro_example_draws_only_what_macos_terminal_can():
    """Every frame, at every beat, uses plain text and the half block alone:
    macOS Terminal shows quadrant and sextant blocks, and the line-drawing
    corners of outlined boxes, as boxes or with gaps."""
    ex = intro_deck()
    allowed = set("▀•·")
    for start, duration, _, _ in ex.timeline():
        for t in (start + duration / 2, start + duration):
            frame = ex.frame(t)
            assert {ch for ch in frame if ord(ch) > 127} <= allowed, t
