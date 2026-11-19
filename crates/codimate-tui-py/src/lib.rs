//! The bridge: Python's one crossing into the engine.
//!
//! Python draws every Scene (once per event) and hands them over in a single call,
//! as lists of flat dicts. This crate turns those into engine values and nothing
//! else: anything that decides what an animation *means* lives in
//! `codimate-tui-core`, which does not know Python exists. Nothing crosses this
//! boundary in a loop.

use codimate_tui_core::{
    BeatSpec, Explanation, Kind, Node, Pace, Pixels, Rgb, Rule, Scene, Shape, glyphs, player,
    scene_to_ansi, scene_to_text,
};
use pyo3::exceptions::{PyOSError, PyValueError};
use pyo3::prelude::*;

/// One node as Python sends it: a dict of flat fields.
///
/// A near-duplicate of `Node`, on purpose: `Node` must not know PyO3 exists, and
/// restating the fields here keeps the payload a plain data structure.
#[derive(FromPyObject)]
#[pyo3(from_item_all)]
struct PyNode {
    name: String,
    kind: String,
    x: f32,
    y: f32,
    w: f32,
    h: f32,
    text: String,
    fg: (u8, u8, u8),
    fill: Option<(u8, u8, u8)>,
    bold: bool,
    opacity: f32,
    z: i32,
    font: Option<Vec<String>>,
}

impl TryFrom<PyNode> for Node {
    type Error = PyErr;

    fn try_from(n: PyNode) -> PyResult<Node> {
        // A closed vocabulary: an unknown kind is an error, never a silent no-op.
        let shape = |shape| Kind::Box {
            w: n.w,
            h: n.h,
            label: n.text.clone(),
            shape,
        };
        let kind = match n.kind.as_str() {
            "box" => shape(Shape::Framed),
            "block" => shape(Shape::Block),
            "oval" => shape(Shape::Oval),
            "text" => Kind::Text {
                text: n.text.clone(),
            },
            "title" => {
                let fonts = n.font.clone().unwrap_or_default();
                if fonts.is_empty() {
                    return Err(PyValueError::new_err(format!(
                        "title `{}` has no font",
                        n.name
                    )));
                }
                for f in &fonts {
                    glyphs::check_font(f)
                        .map_err(|e| PyValueError::new_err(format!("title `{}`: {e}", n.name)))?;
                }
                Kind::Title {
                    text: n.text.clone(),
                    size: n.h,
                    fonts,
                }
            }
            other => {
                return Err(PyValueError::new_err(format!(
                    "node `{}` has unknown kind `{other}` (expected `box`, `block`, `oval`, `text` or `title`)",
                    n.name
                )));
            }
        };
        let rgb = |(r, g, b): (u8, u8, u8)| Rgb(r, g, b);
        Ok(Node {
            name: n.name,
            x: n.x,
            y: n.y,
            kind,
            fg: rgb(n.fg),
            fill: n.fill.map(rgb),
            bold: n.bold,
            opacity: n.opacity,
            z: n.z,
        })
    }
}

#[derive(FromPyObject)]
#[pyo3(from_item_all)]
struct PyBeat {
    name: String,
    caption: String,
    duration: f32,
}

#[derive(FromPyObject)]
#[pyo3(from_item_all)]
struct PyRule {
    pattern: String,
    arc: Option<f32>,
    pace: String,
}

