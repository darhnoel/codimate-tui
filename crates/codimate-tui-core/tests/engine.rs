use codimate_tui_core::motion::between;
use codimate_tui_core::*;

fn one(name: &str, x: f32, y: f32) -> Scene {
    let mut s = Scene::new();
    s.rect(name, x, y, 3.0, 3.0).label("a");
    s
}

#[test]
fn endpoints_are_exact() {
    let (a, b) = (one("n", 0.0, 0.0), one("n", 10.0, 4.0));
    let at0 = between(&a, &b, 0.0, &[]);
    let at1 = between(&a, &b, 1.0, &[]);
    assert_eq!((at0.nodes()[0].x, at0.nodes()[0].y), (0.0, 0.0));
    assert_eq!((at1.nodes()[0].x, at1.nodes()[0].y), (10.0, 4.0));
}

#[test]
fn unmatched_nodes_fade_in_and_out() {
    let (a, b) = (one("old", 0.0, 0.0), one("new", 5.0, 0.0));
    let mid = between(&a, &b, 0.5, &[]);
    assert_eq!(mid.get("new").unwrap().opacity, 0.5);
    assert_eq!(mid.get("old").unwrap().opacity, 0.5);
    assert_eq!(between(&a, &b, 0.0, &[]).get("new").unwrap().opacity, 0.0);
}

#[test]
fn arc_lifts_only_things_that_move() {
    let rules = [Rule::new("*").arc(4.0)];
    let moving = between(&one("n", 0.0, 5.0), &one("n", 10.0, 5.0), 0.5, &rules);
    assert_eq!(
        moving.nodes()[0].y,
        1.0,
        "peak of the hop is `height` above the line"
    );

    let still = between(&one("n", 0.0, 5.0), &one("n", 0.0, 5.0), 0.5, &rules);
    assert_eq!(
        still.nodes()[0].y,
        5.0,
        "a rule never makes a still node move"
    );
}

#[test]
fn labels_switch_at_the_midpoint() {
    let a = one("n", 0.0, 0.0);
    let mut b = Scene::new();
    b.rect("n", 0.0, 0.0, 3.0, 3.0).label("b");
    assert_eq!(between(&a, &b, 0.49, &[]).nodes()[0].content(), "a");
    assert_eq!(between(&a, &b, 0.51, &[]).nodes()[0].content(), "b");
}

#[test]
#[should_panic(expected = "duplicate node name")]
fn duplicate_names_are_rejected() {
    let mut s = Scene::new();
    s.text("x", 0.0, 0.0, "a");
    s.text("x", 1.0, 0.0, "b");
}

fn at(x: f32) -> Scene {
    let mut s = Scene::new();
    s.text("n", x, 0.0, x);
    s
}

fn beat(name: &str, caption: &str, duration: f32) -> BeatSpec {
    BeatSpec {
        name: name.into(),
        caption: caption.into(),
        duration,
    }
}

/// The shape the Python side sends: an opening hold, two events, a closing hold.
fn counter() -> Explanation {
    let scenes = vec![at(0.0), at(0.0), at(5.0), at(10.0), at(10.0)];
    let beats = vec![
        beat("start", "", 1.0),
        beat("inc", "one", 2.0),
        beat("inc", "two", 2.0),
        beat("end", "", 1.0),
    ];
    Explanation::new("counter", (20, 1), scenes, beats, vec![]).unwrap()
}

#[test]
fn scene_and_beat_counts_must_agree() {
    let err = Explanation::new("x", (1, 1), vec![at(0.0)], vec![beat("a", "", 1.0)], vec![]);
    assert_eq!(err.err().unwrap().0, "1 beats need 2 scenes, got 1");
}

#[test]
fn negative_durations_are_rejected() {
    let err = Explanation::new(
        "x",
        (1, 1),
        vec![at(0.0), at(1.0)],
        vec![beat("a", "", -1.0)],
        vec![],
    );
    assert!(err.err().unwrap().0.contains("beat `a` has duration -1"));
}

