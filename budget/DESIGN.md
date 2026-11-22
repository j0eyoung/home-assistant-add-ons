---
name: Budget
description: A household budget that reads like a US Interstate guide sign, with what is left in each category set big and right-aligned like mileage.
colors:
  sign-green: "#0b5d3b"
  sign-green-deep: "#08452c"
  sign-white: "#ffffff"
  sign-legend: "#c9ddd2"
  sign-tint: "#e2eee7"
  sign-yellow: "#ffcc00"
  service-blue: "#1d4f91"
  service-blue-deep: "#163d70"
  service-legend: "#d3e0f2"
  construction-orange: "#f08a24"
  construction-orange-ink: "#a84f00"
  stop-red: "#b3261e"
  good-green: "#19703f"
  ground: "#eef2ef"
  surface: "#ffffff"
  surface-2: "#f5f8f6"
  ink: "#101614"
  ink-2: "#44514a"
  ink-3: "#5f6c65"
  rule: "#d6ded9"
  rule-strong: "#b4c1b9"
  dark-ground: "#0d1411"
  dark-surface: "#151e19"
  dark-surface-2: "#1a251f"
  dark-ink: "#e5ede8"
  dark-ink-3: "#93a29a"
  dark-rule: "#25322b"
typography:
  display:
    fontFamily: "Overpass Variable, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "48px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Overpass Variable, system-ui, sans-serif"
    fontSize: "23px"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Overpass Variable, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Overpass Variable, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Overpass Variable, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  sm: "8px"
  md: "12px"
  pill: "11px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "20px"
components:
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-primary:
    backgroundColor: "{colors.sign-green}"
    textColor: "{colors.sign-white}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.sign-green-deep}"
  shell-bar:
    backgroundColor: "{colors.sign-green}"
    textColor: "{colors.sign-white}"
  sign-panel:
    backgroundColor: "{colors.sign-green}"
    textColor: "{colors.sign-white}"
    rounded: "{rounded.md}"
    padding: "22px 24px 16px"
  service-panel:
    backgroundColor: "{colors.service-blue}"
    textColor: "{colors.sign-white}"
    rounded: "{rounded.md}"
    padding: "18px 20px"
  notice-warn:
    backgroundColor: "{colors.construction-orange}"
    textColor: "{colors.ink}"
    rounded: "10px"
    padding: "14px 18px"
  notice-error:
    backgroundColor: "{colors.stop-red}"
    textColor: "{colors.sign-white}"
    rounded: "10px"
    padding: "14px 18px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "18px 20px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 10px"
    height: "40px"
  count-pill:
    backgroundColor: "{colors.service-blue}"
    textColor: "{colors.sign-white}"
    rounded: "{rounded.pill}"
---

# Design System: Budget

## Overview

**Creative North Star: "Guide Sign"**

The month reads like the green guide sign before an exit. Each category is a line with what is left set large and right-aligned, like mileage, so one glance answers where the month stands. The world is US Interstate signage: sign green, white legends in Overpass (a Highway Gothic descendant), a white inset keyline, and a small set of reserved sign colours that each carry one meaning. Everything else is plain: white panels with one border, standard web controls, tables that wrap.

Density is moderate and calm. The dashboard is the only place the world is loud (one green sign, blue service panels beside it); every other tab keeps the same type, colours, tables and controls on quiet surfaces. Light and dark follow the device. It refuses the white-card dashboard, the spending donut and the hero-metric row, and it is never a corporate banking app (PRODUCT.md).

**Key Characteristics:**
- One sign per screen at most: green, white keyline, right-aligned figures.
- Colour roles are reserved: yellow means over budget, blue means information, orange means a warning, red means an error.
- Overpass is the only face; figures are tabular.
- Panels have one border and no shadow; depth is the sign's own keyline.
- Icons are one drawn SVG stroke set; no glyph icons.

## Colors

A green-tinted neutral ground with one saturated sign green and four reserved signal colours.

