"""Named watchlists saved in watchlists.json (in the app's data folder). The first run starts
from the WATCHLIST setting."""
from __future__ import annotations

import json

from . import config

PATH = config.DATA_DIR / "watchlists.json"
DEFAULT = "My watchlist"


def _load() -> dict:
    try:
        d = json.loads(PATH.read_text())
        if d.get("lists"):
            return d
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"active": DEFAULT, "lists": {DEFAULT: list(config.WATCHLIST)}}


def _save(d: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    tmp.replace(PATH)


def names() -> list[str]:
    return list(_load()["lists"])


def active() -> str:
    d = _load()
    return d["active"] if d["active"] in d["lists"] else next(iter(d["lists"]))


def symbols(name: str | None = None) -> list[str]:
    d = _load()
    return list(d["lists"].get(name or active(), []))


def everything() -> list[str]:
    """Every symbol on any list, in order, without repeats."""
    return list(dict.fromkeys(s for syms in _load()["lists"].values() for s in syms))


def set_active(name: str) -> None:
    d = _load()
    if name in d["lists"]:
        d["active"] = name
        _save(d)


def add(symbol: str, name: str | None = None) -> None:
    d = _load()
    lst = d["lists"].setdefault(name or active(), [])
    s = symbol.strip().upper()
    if s and s not in lst:
        lst.append(s)
        _save(d)


def remove(symbol: str, name: str | None = None) -> None:
    d = _load()
    lst = d["lists"].get(name or active(), [])
    if symbol in lst:
        lst.remove(symbol)
        _save(d)


def move(symbol: str, step: int, name: str | None = None) -> None:
    d = _load()
    lst = d["lists"].get(name or active(), [])
    if symbol in lst:
        i = lst.index(symbol)
        j = max(0, min(len(lst) - 1, i + step))
        lst.insert(j, lst.pop(i))
        _save(d)


def create(name: str) -> None:
    d = _load()
    name = name.strip()
    if name and name not in d["lists"]:
        d["lists"][name] = []
        d["active"] = name
        _save(d)


def rename(old: str, new: str) -> None:
    d = _load()
    new = new.strip()
    if old in d["lists"] and new and new not in d["lists"]:
        d["lists"] = {new if k == old else k: v for k, v in d["lists"].items()}
        if d["active"] == old:
            d["active"] = new
        _save(d)


def delete(name: str) -> None:
    d = _load()
    if name in d["lists"] and len(d["lists"]) > 1:
        del d["lists"][name]
        if d["active"] == name:
            d["active"] = next(iter(d["lists"]))
        _save(d)
