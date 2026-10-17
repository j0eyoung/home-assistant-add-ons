"""Shared helpers: Denver-local dates and distance."""
import datetime as dt
import math
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Denver")


def now():
    return dt.datetime.now(TZ)


def today():
    return now().date()


def miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))
