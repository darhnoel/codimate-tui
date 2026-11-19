//! Motion: how a Scene turns into the next one. Timeless — durations live in
//! [`crate::timeline::Timing`], never here.

use std::collections::HashMap;

use crate::scene::{Kind, Node, Scene};

/// Ease in and out (cubic). Pure remap of `t ∈ [0, 1]`.
pub fn ease(t: f32) -> f32 {
    let t = t.clamp(0.0, 1.0);
    if t < 0.5 {
        4.0 * t * t * t
    } else {
        1.0 - (-2.0 * t + 2.0).powi(3) / 2.0
    }
}

/// The route a moving node takes.
#[derive(Clone, Debug, PartialEq)]
pub enum Path {
    /// A straight line (the default).
    Straight,
    /// A hop: rises `height` cells at the midpoint, then lands.
    Arc { height: f32 },
}

/// How progress through a beat is paced.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Pace {
    /// Ease in and out: things settle at every event. Right for explanations.
    #[default]
    Smooth,
    /// Constant speed: for things that are mid-journey at every event (a game
    /// loop, a scrolling camera). Easing those would make them stop at each tick.
    Linear,
}

impl Pace {
    fn apply(self, t: f32) -> f32 {
        match self {
            Pace::Smooth => ease(t),
            Pace::Linear => t.clamp(0.0, 1.0),
        }
    }
}

/// Picks a [`Path`] and a [`Pace`] for nodes whose name matches `pattern` (`*`
/// matches any run of characters). The first matching rule wins. A rule never
/// makes a still node move.
#[derive(Clone, Debug)]
pub struct Rule {
    pattern: String,
    path: Path,
    pace: Pace,
}

impl Rule {
    pub fn new(pattern: impl Into<String>) -> Self {
        Rule {
            pattern: pattern.into(),
            path: Path::Straight,
            pace: Pace::Smooth,
        }
    }

    pub fn arc(mut self, height: f32) -> Self {
        self.path = Path::Arc { height };
        self
    }

    pub fn pace(mut self, pace: Pace) -> Self {
        self.pace = pace;
        self
    }

    fn matches(&self, name: &str) -> bool {
        glob(&self.pattern, name)
    }
}

fn glob(pattern: &str, name: &str) -> bool {
    match pattern.split_once('*') {
        None => pattern == name,
        Some((head, rest)) => {
            let Some(tail) = name.strip_prefix(head) else {
                return false;
            };
            // Try every split point for the rest of the pattern.
            (0..=tail.len())
                .filter(|&i| tail.is_char_boundary(i))
                .any(|i| glob(rest, &tail[i..]))
        }
    }
}

fn lerp(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t
}

/// The picture `t` of the way from `a` to `b` (`t ∈ [0, 1]`, paced per rule).
///
/// - Nodes in both Scenes interpolate position, size, colour and opacity; text
///   and labels switch at the midpoint.
/// - Nodes only in `b` fade in; nodes only in `a` fade out.
pub fn between(a: &Scene, b: &Scene, t: f32, rules: &[Rule]) -> Scene {
    // Index by name once: pairing is then O(n) per frame, not O(n²).
    let in_a: HashMap<&str, &Node> = a.nodes().iter().map(|n| (n.name.as_str(), n)).collect();
    let in_b: HashMap<&str, &Node> = b.nodes().iter().map(|n| (n.name.as_str(), n)).collect();
    let rule = |name: &str| rules.iter().find(|r| r.matches(name));
    let paced = |name: &str| rule(name).map_or(Pace::Smooth, |r| r.pace).apply(t);

    let mut out: Vec<Node> = Vec::with_capacity(a.nodes().len() + b.nodes().len());
    for nb in b.nodes() {
        let e = paced(&nb.name);
        match in_a.get(nb.name.as_str()) {
            Some(na) => out.push(blend(na, nb, e, rule(&nb.name).map(|r| &r.path))),
            None => {
                let mut n = nb.clone();
                n.opacity *= e;
                out.push(n);
            }
        }
    }
    for na in a.nodes() {
        if !in_b.contains_key(na.name.as_str()) {
            let mut n = na.clone();
            n.opacity *= 1.0 - paced(&na.name);
            out.push(n);
        }
    }

    out.sort_by_key(|n| n.z); // stable: ties keep the order above
    Scene::from_nodes(out)
}

fn blend(a: &Node, b: &Node, e: f32, path: Option<&Path>) -> Node {
    let moved = a.x != b.x || a.y != b.y;
    let lift = match path {
        Some(Path::Arc { height }) if moved => height * 4.0 * e * (1.0 - e),
        _ => 0.0,
    };
    let kind = match (&a.kind, &b.kind) {
        (
            Kind::Box {
                w: wa,
                h: ha,
                label: la,
                shape: sa,
            },
            Kind::Box {
                w: wb,
                h: hb,
                label: lb,
                shape: sb,
            },
        ) => Kind::Box {
            w: lerp(*wa, *wb, e),
            h: lerp(*ha, *hb, e),
            label: if e < 0.5 { la.clone() } else { lb.clone() },
            shape: if e < 0.5 { *sa } else { *sb },
        },
        (
            Kind::Title {
                text: ta,
                size: za,
                fonts: fa,
            },
            Kind::Title {
                text: tb,
                size: zb,
                fonts: fb,
            },
        ) => Kind::Title {
            text: if e < 0.5 { ta.clone() } else { tb.clone() },
            size: lerp(*za, *zb, e),
            fonts: if e < 0.5 { fa.clone() } else { fb.clone() },
        },
        _ if e < 0.5 => a.kind.clone(),
        _ => b.kind.clone(),
    };

    let fill = match (a.fill, b.fill) {
        (Some(fa), Some(fb)) => Some(fa.lerp(fb, e)),
        (Some(f), None) | (None, Some(f)) => Some(f), // can't tween to "nothing"
        (None, None) => None,
    };

    Node {
        name: b.name.clone(),
        x: lerp(a.x, b.x, e),
        y: lerp(a.y, b.y, e) - lift,
        kind,
        fg: a.fg.lerp(b.fg, e),
        fill,
        bold: if e < 0.5 { a.bold } else { b.bold },
        opacity: lerp(a.opacity, b.opacity, e),
        // Lift moving things above still ones so a hop passes over, not under.
        z: if moved { a.z.max(b.z) + 1 } else { b.z },
    }
}

#[cfg(test)]
mod tests {
    use super::glob;

    #[test]
    fn glob_matches() {
        assert!(glob("tok/*", "tok/3"));
        assert!(glob("*", "anything"));
        assert!(glob("a*c", "abbc"));
        assert!(!glob("tok/*", "ptr/3"));
        assert!(glob("exact", "exact"));
        assert!(!glob("exact", "exactly"));
    }
}
