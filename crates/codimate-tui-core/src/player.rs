//! The interactive player: canvas, event list, caption, transport.
//!
//! Because [`Explanation::scene_at`] is pure, the player holds nothing but a clock.
//! Scrubbing, jumping and replaying are all just "draw the scene at this time".

use std::io;
use std::time::{Duration, Instant};

use ratatui::crossterm::event::{
    self, Event as TermEvent, KeyCode, KeyEvent, KeyEventKind, KeyModifiers,
};
use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, LineGauge, List, ListItem, ListState, Paragraph, Wrap};
use ratatui::{DefaultTerminal, Frame};

use crate::render::draw_scene;
use crate::scene::color;
use crate::scene::{Rgb, Scene};
use crate::timeline::Explanation;

const SCRUB_STEP: f32 = 0.25;
const SPEEDS: [f32; 6] = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0];

/// Take over the terminal and play `ex` from `start_at` seconds until the viewer
/// quits. Returns the time they stopped at, so a caller that reloads the
/// explanation can resume in the same place.
///
/// The terminal is restored on every exit path; `ratatui::init` also installs a
/// panic hook that restores it before a panic message is printed.
pub fn run(ex: Explanation, start_at: f32) -> io::Result<f32> {
    let mut terminal = ratatui::init();
    let mut player = Player::new(ex, start_at);
    let result = player.run(&mut terminal);
    ratatui::restore();
    result.map(|()| player.time)
}

struct Player {
    ex: Explanation,
    time: f32,
    playing: bool,
    speed: usize,
    list: ListState,
    /// Full screen: the picture takes the whole terminal, nothing else shown.
    full: bool,
}

impl Player {
    fn new(ex: Explanation, start_at: f32) -> Self {
        let time = start_at.clamp(0.0, ex.duration());
        Player {
            playing: time < ex.duration(),
            ex,
            time,
            speed: 2,
            list: ListState::default(),
            full: false,
        }
    }

    fn run(&mut self, terminal: &mut DefaultTerminal) -> io::Result<()> {
        let mut last = Instant::now();
        loop {
            let now = Instant::now();
            if self.playing {
                self.time += (now - last).as_secs_f32() * SPEEDS[self.speed];
                if self.time >= self.ex.duration() {
                    self.time = self.ex.duration();
                    self.playing = false;
                }
            }
            last = now;

            terminal.draw(|f| self.draw(f))?;

            // ~60 fps while playing; idle politely when paused.
            let wait = if self.playing { 16 } else { 250 };
            if !event::poll(Duration::from_millis(wait))? {
                continue;
            }
            if let TermEvent::Key(key) = event::read()?
                && key.kind == KeyEventKind::Press
                && !self.key(key)
            {
                return Ok(());
            }
        }
    }

