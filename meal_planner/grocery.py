"""Build the grocery list from the plan: scale by headcount, merge duplicates, subtract the pantry,
group by store and aisle. Also the shared name/unit/quantity helpers the rest of the app uses."""
import json
import re
import unicodedata
from fractions import Fraction

import db

STORE_LABEL = {"costco": "Costco", "costco_business": "Costco Business Center",
               "king_soopers": "King Soopers", "other": "Other"}
STORE_ORDER = list(STORE_LABEL)
# unit -> (family, factor to base)
UNITS = {"g": ("mass", 1), "kg": ("mass", 1000), "oz": ("mass", 28.35), "lb": ("mass", 453.6),
         "ml": ("vol", 1), "l": ("vol", 1000), "tsp": ("vol", 4.93), "tbsp": ("vol", 14.8), "cup": ("vol", 236.6),
         "floz": ("vol", 29.57), "pint": ("vol", 473.2), "quart": ("vol", 946.4), "gallon": ("vol", 3785),
         "": ("count", 1)}
_UNIT_ALIAS = {"cups": "cup", "c": "cup", "tbs": "tbsp", "tbl": "tbsp", "tbls": "tbsp", "tblsp": "tbsp",
               "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsps": "tbsp", "teaspoon": "tsp", "teaspoons": "tsp",
               "tsps": "tsp", "pound": "lb", "pounds": "lb", "lbs": "lb", "ounce": "oz", "ounces": "oz",
               "gram": "g", "grams": "g", "kilogram": "kg", "kilograms": "kg", "kgs": "kg", "milliliter": "ml",
               "milliliters": "ml", "millilitre": "ml", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
               "fl oz": "floz", "fl. oz": "floz", "fluid ounce": "floz", "fluid ounces": "floz", "fluid_ounce": "floz",
               "pints": "pint", "quarts": "quart", "qt": "quart", "gallons": "gallon", "gal": "gallon"}

# Words that turn a food into a different product when added: "milk" is not "coconut milk",
# "chicken" is not "chicken broth", "tomato" is not "tomato paste".
_DISTINCT = {"peanut", "almond", "cashew", "coconut", "oat", "soy", "rice", "sesame", "garlic", "onion", "chili",
             "corn", "sweet", "sour", "ice", "cream", "cocoa", "apple", "maple", "condensed", "evaporated",
             "noodle", "vinegar", "flour", "paste", "powder", "sauce", "oil", "milk", "butter", "cheese", "cake",
             "cracker", "bread", "chip", "syrup", "juice", "extract", "stock", "broth", "seasoning", "flake",
             "jam", "jelly", "spread", "dressing", "soup", "mix", "candy", "bar", "cereal", "pie", "wine",
             "water", "salt", "pepper", "jack", "pork", "chestnut", "bun", "roll", "cookie", "puff"}
_STAPLE_WORDS = {"salt", "pepper", "oil", "water", "spray"}
_STAPLE_OK = _STAPLE_WORDS | {"black", "white", "olive", "vegetable", "canola", "cooking", "neutral", "and",
                              "kosher", "sea", "fine", "coarse", "flaky", "table", "freshly", "ground", "cracked",
                              "extra", "virgin", "light", "pure", "ice", "cold", "warm", "hot", "boiling",
                              "lukewarm", "cool", "nonstick", "avocado"}
_IRREGULAR = {"leaves": "leaf", "loaves": "loaf", "halves": "half", "knives": "knife", "potatoes": "potato",
              "tomatoes": "tomato", "mangoes": "mango"}


def _singular(w):
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    if len(w) <= 3 or w.endswith(("ss", "us", "is")):
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ie") and len(w) > 4:          # cookie/cookies and brownie/brownies meet at 'cooky', 'browny'
        return w[:-2] + "y"
    if w.endswith(("ches", "shes", "xes", "oes")):
        return w[:-2]
    return w[:-1] if w.endswith("s") else w


