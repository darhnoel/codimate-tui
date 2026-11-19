//! Big text as pixels: shape a string with a real font, then rasterise it.
//!
//! A terminal draws text one cell at a time, and many terminals get complex
//! scripts wrong: Khmer stacks consonants (`ស្តី`) and moves some vowels in front
//! of the consonant they follow (`េ`). Here the text is *shaped* (rustybuzz, a Rust
//! port of HarfBuzz) and drawn into a coverage bitmap, so it comes out right in any
//! terminal and at any size.
//!
//! Fonts and finished bitmaps are cached: a title is shaped once per size, not once
//! per frame.

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use ab_glyph::{Font as _, FontRef, GlyphId, PxScale, point};

/// How much each pixel of a piece of text is covered, `0.0..=1.0`.
///
/// Pixel `(0, 0)` sits `left`/`top` pixels from the top-left corner of the text's
/// line box (negative when ink pokes out of it). `advance` is the line box's width.
#[derive(Debug)]
pub struct Bitmap {
    pub w: usize,
    pub h: usize,
    pub left: i32,
    pub top: i32,
    pub advance: f32,
    pub cov: Vec<f32>,
}

impl Bitmap {
    pub fn at(&self, x: usize, y: usize) -> f32 {
        self.cov[y * self.w + x]
    }
}

struct Loaded {
    shaper: rustybuzz::Face<'static>,
    outlines: FontRef<'static>,
}

type FontCache = Mutex<HashMap<String, Option<&'static Loaded>>>;
type BitmapCache = Mutex<HashMap<(String, String, u32), Arc<Bitmap>>>;

fn fonts() -> &'static FontCache {
    static C: OnceLock<FontCache> = OnceLock::new();
    C.get_or_init(Default::default)
}

fn bitmaps() -> &'static BitmapCache {
    static C: OnceLock<BitmapCache> = OnceLock::new();
    C.get_or_init(Default::default)
}

/// Load the font file at `path` (cached; a font lives for the whole process).
fn load(path: &str) -> Result<&'static Loaded, String> {
    let mut cache = fonts().lock().expect("font cache poisoned");
    if let Some(found) = cache.get(path) {
        return found.ok_or_else(|| format!("can't use font `{path}`"));
    }
    let loaded = std::fs::read(path).ok().and_then(|bytes| {
        // Fonts are few and live as long as the program: leaking keeps the
        // borrowing simple for both the shaper and the rasteriser.
        let bytes: &'static [u8] = Box::leak(bytes.into_boxed_slice());
        let shaper = rustybuzz::Face::from_slice(bytes, 0)?;
        let outlines = FontRef::try_from_slice(bytes).ok()?;
        Some(&*Box::leak(Box::new(Loaded { shaper, outlines })))
    });
    cache.insert(path.to_string(), loaded);
    loaded.ok_or_else(|| {
        format!("can't read font `{path}` (missing, or not a TrueType/OpenType file)")
    })
}

/// Check a font can be used, so a bad path is reported up front, not mid-play.
pub fn check_font(path: &str) -> Result<(), String> {
    load(path).map(|_| ())
}

/// `text` shaped with `fonts`, `px` pixels tall (the first font's ascender to
/// descender). Each run of text uses the first font that has its letters, so
/// `["Khmer font", "Latin font"]` handles mixed Khmer and English.
///
/// `stretch` is how many pixels across match one pixel down: 1 for square
/// pixels, 2 when pixels are half as wide as they are tall.
pub fn render(fonts: &[String], text: &str, px: f32, stretch: f32) -> Result<Arc<Bitmap>, String> {
    // Sizes animate continuously; a quarter pixel is finer than anyone can see.
    let key = (
        format!("{}\n{stretch}", fonts.join("\n")),
        text.to_string(),
        (px.max(1.0) * 4.0).round() as u32,
    );
    if let Some(b) = bitmaps().lock().expect("bitmap cache poisoned").get(&key) {
        return Ok(b.clone());
    }
    let loaded = fonts
        .iter()
        .map(|f| load(f))
        .collect::<Result<Vec<_>, _>>()?;
    if loaded.is_empty() {
        return Err("a title needs at least one font".into());
    }
    let bitmap = Arc::new(rasterise(&loaded, text, key.2 as f32 / 4.0, stretch));
    bitmaps()
        .lock()
        .expect("bitmap cache poisoned")
        .insert(key, bitmap.clone());
    Ok(bitmap)
}

