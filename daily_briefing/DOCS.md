# Daily Briefing

Builds your day at a glance every minute and publishes it as Home Assistant sensors. A ready-made dashboard shows those sensors in big type, and you cast that dashboard to the TV through Home Assistant Cloud (Nabu Casa). The add-on's own page (sidebar **Briefing**) shows the same content on your phone.

The TV shows a display only. The Google TV remote cannot press or scroll a cast dashboard, and the cards update live while it is on screen.

## Put it on the TV

1. **Create the dashboard.** Settings > Dashboards > Add dashboard > New dashboard from scratch. Title `Daily Briefing`, and set the URL to `daily-briefing`. Open it, tap the pencil, then ⋮ > Raw configuration editor.
2. **Paste the dashboard.** Open the add-on's page (sidebar **Briefing**), expand **Show it on the TV** and press **Copy dashboard**. Select everything in the raw editor, paste, Save. (The same text is in `dashboard.yaml` in this add-on's folder.)
3. **Cast it once to test.** Developer tools > Actions > UI mode > **Google Cast: Show dashboard view**. Pick the Google TV in the entity picker (it lists only Cast devices), set **Dashboard path** to `daily-briefing` and **View path** to `briefing`, then Perform action. Put the Samsung on the Google TV input first.
4. **Cast it every morning** with an automation (replace the entity with the one you picked in step 3):

```yaml
alias: Daily briefing on the TV
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: time
    weekday: [mon, tue, wed, thu, fri]
actions:
  - action: cast.show_lovelace_view
    data:
      entity_id: media_player.office_tv
      dashboard_path: daily-briefing
      view_path: briefing
```

If the cast is bright white, the cast session is using the light theme. Try Developer tools > Actions > `frontend.set_theme` with theme `default` and mode `dark`.

## Sections

Today (date, weather, sunrise and sunset, calendar events), Workout, Meals, Due today, Ski, Money, Shopping. Each one is a sensor, `sensor.daily_briefing_<section>`, whose state is a short headline and whose `lines` attribute holds the rows. A section that cannot be read shows **Unavailable**. **Off season** (Ski) and **Not set up** (Money, Due today) are normal until configured.

| Section | Comes from |
|---|---|
| Today | Home Assistant weather, sun and calendar entities. Holiday and birthday calendars are skipped unless you list them under Calendars. |
| Workout | Workout Tracker sensors (`sensor.workout_today`, `sensor.workout_streak`). |
| Meals | Meal Planner: today's meals, tomorrow's meals as the prep, and pantry items to use up. |
| Due today | Home Maintenance sensor (`sensor.home_maintenance_due`) and Work Tracker tasks due today (needs `api_key`). |
| Ski | Ski Assistant: best resort today. Shown November to April, or whenever a lift is running. |
| Money | Budget: safe to spend this week and the month so far (needs `api_token`). |
| Shopping | The `todo.shopping_list` list (change it under Shopping list). |

## Options

- **Notify service / Morning phone summary / Morning time**: a short text summary at 07:00 by default. An add-on started after that time does not send it late.
- **Calendars**: calendar entities to include. Empty means all except holidays and birthdays.
- **Weather entity**: empty means `weather.home` or the first weather entity.
- **Budget API token / Work Tracker API key**: the `api_token` and `api_key` of those add-ons. Blank options are filled from the shared `addon_secrets.json`.
- **Refresh every (seconds)**: 30 to 600, default 60. A sensor is only written when its value changes.

The recorder keeps a history of every sensor change. To keep these out of it, add `sensor.daily_briefing_*` to the recorder's `exclude` list.