    /// Handle one key. Returns `false` to quit.
    fn key(&mut self, key: KeyEvent) -> bool {
        let end = self.ex.duration();
        // Raw mode turns Ctrl+C into an ordinary key, and when we run inside Python
        // its interrupt handler can't fire while we hold the terminal — so Ctrl+C
        // has to mean "quit" here or there is no way out.
        if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
            return false;
        }
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => return false,
            KeyCode::Char(' ') => {
                if self.time >= end {
                    self.time = 0.0;
                }
                self.playing = !self.playing;
            }
            KeyCode::Left | KeyCode::Char('h') => self.seek(self.time - SCRUB_STEP),
            KeyCode::Right | KeyCode::Char('l') => self.seek(self.time + SCRUB_STEP),
            KeyCode::Up | KeyCode::Char('k') => self.prev_beat(),
            KeyCode::Down | KeyCode::Char('j') => self.next_beat(),
            KeyCode::Home | KeyCode::Char('r') => self.seek(0.0),
            KeyCode::End => self.seek(end),
            KeyCode::Char('+') | KeyCode::Char('=') => {
                self.speed = (self.speed + 1).min(SPEEDS.len() - 1)
            }
            KeyCode::Char('-') => self.speed = self.speed.saturating_sub(1),
            KeyCode::Char('f') => self.full = !self.full,
            _ => {}
        }
        true
    }

    fn seek(&mut self, t: f32) {
        self.time = t.clamp(0.0, self.ex.duration());
        self.playing = false;
    }

    /// Back to the start of this beat, or to the previous beat if already near it.
    fn prev_beat(&mut self) {
        let i = self.ex.beat_at(self.time);
        let beats = self.ex.beats();
        let target = if self.time - beats[i].start > 0.15 || i == 0 {
            beats[i].start
        } else {
            beats[i - 1].start
        };
        self.seek(target);
    }

    fn next_beat(&mut self) {
        let i = self.ex.beat_at(self.time);
        match self.ex.beats().get(i + 1) {
            Some(b) => {
                let s = b.start;
                self.seek(s);
            }
            None => self.seek(self.ex.duration()),
        }
    }

    /// Draw the picture into `area`, scaled to fill it when the explanation asks
    /// to fit. Returns false when the picture doesn't fit and is cut off.
    fn stage(&self, f: &mut Frame, scene: &Scene, area: Rect, bg: Rgb) -> bool {
        let (cw, ch) = self.ex.canvas;
        if self.ex.fit {
            let s = (area.width as f32 / cw as f32).min(area.height as f32 / ch as f32);
            let canvas = (
                ((cw as f32 * s).floor() as u16).max(1),
                ((ch as f32 * s).floor() as u16).max(1),
            );
            draw_scene(
                &scene.scaled(s),
                canvas,
                area,
                bg,
                self.ex.pixels,
                f.buffer_mut(),
            );
            true
        } else {
            draw_scene(scene, (cw, ch), area, bg, self.ex.pixels, f.buffer_mut());
            area.width >= cw && area.height >= ch
        }
    }

    fn draw(&mut self, f: &mut Frame) {
        let bg = color::BG;
        let bg_color = Color::Rgb(bg.0, bg.1, bg.2);
        let muted = Color::Rgb(color::MUTED.0, color::MUTED.1, color::MUTED.2);
        let accent = Color::Rgb(color::ORANGE.0, color::ORANGE.1, color::ORANGE.2);
        f.render_widget(
            Block::default().style(Style::default().bg(bg_color)),
            f.area(),
        );

        let scene = self.ex.scene_at(self.time);
        if self.full {
            self.stage(f, &scene, f.area(), bg);
            return;
        }

        let [main, transport] =
            Layout::vertical([Constraint::Min(5), Constraint::Length(2)]).areas(f.area());
        let [stage, side] =
            Layout::horizontal([Constraint::Min(20), Constraint::Length(26)]).areas(main);
        let [canvas_area, caption_area] =
            Layout::vertical([Constraint::Min(3), Constraint::Length(3)]).areas(stage);

        // Canvas.
        let (cw, ch) = self.ex.canvas;
        let frame_block = Block::bordered()
            .border_type(BorderType::Rounded)
            .border_style(Style::default().fg(muted))
            .title(Span::styled(
                format!(" {} ", self.ex.title),
                Style::default().add_modifier(Modifier::BOLD),
            ));
        let inner = frame_block.inner(canvas_area);
        f.render_widget(frame_block, canvas_area);
        if !self.stage(f, &scene, inner, bg) {
            let warn = format!(" terminal too small: need {}×{} ", cw + 28, ch + 7);
            f.render_widget(
                Paragraph::new(warn).style(Style::default().fg(Color::Black).bg(accent)),
                Rect { height: 1, ..inner },
            );
        }

        // Caption.
        let caption = Paragraph::new(self.ex.caption_at(self.time).to_string())
            .wrap(Wrap { trim: true })
            .block(
                Block::bordered()
                    .border_type(BorderType::Rounded)
                    .border_style(Style::default().fg(muted)),
            );
        f.render_widget(caption, caption_area);

        // Event list.
        let current = self.ex.beat_at(self.time);
        let items: Vec<ListItem> = self
            .ex
            .beats()
            .iter()
            .enumerate()
            .map(|(i, b)| {
                let style = if i < current {
                    Style::default().fg(muted)
                } else {
                    Style::default()
                };
                ListItem::new(Line::from(vec![
                    Span::styled(format!("{:>5.1}s ", b.start), Style::default().fg(muted)),
                    Span::styled(b.name.clone(), style),
                ]))
            })
            .collect();
        self.list.select(Some(current));
        let list = List::new(items)
            .highlight_symbol("▶ ")
            .highlight_style(Style::default().fg(accent).add_modifier(Modifier::BOLD))
            .block(
                Block::bordered()
                    .border_type(BorderType::Rounded)
                    .border_style(Style::default().fg(muted))
                    .title(" events "),
            );
        f.render_stateful_widget(list, side, &mut self.list);

        // Transport: progress line + key help.
        let [bar, help] =
            Layout::vertical([Constraint::Length(1), Constraint::Length(1)]).areas(transport);
        let total = self.ex.duration().max(f32::EPSILON);
        let state = if self.playing { "▶" } else { "⏸" };
        let gauge = LineGauge::default()
            .ratio((self.time / total).clamp(0.0, 1.0) as f64)
            .label(format!(
                " {state} {:5.2}s / {:.2}s  {}x ",
                self.time, total, SPEEDS[self.speed]
            ))
            .filled_style(Style::default().fg(accent))
            .unfilled_style(Style::default().fg(muted));
        f.render_widget(gauge, bar);
        f.render_widget(
            Paragraph::new(
                " space play/pause · ←/→ scrub · ↑/↓ event · r restart · +/- speed · f full screen · q quit",
            )
            .style(Style::default().fg(muted)),
            help,
        );
    }
}
