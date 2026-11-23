"""Tiny cached JSON GET (stdlib only, in-memory cache: no disk writes). Asks for gzip, which cuts the
MtnPowder feed from ~20s to ~1s and halves Open-Meteo's time.

When a refresh fails, the last good answer (up to stale_max old, a day by default) is served instead of an error,
and the URL isn't tried again for RETRY_AFTER seconds. A slow or down source can't hold every page load for its
timeout. `body` makes it a POST (Overpass); `text=True` returns the page as text instead of parsing JSON."""
import gzip
import hashlib
import json
import time
import urllib.request

STALE_MAX = 24 * 3600
RETRY_AFTER = 300
_cache = {}   # key -> (fetched_at, data)
_failed = {}  # key -> (failed_at, message)


def get(url, ttl=1800, timeout=20, body=None, text=False, stale_max=STALE_MAX):
    key = url if body is None else f"{url}#{hashlib.sha1(body).hexdigest()}"
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    usable = hit if hit and now - hit[0] < stale_max else None
    fail = _failed.get(key)
    # With an older answer to show, wait RETRY_AFTER before trying again; with nothing to show, only a minute
    if fail and now - fail[0] < (RETRY_AFTER if usable else 60):
        if usable:
            return usable[1]
        raise RuntimeError(fail[1])
    try:
        req = urllib.request.Request(url, data=body,
                                     headers={"User-Agent": "ski-assistant-ha-addon", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        data = raw.decode("utf-8", "replace") if text else json.loads(raw)
    except Exception as e:
        _failed[key] = (now, str(e) or type(e).__name__)
        print(f"[httpjson] {url.split('?')[0]} failed ({_failed[key][1]}); "
              f"{'serving the answer from ' + time.strftime('%H:%M', time.localtime(usable[0])) if usable else 'nothing cached'}", flush=True)
        if usable:
            return usable[1]
        raise
    _failed.pop(key, None)
    _cache[key] = (time.time(), data)
    return data


def fetched_at(url):
    """When the answer get() last returned for this URL was fetched (epoch seconds), or None."""
    hit = _cache.get(url)
    return hit[0] if hit else None
