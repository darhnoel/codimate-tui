//! Draw a [`Scene`] into a ratatui [`Buffer`]. One-directional: nothing here
//! feeds back into the Scene.
//!
//! Two kinds of thing get drawn:
//!
//! - **Cell things** — text and framed boxes — write terminal characters.
//! - **Pixel things** — solid blocks, ovals and titles — paint into a pixel
//!   buffer where every cell holds a small patch of pixels ([`Pixels`]). When
//!   the scene is done, each painted cell becomes the one block character that
//!   best shows its patch in two colours.
//!
//! Draw order still decides what is on top: text written over pixels hides them
//! for that cell, and pixels painted over text replace it.

use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::{Color, Modifier, Style};
use unicode_segmentation::UnicodeSegmentation;
use unicode_width::UnicodeWidthStr;

use crate::scene::{Kind, Node, Rgb, Scene, Shape};

/// Below this opacity a node isn't drawn at all — a character can't be partly there.
const INVISIBLE: f32 = 0.04;

/// How many pixels each terminal cell holds for solid shapes and titles.
///
/// A cell is about twice as tall as it is wide. More pixels per cell means more
/// detail, but every cell can still show only two colours, and the finer
/// characters need a terminal font (or terminal) that draws them.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Pixels {
    /// 1 × 2 per cell with `▀`. Works everywhere; pixels are square.
    #[default]
    Half,
    /// 2 × 2 per cell with quadrant blocks `▚▞▙…`. Widely supported.
    Quad,
    /// 2 × 3 per cell with sextant blocks `🬀🬂🬎…` (Unicode 13). The most detail;
    /// needs a terminal that draws them (VS Code, kitty, WezTerm, foot, …).
    Sextant,
}

impl Pixels {
    /// Pixels per cell: (across, down).
    pub fn per_cell(self) -> (i32, i32) {
        match self {
            Pixels::Half => (1, 2),
            Pixels::Quad => (2, 2),
            Pixels::Sextant => (2, 3),
        }
    }

    /// Width of one pixel relative to its height (a cell being 1 wide, 2 tall).
    fn aspect(self) -> f32 {
        let (sx, sy) = self.per_cell();
        sy as f32 / (2.0 * sx as f32)
    }

    pub fn parse(s: &str) -> Option<Pixels> {
        match s {
            "half" => Some(Pixels::Half),
            "quad" => Some(Pixels::Quad),
            "sextant" => Some(Pixels::Sextant),
            _ => None,
        }
    }
}

fn rgb(c: Rgb) -> Color {
    Color::Rgb(c.0, c.1, c.2)
}

fn as_rgb(c: Color, or: Rgb) -> Rgb {
    match c {
        Color::Rgb(r, g, b) => Rgb(r, g, b),
        _ => or,
    }
}

/// Draw `scene` (laid out on a `canvas` of cells) centred inside `area`, over a
/// `bg`-coloured background. Anything outside the canvas or `area` is clipped.
pub fn draw_scene(
    scene: &Scene,
    canvas: (u16, u16),
    area: Rect,
    bg: Rgb,
    pixels: Pixels,
    buf: &mut Buffer,
) {
    buf.set_style(area, Style::default().bg(rgb(bg)));
    let ox = area.x as i32 + (area.width.saturating_sub(canvas.0) / 2) as i32;
    let oy = area.y as i32 + (area.height.saturating_sub(canvas.1) / 2) as i32;
    // The canvas is the stage: a node outside it (a scrolled-away part of a game
    // world, say) is clipped even when the terminal has room to show it.
    let stage = Rect::new(ox as u16, oy as u16, canvas.0, canvas.1).intersection(area);
    let (sx, sy) = pixels.per_cell();
    let cells = stage.width as usize * stage.height as usize;
    let mut pen = Pen {
        buf,
        area: stage,
        bg,
        pixels,
        fb: vec![bg; cells * (sx * sy) as usize],
        painted: vec![false; cells],
    };
    for node in scene.nodes() {
        if node.opacity >= INVISIBLE {
            pen.node(node, ox, oy);
        }
    }
    pen.finish();
}

