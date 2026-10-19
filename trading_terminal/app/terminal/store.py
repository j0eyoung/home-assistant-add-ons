"""Where collected market data lives: an S3-compatible bucket (Cloudflare R2, Backblaze B2, a NAS
running MinIO/TrueNAS/Synology...) or a folder (e.g. Home Assistant network storage at /share).

Settings (environment / add-on options):
  STORE_TYPE   off | s3 | folder          (off by default: nothing is collected)
  STORE_PATH   folder path for "folder"   (e.g. /share/trading_terminal)
  S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY, S3_PREFIX (optional), S3_REGION (optional)

Data is stored as Parquet files (compressed, column-oriented) under keys like prices/daily/AAPL.parquet.
"""
from __future__ import annotations

import io
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd

CACHE_SECONDS = 300  # recent reads are kept in memory so a chart doesn't re-download its file
_mem: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()


def kind() -> str:
    return os.getenv("STORE_TYPE", "off").strip().lower() or "off"


def enabled() -> bool:
    return kind() in ("s3", "folder") and _configured()


def _configured() -> bool:
    if kind() == "folder":
        return bool(os.getenv("STORE_PATH", "").strip())
    if kind() == "s3":
        return all(os.getenv(k, "").strip() for k in ("S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY"))
    return False


def why_off() -> str:
    """Plain reason collection is off, naming the missing settings (never their values)."""
    k = kind()
    if k == "off":
        return "store_type is 'off'; set it to 's3' or 'folder'"
    if k == "folder":
        return "store_path is empty" if not os.getenv("STORE_PATH", "").strip() else "folder settings look fine"
    if k == "s3":
        missing = [k.lower() for k in ("S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY")
                   if not os.getenv(k, "").strip()]
        return f"missing: {', '.join(missing)}" if missing else "s3 settings look complete"
    return f"unknown store_type '{k}'"


def describe() -> str:
    if kind() == "folder":
        return f"folder {os.getenv('STORE_PATH')}"
    if kind() == "s3":
        host = os.getenv("S3_ENDPOINT", "").split("//")[-1].split("/")[0]
        return f"bucket '{os.getenv('S3_BUCKET')}' at {host}"
    return "off"


class _Folder:
    def __init__(self, root: str):
        self.root = Path(root)

    def get(self, key: str) -> bytes | None:
        p = self.root / key
        return p.read_bytes() if p.exists() else None

    def put(self, key: str, data: bytes) -> None:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def list(self, prefix: str) -> list[tuple[str, int]]:
        base = self.root / prefix
        if not base.exists():
            return []
        return [(str(p.relative_to(self.root)).replace("\\", "/"), p.stat().st_size)
                for p in base.rglob("*") if p.is_file() and not p.name.endswith(".tmp")]


class _S3:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = os.environ["S3_BUCKET"].strip()
        self.prefix = os.getenv("S3_PREFIX", "trading-terminal/").strip().lstrip("/")
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"
        self.client = boto3.client(
            "s3", endpoint_url=os.environ["S3_ENDPOINT"].strip(),
            aws_access_key_id=os.environ["S3_ACCESS_KEY"].strip(),
            aws_secret_access_key=os.environ["S3_SECRET_KEY"].strip(),
            region_name=os.getenv("S3_REGION", "auto").strip() or "auto",
            # boto3 >= 1.36 adds checksum headers to every upload by default; S3-compatible services
            # such as Backblaze B2 can reject them, so only send them when an operation requires it.
            config=Config(retries={"max_attempts": 4, "mode": "standard"}, connect_timeout=10, read_timeout=60,
                          request_checksum_calculation="when_required",
                          response_checksum_validation="when_required"),
        )

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self.prefix + key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            if getattr(e, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self.prefix + key, Body=data)

    def list(self, prefix: str) -> list[tuple[str, int]]:
        out, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": self.prefix + prefix}
            if token:
                kw["ContinuationToken"] = token
            r = self.client.list_objects_v2(**kw)
            out += [(o["Key"][len(self.prefix):], o["Size"]) for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return out
            token = r["NextContinuationToken"]


@lru_cache(maxsize=1)
def _backend():
    return _Folder(os.environ["STORE_PATH"].strip()) if kind() == "folder" else _S3()


def read(key: str) -> pd.DataFrame | None:
    """A stored table, or None if missing / storage is off."""
    if not enabled():
        return None
    with _lock:
        hit = _mem.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1].copy() if hit[1] is not None else None
    raw = _backend().get(key)
    df = pd.read_parquet(io.BytesIO(raw)) if raw else None
    with _lock:
        _mem[key] = (time.time(), df)
    return df.copy() if df is not None else None


def write(key: str, df: pd.DataFrame) -> int:
    """Save a table; returns its size in bytes."""
    buf = io.BytesIO()
    df.to_parquet(buf, compression="zstd")
    data = buf.getvalue()
    _backend().put(key, data)
    with _lock:
        _mem[key] = (time.time(), df.copy())
    return len(data)


def read_json(key: str) -> dict:
    import json

    if not enabled():
        return {}
    raw = _backend().get(key)
    return json.loads(raw) if raw else {}


def write_json(key: str, value: dict) -> None:
    import json

    _backend().put(key, json.dumps(value, indent=1, default=str).encode())


def usage() -> dict[str, tuple[int, int]]:
    """{top-level folder: (files, bytes)}."""
    if not enabled():
        return {}
    out: dict[str, list[int]] = {}
    for key, size in _backend().list(""):
        top = "/".join(key.split("/")[:2]) if key.startswith("prices/") else key.split("/")[0]
        n = out.setdefault(top, [0, 0])
        n[0] += 1
        n[1] += size
    return {k: (v[0], v[1]) for k, v in sorted(out.items())}
