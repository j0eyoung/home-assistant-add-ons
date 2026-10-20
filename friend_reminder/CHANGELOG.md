# Changelog

## 0.1.3

- Contacts import: every contact now starts on "Don't remind". Pick Close, Good or Casual only for the people you want reminders about. Saving remembers the rest, so the next import of the same file lists only new contacts. Searching (or ticking "Also show the contacts already sorted") still finds them if you change your mind.
- Without a contact picker (for example in the Home Assistant app), the contacts-file import is shown first.
- The page now uses the add-on's icon as its browser tab icon.

## 0.1.2

- Moved into the shared add-ons repository; options can be filled from the shared secrets file.

## 0.1.0

First version.

- Add friends by importing a contacts file (.vcf, exported from the Contacts app or Google Contacts; birthdays come along), with the phone's contact picker where the browser has one (Chrome on Android), or one at a time. Then give each one a closeness: Close (every 2 weeks), Good (monthly) or Casual (every 3 months). Any friend can have their own custom interval instead.
- Friends are ranked by how overdue you are: days since you last talked divided by their interval. A friend is due once that reaches 1.0, and the most overdue come first.
- A daily nudge on your phone at the time you choose (midday by default), for 1 or 2 friends. Every nudge has Done, Snooze and Skip buttons. Tapping Done restarts that friend's clock, Snooze asks again in a few days, and Skip leaves them alone for one full interval.
- Birthdays jump the queue: a friend whose birthday is today is nudged first.
- Notes per friend (a new job, a sick parent, a kid's birthday).
- Claude drafts a short conversation opener from a friend's notes. Needs your own Anthropic API key in the add-on options, billed per use by Anthropic and kept on your Home Assistant. The add-on works without it.
- Pick the Claude model in the options: claude-opus-5-5, claude-sonnet-5-5 or claude-haiku-5-5.
- Works only through Home Assistant (sidebar panel "Friends"); nothing is exposed on your network. The database is kept in the add-on's own config folder so it survives updates.