struct Pen<'a> {
    buf: &'a mut Buffer,
    /// The stage, in buffer cells. The pixel buffer covers exactly this.
    area: Rect,
    bg: Rgb,
    pixels: Pixels,
    /// Stage pixels, row by row: `area.width * sx` across, `area.height * sy` down.
    fb: Vec<Rgb>,
    /// Per stage cell: shows pixels (true) or a character (false).
    painted: Vec<bool>,
}

impl Pen<'_> {
    fn node(&mut self, n: &Node, ox: i32, oy: i32) {
        // Fading means mixing toward the background colour.
        let fg = self.bg.lerp(n.fg, n.opacity);
        let fill = n.fill.map(|f| self.bg.lerp(f, n.opacity));
        let mut style = Style::default().fg(rgb(fg));
        if let Some(f) = fill {
            style = style.bg(rgb(f));
        }
        if n.bold {
            style = style.add_modifier(Modifier::BOLD);
        }
        let x = ox + n.x.round() as i32;
        let y = oy + n.y.round() as i32;

        match &n.kind {
            Kind::Text { text } => self.put(x, y, text, style),
            Kind::Title { text, size, fonts } => self.title(n, ox, oy, text, *size, fonts),
            Kind::Box { w, h, label, shape } if shape.is_solid() => {
                let color = fill.unwrap_or(fg);
                self.solid(n, ox, oy, (*w, *h), *shape, color);
                // The label keeps whatever colour lies under it, like text on a box.
                let row = (n.y + h / 2.0 - 0.25).round() as i32;
                let lx = x + (w.round().max(1.0) as i32 - width(label)) / 2;
                let mut text = Style::default().fg(rgb(fg));
                if n.bold {
                    text = text.add_modifier(Modifier::BOLD);
                }
                self.put(lx, oy + row, label, text);
            }
            Kind::Box { w, h, label, .. } => {
                let (w, h) = (w.round().max(1.0) as i32, h.round().max(1.0) as i32);
                if fill.is_some() {
                    for row in y..y + h {
                        for col in x..x + w {
                            self.put(col, row, " ", style);
                        }
                    }
                }
                if w >= 2 && h >= 2 {
                    self.border(x, y, w, h, style);
                }
                let lx = x + (w - width(label)) / 2;
                self.put(lx, y + h / 2, label, style);
            }
        }
    }

    /// Paint a solid Block or Oval into the pixel buffer.
    fn solid(&mut self, n: &Node, ox: i32, oy: i32, (w, h): (f32, f32), shape: Shape, c: Rgb) {
        let (sx, sy) = self.pixels.per_cell();
        let (sx, sy) = (sx as f32, sy as f32);
        let col0 = ((ox as f32 + n.x) * sx).round() as i32;
        let row0 = ((oy as f32 + n.y) * sy).round() as i32;
        let (cols, rows) = (
            (w * sx).round().max(1.0) as i32,
            (h * sy).round().max(1.0) as i32,
        );
        let (rx, ry) = (cols as f32 / 2.0, rows as f32 / 2.0);
        for r in 0..rows {
            for col in 0..cols {
                let inside = match shape {
                    Shape::Oval => {
                        let dx = (col as f32 + 0.5 - rx) / rx;
                        let dy = (r as f32 + 0.5 - ry) / ry;
                        dx * dx + dy * dy <= 1.0
                    }
                    _ => true,
                };
                if inside {
                    self.blend(col0 + col, row0 + r, c, 1.0);
                }
            }
        }
    }

    /// Big text: shaped and rasterised by [`crate::glyphs`] at this pixel size,
    /// then blended in, so its soft edges mix with whatever is underneath.
    fn title(&mut self, n: &Node, ox: i32, oy: i32, text: &str, size: f32, fonts: &[String]) {
        let (sx, sy) = self.pixels.per_cell();
        // Fonts are checked when the explanation is built; a failure here would
        // only mean a font file vanished mid-play, so draw nothing.
        let Ok(bm) =
            crate::glyphs::render(fonts, text, size * sy as f32, 1.0 / self.pixels.aspect())
        else {
            return;
        };
        let left = (ox as f32 + n.x) * sx as f32 - bm.advance / 2.0;
        let col0 = left.round() as i32 + bm.left;
        let row0 = ((oy as f32 + n.y) * sy as f32).round() as i32 + bm.top;
        let (from, to) = (n.fg, n.fill.unwrap_or(n.fg));
        let span = bm.advance.max(1.0);
        for y in 0..bm.h {
            for x in 0..bm.w {
                let cov = bm.at(x, y) * n.opacity;
                if cov < 0.03 {
                    continue;
                }
                let along = ((bm.left + x as i32) as f32 / span).clamp(0.0, 1.0);
                self.blend(col0 + x as i32, row0 + y as i32, from.lerp(to, along), cov);
            }
        }
    }

    /// Stage cell index of buffer cell (col, row), if it's on stage.
    fn cell(&self, col: i32, row: i32) -> Option<usize> {
        let a = self.area;
        let (cx, cy) = (col - a.x as i32, row - a.y as i32);
        (cx >= 0 && cy >= 0 && cx < a.width as i32 && cy < a.height as i32)
            .then(|| cy as usize * a.width as usize + cx as usize)
    }

    /// The pixel-buffer indices of one stage cell's pixels, row by row.
    fn cell_pixels(&self, cell: usize) -> impl Iterator<Item = usize> + use<> {
        let (sx, sy) = self.pixels.per_cell();
        let w = self.area.width as usize;
        let (cx, cy) = (cell % w, cell / w);
        let stride = w * sx as usize;
        (0..sy as usize).flat_map(move |r| {
            let row = (cy * sy as usize + r) * stride + cx * sx as usize;
            row..row + sx as usize
        })
    }

    /// Mix `c` into one pixel by `alpha` (1 = cover it completely). Pixel
    /// coordinates are buffer cells × [`Pixels::per_cell`].
    fn blend(&mut self, px: i32, py: i32, c: Rgb, alpha: f32) {
        let (sx, sy) = self.pixels.per_cell();
        let Some(cell) = self.cell(px.div_euclid(sx), py.div_euclid(sy)) else {
            return;
        };
        if !self.painted[cell] {
            // The cell held a character (or nothing): its pixels start as the
            // colour it showed behind that character.
            let a = self.area;
            let w = a.width as usize;
            let under = as_rgb(
                self.buf[(a.x + (cell % w) as u16, a.y + (cell / w) as u16)].bg,
                self.bg,
            );
            for i in self.cell_pixels(cell).collect::<Vec<_>>() {
                self.fb[i] = under;
            }
            self.painted[cell] = true;
        }
        let stride = self.area.width as i32 * sx;
        let (lx, ly) = (px - self.area.x as i32 * sx, py - self.area.y as i32 * sy);
        let i = (ly * stride + lx) as usize;
        self.fb[i] = self.fb[i].lerp(c, alpha);
    }

    fn border(&mut self, x: i32, y: i32, w: i32, h: i32, style: Style) {
        let (r, b) = (x + w - 1, y + h - 1);
        for col in x + 1..r {
            self.put(col, y, "─", style);
            self.put(col, b, "─", style);
        }
        for row in y + 1..b {
            self.put(x, row, "│", style);
            self.put(r, row, "│", style);
        }
        self.put(x, y, "╭", style);
        self.put(r, y, "╮", style);
        self.put(x, b, "╰", style);
        self.put(r, b, "╯", style);
    }

    /// Write `s` from (x, y), one *visible character* per cell group, skipping
    /// anything outside the area. A visible character can be several code points:
    /// Khmer `ស្តី` is four, kept together so the terminal can stack them. It takes
    /// as many cells as the terminal will give it ([`width`]).
    /// Cells keep their existing background when `style` has none, so text drawn
    /// over a box (or over pixels) sits on it.
    fn put(&mut self, x: i32, y: i32, s: &str, style: Style) {
        let mut col = x;
        for g in s.graphemes(true) {
            let w = width(g).max(1);
            let cells: Option<Vec<usize>> = (0..w).map(|k| self.cell(col + k, y)).collect();
            if let Some(cells) = cells {
                for (k, &cell) in cells.iter().enumerate() {
                    self.unpaint(cell);
                    let target = &mut self.buf[((col + k as i32) as u16, y as u16)];
                    // Cells a wide character spills into show nothing of their own.
                    target.set_symbol(if k == 0 { g } else { "" });
                    target.set_style(style);
                }
            }
            col += w;
        }
    }

    /// Turn a pixel cell back into a character cell, keeping the average of its
    /// pixels as the background a character is drawn on.
    fn unpaint(&mut self, cell: usize) {
        if !self.painted[cell] {
            return;
        }
        let px: Vec<Rgb> = self.cell_pixels(cell).map(|i| self.fb[i]).collect();
        let avg = mean(&px);
        let w = self.area.width as usize;
        let target = &mut self.buf[(
            self.area.x + (cell % w) as u16,
            self.area.y + (cell / w) as u16,
        )];
        target.set_bg(rgb(avg));
        target.modifier = Modifier::empty();
        self.painted[cell] = false;
    }

    /// Turn every painted cell into the block character that best shows its pixels.
    fn finish(&mut self) {
        let w = self.area.width as usize;
        for cell in 0..self.painted.len() {
            if !self.painted[cell] {
                continue;
            }
            let px: Vec<Rgb> = self.cell_pixels(cell).map(|i| self.fb[i]).collect();
            let (symbol, fg, bg) = to_block(self.pixels, &px);
            let target = &mut self.buf[(
                self.area.x + (cell % w) as u16,
                self.area.y + (cell / w) as u16,
            )];
            target.set_symbol(symbol);
            target.set_fg(rgb(fg)).set_bg(rgb(bg));
            target.modifier = Modifier::empty();
        }
    }
}

