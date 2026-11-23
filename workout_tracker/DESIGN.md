---
name: Workouts
description: A home exercise program sheet, filled in as you go: copier-white paper, ink rules, a clinic-teal letterhead, ballpoint blue for what you log, highlighter yellow for what is next.
colors:
  paper: "#fafaf7"
  sheet: "#ffffff"
  sheet-2: "#f0efe9"
  line: "#dedbd1"
  rule: "#26303b"
  ink: "#1b232d"
  ink-2: "#4d5763"
  teal: "#0e6a70"
  teal-2: "#0b5459"
  teal-soft: "#dcedee"
  on-teal: "#ffffff"
  on-teal-2: "#cfe6e7"
  pen: "#2440b3"
  pen-soft: "#e7ebf8"
  highlighter: "#f3dd4e"
  on-highlighter: "#1b232d"
  ok: "#237a4b"
  warn: "#9a5b00"
  danger: "#b3261e"
  series-orange: "#c0561d"
typography:
  display:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.65rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "1.06rem"
    fontWeight: 800
    lineHeight: 1.25
  title:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "1.08rem"
    fontWeight: 800
    lineHeight: 1.25
  body:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "0.86rem"
    fontWeight: 700
    lineHeight: 1.3
  figure:
    fontFamily: "Atkinson Hyperlegible Next, Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "2.2rem"
    fontWeight: 800
    lineHeight: 1
rounded:
  box: "3px"
  card: "4px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  tap: "48px"
components:
  button:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.box}"
    height: "48px"
    padding: "0 16px"
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.on-teal}"
    rounded: "{rounded.box}"
    height: "48px"
    padding: "0 16px"
  button-primary-hover:
    backgroundColor: "{colors.teal-2}"
  chip:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.box}"
    height: "44px"
    padding: "0 14px"
  chip-on:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.on-teal}"
  card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "14px"
  dose-box:
    textColor: "{colors.ink}"
    rounded: "{rounded.box}"
    padding: "0 7px"
  tick-box:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.pen}"
    rounded: "{rounded.box}"
    size: "30px"
  set-input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.pen}"
    rounded: "{rounded.box}"
    height: "44px"
  set-input-next:
    backgroundColor: "{colors.highlighter}"
    textColor: "{colors.on-highlighter}"
  hold-button:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.box}"
    height: "44px"
  hold-button-done:
    backgroundColor: "{colors.pen}"
    textColor: "{colors.sheet}"
  letterhead:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.on-teal}"
  score-box:
    textColor: "{colors.on-teal}"
    rounded: "{rounded.box}"
    height: "40px"
    padding: "4px 10px"
  tab-bar:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.on-teal-2}"
    height: "64px"
---

# Design System: Workouts

## Overview

**Creative North Star: "The Physio's Program Sheet"**

Workouts is the printed home exercise program a physio hands you, filled in as you go. The ground is copier-white paper; the rules, boxes and text are near-black ink; one flat clinic-teal letterhead owns the shell, top and bottom. Everything Joe writes in (weights, reps, ticks, hold buttons he has finished, notes to the coach) is ballpoint blue. The thing to do next is picked out in highlighter yellow. There is no third voice: no gradients, no shadows, no progress rings, no dark cards with a neon accent.

It is built for one person, one-handed and sweaty between sets, sometimes at arm's length. So type is Atkinson Hyperlegible Next with tabular numerals throughout, tap targets are 44 to 48px, and numbers are large and heavy. The look is drawn, not decorated: boxes with 3px corners, 1.5px ink rules, ticks that are one ballpoint stroke, and time shown as length (a 45 s hold is a longer box than a 20 s one). Real exercise photos appear as thumbnails; figures are never drawn.

Dark mode follows the phone and is a carbon-copy slate version of the same sheet: the roles stay put (teal shell, blue for what you log, yellow for next), only the values move.

**Key Characteristics:**
- Paper, ink, one teal shell, one blue pen, one yellow highlighter.
- Flat: depth comes from rules and tone, never shadow.
- Drawn boxes with small square corners (3px) and 1.5px ink rules.
- Numbers heavy and tabular; blue means "you wrote this".
- Time and amount are drawn to length (holds, cardio rule).
- No emoji; every icon is a one-stroke SVG.

## Colors

A restrained sheet palette: warm off-white paper, cool ink, teal for the shell, and two marker colours with fixed jobs. Dark-mode values are given in parentheses after the light ones; the same token names carry both.

