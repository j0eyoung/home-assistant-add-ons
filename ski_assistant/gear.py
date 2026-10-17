"""Rule-based clothing and gear call from the day's temperature, wind and snow."""


def call(day, fresh_in=0.0, skis=False):
    mid = (day["tmax_f"] + day["tmin_f"]) / 2
    eff = mid - max(0.0, day["wind_mph"] - 5) * 0.25  # rough wind-chill
    gust = day["gust_mph"]
    if eff <= 0:
        wear = ["Midweight merino base", "Fleece mid layer", "Insulated shell and pants", "Balaclava or neck gaiter",
                "Mittens with hand warmers"]
    elif eff <= 15:
        wear = ["Midweight base", "Fleece mid layer", "Shell jacket and pants", "Neck gaiter", "Warm gloves"]
    elif eff <= 28:
        wear = ["Light base", "Light mid layer or vest", "Shell jacket and pants", "Gloves"]
    elif eff <= 40:
        wear = ["Light base", "Shell jacket (skip the mid layer)", "Light gloves", "Sunscreen"]
    else:
        wear = ["Light base", "Shell jacket, vents open", "Light gloves", "Sunscreen"]
    notes = []
    if fresh_in >= 4:
        notes += ["Low-light lens for goggles", "Waterproof gloves plus a dry spare pair"]
    if fresh_in >= 8:
        notes.append("Powder day: be at the lot early")
    if fresh_in < 0.5 and day["tmax_f"] > 30:
        notes.append("Sunny: dark lens and sunscreen")
    if gust >= 35:
        notes += ["Windy: cover your face", "Expect lift holds up high"]
    if skis:
        notes.append("Skis: pack the ski boot bag; stick to greens and blues while learning")
    return {"feels_like_f": round(eff), "wear": wear, "notes": notes}