#[test]
fn bridge_scenes_reject_duplicate_names() {
    let n = at(0.0).nodes()[0].clone();
    assert!(Scene::try_from_nodes(vec![n.clone(), n]).is_err());
}

#[test]
fn timeline_has_holds_around_events() {
    let ex = counter();
    let names: Vec<_> = ex.beats().iter().map(|b| b.name.as_str()).collect();
    assert_eq!(names, ["start", "inc", "inc", "end"]);
    assert_eq!(ex.duration(), 6.0);
    assert_eq!(ex.beat_at(0.5), 0);
    assert_eq!(ex.beat_at(1.0), 1);
    assert_eq!(ex.beat_at(99.0), 3);
}

#[test]
fn scene_at_lands_on_each_view_scene() {
    let ex = counter();
    assert_eq!(ex.scene_at(0.0).get("n").unwrap().x, 0.0);
    assert_eq!(ex.scene_at(3.0).get("n").unwrap().x, 5.0); // end of first event
    assert_eq!(ex.scene_at(6.0).get("n").unwrap().x, 10.0);
    assert_eq!(ex.scene_at(2.0).get("n").unwrap().x, 2.5); // halfway, eased midpoint
}

#[test]
fn caption_persists_through_the_closing_hold() {
    let ex = counter();
    assert_eq!(ex.caption_at(0.5), "");
    assert_eq!(ex.caption_at(2.0), "one");
    assert_eq!(ex.caption_at(5.5), "two");
}

#[test]
fn boxes_render_with_border_and_centred_label() {
    let mut s = Scene::new();
    s.rect("b", 1.0, 0.0, 5.0, 3.0).label("42");
    s.text("t", 0.0, 3.0, "hi");
    let text = scene_to_text(&s, (8, 4), Pixels::Half);
    assert_eq!(text, " ╭───╮\n │42 │\n ╰───╯\nhi\n");
}

#[test]
fn invisible_nodes_are_not_drawn() {
    let mut s = Scene::new();
    s.text("t", 0.0, 0.0, "ghost").opacity(0.0);
    assert_eq!(scene_to_text(&s, (6, 1), Pixels::Half), "\n");
}

#[test]
fn linear_pace_keeps_constant_speed() {
    let (a, b) = (one("n", 0.0, 0.0), one("n", 10.0, 0.0));
    let smooth = between(&a, &b, 0.25, &[]);
    let linear = between(&a, &b, 0.25, &[Rule::new("*").pace(Pace::Linear)]);
    assert_eq!(linear.nodes()[0].x, 2.5);
    assert!(
        smooth.nodes()[0].x < 1.0,
        "smooth is still accelerating at a quarter"
    );
}

#[test]
fn nodes_outside_the_canvas_are_clipped() {
    use ratatui::{buffer::Buffer, layout::Rect};
    let mut s = Scene::new();
    s.text("inside", 0.0, 0.0, "ab");
    s.text("outside", 6.0, 0.0, "zz"); // past a 4-wide canvas
    let area = Rect::new(0, 0, 20, 1); // the terminal has room, the stage doesn't
    let mut buf = Buffer::empty(area);
    draw_scene(&s, (4, 1), area, color::BG, Pixels::Half, &mut buf);
    let row: String = (0..20).map(|x| buf[(x, 0)].symbol()).collect();
    assert_eq!(row.trim(), "ab");
}

