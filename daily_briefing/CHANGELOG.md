# Changelog

## 0.1.1

- Removed the Friends section: the dashboard has 7 cards and `sensor.daily_briefing_friends` is no longer published (a copy made by 0.1.0 disappears when Home Assistant restarts). The add-on no longer talks to Friend Reminder.

## 0.1.0

First version.

- Builds your day at a glance every minute: Today (date, weather with the day's high and low, sunrise and sunset, calendar events), Workout, Meals, Friends, Due today (home maintenance and work tasks), Ski (in season), Money and Shopping.
- Every section works on its own: if one source is down it shows "Unavailable" and the others still show. Ski shows "Off season" and Money or Work show "Not set up" until their tokens are filled.
- Publishes each section as a Home Assistant sensor (`sensor.daily_briefing_today`, `_workout`, `_meals`, `_friends`, `_due`, `_ski`, `_money`, `_shopping` and `_summary`). A sensor is only written when its value changes.
- Ships a ready-made TV dashboard (`dashboard.yaml`, also behind the "Show it on the TV" button on the add-on's page). Cast it with `cast.show_lovelace_view` through Nabu Casa. The add-on's Documentation tab has the steps and a morning automation.
- The add-on's own page (sidebar "Briefing") shows the same content for your phone.
- Optional morning summary on your phone at a time you choose (07:00 by default). An add-on started after that time does not send it late.
- Reads the other add-ons over Home Assistant's internal network and never writes to them. Nothing is stored on disk.
