# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One person, the owner, managing their own household money. No one else uses or edits it. They use it about equally in two ways: quick checks on a phone inside the Home Assistant companion app, and longer sit-down sessions on a computer going through transactions, the budget and the payoff plan.

## Product Purpose

A personal budget that runs at home on a Home Assistant Green. Bank data arrives once a day through SimpleFIN Bridge (manual accounts and bank-file imports cover the rest), Claude categorizes transactions, and the app answers: how this month is going against the budget, what is safe to spend this week, which new charges need a look, and when each debt will be paid off. Success is the owner knowing where the month stands at a glance and keeping the payoff plan on track without spreadsheet work.

When the app opens, the most important thing to see first is this month's spending against the budget, by category.

## Positioning

It is the owner's own system, not a bank's or an aggregator's: private data on their own hardware, a payoff plan built around one number (the most they can spend each month and still make every payoff date), weekly safe-to-spend derived from that plan, and AI categorization that learns from their corrections.

## Operating Context

- Phone: the Home Assistant app's sidebar panel (ingress), often a quick glance; light or dark follows the phone.
- Computer: a browser tab, for reviewing transactions, setting budgets, editing the plan and importing bank files.
- Data refreshes once a day; the Daily Briefing add-on reads `/api/summary` and `/api/briefing`.

## Capabilities and Constraints

- Tabs: Dashboard, Transactions (To review queue, the month's list, and Owed to you), Budget, Recurring, Debt, Plan, Year, Accounts, Ask (questions answered by Claude over the data).
- Text in tables and lists is never cut off; it wraps. Short values stay on one line.
- Runs on ARM hardware with little memory: light dependencies, no heavy charting libraries.
- Frontend URLs stay relative (Home Assistant ingress).
- Must work in light and dark mode, and on a 375px-wide phone without sideways scrolling.

## Brand Commitments

- Name: Budget. The add-on has its own icon (`icon.png`, `web/public/icon.svg`), also used as the favicon.

## Evidence on Hand

Real data only exists on the owner's Home Assistant; sample data for design and testing must be labeled as sample and never presented as theirs.

## Product Principles

1. Lead with where the month stands; everything else is one tap away.
2. Numbers first, readable at a glance on a phone, without becoming a spreadsheet.
3. Plain words over finance jargon; the owner's own categories and names.
4. Nothing hidden that matters today; what isn't current goes behind "Show".
5. Calm and personal, never a corporate banking app.