#[test]
fn solid_shapes_paint_half_cells() {
    // A block one cell wide starting halfway down row 0 and one cell tall: it
    // covers the bottom half of row 0 and the top half of row 1.
    let mut s = Scene::new();
    s.block("b", 0.0, 0.5, 1.0, 1.0).fill(color::RED);
    let text = scene_to_text(&s, (2, 3), Pixels::Half);
    assert_eq!(
        text, "\u{2580}\n\u{2580}\n\n",
        "half-cell rows come out as upper-half blocks"
    );

    // The ANSI form carries the colours: row 0 is background over red, row 1
    // red over background.
    let ansi = scene_to_ansi(&s, (1, 2), Pixels::Half);
    let rows: Vec<&str> = ansi.lines().collect();
    assert!(
        rows[0].contains("38;2;22;24;30;48;2;230;80;80m\u{2580}"),
        "{:?}",
        rows[0]
    );
    assert!(
        rows[1].contains("38;2;230;80;80;48;2;22;24;30m\u{2580}"),
        "{:?}",
        rows[1]
    );
}

#[test]
fn solid_block_has_no_border_but_rect_does() {
    let mut s = Scene::new();
    s.block("flat", 0.0, 0.0, 4.0, 2.0).fill(color::BLUE);
    s.rect("framed", 5.0, 0.0, 4.0, 2.0);
    let text = scene_to_text(&s, (9, 2), Pixels::Half);
    assert_eq!(text, "     ╭──╮\n     ╰──╯\n");
}

#[test]
fn oval_is_rounder_than_its_box() {
    // A circle 8 cells wide and 4 tall (8 × 8 pixels): the corners stay empty.
    let mut s = Scene::new();
    s.oval("o", 0.0, 0.0, 8.0, 4.0).fill(color::GREEN);
    let text = scene_to_text(&s, (8, 4), Pixels::Half);
    let rows: Vec<&str> = text.lines().collect();
    assert!(
        rows[0].starts_with(' ') && rows[0].contains('\u{2580}'),
        "{:?}",
        rows[0]
    );
    assert!(
        rows[3].starts_with(' ') && rows[3].contains('\u{2580}'),
        "{:?}",
        rows[3]
    );
}

#[test]
fn shape_switches_at_the_midpoint() {
    let mut a = Scene::new();
    a.oval("eye", 0.0, 0.0, 2.0, 1.0);
    let mut b = Scene::new();
    b.block("eye", 0.0, 0.0, 2.0, 0.5);
    let shape = |s: &Scene| match &s.get("eye").unwrap().kind {
        Kind::Box { shape, .. } => *shape,
        _ => unreachable!(),
    };
    assert_eq!(shape(&between(&a, &b, 0.4, &[])), Shape::Oval);
    assert_eq!(shape(&between(&a, &b, 0.6, &[])), Shape::Block);
}

#[test]
fn text_keeps_combined_letters_together() {
    // ស្តី is four code points but one visible letter group: it must stay in one
    // piece (the terminal stacks it), and what follows starts after its width.
    let mut s = Scene::new();
    s.text("t", 0.0, 0.0, "ស្តី|");
    let text = scene_to_text(&s, (10, 1), Pixels::Half);
    assert!(text.starts_with("ស្តី"), "{text:?}");
    assert_eq!(text.trim_end(), "ស្តី|");
}

const KHMER: &str = "/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf";
const LATIN: &str = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf";

fn have_fonts() -> bool {
    let ok = std::path::Path::new(KHMER).exists() && std::path::Path::new(LATIN).exists();
    if !ok {
        eprintln!("skipping: Noto Sans / Noto Sans Khmer not installed");
    }
    ok
}

#[test]
fn titles_are_drawn_as_pixels_centred_on_x() {
    if !have_fonts() {
        return;
    }
    let mut s = Scene::new();
    s.title("t", 20.0, 0.0, "ខ្មែរ", 6.0, vec![KHMER.into()]);
    let text = scene_to_text(&s, (40, 8), Pixels::Half);
    assert!(
        text.contains('\u{2580}'),
        "title ink shows as half blocks:\n{text}"
    );
    let cols: Vec<usize> = text
        .lines()
        .flat_map(|l| {
            l.chars()
                .enumerate()
                .filter(|(_, c)| *c != ' ')
                .map(|(i, _)| i)
                .collect::<Vec<_>>()
        })
        .collect();
    let (l, r) = (*cols.iter().min().unwrap(), *cols.iter().max().unwrap());
    let middle = (l + r) as f32 / 2.0;
    assert!(
        (middle - 20.0).abs() <= 1.5,
        "ink spans {l}..{r}, centre {middle}"
    );
}