fn mean(px: &[Rgb]) -> Rgb {
    let n = px.len().max(1) as u32;
    let sum = |f: fn(&Rgb) -> u8| (px.iter().map(|p| f(p) as u32).sum::<u32>() / n) as u8;
    Rgb(sum(|p| p.0), sum(|p| p.1), sum(|p| p.2))
}

fn dist(a: Rgb, b: Rgb) -> i32 {
    let d = |x: u8, y: u8| x as i32 - y as i32;
    d(a.0, b.0).pow(2) + d(a.1, b.1).pow(2) + d(a.2, b.2).pow(2)
}

/// The block character, foreground and background that best show a cell's
/// pixels (row by row) with only two colours: split the pixels into the two most
/// different groups, colour each group by its average, and pick the character
/// whose shape matches the foreground group.
fn to_block(pixels: Pixels, px: &[Rgb]) -> (&'static str, Rgb, Rgb) {
    let mut far = (0, 0, 0);
    for i in 0..px.len() {
        for j in i + 1..px.len() {
            let d = dist(px[i], px[j]);
            if d > far.2 {
                far = (i, j, d);
            }
        }
    }
    if far.2 == 0 {
        return (" ", px[0], px[0]);
    }
    let (a, b) = (px[far.0], px[far.1]);
    let mut mask = 0usize;
    for (i, &p) in px.iter().enumerate() {
        if dist(p, a) <= dist(p, b) {
            mask |= 1 << i;
        }
    }
    let ones: Vec<Rgb> = (0..px.len())
        .filter(|i| mask & (1 << i) != 0)
        .map(|i| px[i])
        .collect();
    let zeros: Vec<Rgb> = (0..px.len())
        .filter(|i| mask & (1 << i) == 0)
        .map(|i| px[i])
        .collect();
    let (fg, bg) = (mean(&ones), mean(&zeros));
    match pixels {
        // Always `▀` (top pixel in the foreground), as before: the top pixel is bit 0.
        Pixels::Half if mask == 1 => ("\u{2580}", fg, bg),
        Pixels::Half => ("\u{2580}", bg, fg),
        Pixels::Quad => (QUADRANTS[mask], fg, bg),
        Pixels::Sextant => (sextant(mask), fg, bg),
    }
}

