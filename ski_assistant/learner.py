"""Learning to ski: what a skis day counts besides the usual snow, wind, temperature, crowds and drive.

On a skis day 25 of the 100 points go to learning (the other factors keep 75%):
  open runs  10  open greens and blues in today's live report; a groomed one counts 1, an ungroomed one half,
                 and 12 or more gets the full 10 (laps off a lift or two are plenty while learning). A resort
                 whose report doesn't say gets the middle of the resorts that have greens and blues open that
                 day, so it's neither helped nor hurt.
  share       5  how much of the whole mountain is green or blue (OpenSkiMap's statistics)
  surface     5  full when the snow isn't firm, half when it's firm first thing but softens by midday, none
                 when it stays firm and icy all day (forecast.py: the morning after a thaw and a hard refreeze)
  wind      2.5  full with gusts of 20 mph or less, none at 40
  light     2.5  full with 60% cloud or less from 9am to 3pm, none at 90% (flat light hides the bumps)
Open runs are today's, used for every date: in early season what's open now is the best guess for the next
few days. Lift and trail status only means something while the lifts run, so the 9am-3pm count is kept and used
through the evening and the next morning when the feed shows fewer open overnight."""
import util

W_RUNS, W_SHARE, W_SURFACE, W_WIND, W_LIGHT = 10, 5, 5, 2.5, 2.5
LEARN = W_RUNS + W_SHARE + W_SURFACE + W_WIND + W_LIGHT  # 25
FULL_RUNS = 12
LEVELS = ("green", "blue")
_day = {}  # resort id -> (date, counts) from the last 9am-3pm look


def terrain(r, live, pct=None):
    """Greens and blues open: {"open", "groomed", "of"} from the live list, or {"open", "estimated": True} from
    the run count and the mountain's green-and-blue share when the feed has counts only. None without a report."""
    trails = (live or {}).get("trails")
    if trails:
        gb = [x for x in trails if x.get("level") in LEVELS]
        on = [x for x in gb if x["status"] == "open"]
        c = {"open": len(on), "green": sum(1 for x in on if x["level"] == "green"),
             "groomed": sum(1 for x in on if x.get("groomed")), "of": len(gb)}
    elif live and live.get("trails_open") is not None and pct is not None:
        c = {"open": round(live["trails_open"] * pct / 100), "green": None, "groomed": None, "of": None,
             "estimated": True}
    else:
        return None
    if 9 <= util.now().hour < 15:
        _day[r["id"]] = (util.today(), c)
    else:
        hit = _day.get(r["id"])
        if hit and (util.today() - hit[0]).days <= 1 and hit[1]["open"] > c["open"]:
            c = hit[1] | {"remembered": True}
    return c


def runs(t):
    """0-1 for open greens and blues (an unknown grooming count takes three in four as groomed)."""
    n = t["open"] * 0.75 if t.get("groomed") is None else t["groomed"] + 0.5 * (t["open"] - t["groomed"])
    return min(1.0, n / FULL_RUNS)


def score(base, day, t, pct, fill=None):
    """(skis-day score, its learning points by part) from the usual score and the day's forecast. `fill` is the
    open-runs value for a resort with no count (the middle of the other resorts')."""
    share = (pct if pct is not None else 50) / 100
    cloud = day.get("cloud_day")
    parts = {"runs": W_RUNS * (runs(t) if t else fill if fill is not None else share),
             "share": W_SHARE * share,
             "surface": W_SURFACE * {"softens": 0.5, "firm": 0.0}.get(day.get("surface"), 1.0),
             "wind": W_WIND * max(0.0, min(1.0, (40 - day["gust_mph"]) / 20)),
             "light": W_LIGHT * (1.0 if cloud is None else max(0.0, min(1.0, (90 - cloud) / 30)))}
    return round(base * (100 - LEARN) / 100 + sum(parts.values()), 1), {k: round(v, 1) for k, v in parts.items()}
