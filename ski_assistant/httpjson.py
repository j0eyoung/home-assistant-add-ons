"""Tiny cached JSON GET (stdlib only, in-memory cache: no disk writes). Asks for gzip, which cuts the
MtnPowder feed from ~20s to ~1s and halves Open-Meteo's time."""
import gzip
import json
import time
import urllib.request

_cache = {}


def get(url, ttl=1800, timeout=20):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": "ski-assistant-ha-addon", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    data = json.loads(raw)
    _cache[url] = (time.time(), data)
    return data