fn build(
    title: String,
    canvas: (u16, u16),
    scenes: Vec<Vec<PyNode>>,
    beats: Vec<PyBeat>,
    rules: Vec<PyRule>,
) -> PyResult<Explanation> {
    let scenes = scenes
        .into_iter()
        .map(|nodes| {
            let nodes = nodes
                .into_iter()
                .map(Node::try_from)
                .collect::<PyResult<Vec<_>>>()?;
            Scene::try_from_nodes(nodes).map_err(|e| PyValueError::new_err(e.0))
        })
        .collect::<PyResult<Vec<_>>>()?;
    let beats = beats
        .into_iter()
        .map(|b| BeatSpec {
            name: b.name,
            caption: b.caption,
            duration: b.duration,
        })
        .collect();
    let rules = rules
        .into_iter()
        .map(|r| {
            let pace = match r.pace.as_str() {
                "smooth" => Pace::Smooth,
                "linear" => Pace::Linear,
                other => {
                    return Err(PyValueError::new_err(format!(
                        "rule `{}` has unknown pace `{other}` (expected `smooth` or `linear`)",
                        r.pattern
                    )));
                }
            };
            let rule = Rule::new(r.pattern).pace(pace);
            Ok(match r.arc {
                Some(h) => rule.arc(h),
                None => rule,
            })
        })
        .collect::<PyResult<Vec<_>>>()?;
    Explanation::new(title, canvas, scenes, beats, rules).map_err(|e| PyValueError::new_err(e.0))
}

fn parse_pixels(s: &str) -> PyResult<Pixels> {
    Pixels::parse(s).ok_or_else(|| {
        PyValueError::new_err(format!(
            "pixels must be `half`, `quad` or `sextant`, got `{s}`"
        ))
    })
}

/// Play in the terminal from `start_at` seconds; returns the time the viewer
/// quit at.
#[pyfunction]
#[pyo3(signature = (scenes, beats, rules, title, canvas, start_at = 0.0, pixels = "half", fit = false))]
#[allow(clippy::too_many_arguments)]
fn play(
    py: Python<'_>,
    scenes: Vec<Vec<PyNode>>,
    beats: Vec<PyBeat>,
    rules: Vec<PyRule>,
    title: String,
    canvas: (u16, u16),
    start_at: f32,
    pixels: &str,
    fit: bool,
) -> PyResult<f32> {
    let mut ex = build(title, canvas, scenes, beats, rules)?;
    ex.pixels = parse_pixels(pixels)?;
    ex.fit = fit;
    // Release the GIL: the player owns the thread until the viewer quits.
    py.detach(|| player::run(ex, start_at))
        .map_err(|e| PyOSError::new_err(format!("terminal error: {e}")))
}

/// One moment as text, plus the caption showing at that moment. With `color`,
/// the text carries 24-bit ANSI colour codes (needed to see solid shapes).
#[pyfunction]
#[pyo3(signature = (scenes, beats, rules, canvas, seconds, color = false, pixels = "half", scale = 1.0))]
#[allow(clippy::too_many_arguments)]
fn frame_text(
    scenes: Vec<Vec<PyNode>>,
    beats: Vec<PyBeat>,
    rules: Vec<PyRule>,
    canvas: (u16, u16),
    seconds: f32,
    color: bool,
    pixels: &str,
    scale: f32,
) -> PyResult<(String, String)> {
    let ex = build(String::new(), canvas, scenes, beats, rules)?;
    let pixels = parse_pixels(pixels)?;
    if !(scale.is_finite() && scale > 0.0) {
        return Err(PyValueError::new_err(format!(
            "scale must be above 0, got {scale}"
        )));
    }
    let scene = ex.scene_at(seconds).scaled(scale);
    let size = (
        ((ex.canvas.0 as f32 * scale).floor() as u16).max(1),
        ((ex.canvas.1 as f32 * scale).floor() as u16).max(1),
    );
    let text = if color {
        scene_to_ansi(&scene, size, pixels)
    } else {
        scene_to_text(&scene, size, pixels)
    };
    Ok((text, ex.caption_at(seconds).to_string()))
}

/// How many cells wide `text` is as a title `size` cells tall in `fonts`.
#[pyfunction]
fn measure(fonts: Vec<String>, text: &str, size: f32) -> PyResult<f32> {
    glyphs::measure(&fonts, text, size * 2.0).map_err(PyValueError::new_err)
}

#[pymodule]
fn _codimate_tui(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(measure, m)?)?;
    m.add_function(wrap_pyfunction!(play, m)?)?;
    m.add_function(wrap_pyfunction!(frame_text, m)?)?;
    Ok(())
}