/// Quadrant characters by mask: bit 0 top-left, 1 top-right, 2 bottom-left,
/// 3 bottom-right.
const QUADRANTS: [&str; 16] = [
    " ", "▘", "▝", "▀", "▖", "▌", "▞", "▛", "▗", "▚", "▐", "▜", "▄", "▙", "▟", "█",
];

/// Sextant characters by mask: bits 0–5 are top-left, top-right, middle-left,
/// middle-right, bottom-left, bottom-right. Unicode's sextant block (U+1FB00)
/// holds every pattern in order except four that already existed: empty, full,
/// left half and right half.
fn sextant(mask: usize) -> &'static str {
    const TABLE: [&str; 64] = {
        // Built by hand-checking against the Unicode chart; see the test below.
        [
            " ", "🬀", "🬁", "🬂", "🬃", "🬄", "🬅", "🬆", "🬇", "🬈", "🬉", "🬊", "🬋", "🬌", "🬍", "🬎", "🬏",
            "🬐", "🬑", "🬒", "🬓", "▌", "🬔", "🬕", "🬖", "🬗", "🬘", "🬙", "🬚", "🬛", "🬜", "🬝", "🬞", "🬟",
            "🬠", "🬡", "🬢", "🬣", "🬤", "🬥", "🬦", "🬧", "▐", "🬨", "🬩", "🬪", "🬫", "🬬", "🬭", "🬮", "🬯",
            "🬰", "🬱", "🬲", "🬳", "🬴", "🬵", "🬶", "🬷", "🬸", "🬹", "🬺", "🬻", "█",
        ]
    };
    TABLE[mask]
}

