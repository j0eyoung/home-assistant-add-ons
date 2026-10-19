"""Yoga pictures from a PRIVATE S3-compatible bucket (Backblaze B2), set up the same way as the Trading Terminal:
endpoint, bucket and key from this add-on's Configuration tab.

The page asks this add-on for `api/media/yoga/<file>.jpg`; the add-on fetches it from the bucket with the key
(which never reaches the browser) and keeps a copy under /data/media-cache, so each picture is downloaded once.
The pictures are CC0, so the cache is not sensitive."""
import json
import os
import re

OPTIONS_PATH = "/data/options.json"
CACHE_DIR = os.getenv("MEDIA_CACHE_DIR", "/data/media-cache")
NAME_RE = re.compile(r"^[a-z0-9-]+\.jpg$")
_client = {"c": None, "sig": None}


def settings():
    try:
        with open(OPTIONS_PATH, encoding="utf-8") as f:
            o = json.load(f)
    except (OSError, ValueError):
        o = {}
    prefix = (o.get("s3_prefix") or "workout/yoga").strip().strip("/")
    return {"endpoint": (o.get("s3_endpoint") or "").strip(), "bucket": (o.get("s3_bucket") or "").strip(),
            "key": (o.get("s3_access_key") or "").strip(), "secret": (o.get("s3_secret_key") or "").strip(),
            "region": (o.get("s3_region") or "auto").strip() or "auto", "prefix": prefix}


def configured():
    s = settings()
    return bool(s["endpoint"] and s["bucket"] and s["key"] and s["secret"])


def _s3(s):
    sig = (s["endpoint"], s["key"], s["secret"], s["region"])
    if _client["c"] is None or _client["sig"] != sig:
        import boto3
        from botocore.config import Config
        _client["c"] = boto3.client(
            "s3", endpoint_url=s["endpoint"], aws_access_key_id=s["key"], aws_secret_access_key=s["secret"],
            region_name=s["region"],
            # same as the Trading Terminal: boto3 checksum headers can be refused by Backblaze B2
            config=Config(retries={"max_attempts": 4, "mode": "standard"}, connect_timeout=10, read_timeout=60,
                          request_checksum_calculation="when_required", response_checksum_validation="when_required"))
        _client["sig"] = sig
    return _client["c"]


_HINTS = {
    "NoSuchBucket": "The bucket name wasn't found. Check the bucket name and the endpoint.",
    "InvalidAccessKeyId": "The access key isn't recognised. Check the key ID and the endpoint region.",
    "SignatureDoesNotMatch": "The secret key doesn't match the access key. Re-paste the secret.",
    "AccessDenied": "The key has no permission to read this bucket or folder. Give the key read access to the bucket.",
    "403": "The key has no permission to read this bucket or folder.",
    "NoSuchKey": "Connected, but the picture wasn't found. Check the folder name and that the files are directly inside it.",
    "404": "Connected, but the picture wasn't found. Check the folder name and that the files are directly inside it.",
}


def test():
    """Try a few pictures; passes if any loads. Otherwise says plainly what went wrong (never includes the keys)."""
    result = None
    for name in ("adho-mukha-svanasana-1.jpg", "balasana-1.jpg", "vrksasana-1.jpg"):
        result = _test_one(name)
        if result["ok"] or "found" not in result["message"].lower() and "Looked for" not in result["message"]:
            return result  # worked, or a connection problem that more files won't change
    return result


def _test_one(name):
    s = settings()
    if not configured():
        missing = [k for k, v in (("endpoint", s["endpoint"]), ("bucket", s["bucket"]), ("access key", s["key"]),
                                  ("secret key", s["secret"])) if not v]
        return {"ok": False, "message": "Not set up yet. Missing: " + ", ".join(missing) + "."}
    where = f"bucket '{s['bucket']}', folder '{s['prefix']}'"
    try:
        import boto3  # noqa: F401
    except ImportError:
        return {"ok": False, "message": "The storage library (boto3) isn't installed in this add-on image."}
    path = os.path.join(CACHE_DIR, name)
    try:
        if os.path.exists(path):
            os.remove(path)  # test against the bucket, not the cache
        get(name)
        return {"ok": True, "message": f"Working: fetched {name} from {where}."}
    except FileNotFoundError:
        msg = _HINTS["NoSuchKey"] + f" Looked for {s['prefix']}/{name} in {where}."
        try:  # show what IS there, to spot a missing file or an extra subfolder
            listing = _s3(s).list_objects_v2(Bucket=s["bucket"], Prefix=s["prefix"] + "/", MaxKeys=1000)
            keys = [o["Key"] for o in listing.get("Contents", [])]
            jpgs = [k for k in keys if k.endswith(".jpg")]
            direct = [k for k in jpgs if "/" not in k[len(s["prefix"]) + 1:]]
            if not keys:
                msg += " Nothing at all was found in that folder."
            else:
                msg += f" Found {len(jpgs)} .jpg files under it, {len(direct)} directly inside (expected 213)."
                nested = [k for k in jpgs if k not in direct]
                if nested:
                    msg += f" Some are in a subfolder, e.g. {nested[0]}."
                elif direct:
                    msg += f" Example: {direct[0]}."
        except Exception:
            msg += " (The key can't list the folder, so I can't show what's inside.)"
        return {"ok": False, "message": msg}
    except RuntimeError as e:
        code = str(e)
        return {"ok": False, "message": _HINTS.get(code, f"The storage service said: {code}.") + f" ({where})"}
    except Exception as e:
        return {"ok": False, "message": f"Couldn't reach the endpoint: {type(e).__name__}. Check the endpoint address."}


def get(name):
    """Path of the cached picture, fetching it first if needed. Raises FileNotFoundError / RuntimeError."""
    if not NAME_RE.match(name):
        raise FileNotFoundError(name)
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path):
        return path
    s = settings()
    if not configured():
        raise RuntimeError("the bucket key isn't set in the add-on's Configuration tab")
    client = _s3(s)
    try:
        body = client.get_object(Bucket=s["bucket"], Key=f"{s['prefix']}/{name}")["Body"].read()
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError(name)
        raise RuntimeError(code or str(e)[:120])
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, path)
    return path