def norm(name):
    """'Fresh Blueberries (optional)' -> 'blueberry'; 'Jalapeño' -> 'jalapeno'."""
    n = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)|,.*", "", n)
    n = re.sub(r"\b(fresh|large|small|medium|chopped|diced|sliced|minced|organic|boneless|skinless)\b", "", n)
    n = re.sub(r"[^a-z ]", " ", n).strip()
    return " ".join(_singular(w) for w in n.split())


def same(a, b):
    """Whole-word match on normalised names: 'chicken' ~ 'chicken breast', but not 'egg' ~ 'eggplant',
    'oat' ~ 'goat cheese' or 'milk' ~ 'coconut milk'."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    s, l = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return s <= l and not ((l - s) & _DISTINCT)


def is_staple(name):
    """Salt, pepper, cooking oil and water however they are written ('Kosher salt', 'Salt & pepper')."""
    words = set(norm(name).split()) - {"to", "taste", "for", "frying"}
    return bool(words & _STAPLE_WORDS) and words <= _STAPLE_OK


def covers(pantry_key, ingredient_key):
    """Does a pantry item cover an ingredient? A pantry 'Salt' only covers salt, not 'unsalted butter'."""
    if is_staple(pantry_key):
        return is_staple(ingredient_key) and bool(set(pantry_key.split()) & set(ingredient_key.split()) & _STAPLE_WORDS)
    return same(pantry_key, ingredient_key)


def canon_unit(u):
    u = str(u or "").lower().strip().rstrip(".")
    return _UNIT_ALIAS.get(u, u)


def family(unit):
    return UNITS.get(canon_unit(unit), ("count", 1))


def to_qty(v):
    """2, '2', '1/2', '1 1/2', '1.5' -> float; anything else -> 0."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if v == v and abs(v) < 1e7 else 0.0
    try:
        return float(sum(Fraction(p) for p in str(v).strip().split()))
    except (ValueError, ZeroDivisionError, TypeError):
        return 0.0


def clean_store(s):
    s = str(s or "").strip().lower().replace(" ", "_")
    return s if s in STORE_LABEL else ("costco_business" if "business" in s else "costco" if "costco" in s
                                       else "king_soopers" if "king" in s or "kroger" in s else "other")


