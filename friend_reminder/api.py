"""Add-on web server: the phone-first UI in static/ plus the JSON API behind it. Served through Home Assistant
ingress under a per-install path prefix, so the page only uses relative URLs (fetch("api/state"))."""
import datetime
import ipaddress
import json
import os
import re
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import ai
import config
import db
import friends
import ha
import nudger
import ranking
import vcard

HERE = os.path.dirname(os.path.abspath(__file__))


def _version():
    try:
        with open(os.path.join(HERE, "config.yaml")) as f:
            return re.search(r'^version:\s*"?([^"\n]+)"?', f.read(), re.M).group(1)
    except Exception:
        return "dev"


VERSION = _version()

db.init_db()
app = FastAPI(title="Friend Reminder", docs_url=None, redoc_url=None, openapi_url=None)

# Only Home Assistant's ingress proxy (172.30.32.2, already logged in to HA) may talk to the add-on.
# Outside Home Assistant (local development) everything is allowed.
INGRESS = ipaddress.ip_address("172.30.32.2")
MAX_BODY = 1_000_000
MAX_VCF = 15_000_000        # a whole address book; photos are stripped by the page before upload


@app.middleware("http")
async def only_home_assistant(request: Request, call_next):
    if os.getenv("SUPERVISOR_TOKEN"):
        try:
            ok = ipaddress.ip_address(request.client.host) == INGRESS
        except Exception:
            ok = False
        if not ok:
            return JSONResponse({"detail": "Open Friend Reminder from Home Assistant."}, status_code=403)
    limit = {"/api/import/vcf": MAX_VCF + 1000, "/api/import/save": 4 * MAX_BODY}.get(request.url.path, MAX_BODY)
    if int(request.headers.get("content-length") or 0) > limit:
        return JSONResponse({"detail": "That is too much at once."}, status_code=413)
    return await call_next(request)


class NoCacheStatic(StaticFiles):
    """ETag revalidation (a cheap 304) so phones pick up new JS right after an add-on update."""
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-cache"
        return r


app.mount("/static", NoCacheStatic(directory=os.path.join(HERE, "static")), name="static")


@app.get("/")
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as f:
        html = f.read().replace("__V__", VERSION)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- input checks

def _text(v):
    """Stripped text without lone surrogates (half an emoji), which SQLite cannot store."""
    return str(v).encode("utf-8", "replace").decode("utf-8").strip()


def _clean(v):
    v = _text(v) if v is not None else None
    return v or None


def _check_date(v):
    v = _clean(v)
    if v is None:
        return None
    try:
        d = datetime.date.fromisoformat(v)
    except ValueError:
        raise ValueError("Dates look like 2026-10-16.")
    if d > datetime.date.today():
        raise ValueError("That date is in the future.")
    return d.isoformat()


def _check_birthday(v):
    v = _clean(v)
    if v is None:
        return None
    if not ranking.parse_birthday(v) or not re.fullmatch(r"(\d{4}-)?\d{2}-\d{2}", v):
        raise ValueError("Birthdays look like 03-14, or 1990-03-14 with the year.")
    return v


def _check_tier(v):
    if v not in ranking.TIERS:
        raise ValueError("Tier is close, good or casual.")
    return v


class Checked(BaseModel):
    """Shared clean-up and checks; each applies only to the fields a model has."""
    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def strip_name(cls, v):
        return _text(v) if v is not None else None

    @field_validator("phone", "email", mode="before", check_fields=False)
    @classmethod
    def clean_optional(cls, v):
        return _clean(v)

    @field_validator("notes", mode="before", check_fields=False)
    @classmethod
    def clean_notes(cls, v):
        return _text(v or "")

    @field_validator("tier", check_fields=False)
    @classmethod
    def check_tier(cls, v):
        return v if v is None else _check_tier(v)

    @field_validator("last_contact", "date", mode="before", check_fields=False)
    @classmethod
    def check_date(cls, v):
        return _check_date(v)

    @field_validator("birthday", mode="before", check_fields=False)
    @classmethod
    def check_birthday(cls, v):
        return _check_birthday(v)


class FriendIn(Checked):
    name: str = Field(min_length=1, max_length=80)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=120)
    tier: str = "good"
    interval_days: Optional[int] = Field(None, ge=1, le=730)
    last_contact: Optional[str] = None
    birthday: Optional[str] = None
    notes: str = Field("", max_length=2000)


class FriendPatch(Checked):
    """Only the fields sent are changed; send null to clear an optional field."""
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=120)
    tier: Optional[str] = None
    interval_days: Optional[int] = Field(None, ge=1, le=730)
    last_contact: Optional[str] = None
    birthday: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)


class NewFriends(BaseModel):
    friends: List[FriendIn] = Field(min_length=1, max_length=500)


class DoneIn(Checked):
    date: Optional[str] = None

class VcfIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_VCF)


class Contact(Checked):
    name: str = Field(min_length=1, max_length=80)
    phone: Optional[str] = Field(None, max_length=40)


