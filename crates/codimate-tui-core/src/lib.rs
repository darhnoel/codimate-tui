//! codimate-tui engine.
//!
//! Authors write explainers in Python. The Python package draws one [`Scene`] per
//! moment and hands them over once, with the beats and motion rules; this crate
//! does everything per frame: interpolation ([`motion`]), the timeline
//! ([`timeline`]), drawing ([`render`]) and the interactive player ([`player`]).
//!
//! Nodes are paired across Scenes **by name**. Whatever differs becomes movement.

pub mod glyphs;
pub mod motion;
pub mod player;
pub mod render;
pub mod scene;
pub mod timeline;

pub use motion::{Pace, Path, Rule, ease};
pub use render::{Pixels, draw_scene, scene_to_ansi, scene_to_text};
pub use scene::{Kind, Node, Rgb, Scene, Shape, centered_row, color};
pub use timeline::{Beat, BeatSpec, Error, Explanation};
