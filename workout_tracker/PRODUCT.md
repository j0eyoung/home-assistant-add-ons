# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One person, Joe, training in his home gym. He uses it mostly on his phone in the gym, mid-workout (confirmed): the morning check-in, ticking the daily non-negotiables, logging sets (weight × reps), running hold and rest timers, then the cool-down. Planning (Week, Coach) and review (History, PT report) happen on the same phone, sometimes on a PC.

## Product Purpose

A self-regulating training plan for a body in rehab. Each day's workout adapts to the morning check-in (left kidney/flank and pelvic floor scores, 1-10), Garmin data and the exercises his physio gave him, while building toward the ski season. Success: he trains consistently, symptoms stay down, loads go up in safe steps, and his PT gets a clear record.

## Positioning

Not a generic gym log. Every plan, progression step and coach suggestion is screened against his own medical constraints and symptom history, and the AI coach (Claude, acting as PT and strength coach) can only change the plan through checked proposals he approves with one tap.

## Operating Context

- Runs as a Home Assistant add-on on an HA Green. Opened from the Home Assistant sidebar (ingress) or installed on the phone's home screen as an app (PWA). Publishes HA sensors and sends phone notifications (morning check-in reminder, arriving at the PT office, water nudge).
- Home gym: treadmill, Peloton, water rower, squat rack, bench, cable machine, dumbbells, barbell, kettlebell, bands, vibration board, inversion table.
- Rituals: the morning check-in; daily non-negotiables (breathing and deep-core activation); PT visits every two weeks with a printable report and biofeedback readings; the ski-season build-up to opening day.

## Capabilities and Constraints

- Five tabs: Today, Week, Coach, Mind & Body, More (History, Library, PT report, Settings).
- Today: check-in, water, snow-day log, daily non-negotiables with timers and guided breathing, strength cards (pictures, how-to, last time and suggested weight/reps, set logging, rest and hold timers, swap, "Bothered me"), cardio, optional guided cool-down, done card with personal records.
- Week: the week's day types and muscle groups, a coach-planned 4-week block, cardio machine unlock status, ski readiness checks.
- Coach: shared chat with Apply / No thanks on suggested plan changes.
- Mind & Body: yoga poses, Baduanjin qigong, guided sessions in a natural voice, meditations.
- Stack: FastAPI with a vanilla JS single page (static/app.js, static/app.css, static/index.html), no build step, relative URLs so it works behind Home Assistant ingress. Offline-capable service worker.
- Must keep (confirmed): Today's order (daily non-negotiables, strength, cardio, cool-down), the five-tab bar, dark and light mode following the phone.
- Confirmed problems with the current interface: it looks generic, and History, Library, PT report and Settings are hard to find.

## Brand Commitments

- Name: "AI Workout Tracker"; Home Assistant panel title "Workouts" with the dumbbell icon; home-screen app icons in static/icon-*.png.
- Voice: plain, short, second person, encouraging without hype; safety notes stated plainly ("Stop if your left flank pulls").

## Evidence on Hand

- Exercise pictures from the Free Exercise DB and RepDB illustrations; CC-licensed yoga and qigong photos bundled in static/ with credits shown in the app; a private bucket of yoga photos.
- Real training data lives in his database; mockups use labelled sample data.

## Product Principles

1. Safety gates first: symptoms and the PT's rules outrank progression everywhere.
2. Nothing changes the plan without an explicit tap.
3. Mid-set use wins: what he needs during a set is one glance and one tap away.
4. Everything is set up inside the app, never by editing files or pasting into chat.
5. Plain words over training jargon.

## Accessibility & Inclusion

Used one-handed and sweaty between sets, sometimes propped at arm's length: large tap targets, numbers readable at a glance, works in a bright or dim room. No text is ever cut off; long text wraps.