### Primary
- **Sign Green** (#0b5d3b): the shell bar, the dashboard sign, primary buttons, selected segments, input focus borders, the day-header rule, the bulk-action bar and toasts. Unchanged in dark mode.
- **Sign Green Deep** (#08452c): hover on green surfaces. **Sign Tint** (#e2eee7; dark #173326) fills good notices and the active choice tile.
- **Sign Legend** (#c9ddd2): secondary text on green. Primary text on green is white (#ffffff).

### Secondary
- **Service Blue** (#1d4f91; dark #22599f): information panels (safe to spend, to review) and the count pill. **Service Legend** (#d3e0f2) is secondary text on blue. As link and guess-tag text on light surfaces it reads #1d4f91, in dark #8fb8ff.

### Tertiary
- **Sign Yellow** (#ffcc00): over budget, on green and blue grounds: the over line's text and pace fill, the total when over, the diamond marker, and over text and bar fill inside service panels.
- **Construction Orange** (#f08a24): warning notices and the merge hint, with ink (#101614) text. As text on light surfaces it is Orange Ink (#a84f00; dark #f5a04a), used for the drawn caution icon.
- **Stop Red** (#b3261e): error banners, and "over" or negative figures on light surfaces (dark text variant #ff8a80). Good figures use #19703f (dark #6fd3a1).

### Neutral
- **Ground** (#eef2ef; dark #0d1411), **Surface** (#ffffff; dark #151e19), **Surface 2** (#f5f8f6; dark #1a251f): page, panel, and hover or inset fill.
- **Ink** (#101614; dark #e5ede8), **Ink 2** (#44514a; dark #b3c1b9), **Ink 3** (#5f6c65; dark #93a29a): text, secondary and tertiary text, and idle categories off the sign.
- **Rule** (#d6ded9; dark #25322b) and **Rule Strong** (#b4c1b9; dark #384a40): borders and dividers.

### Named Rules
**The One Reserved Ink Rule.** Yellow means over budget and nothing else. It appears only on green or blue grounds. On white surfaces "over" is stop red.

**The Idle Grey Rule.** Categories with nothing spent print in Sign Legend at weight 600, never in yellow or green emphasis.

**The Sign Family Rule.** Notices borrow the sign families: orange for attention, red for errors, each with a 2px inner keyline (an outline at a negative offset); blue and green panels likewise.

## Typography

**Display Font:** Overpass Variable (self-hosted via `@fontsource-variable/overpass`, with system-ui fallback)
**Body Font:** Overpass Variable
**Label/Mono Font:** Overpass Variable; `font-variant-numeric: tabular-nums` on the body.

**Character:** A Highway Gothic descendant: open, sturdy, legible at a glance. One face at weights 400 to 800; hierarchy comes from size and weight.

### Hierarchy
- **Display** (800, 48px, 1.05, -0.02em; 40px on phones): the sign's month total.
- **Figure** (800, 34px, 1.1): service panel numbers. The Plan hero number is 44px (34px on phones).
- **Headline** (700 to 800, 23px): app title, sign category lines and amounts (21px on phones).
- **Title** (700, 19px, 1.25): section headings (h2); service headings are 16px.
- **Body** (400, 16px, 1.45): running text, insights capped at 72ch.
- **Label** (700, 13px, +0.04em, uppercase): table column headings only. Small text is 14px (`.small`, `.muted`); tags and badges 12 to 13px.

### Named Rules
**The Right-Aligned Mileage Rule.** Figures sit at the right edge of their line, bold, never wrapped; the name wraps at spaces on the left.

## Layout

A 1200px centred column (20px gutters, 12px on phones) under an edge-to-edge green bar. The dashboard is a two-column grid (1.55fr sign, 1fr service panels, 16px gap) that collapses to one column at 900px. Panels stack with 16px margins (12px on phones). Tables fill the width; columns size to content, text wraps at spaces, figures and dates stay on one line (`white-space: nowrap`), and a very long value scrolls inside `.table-wrap`. Breakpoints: 900px (dashboard), 800px (hide secondary columns), 640px (phone: scrolling tab row, month picker beside the title, Transactions and Plan goals restack as grid rows). Month in figures is a ruled list with hairline dividers, not cards.

### Named Rules
**The Never Truncate Rule.** Text in tables and lists is never cut with an ellipsis or a fixed width; it wraps at spaces, and short values stay on one line.

**The Guide Words Rule.** In Transactions the day header (`tr.day-row th`) is sticky at the top of the scroll, on the ground colour with a 2px sign-green rule under it and that day's total at the right.

## Elevation & Depth

Flat. Panels carry one 1px border and no shadow. Depth on green and blue panels comes from a 2px white keyline drawn as an outline at a negative offset (-6 to -7px). Only two things float and get a soft ambient shadow (0 6px 20px rgba(0,0,0,0.22)): the toast and the sticky bulk-action bar. The sign has a 1px hairline shadow (0 1px 2px). Focus is a 3px soft ring (`--select`) on inputs and a 2px outline elsewhere (white on green and blue).

### Named Rules
**The Keyline Rule.** The inner white or ink keyline is the sign's border. Draw it with an outline at a negative offset, not a second element.

**The In-Place State Rule.** A state restyles the row where it stands: over turns the line yellow with a diamond, idle turns it grey, selected tints the row, pending greys the text. Rows do not move to another list to show state.

## Shapes

Sign radii of 12px on panels and the sign, 10px on notices and the segmented control, 8px on controls, 4 to 6px on bars and the logo, and a pill (11px) on the count and badges. The pace rule is a 6px track; the diamond marker is a 15px square rotated 45 degrees with a 2px ink border. Standard web controls everywhere; no clipped or custom-shaped buttons.

## Components

### Buttons
- **Shape:** 8px radius, 1px strong border, padding 8px 14px, weight 600.
- **Default:** surface fill; hover to Surface 2 with a darker border; press moves 1px down.
- **Primary:** sign green fill, white text; hover to Sign Green Deep.
- **On green and blue:** transparent with a 60% white border; hover fills the deep shade.
- **Link, mini, toggle:** text-only red link; quiet mini button that shows its border on hover; toggle that fills green when on.
- **Focus:** 2px outline in service blue (white on green and blue).

### Shell bar and tabs
Edge-to-edge sign green, white 23px/800 title with the logo, tabs as text buttons in Sign Legend; the active tab is white with a 3px inset underline. The count pill turns white with green text here. On phones the tabs scroll sideways under the title.

### The Sign (signature)
Month heading with "Day N of M", the total at 48px, a pace rule, then a 2px white rule and one row per category: name left (23px/700), remaining right (23px/800), a meta line (trend icon and last month's figure), and a 6px pace rule. Rows are sorted by what is closest to running out. Over rows turn yellow with a diamond and a yellow pace fill; idle rows print in Sign Legend. Unbudgeted categories follow under their own 2px rule; quiet ones sit behind a show toggle. The loading state keeps the sign's shape with quiet bars.

**The Pace Tick Rule.** Each pace rule is a track (20% white) with a fill (62% white, yellow when over) and a 3px tick that marks today's day of the month, shown only for the current month.

### Service panels
Blue with white legends and the same keyline. Title in Service Legend, figure at 34px/800, a 6px bar (white fill, yellow when over). Whole-panel buttons (`button.service`) are full-width flex rows with a drawn arrow.

### Panels and tables
White surface, 1px rule, 12px radius, 18px 20px padding. Table headings are 13px uppercase labels in Ink 3; rows divide with 1px rules; hover fills Surface 2; split rows use a dashed rule; selected rows take the selection tint. Row actions appear on hover (desktop) over the row's text, and sit behind a "more" button on touch.

### Inputs
40px minimum height, 8px radius, 1px strong border. Focus: border to sign green plus a 3px soft green ring. Phones set 16px text to stop zoom.

### Notices
Orange warning (ink text, ink keyline, drawn warning icon), red error (white text, keyline), good (sign tint). Information goes in a blue service panel, not a notice.

## Do's and Don'ts

### Do:
- **Do** keep yellow (#ffcc00) for over budget only, and only on green or blue grounds.
- **Do** right-align figures at the line's edge, bold, on one line.
- **Do** use the drawn SVG icons in `Icon.tsx` (24px grid, 2px round strokes) for arrows, checks, warnings and more.
- **Do** let a state restyle the row in place.
- **Do** wrap text at spaces and size columns to content; check new tables at 375px.
- **Do** build light and dark from the same tokens; sign green stays the same in both.

### Don't:
- **Don't** use yellow for emphasis, hover, selection or decoration.
- **Don't** add a second sign to a screen or use green panels for ordinary content.
- **Don't** truncate text with ellipses, clips or fixed widths, or hide it in a tooltip.
- **Don't** use glyph or emoji icons, kickers above headings, or hard offset shadows.
- **Don't** use a donut chart or a row of hero-metric cards for the month.
