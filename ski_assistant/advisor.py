"""Ask Claude "where should I go Saturday?" from the add-on's own data (ranking, leave times, gear, pass and log).
Uses the Anthropic API key from the add-on options (ANTHROPIC_API_KEY)."""
import json
import os

import anthropic

import ranking
import resorts
import season
import settings
import util

SYSTEM = """You are a ski and snowboard trip planner for one rider in Colorado. Answer from the JSON data only;
if the data does not cover something, say so. The rider has an Ikon full pass and a Keystone pass, mostly
snowboards, and is learning to ski. Give one clear pick, the leave time, and one or two reasons
(snow, wind, crowds, drive). Mention a runner-up only if it is close. Keep it under 120 words, plain text."""


def available():
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _compact(rows):
    keep = ("resort", "score", "fresh_in", "tmax_f", "tmin_f", "gust_mph", "leave", "beginner_pct", "live", "pass")
    return [{k: r.get(k) for k in keep} for r in rows if "error" not in r]


def ask(question, date=None, skis=False, departure=None):
    date = date or util.today().isoformat()
    rows = ranking.best_days(resorts.load(), date, skis=skis, departure=departure)
    context = {"today": util.today().isoformat(), "date_asked_about": date, "skis_day": skis,
               "departure": settings.departure(departure)["name"], "ranking": _compact(rows),
               "gear_for_top_pick": rows[0].get("gear") if rows and "error" not in rows[0] else None,
               "season": season.pass_summary()}
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = client.beta.messages.create(
        model=settings.load()["claude_model"],
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # retry on another model if a safety classifier declines
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Data:\n{json.dumps(context)}\n\nQuestion: {question}"}],
    )
    if response.stop_reason == "refusal":
        return {"answer": "Claude declined to answer that one.", "date": date}
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return {"answer": text, "date": date}