### Primary
- **Clinic Teal** (`{colors.teal}`, dark #0f5d62): the letterhead band, the bottom tab bar, the primary button, the selected chip, section numbers (2.1, 2.2) and the more-page icons. Dark mode lifts the text-use of teal (section numbers, icons, links, PT badge) to a pale teal, #7fcace, so it stays legible on slate.
- **Deep Teal** (`{colors.teal-2}`, dark #0b474b): hover and pressed state of the primary button.
- **Teal Wash** (`{colors.teal-soft}`, dark #173a3d): the seasonal banner behind the ski-season note.
- **On Teal** (`{colors.on-teal}`) and **Pale On Teal** (`{colors.on-teal-2}`, dark #bfdddf): text and outlines on the letterhead and tab bar.

### Secondary
- **Ballpoint Blue** (`{colors.pen}`, dark #9db2ff): everything the person logged or wrote: set weights and reps, ticks, finished hold buttons, last-time values, the user's chat messages, the active rest timer, guided breathing, chart series A. Its wash, **Pen Wash** (`{colors.pen-soft}`, dark #1f2745), sits behind coach-chat notes from the user and the breathing circle.

### Tertiary
- **Highlighter Yellow** (`{colors.highlighter}`, dark #e5cf45): only "next" and "today": the next set's input, the next hold, today's row in Week, the active-tab underline, personal-record marks and the text selection colour. Text on it is **{colors.on-highlighter}** (dark #14181c).

### Neutral
- **Copier Paper** (`{colors.paper}`, dark #121619): page ground. 
- **Sheet** (`{colors.sheet}`, dark #1a1f24): inputs, boxes, cards, the toast's inverse.
- **Sheet Grey** (`{colors.sheet-2}`, dark #232a31): picture placeholders.
- **Pencil Line** (`{colors.line}`, dark #313941): hairline separators between rows, dashed how-to rules, card borders.
- **Ink Rule** (`{colors.rule}`, dark #c5cbd1): the 1.5px box and section rules.
- **Ink** (`{colors.ink}`, dark #e8eae5): text. **Soft Ink** (`{colors.ink-2}`, dark #a7b0ba): secondary text, units, last-time labels.
- Status: **ok** `{colors.ok}`, **warn** `{colors.warn}`, **danger** `{colors.danger}` (dark #57c38a, #e0a84a, #ff7a70), used only for status text and the "Bothered me" badge tint. Chart series B is **{colors.series-orange}** (dark #f08a4b).

### Named Rules
**The Pen Rule.** Blue means a person wrote it. Weights, reps, ticks, finished holds, the user's chat lines. Never use blue for chrome, links or decoration.

**The Highlighter Rule.** Yellow marks exactly one thing: what is next or today. At most one next set, one next hold, one today row on screen. It never fills a button, a banner or a decorative shape.

**The Teal Shell Rule.** Teal owns the shell (letterhead, tab bar) and the primary action. The page between them stays paper and ink.

## Typography

**Display, Body and Label Font:** Atkinson Hyperlegible Next (self-hosted woff2, weights 200 to 800, with Atkinson Hyperlegible, system-ui, -apple-system, Segoe UI, Roboto as fallbacks). One family; hierarchy comes from weight and size only.

**Character:** Built for legibility at arm's length. Numerals are tabular everywhere (`font-variant-numeric: tabular-nums` on body) so set boxes and timers do not jitter. Weight 800 carries every heading and every number that matters; 600 to 700 carries labels and buttons; 400 is for reading text.

### Hierarchy
- **Display** (800, 1.65rem, 1.1, -0.015em): the letterhead title; on Today it is the date.
- **Headline** (800, 1.06rem, 1.25): section headings (h2); numbered sections pair it with a 1.25rem 800 teal section number.
- **Title** (800, 1.05 to 1.08rem, 1.25): exercise names and card titles. Records-page names are 1.22rem 800.
- **Body** (400, 16px, 1.45): reading text; secondary lines are 0.9rem in Soft Ink; small notes 0.84 to 0.86rem.
- **Label** (600 to 700, 0.74 to 0.9rem): buttons (600, 800 for primary), dose boxes (700, 0.86rem), badges (0.74rem 700), tab labels (0.74rem 600, 800 active).
- **Figure** (800, 1.7 to 2.2rem, 1): cardio minutes, timer time (2.1rem), stats, score numbers (1.35rem).

### Named Rules
**The Heavy Number Rule.** Any number the person acts on (a weight, reps, minutes, a countdown) is weight 800 and tabular.

**The One Family Rule.** No second face. Contrast comes from weight and size, never from a new font.

## Layout

A single column, `max-width: 720px`, centred, with 16px side gutters (the letterhead's text lines up with this column on wide screens). Phone-first: 375px is the design width and desktop simply shows the same column on paper. Vertical rhythm is 4/8/12/16px; sections are separated by 28px above the heading and 10px below. The page leaves 78px (plus safe-area inset) at the bottom for the fixed tab bar; the rest timer bar and the coach composer sit above it.

The program is a sheet, not a feed: rows are separated by 1px Pencil Line rules rather than boxed as cards, and a section is announced by a ruled heading. Tap targets are 44px minimum (48px for primary actions and tick rows). Set rows are a grid: 44px done-box, 26px set number, weight and reps inputs, 44px remove, with the remove control kept clear of the reps box so a mid-set tap cannot delete a set. Narrow screens (480px and under) fold the Week buttons to two columns. Swiping horizontally moves between tabs, except over inputs, chips and galleries. Print hides the shell and prints the PT report on white.

## Elevation & Depth

Flat. There are no box-shadows anywhere in the system. Depth is conveyed by ink rules (1.5px around actionable boxes, 1px hairlines between rows), by tone (Paper under Sheet), and by the fixed teal bands. The few things that float (the timer bar, the trophy dialog) are marked with a heavier 2px ink border, not a shadow, and the toast is an inverted ink slab. The only transform feedback is a 1px press on buttons.

### Named Rules
**The No Shadow Rule.** If something has to stand apart, give it a rule or a tone. A drop shadow, glow or blur is never the answer.

## Shapes

Two corner values and no others in the system: **3px** for every drawn box (buttons, inputs, tick boxes, dose boxes, chips, set boxes, hold bars, score boxes, badges, thumbnails, the toast) and **4px** for cards, the timer bar and dialogs. Pictures take 3px. Everything is outlined in ink (1.5px) when it can be tapped or typed into, and in the paler Pencil Line (1px) when it is only a container. Circles appear only for the breathing guide and the trophy cup. Pills and large rounded cards are not part of this world.

## Components

### Letterhead and Tab Bar
The teal letterhead holds the title (the date on Today), a sub line (day label, phase and block week), a save-state note and two outlined score boxes (1.5px pale-teal outline, 40px tall, a 1.35rem number plus its label). A "Snow day?" action is the one filled white box on the teal, because it is an action and the scores are readings. The bottom tab bar is the same teal, five equal buttons, 64px tall, 24px drawn icons with 0.74rem labels; the active tab turns white, goes to weight 800 and gets a 24px by 3px highlighter-yellow bar beneath it. Focus rings on the bar are yellow.

### Numbered Ruled Sections
`h2.sec`: a flex row with a teal 1.25rem section number, the 800 heading, and an optional right-aligned meta, closed by a 1.5px ink rule. Exercise rows inside carry their own numbers (2.1, 2.2) in teal.

### Tick-Line Rows (daily non-negotiables)
One ruled line each: a 30px drawn tick box, the name and dose, a boxed timer button (play icon plus length) and a chevron for the how-to. Row height 48px. Ticking draws a ballpoint-blue check (a mask-drawn stroke) in with a 0.2s scale and fade, and the name turns Soft Ink.

### Strength Rows
Index number in teal, a 56px photo thumbnail, the exercise name (800), a **dose box** (1.5px ink outline, 3px corners, 0.86rem 700, for example "2 × 10–12") showing today's set count, and the remainder of the dose as a note. "Last time" values sit in blue with the next suggestion in bold blue beneath. The set boxes below are the signature: each set is a done-box, set number, weight input and reps input, all with 1.5px ink outlines and 1.12rem 800 blue numerals; the next set's inputs fill highlighter yellow with dark text; finished sets fade their borders to Pencil Line. Bodyweight and band moves drop the weight box. Row actions (Same as last time, Add set) are 44px outlined buttons, with Swap and Bothered me as quiet text links.

### Holds Drawn to Length
Timed holds are 44px buttons whose width is the hold time as a share of 120 s (min 28%, 88px floor); between holds a 3px Pencil Line bar, drawn to the rest's length, stands for the rest. A finished hold fills blue with a white tick; the next hold fills yellow. The same idea is the rule that follows.

### Measured Cardio Rule
Cardio minutes are an SVG ruler, always drawn at one scale (45 minutes fills the line): a tick every 5 minutes, longer every 15, the warm-up's first 5 minutes in highlighter yellow and labelled, the total written at the end in ink. Beside it sits a 2.2rem 800 minutes figure.

### Paused Rows
An exercise sitting out because it bothered Joe prints as a whole greyed row: Soft Ink name with a 1.5px strike-through, a greyscale 60% thumbnail and a note saying until when. It is never hidden.

### Buttons
- **Shape:** 3px corners, 1.5px ink outline, 48px tall (44px for small), 600 weight.
- **Primary:** teal fill, white text, weight 800, full width; Deep Teal on hover. Only one primary per view.
- **Quiet / link:** no box, teal text, underline on hover; "muted-link" in Soft Ink for dismiss-type actions.
- **Press:** 1px downward nudge, 0.15s. Disabled drops to 55% opacity.

### Chips and Section Jump Links
Chips are 44px outlined boxes; the selected one fills teal. Long pages (Settings, History, PT report) open with a row of section jump links: 40px outlined ink boxes, 0.88rem 600, linking to each section heading.

### Binder-Style Records
The Records tab is a table of contents ruled on the paper: 1.5px rules above and between entries, a 26px drawn icon in teal, the page name at 1.22rem 800 (underlined on hover), a one-line description, and the page's sections listed as small outlined chips that jump straight to them. Sub-pages show a "More" back link on the letterhead.

### Inputs
1.5px ink outline, 3px corners, Sheet fill, 44 to 48px tall; text fields are 12px padded. Focus is a 2px ballpoint-blue outline offset 2px. The caret is blue. Settings checkboxes are the same drawn boxes as Today's ticks (26px, blue check).

### Cards, Toast, Timer Bar
Cards are Sheet with a 1px Pencil Line border and 4px corners; the "done" card uses the 1.5px ink rule. The toast is an ink slab with Paper text; it fades and rises 6px over 0.2 to 0.3s. The timer bar is a fixed Sheet panel with a 2px ink border (blue while resting) and a 2.1rem countdown.

### Motion
Short and functional. Ease is `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out). Ticks scale from 0.6 to 1 with a fade over 0.25s; the toast fades and rises; buttons press 1px. The breathing circle (8s) and the start/finish exercise picture flip are content, not decoration. The trophy cup pop and confetti appear only for a personal record. `prefers-reduced-motion` collapses all animation and transition to near-zero and removes the confetti.

### Icons
One drawn set, 24px viewBox, 1.9 stroke (1.8 on the tab bar), round caps and joins, `currentColor`, no fill. Icons are inline SVG authored for the app. No emoji, no icon font, no glyph characters used as icons.

## Do's and Don'ts

### Do:
- **Do** write everything the person enters or logs in Ballpoint Blue (`{colors.pen}`), and nothing else.
- **Do** use highlighter yellow only for what is next or today: one next set, one next hold, today's row.
- **Do** keep the shell flat teal (letterhead and tab bar) and the page paper and ink.
- **Do** draw every box with a 3px corner and a 1.5px ink outline; use 4px only for cards, the timer bar and dialogs.
- **Do** draw time and amount to length where there is a duration: holds, rests, the cardio rule.
- **Do** keep tap targets at 44px or more (48px for primary actions) and numbers at weight 800, tabular.
- **Do** wrap long text; never cut text off with ellipsis or a clipped width.
- **Do** author new icons as one-stroke SVG with the existing 24px grid and stroke settings.
- **Do** keep real exercise photos as thumbnails with the 3px corner and a Sheet Grey placeholder.
- **Do** respect `prefers-reduced-motion` and the phone's light or dark setting.

### Don't:
- **Don't** add shadows, glows, gradients or blurs; use a rule or a tone for separation.
- **Don't** use dark cards with one neon accent, progress rings or gauges; this app refuses that category default.
- **Don't** use blue for links, chrome or decoration, or yellow for fills, banners or buttons.
- **Don't** use emoji or text glyphs as icons, and don't draw figures where a real photo belongs.
- **Don't** introduce a second typeface or a new radius.
- **Don't** put a second primary button in a view, or float cards where a ruled sheet row works.
- **Don't** animate for decoration; motion is short ease-out feedback only.

### Drift not canonized
The build carries a few off-system values that future surfaces should not copy: the coach "changes" panel uses an 8px radius, chat bubbles use a 4px bottom corner, and the personal-record mark, week-day "today" label and block-day tags use a 3px radius written as a literal rather than the token. The confetti pieces use a 2px radius.