def clean_ingredients(raw):
    """Never raises: strings become {"name": ...}, junk is dropped, qty becomes a number."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    out = []
    for i in raw if isinstance(raw, list) else []:
        if isinstance(i, str):
            i = {"name": i}
        if not isinstance(i, dict) or not str(i.get("name") or "").strip():
            continue
        out.append({"name": str(i["name"]).strip()[:200], "qty": to_qty(i.get("qty")),
                    "unit": canon_unit(i.get("unit")), "aisle": str(i.get("aisle") or "Other")[:40],
                    "store": clean_store(i.get("store") or "king_soopers"), "note": str(i.get("note") or "")[:200]})
    return out


def clean_steps(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = [raw]
    return [str(s) for s in raw if s] if isinstance(raw, list) else []


def pack_count(pack_size):
    """'24 ct' -> 24, '18 pk' -> 18, 'dozen' -> 12, else 1 (one package = one item)."""
    ps = str(pack_size or "")
    m = re.search(r"(\d+)\s*(?:ct|count|pk|pack|pcs|pieces|ea|eggs)\b", ps, re.I)
    return int(m.group(1)) if m else (12 if re.search(r"\bdozen\b", ps, re.I) else 1)


def leftover_heads(start=None, end=None):
    """{'date|slot': people} eating leftovers of that meal, which is cooked bigger to feed them."""
    where, args = ("AND date BETWEEN ? AND ?", (start, end)) if start else ("", ())
    return {r["leftover_of"]: r["n"] for r in db.rows(
        "SELECT leftover_of, sum(headcount) n FROM plan_meals WHERE COALESCE(leftover_of,'')<>'' "
        f"{where} GROUP BY leftover_of", args)}


def week_ingredients(start, end):
    """Leftover meals add nothing of their own: their people are added to the meal that is cooked double."""
    meals = db.rows("SELECT pm.date, pm.slot, pm.headcount, r.servings, r.ingredients FROM plan_meals pm "
                    "JOIN recipes r ON r.id=pm.recipe_id WHERE pm.date BETWEEN ? AND ? "
                    "AND COALESCE(pm.cooked,0)=0 AND COALESCE(pm.leftover_of,'')=''", (start, end))
    extra = leftover_heads(start, end)
    totals = {}
    for m in meals:
        people = (m["headcount"] or 1) + extra.get(f"{m['date']}|{m['slot']}", 0)
        scale = people / max(int(to_qty(m["servings"]) or 1), 1)
        for ing in clean_ingredients(m["ingredients"]):
            n = norm(ing["name"])
            if not n or n == "water" or (is_staple(ing["name"]) and not ing["qty"]):
                continue
            fam, factor = family(ing["unit"])
            t = totals.setdefault((n, fam), {"name": ing["name"], "base": 0.0, "fam": fam, "unit": ing["unit"],
                                             "store": ing["store"], "aisle": ing["aisle"], "note": ing["note"],
                                             "unspec": False, "covered": False})
            t["base"] += ing["qty"] * factor * scale
            t["unspec"] = t["unspec"] or not ing["qty"]
            if ing["note"] and not t["note"]:
                t["note"] = ing["note"]
    return totals


def subtract_pantry(totals):
    for item in db.rows("SELECT name, qty, unit, pack_size FROM pantry WHERE qty>0"):
        key = norm(item["name"])
        if not key:
            continue
        pf, pfactor = family(item["unit"])
        for (n, fam), t in totals.items():
            if not covers(key, n):
                continue
            t["covered"] = True
            if fam == "count" and pf == "count":
                t["base"] -= item["qty"] * (pack_count(item["pack_size"]) if not item["unit"] else 1)
            elif fam == pf and item["unit"]:
                t["base"] -= item["qty"] * pfactor
            else:
                t["base"] = 0      # tracked as packages (or a different kind of unit): any stock covers it
    return {k: t for k, t in totals.items() if t["base"] > 0.01 or (t["unspec"] and not t["covered"])}


def _display(t):
    fam, base = t["fam"], max(t["base"], 0)
    if fam == "count":
        return (round(base + 0.49) if base > 0.01 else 0), ""
    unit = t["unit"] if family(t["unit"])[0] == fam else ("g" if fam == "mass" else "ml")
    return round(base / family(unit)[1], 1), unit


def rebuild(start, end):
    """Fresh list from the plan. Keeps manual rows, and keeps the ticked/sent-to-HA state of items that are
    still needed so a rebuild never re-sends the whole list to the Home Assistant to-do list. A manual row with
    the same name wins over the plan's (the cook edited or added it), and remembered store/aisle choices apply."""
    totals = subtract_pantry(week_ingredients(start, end))
    prefs = {r["key"]: r for r in db.rows("SELECT key, store, aisle FROM item_prefs")}
    conn = db.connect()
    old = {norm(r["name"]): (r["checked"], r["synced"]) for r in
           conn.execute("SELECT name, checked, synced FROM grocery WHERE note IS NOT 'manual'")}
    manual = {norm(r[0]) for r in conn.execute("SELECT name FROM grocery WHERE note IS 'manual'")}
    conn.execute("DELETE FROM grocery WHERE note IS NOT 'manual'")
    for (n, _), t in totals.items():
        qty, unit = _display(t)
        if (not qty and not t["unspec"]) or n in manual:
            continue
        checked, synced = old.get(n, (0, 0))
        p = prefs.get(n) or {}
        conn.execute("INSERT INTO grocery(name,qty,unit,store,aisle,note,checked,synced) VALUES(?,?,?,?,?,?,?,?)",
                     (t["name"], qty, unit, clean_store(p.get("store") or t["store"]), p.get("aisle") or t["aisle"],
                      t["note"] or "", checked, synced))
    conn.commit()
    conn.close()
    return listing()


