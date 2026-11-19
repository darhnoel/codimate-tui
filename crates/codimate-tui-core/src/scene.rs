//! A [`Scene`] is one still picture: named nodes placed on a grid of terminal cells.
//!
//! The name of a node is its identity. The motion layer pairs nodes across two
//! Scenes by name and animates whatever differs, so a name that follows a *thing*
//! makes it travel, while a name that follows a *place* makes it change in place.

/// A 24-bit colour.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rgb(pub u8, pub u8, pub u8);

impl Rgb {
    /// Mix from `self` (t = 0) to `other` (t = 1).
    pub fn lerp(self, other: Rgb, t: f32) -> Rgb {
        let ch = |a: u8, b: u8| {
            (a as f32 + (b as f32 - a as f32) * t)
                .round()
                .clamp(0.0, 255.0) as u8
        };
        Rgb(
            ch(self.0, other.0),
            ch(self.1, other.1),
            ch(self.2, other.2),
        )
    }
}

/// A small default palette that reads well on a dark background.
pub mod color {
    use super::Rgb;
    pub const BG: Rgb = Rgb(22, 24, 30);
    pub const FG: Rgb = Rgb(220, 223, 228);
    pub const MUTED: Rgb = Rgb(92, 99, 112);
    pub const DIM: Rgb = Rgb(44, 48, 58);
    pub const BLUE: Rgb = Rgb(66, 135, 245);
    pub const ORANGE: Rgb = Rgb(240, 150, 50);
    pub const GREEN: Rgb = Rgb(80, 200, 120);
    pub const RED: Rgb = Rgb(230, 80, 80);
    pub const YELLOW: Rgb = Rgb(235, 200, 80);
    pub const PURPLE: Rgb = Rgb(170, 110, 230);
}

/// How a box is drawn.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Shape {
    /// A diagram box: rounded border once it is at least 2×2, solid below that.
    Framed,
    /// A solid rectangle with no outline.
    Block,
    /// A solid ellipse filling the `w` × `h` rectangle.
    Oval,
}

impl Shape {
    /// Block and Oval are solid colour with no outline, drawn at twice the
    /// vertical detail (each cell holds two square "pixels", one above the other).
    pub fn is_solid(self) -> bool {
        matches!(self, Shape::Block | Shape::Oval)
    }
}

/// What a node draws.
#[derive(Clone, Debug, PartialEq)]
pub enum Kind {
    /// A shape `w` × `h` cells with a centred label. Solid shapes take their colour
    /// from `fill` (or `fg` when there is none) and honour half-cell `y` and `h`.
    Box {
        w: f32,
        h: f32,
        label: String,
        shape: Shape,
    },
    /// A line of terminal text, drawn by the terminal's own font.
    Text { text: String },
    /// Big text drawn as pixels: shaped with the font files in `fonts` (so complex
    /// scripts such as Khmer come out right in any terminal; the first font with
    /// a letter draws it), `size` cells tall,
    /// centred on the node's `x`. `fg` colours it; with a `fill` too, the colour
    /// runs from `fg` on the left to `fill` on the right.
    Title {
        text: String,
        size: f32,
        fonts: Vec<String>,
    },
}

/// One named element of a Scene. `x`/`y` are the top-left corner in cells and may
/// be fractional; the renderer rounds them, so motion stays smooth in between.
#[derive(Clone, Debug, PartialEq)]
pub struct Node {
    pub name: String,
    pub x: f32,
    pub y: f32,
    pub kind: Kind,
    pub fg: Rgb,
    pub fill: Option<Rgb>,
    pub bold: bool,
    pub opacity: f32,
    pub z: i32,
}

impl Node {
    fn new(name: String, x: f32, y: f32, kind: Kind) -> Self {
        Node {
            name,
            x,
            y,
            kind,
            fg: color::FG,
            fill: None,
            bold: false,
            opacity: 1.0,
            z: 0,
        }
    }

    pub fn fg(&mut self, c: Rgb) -> &mut Self {
        self.fg = c;
        self
    }

    pub fn fill(&mut self, c: Rgb) -> &mut Self {
        self.fill = Some(c);
        self
    }

    pub fn bold(&mut self) -> &mut Self {
        self.bold = true;
        self
    }

    pub fn opacity(&mut self, o: f32) -> &mut Self {
        self.opacity = o.clamp(0.0, 1.0);
        self
    }

    /// Higher `z` draws on top. Ties keep insertion order.
    pub fn z(&mut self, z: i32) -> &mut Self {
        self.z = z;
        self
    }

    /// Set a box's label or replace a text node's text.
    pub fn label(&mut self, s: impl ToString) -> &mut Self {
        match &mut self.kind {
            Kind::Box { label, .. } => *label = s.to_string(),
            Kind::Text { text } | Kind::Title { text, .. } => *text = s.to_string(),
        }
        self
    }

