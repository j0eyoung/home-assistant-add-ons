"""Receipt and photo files for appliances and shutoffs. The bytes go to the user's S3-compatible bucket (Cloudflare R2,
same s3_* options as the Workout and Meal Planner add-ons), never to the Green's disk; SQLite keeps only the metadata
and the object key."""
import datetime
import re
import uuid

import config
import db

MAX_BYTES = 10_000_000
OWNERS = ("appliance", "shutoff")
_client = {"c": None, "sig": None}


class NotConfigured(RuntimeError):
    pass


def settings():
    o = config.options()
    return {"endpoint": o["s3_endpoint"], "bucket": o["s3_bucket"], "key": o["s3_access_key"],
            "secret": o["s3_secret_key"], "region": o["s3_region"] or "auto",
            "prefix": (o["s3_prefix"] or "home/receipts").strip("/")}


def bucket_ready():
    s = settings()
    return bool(s["endpoint"] and s["bucket"] and s["key"] and s["secret"])


def _s3():
    s = settings()
    sig = (s["endpoint"], s["key"], s["secret"], s["region"])
    if _client["c"] is None or _client["sig"] != sig:
        import boto3
        from botocore.config import Config
        _client["c"] = boto3.client(
            "s3", endpoint_url=s["endpoint"], aws_access_key_id=s["key"], aws_secret_access_key=s["secret"],
            region_name=s["region"],
            # boto3 checksum headers can be refused by some S3-compatible stores (same as the other add-ons)
            config=Config(retries={"max_attempts": 4, "mode": "standard"}, connect_timeout=10, read_timeout=60,
                          request_checksum_calculation="when_required", response_checksum_validation="when_required"))
        _client["sig"] = sig
    return _client["c"]


def _ok_type(content_type):
    return content_type == "application/pdf" or content_type.startswith("image/")


def save(owner_type, owner_id, filename, content_type, data):
    if owner_type not in OWNERS:
        raise ValueError("Unknown owner.")
    if not _ok_type(content_type):
        raise ValueError("Upload a photo or a PDF.")
    if not data or len(data) > MAX_BYTES:
        raise ValueError(f"The file must be 1 byte to {MAX_BYTES // 1_000_000} MB.")
    if not bucket_ready():
        raise NotConfigured("Receipt storage is not set up. Fill in the s3_* options in the add-on's Configuration tab.")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "file")[-80:]
    key = f"{settings()['prefix']}/{owner_type}/{owner_id}/{uuid.uuid4().hex[:12]}-{safe}"
    _s3().put_object(Bucket=settings()["bucket"], Key=key, Body=data, ContentType=content_type)
    aid = db.run("INSERT INTO attachments(owner_type,owner_id,filename,content_type,size,s3_key,added) VALUES(?,?,?,?,?,?,?)",
                 (owner_type, owner_id, safe, content_type, len(data), key, datetime.date.today().isoformat()))
    return meta(aid)


def meta(attachment_id):
    r = db.rows("SELECT id, owner_type, owner_id, filename, content_type, size, added FROM attachments WHERE id=?",
                (attachment_id,))
    return r[0] if r else None


def list_for(owner_type, owner_id):
    return db.rows("SELECT id, filename, content_type, size, added FROM attachments WHERE owner_type=? AND owner_id=? "
                   "ORDER BY id", (owner_type, owner_id))


def fetch(attachment_id):
    """(metadata, bytes) from the bucket; None when there is no such file."""
    r = db.rows("SELECT * FROM attachments WHERE id=?", (attachment_id,))
    if not r:
        return None
    if not bucket_ready():
        raise NotConfigured("Receipt storage is not set up.")
    body = _s3().get_object(Bucket=settings()["bucket"], Key=r[0]["s3_key"])["Body"].read()
    return r[0], body


def remove(attachment_id):
    r = db.rows("SELECT s3_key FROM attachments WHERE id=?", (attachment_id,))
    if not r:
        return False
    if bucket_ready():
        try:
            _s3().delete_object(Bucket=settings()["bucket"], Key=r[0]["s3_key"])
        except Exception as e:
            print(f"Could not delete {r[0]['s3_key']} from the bucket: {e}", flush=True)
    return db.changed("DELETE FROM attachments WHERE id=?", (attachment_id,)) > 0
