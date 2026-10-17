"""Tiny cached JSON GET (stdlib only, in-memory cache: no disk writes)."""
import json
import time
import urllib.request

_cache = {}


def get(url, ttl=1800, timeout=20):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": "ski-assistant-ha-addon"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    _cache[url] = (time.time(), data)
    return data