    /// The text this node shows (box label or text).
    pub fn content(&self) -> &str {
        match &self.kind {
            Kind::Box { label, .. } => label,
            Kind::Text { text } | Kind::Title { text, .. } => text,
        }
    }
}

/// One still picture.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Scene {
    nodes: Vec<Node>,
}

impl Scene {
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a framed box with its top-left corner at (`x`, `y`).
    pub fn rect(&mut self, name: impl Into<String>, x: f32, y: f32, w: f32, h: f32) -> &mut Node {
        self.shape(name, x, y, w, h, Shape::Framed)
    }

    /// Add a solid rectangle with no outline.
    pub fn block(&mut self, name: impl Into<String>, x: f32, y: f32, w: f32, h: f32) -> &mut Node {
        self.shape(name, x, y, w, h, Shape::Block)
    }

    /// Add a solid ellipse inside the `w` × `h` rectangle at (`x`, `y`).
    pub fn oval(&mut self, name: impl Into<String>, x: f32, y: f32, w: f32, h: f32) -> &mut Node {
        self.shape(name, x, y, w, h, Shape::Oval)
    }

    fn shape(
        &mut self,
        name: impl Into<String>,
        x: f32,
        y: f32,
        w: f32,
        h: f32,
        shape: Shape,
    ) -> &mut Node {
        let kind = Kind::Box {
            w,
            h,
            label: String::new(),
            shape,
        };
        self.push(Node::new(name.into(), x, y, kind))
    }

    /// Add a line of text starting at (`x`, `y`).
    pub fn text(
        &mut self,
        name: impl Into<String>,
        x: f32,
        y: f32,
        text: impl ToString,
    ) -> &mut Node {
        let kind = Kind::Text {
            text: text.to_string(),
        };
        self.push(Node::new(name.into(), x, y, kind))
    }

    /// Add big pixel text `size` cells tall, centred on `x`, using the font file
    /// files in `fonts` (first one that has a letter draws it). See [`Kind::Title`].
    pub fn title(
        &mut self,
        name: impl Into<String>,
        x: f32,
        y: f32,
        text: impl ToString,
        size: f32,
        fonts: Vec<String>,
    ) -> &mut Node {
        let kind = Kind::Title {
            text: text.to_string(),
            size,
            fonts,
        };
        self.push(Node::new(name.into(), x, y, kind))
    }

    /// This picture `s` times bigger: positions, shape sizes and title sizes all
    /// scale. Terminal text keeps its size (a terminal can't draw bigger letters),
    /// only its position moves.
    pub fn scaled(&self, s: f32) -> Scene {
        let nodes = self
            .nodes
            .iter()
            .map(|n| {
                let mut n = n.clone();
                n.x *= s;
                n.y *= s;
                match &mut n.kind {
                    Kind::Box { w, h, .. } => {
                        *w *= s;
                        *h *= s;
                    }
                    Kind::Title { size, .. } => *size *= s,
                    Kind::Text { .. } => {}
                }
                n
            })
            .collect();
        Scene { nodes }
    }

    pub fn nodes(&self) -> &[Node] {
        &self.nodes
    }

    pub fn get(&self, name: &str) -> Option<&Node> {
        self.nodes.iter().find(|n| n.name == name)
    }

    /// Build a Scene from nodes made elsewhere (the Python bridge). Rejects
    /// duplicate names, as [`Scene::rect`] and [`Scene::text`] do.
    pub fn try_from_nodes(nodes: Vec<Node>) -> Result<Self, crate::timeline::Error> {
        let mut seen = std::collections::HashSet::with_capacity(nodes.len());
        for n in &nodes {
            if !seen.insert(n.name.as_str()) {
                return Err(crate::timeline::Error(format!(
                    "duplicate node name `{}` in one Scene: names are identity and must be unique",
                    n.name
                )));
            }
        }
        Ok(Scene { nodes })
    }

    /// Build a Scene from nodes already known to be unique (the motion layer).
    pub(crate) fn from_nodes(nodes: Vec<Node>) -> Self {
        Scene { nodes }
    }

    fn push(&mut self, node: Node) -> &mut Node {
        // Two nodes with one name would make "what moved" ambiguous, so this is
        // an error rather than a silent last-one-wins.
        assert!(
            self.get(&node.name).is_none(),
            "duplicate node name `{}` in one Scene: names are identity and must be unique",
            node.name
        );
        self.nodes.push(node);
        self.nodes.last_mut().expect("just pushed")
    }
}

/// X positions for `n` items of width `w` with `gap` cells between them, centred on
/// a canvas `canvas_w` cells wide.
pub fn centered_row(n: usize, w: f32, gap: f32, canvas_w: f32) -> Vec<f32> {
    if n == 0 {
        return Vec::new();
    }
    let total = n as f32 * w + (n - 1) as f32 * gap;
    let x0 = ((canvas_w - total) / 2.0).floor();
    (0..n).map(|i| x0 + i as f32 * (w + gap)).collect()
}