/// The width `text` takes at `px` pixels tall, in square pixels (its advance).
pub fn measure(fonts: &[String], text: &str, px: f32) -> Result<f32, String> {
    render(fonts, text, px, 1.0).map(|b| b.advance)
}

/// Split `text` into runs, each with the index of the font that draws it: the
/// first font that has the character. Spaces, and anything the current font can
/// draw, stay in the current run so marks are never split from their letter.
fn runs<'t>(fonts: &[&Loaded], text: &'t str) -> Vec<(usize, &'t str)> {
    let has = |f: usize, ch: char| fonts[f].shaper.glyph_index(ch).is_some();
    let mut out: Vec<(usize, &str)> = Vec::new();
    let (mut font, mut start) = (None::<usize>, 0);
    for (i, ch) in text.char_indices() {
        if let Some(f) = font
            && (ch.is_whitespace() || has(f, ch))
        {
            continue;
        }
        let pick = (0..fonts.len()).find(|&f| has(f, ch)).unwrap_or(0);
        if font != Some(pick) {
            if let Some(f) = font {
                out.push((f, &text[start..i]));
            }
            font = Some(pick);
            start = i;
        }
    }
    out.push((font.unwrap_or(0), &text[start..]));
    out
}

fn rasterise(fonts: &[&Loaded], text: &str, px: f32, stretch: f32) -> Bitmap {
    // The first font sets the size: `px` spans its ascender to descender. Every
    // font is then drawn at the same em size, so letters match across fonts,
    // and all share the first font's baseline.
    let first = &fonts[0].outlines;
    let em_px = px / first.height_unscaled() * first.units_per_em().unwrap_or(1000.0);
    let baseline = first.ascent_unscaled() * px / first.height_unscaled();

    let mut ink: Vec<(i32, i32, f32)> = Vec::new();
    let mut pen = 0.0f32;
    for (f, run) in runs(fonts, text) {
        let font = fonts[f];
        let k = em_px / font.outlines.units_per_em().unwrap_or(1000.0); // px per font unit
        let tall = k * font.outlines.height_unscaled();
        let scale = PxScale {
            x: tall * stretch,
            y: tall,
        };
        let mut buffer = rustybuzz::UnicodeBuffer::new();
        buffer.push_str(run);
        buffer.guess_segment_properties();
        let shaped = rustybuzz::shape(&font.shaper, &[], buffer);
        for (info, pos) in shaped.glyph_infos().iter().zip(shaped.glyph_positions()) {
            let x = pen + pos.x_offset as f32 * k * stretch;
            let y = baseline - pos.y_offset as f32 * k;
            let glyph = GlyphId(info.glyph_id as u16).with_scale_and_position(scale, point(x, y));
            if let Some(outline) = font.outlines.outline_glyph(glyph) {
                let b = outline.px_bounds();
                outline.draw(|gx, gy, c| {
                    ink.push((b.min.x as i32 + gx as i32, b.min.y as i32 + gy as i32, c));
                });
            }
            pen += pos.x_advance as f32 * k * stretch;
        }
    }
    let advance = pen;
    let (Some(l), Some(r), Some(t), Some(b)) = (
        ink.iter().map(|p| p.0).min(),
        ink.iter().map(|p| p.0).max(),
        ink.iter().map(|p| p.1).min(),
        ink.iter().map(|p| p.1).max(),
    ) else {
        return Bitmap {
            w: 0,
            h: 0,
            left: 0,
            top: 0,
            advance,
            cov: Vec::new(),
        };
    };
    let (w, h) = ((r - l + 1) as usize, (b - t + 1) as usize);
    let mut cov = vec![0.0f32; w * h];
    for (x, y, c) in ink {
        let i = (y - t) as usize * w + (x - l) as usize;
        cov[i] = (cov[i] + c).min(1.0); // overlapping marks add up, capped
    }
    Bitmap {
        w,
        h,
        left: l,
        top: t,
        advance,
        cov,
    }
}
