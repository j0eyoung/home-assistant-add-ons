# j0eyoung's Home Assistant Add-ons

Add this repository in Home Assistant: **Settings > Add-ons > Add-on Store > ⋮ > Repositories**, then paste
`https://github.com/j0eyoung/home-assistant-add-ons`.

| Add-on | What it does |
|---|---|
| [Budget](budget) | Personal budgeting with SimpleFIN bank sync and Claude AI. |
| [Trading Terminal](trading_terminal) | Market data, research and paper/live trading through Alpaca and Interactive Brokers. |
| [IB Gateway](ib_gateway) | Headless Interactive Brokers Gateway for the Trading Terminal. |
| [Friend Reminder](friend_reminder) | A daily phone nudge to reach out to friends you haven't talked to in a while, with Claude-drafted openers. |
| [Home Maintenance Log](home_maintenance) | Recurring home upkeep with Done / Snooze phone reminders, printer toner alerts that add cartridges to the shopping list, an appliance and warranty register, and receipts stored in your own bucket. |
| [Ski Assistant](ski_assistant) | 16-day snow forecasts for Colorado resorts (ECMWF + GFS), Daily Snow, radar, powder alerts, best-day picks, leave times that beat I-70 traffic, season log. |

Images are built by GitHub Actions for `aarch64` and `amd64` and published to GHCR, so Home Assistant only downloads them.

## Shared secrets

Instead of typing the same keys into every add-on, copy [addon_secrets.example.json](addon_secrets.example.json) to `addon_secrets.json` in the Home Assistant config folder and fill in the keys. Blank add-on options are filled from it at start; an option set in an add-on's Configuration tab always wins.
