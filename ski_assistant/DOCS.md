# Ski Assistant

## Dashboard card

The add-on keeps `sensor.ski_best_bet` up to date every 15 minutes: the best resort and day in the next five days, with fresh snow, the high, gusts, when to leave and the drive. When a calendar is set in Settings, it only picks days you're free.

To put it on a dashboard: **Edit dashboard → Add card → Manual**, and paste:

```yaml
type: markdown
title: Ski
content: >-
  {% set b = 'sensor.ski_best_bet' %}
  {% if states(b) not in ['unknown', 'unavailable'] %}
  **{{ states(b) }}**, {{ state_attr(b, 'day') }}: {{ state_attr(b, 'fresh_in') }}″ fresh,
  high {{ state_attr(b, 'high_f') }}°F, gusts {{ state_attr(b, 'gust_mph') }} mph

  Leave **{{ state_attr(b, 'leave_at') }}**, {{ state_attr(b, 'drive') }} drive

  [Open Ski Assistant]({{ state_attr(b, 'panel') }})
  {% else %}No pick yet.{% endif %}
```

Its attributes: `date`, `day`, `fresh_in`, `high_f`, `gust_mph`, `leave_at`, `drive`, `next_best`, `panel` (the link to this add-on's page). The add-on also keeps `sensor.ski_best_today` (today's top resort) and `sensor.ski_days_this_season`.

## Picking only days you're free

Under **More → Settings**, set **Calendar for free days** to one of your calendars (for example `calendar.work`). A day counts as busy when a timed event overlaps 8am to 3pm; all-day events such as holidays and birthdays don't count. The best bet is always a free day, and busy days show **Busy** under their snow total.

## Where leave times start

Leave times and drive times start from the first line of **Departure points** under **More → Settings** (name, latitude, longitude). Until you change it, that is a placeholder in downtown Denver, and the Forecast tab reminds you.

## Resorts that aren't open

A resort whose report says it isn't open for the season yet (or has closed for it), or that has no lifts running in the middle of the day, drops to the bottom of the Plan list and is never the best bet. A resort you add without a live report is always treated as open.

## Open lifts and trails, and the trail map

Each resort page shows how many lifts and trails are open, and **Open right now** lists them by name, from the feeds the resorts' own websites use: MtnPowder (Winter Park, Arapahoe Basin, Steamboat), POWDR (Copper, Eldora) and Aspen Snowmass's own report (all four mountains). Keystone's site blocks the add-on, so it only has lift and run counts from OnTheSnow, without names. These are unofficial feeds, so a resort can drop out for a while if its site changes.

The trail map draws each resort's runs and lifts from OpenStreetMap (the data OpenSkiMap shows) and colours them by matching names with the resort's report, which finds about 9 in 10 runs. A run the report names but the map can't find is listed under the map. The runs and lifts for the built-in resorts ship with the add-on; for a resort you add in `ski_resorts.json`, the first map is fetched from OpenStreetMap and can take a minute.
