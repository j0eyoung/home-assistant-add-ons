"""Tiny cached JSON GET (stdlib only, in-memory cache: no disk writes). Asks for gzip, which cuts the
MtnPowder feed from ~20s to ~1s and halves Open-Meteo's time.

When a refresh fails, the last good answer (up to STALE_MAX old) is served instead of an error, and the URL
isn't tried again for RETRY_AFTER seconds. A slow or down source can't hold every page load for its timeout."""
import gzip
import json
import time
import urllib.request

STALE_MAX = 24 * 3600
RETRY_AFTER = 300
_cache = {}   # url -> (fetched_at, data)
_failed = {}  # url -> (failed_at, message)


def get(url, ttl=1800, timeout=20):
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < ttl:
        return hit[1]
    usable = hit if hit and now - hit[0] < STALE_MAX else None
    fail = _failed.get(url)
    # With an older answer to show, wait RETRY_AFTER before trying again; with nothing to show, only a minute
    if fail and now - fail[0] < (RETRY_AFTER if usable else 60):
        if usable:
            return usable[1]
        raise RuntimeError(fail[1])
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ski-assistant-ha-addon", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        data = json.loads(raw)
    except Exception as e:
        _failed[url] = (now, str(e) or type(e).__name__)
        print(f"[httpjson] {url.split('?')[0]} failed ({_failed[url][1]}); "
              f"{'serving the answer from ' + time.strftime('%H:%M', time.localtime(usable[0])) if usable else 'nothing cached'}", flush=True)
        if usable:
            return usable[1]
        raise
    _failed.pop(url, None)
    _cache[url] = (time.time(), data)
    return data


def fetched_at(url):
    """When the answer get() last returned for this URL was fetched (epoch seconds), or None."""
    hit = _cache.get(url)
    return hit[0] if hit else None