#[test]
fn letters_a_font_lacks_fall_back_to_the_next_font() {
    if !have_fonts() {
        return;
    }
    let both = [KHMER.to_string(), LATIN.to_string()];
    let latin = [LATIN.to_string()];
    // Noto Sans Khmer has no Latin letters: with a fallback, "Terminal" is drawn
    // by Noto Sans at the same em size, so it measures the same as Noto Sans alone
    // scaled to the Khmer font's em.
    let mixed = glyphs::measure(&both, "Terminal", 20.0).unwrap();
    let alone = glyphs::measure(&latin, "Terminal", 20.0).unwrap();
    assert!(mixed > 0.0 && alone > 0.0);
    let khmer_only = glyphs::measure(&both[..1], "Terminal", 20.0).unwrap();
    assert_ne!(
        mixed, khmer_only,
        "fallback changed which font drew the Latin"
    );
}

#[test]
fn a_bad_font_is_reported() {
    assert!(glyphs::check_font("/no/such/font.ttf").is_err());
}

#[test]
fn finer_pixels_pick_the_matching_block_character() {
    // A block covering the left half of a cell: one pixel column of two (quad,
    // sextant), so it shows as the left-half block in both.
    let mut s = Scene::new();
    s.block("b", 0.0, 0.0, 0.5, 1.0).fill(color::RED);
    assert_eq!(scene_to_text(&s, (1, 1), Pixels::Quad), "▌\n");
    assert_eq!(scene_to_text(&s, (1, 1), Pixels::Sextant), "▌\n");

    // The top third of a cell, full width: sextant pixels 1 and 2 (🬂).
    let mut s = Scene::new();
    s.block("b", 0.0, 0.0, 1.0, 1.0 / 3.0).fill(color::RED);
    assert_eq!(scene_to_text(&s, (1, 1), Pixels::Sextant), "🬂\n");

    // A whole cell is a full block, in every mode but half (which shows a
    // solid cell as a coloured space).
    let mut s = Scene::new();
    s.block("b", 0.0, 0.0, 1.0, 1.0).fill(color::RED);
    assert_eq!(scene_to_text(&s, (1, 1), Pixels::Sextant), "\n");
}

#[test]
fn text_over_pixels_sits_on_their_colour() {
    let mut s = Scene::new();
    s.block("b", 0.0, 0.0, 4.0, 1.0).fill(color::BLUE);
    s.text("t", 1.0, 0.0, "hi");
    let ansi = scene_to_ansi(&s, (4, 1), Pixels::Sextant);
    // "h" is drawn on blue, not on the stage background.
    assert!(ansi.contains("48;2;66;135;245mh"), "{ansi:?}");
}

#[test]
fn scaling_grows_shapes_and_titles_but_not_terminal_text() {
    let mut s = Scene::new();
    s.block("b", 1.0, 2.0, 3.0, 4.0);
    s.title("t", 5.0, 1.0, "hi", 6.0, vec!["font.ttf".into()]);
    s.text("x", 2.0, 2.0, "label");
    let big = s.scaled(2.0);
    let b = big.get("b").unwrap();
    assert_eq!((b.x, b.y), (2.0, 4.0));
    assert!(matches!(b.kind, Kind::Box { w, h, .. } if w == 6.0 && h == 8.0));
    assert!(matches!(&big.get("t").unwrap().kind, Kind::Title { size, .. } if *size == 12.0));
    let x = big.get("x").unwrap();
    assert_eq!((x.x, x.y, x.content()), (4.0, 4.0, "label"));
}
