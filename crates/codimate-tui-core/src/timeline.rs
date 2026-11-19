//! A finished explanation as a function of time.
//!
//! The engine receives Scenes that are already drawn (one per moment) and the
//! beats between them. It never runs the author's code. The one question an
//! [`Explanation`] answers is: what does the screen look like at `seconds`? The
//! answer is pure, so seeking anywhere is instant.

use crate::motion::{Rule, between};
use crate::scene::Scene;

/// What the author says about one stretch of time: its name, a caption, and how
/// long it lasts. Beat `i` animates from Scene `i` to Scene `i + 1`; a hold is a
/// beat between two identical Scenes.
#[derive(Clone, Debug, PartialEq)]
pub struct BeatSpec {
    pub name: String,
    pub caption: String,
    pub duration: f32,
}

/// A [`BeatSpec`] placed on the timeline.
#[derive(Clone, Debug, PartialEq)]
pub struct Beat {
    pub name: String,
    pub caption: String,
    pub start: f32,
    pub duration: f32,
}

/// Why an Explanation couldn't be built. The message is written for the author.
#[derive(Debug, Clone, PartialEq)]
pub struct Error(pub String);

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for Error {}

/// Scenes, beats, motion rules and canvas size, combined.
pub struct Explanation {
    pub title: String,
    pub canvas: (u16, u16),
    /// How finely solid shapes and titles are drawn. See [`crate::render::Pixels`].
    pub pixels: crate::render::Pixels,
    /// Scale the picture to fill the player's stage instead of drawing it at
    /// its canvas size. Best for pictures made of shapes and titles.
    pub fit: bool,
    scenes: Vec<Scene>,
    beats: Vec<Beat>,
    rules: Vec<Rule>,
}

impl Explanation {
    /// `scenes` must be exactly one longer than `beats`.
    pub fn new(
        title: impl Into<String>,
        canvas: (u16, u16),
        scenes: Vec<Scene>,
        beats: Vec<BeatSpec>,
        rules: Vec<Rule>,
    ) -> Result<Self, Error> {
        if beats.is_empty() {
            return Err(Error("an explanation needs at least one beat".into()));
        }
        if scenes.len() != beats.len() + 1 {
            return Err(Error(format!(
                "{} beats need {} scenes, got {}",
                beats.len(),
                beats.len() + 1,
                scenes.len()
            )));
        }
        let mut start = 0.0;
        let mut placed = Vec::with_capacity(beats.len());
        for b in beats {
            if !b.duration.is_finite() || b.duration < 0.0 {
                return Err(Error(format!(
                    "beat `{}` has duration {}; durations must be finite and not negative",
                    b.name, b.duration
                )));
            }
            placed.push(Beat {
                name: b.name,
                caption: b.caption,
                start,
                duration: b.duration,
            });
            start += b.duration;
        }
        Ok(Explanation {
            title: title.into(),
            canvas,
            pixels: Default::default(),
            fit: false,
            scenes,
            beats: placed,
            rules,
        })
    }

    pub fn beats(&self) -> &[Beat] {
        &self.beats
    }

    pub fn duration(&self) -> f32 {
        self.beats.last().map_or(0.0, |b| b.start + b.duration)
    }

    /// Index of the beat playing at `seconds` (clamped to the timeline).
    pub fn beat_at(&self, seconds: f32) -> usize {
        let s = seconds.clamp(0.0, self.duration());
        self.beats.iter().rposition(|b| b.start <= s).unwrap_or(0)
    }

    /// The caption to show at `seconds`: the current beat's, or the most recent
    /// one before it, so a hold doesn't blank the explanation.
    pub fn caption_at(&self, seconds: f32) -> &str {
        let i = self.beat_at(seconds);
        self.beats[..=i]
            .iter()
            .rev()
            .map(|b| b.caption.as_str())
            .find(|c| !c.is_empty())
            .unwrap_or("")
    }

    /// What the canvas shows at `seconds`. Pure.
    pub fn scene_at(&self, seconds: f32) -> Scene {
        let i = self.beat_at(seconds);
        let beat = &self.beats[i];
        let t = if beat.duration > 0.0 {
            ((seconds - beat.start) / beat.duration).clamp(0.0, 1.0)
        } else {
            1.0
        };
        between(&self.scenes[i], &self.scenes[i + 1], t, &self.rules)
    }
}