/// How many terminal cells `s` takes, by the same rule terminals use.
pub fn width(s: &str) -> i32 {
    s.width() as i32
}

/// The scene as plain text (no colour), `canvas` sized. Handy for tests and for
/// looking at a frame without a terminal.
pub fn scene_to_text(scene: &Scene, canvas: (u16, u16), pixels: Pixels) -> String {
    let area = Rect::new(0, 0, canvas.0, canvas.1);
    let mut buf = Buffer::empty(area);
    draw_scene(
        scene,
        canvas,
        area,
        crate::scene::color::BG,
        pixels,
        &mut buf,
    );
    let mut out = String::new();
    for y in 0..canvas.1 {
        let line: String = (0..canvas.0).map(|x| buf[(x, y)].symbol()).collect();
        out.push_str(line.trim_end());
        out.push('\n');
    }
    out
}

/// The scene in 24-bit colour, as ANSI escape codes, `canvas` sized. Prints a
/// faithful still in any truecolor terminal — handy for checking solid shapes,
/// which plain text can't show.
pub fn scene_to_ansi(scene: &Scene, canvas: (u16, u16), pixels: Pixels) -> String {
    use std::fmt::Write;
    let bg = crate::scene::color::BG;
    let area = Rect::new(0, 0, canvas.0, canvas.1);
    let mut buf = Buffer::empty(area);
    draw_scene(scene, canvas, area, bg, pixels, &mut buf);
    let mut out = String::new();
    for y in 0..canvas.1 {
        for x in 0..canvas.0 {
            let cell = &buf[(x, y)];
            let f = as_rgb(cell.fg, crate::scene::color::FG);
            let b = as_rgb(cell.bg, bg);
            let bold = if cell.modifier.contains(Modifier::BOLD) {
                "1;"
            } else {
                ""
            };
            let _ = write!(
                out,
                "\x1b[0;{bold}38;2;{};{};{};48;2;{};{};{}m{}",
                f.0,
                f.1,
                f.2,
                b.0,
                b.1,
                b.2,
                cell.symbol()
            );
        }
        out.push_str("\x1b[0m\n");
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sextant_table_follows_unicode_order() {
        // Every pattern except the four pre-existing ones is U+1FB00 onward, in
        // mask order, skipping those four.
        let mut code = 0x1FB00u32;
        for mask in 0..64 {
            let expected = match mask {
                0 => " ".to_string(),
                21 => "▌".to_string(),
                42 => "▐".to_string(),
                63 => "█".to_string(),
                _ => {
                    let c = char::from_u32(code).unwrap().to_string();
                    code += 1;
                    c
                }
            };
            assert_eq!(sextant(mask), expected, "mask {mask}");
        }
    }
}