# --- Quick add: "2 lb chicken thighs" -> qty, unit, name; then where the cook usually files it ------------

_PACK = {"can": "can", "cans": "can", "jar": "jar", "jars": "jar", "bag": "bag", "bags": "bag", "box": "box",
         "boxes": "box", "pack": "pack", "packs": "pack", "pkg": "pack", "bunch": "bunch", "bunches": "bunch",
         "bottle": "bottle", "bottles": "bottle", "carton": "carton", "cartons": "carton", "loaf": "loaf",
         "loaves": "loaf", "head": "head", "heads": "head", "dozen": "dozen", "doz": "dozen"}
_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "half": 0.5}
_QTY = r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|(?:" + "|".join(_WORDS) + r")\b)"


def _unit_word(w):
    w = w.lower().rstrip(".")
    if w in _PACK:
        return _PACK[w]
    u = canon_unit(w)
    return u if u in UNITS and u else None


def parse_quick(text):
    """'2 lb chicken thighs', '1 1/2 cups rice', 'milk x2', 'a dozen eggs', 'eggs' -> {name, qty, unit}.
    qty 0 means no amount was given."""
    t = " ".join(str(text or "").split())[:200]
    qty, unit = 0.0, ""
    m = re.match(r"^(.*?)\s*[x×]\s*(\d+(?:\.\d+)?)$", t, re.I)          # 'milk x2'
    if m and m.group(1):
        t, qty = m.group(1), float(m.group(2))
    m = re.match(rf"^{_QTY}\s*(.*)$", t, re.I)
    if m and m.group(2):
        q = m.group(1).lower()
        qty, t = (float(_WORDS[q]) if q in _WORDS else to_qty(q)), m.group(2)
        m2 = re.match(r"^(fl\.? oz|[a-zA-Z.]+)\s+(?:of\s+)?(.+)$", t)
        if m2 and _unit_word(m2.group(1)):
            unit, t = _unit_word(m2.group(1)), m2.group(2)
    if unit == "dozen":
        qty, unit = qty * 12, ""
    name = t.strip(" ,.-")
    return {"name": name[:1].upper() + name[1:], "qty": round(qty, 2), "unit": unit}


def placement(name):
    """Store and aisle for an item: what the cook chose before, else what the plan used, else a guess."""
    from recipes import aisle_for
    n = norm(name)
    prefs = db.rows("SELECT key, store, aisle FROM item_prefs")
    hit = next((p for p in prefs if p["key"] == n), None) or next((p for p in prefs if n and same(p["key"], n)), None)
    if hit:
        return {"store": clean_store(hit["store"]), "aisle": hit["aisle"] or aisle_for(name), "known": True}
    bought = db.rows("SELECT store FROM purchases WHERE key=? AND store<>'' ORDER BY id DESC LIMIT 1", (n,))
    return {"store": clean_store(bought[0]["store"]) if bought else "king_soopers", "aisle": aisle_for(name),
            "known": False}


def remember(name, store=None, aisle=None):
    n = norm(name)
    if not n:
        return
    db.run("INSERT INTO item_prefs(key,name,store,aisle) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
           "name=excluded.name, store=COALESCE(excluded.store,store), aisle=COALESCE(excluded.aisle,aisle)",
           (n, str(name).strip()[:200], clean_store(store) if store else None, str(aisle)[:40] if aisle else None))


def listing():
    items = db.rows("SELECT * FROM grocery ORDER BY aisle, name")
    groups = {}
    for i in items:
        groups.setdefault(i["store"] if i["store"] in STORE_LABEL else "other", {}).setdefault(i["aisle"], []).append(i)
    return [{"store": s, "label": STORE_LABEL[s],
             "aisles": [{"aisle": a, "items": groups[s][a]} for a in sorted(groups[s])]}
            for s in STORE_ORDER if s in groups]