class ImportSave(BaseModel):
    friends: List[FriendIn] = Field(default_factory=list, max_length=500)
    ignore: List[Contact] = Field(default_factory=list, max_length=vcard.MAX_CONTACTS)


class Diag(BaseModel):
    report: dict


FriendId = Annotated[int, Path(ge=-2**62, le=2**62)]   # SQLite integers are 64-bit; bigger ids are a clean 422, not a 500


def _found(ok):
    if not ok:
        raise HTTPException(404, "No such friend.")


# ---------------------------------------------------------------- state

@app.get("/api/state")
def state():
    opts = config.options()
    ranked = friends.ranked()
    service = ha.notify_service()
    return {
        "version": VERSION,
        "today": friends.today().isoformat(),
        "friends": ranked,
        "due": sum(1 for f in ranked if f["birthday_today"] or (f["due"] and not f["snoozed"])),
        "tiers": ranking.TIERS,
        "snooze_days": ranking.SNOOZE_DAYS,
        "settings": {
            "in_home_assistant": ha.available(),
            "notify_service": service,
            "phones": [] if service else ha.phones_seen(),
            "nudge_time": nudger.nudge_time().strftime("%H:%M"),
            "nudges_per_day": opts["nudges_per_day"],
            "claude": ai.available(),
            "model": opts["model"],
        },
        "panel_url": ha.panel_url() if ha.available() else None,
        "last_nudge": db.get_setting("last_nudge"),
    }


# ---------------------------------------------------------------- friends

@app.post("/api/friends")
def add_friends(req: NewFriends):
    return friends.add_many([f.model_dump() for f in req.friends])


@app.put("/api/friends/{fid}")
def edit_friend(fid: FriendId, req: FriendPatch):
    changes = req.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise HTTPException(422, "A friend needs a name.")
    if "tier" in changes and changes["tier"] is None:
        raise HTTPException(422, "Tier is close, good or casual.")
    _found(friends.update(fid, changes))
    return friends.assessed(fid)


@app.delete("/api/friends/{fid}")
def delete_friend(fid: FriendId):
    _found(friends.delete(fid))
    return {"ok": True}


@app.post("/api/friends/{fid}/done")
def done(fid: FriendId, req: Optional[DoneIn] = None):
    _found(friends.done(fid, req.date if req else None))
    return friends.assessed(fid)


@app.post("/api/friends/{fid}/snooze")
def snooze(fid: FriendId):
    _found(friends.snooze(fid))
    return friends.assessed(fid)


@app.post("/api/friends/{fid}/skip")
def skip(fid: FriendId):
    _found(friends.skip(fid))
    return friends.assessed(fid)


@app.post("/api/friends/{fid}/opener")
def draft_opener(fid: FriendId):
    f = friends.assessed(fid)
    _found(f)
    try:
        text = ai.opener(f)
    except Exception as e:
        raise HTTPException(503 if isinstance(e, ai.NotConfigured) else 502, ai.describe_error(e))
    friends.save_opener(fid, text)
    return {"opener": text}


@app.post("/api/import/vcf")
def import_vcf(req: VcfIn):
    """Reads a contacts file and lists who is in it (nothing is saved; the page then adds the ones ticked)."""
    contacts = vcard.parse(req.text)
    if not contacts:
        raise HTTPException(422, "No contacts found in that file. Export a .vcf (vCard) file from the Contacts app "
                                 "or Google Contacts and try again.")
    for c, status in zip(contacts, friends.import_status(contacts)):
        c["on_list"], c["ignored"] = status == "friend", status == "ignored"
    return {"contacts": contacts}


@app.post("/api/import/save")
def save_import(req: ImportSave):
    """Adds the contacts given a closeness and remembers the ones left on Don't remind."""
    if not req.friends and not req.ignore:
        raise HTTPException(422, "Nothing to save.")
    return friends.save_import([f.model_dump() for f in req.friends], [c.model_dump() for c in req.ignore])


# ---------------------------------------------------------------- nudges

@app.post("/api/nudge/test")
def test_nudge(fid: Optional[int] = None):
    try:
        f = nudger.test(fid)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, str(e)[:300] or type(e).__name__)
    return {"sent_to": ha.notify_service(), "friend": f["name"]}


# ---------------------------------------------------------------- Contact Picker check

@app.post("/api/diag")
def save_diag(req: Diag):
    """What the phone's browser reported about the Contact Picker (kept so it can be read back later)."""
    raw = json.dumps(req.report)[:4000]
    db.set_setting("picker_diag", {"at": datetime.datetime.now().isoformat(timespec="seconds"), "report": json.loads(raw) if len(raw) < 4000 else raw})
    print(f"Contact Picker check: {raw[:500]}", flush=True)
    return {"ok": True}


@app.get("/api/diag")
def read_diag():
    return db.get_setting("picker_diag") or {}


nudger.start()
