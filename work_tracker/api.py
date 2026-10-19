"""Add-on web server: JSON API for hours and tasks (the phone UI in static/ comes next). Served through Home
Assistant ingress under a per-install path prefix, so the page only uses relative URLs (fetch("api/state"))."""
import datetime
import ipaddress
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import db
import ha
import hours
import nudger
import tasks

HERE = os.path.dirname(os.path.abspath(__file__))


def _version():
    try:
        with open(os.path.join(HERE, "config.yaml")) as f:
            return re.search(r'^version:\s*"?([^"\n]+)"?', f.read(), re.M).group(1)
    except Exception:
        return "dev"


VERSION = _version()

db.init_db()
app = FastAPI(title="Work Tracker", docs_url=None, redoc_url=None, openapi_url=None)

# Only Home Assistant's ingress proxy (172.30.32.2, already logged in to HA) may talk to the add-on.
INGRESS = ipaddress.ip_address("172.30.32.2")
MAX_BODY = 1_000_000


@app.middleware("http")
async def only_home_assistant(request: Request, call_next):
    if os.getenv("SUPERVISOR_TOKEN"):
        try:
            ok = ipaddress.ip_address(request.client.host) == INGRESS
        except Exception:
            ok = False
        if not ok:
            return JSONResponse({"detail": "Open Work Tracker from Home Assistant."}, status_code=403)
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return JSONResponse({"detail": "That is too much at once."}, status_code=413)
    return await call_next(request)


@app.exception_handler(ValueError)
async def bad_value(request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


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


def _day(s, default):
    try:
        return datetime.date.fromisoformat(s) if s else default
    except ValueError:
        raise HTTPException(400, "Dates look like 2026-10-19.")


def _found(x):
    if not x:
        raise HTTPException(404, "Not found.")
    return x


class TimerStart(BaseModel):
    client: str
    case_no: str = ""
    note: str = ""
    billable: bool = True


class EntryIn(BaseModel):
    client: str
    case_no: str = ""
    note: str = ""
    date: str
    minutes: int
    start_time: str = "00:00"
    billable: bool = True


class EntryPatch(BaseModel):
    client: Optional[str] = None
    case_no: Optional[str] = None
    note: Optional[str] = None
    billable: Optional[bool] = None
    start: Optional[str] = None
    end: Optional[str] = None


class TaskIn(BaseModel):
    title: str
    due: Optional[str] = None
    client: str = ""
    case_no: str = ""


class TaskPatch(BaseModel):
    title: Optional[str] = None
    due: Optional[str] = None
    client: Optional[str] = None
    case_no: Optional[str] = None


def _fields(m):
    return m.model_dump(exclude_unset=True)


@app.get("/api/state")
def state():
    return {"version": VERSION, "now": hours.now().strftime(hours.FMT), "running": hours.running(),
            "totals": hours.totals(), "recent": hours.recent_clients(),
            "tasks": tasks.listing(), "phone": ha.notify_service()}


@app.post("/api/timer/start")
def timer_start(body: TimerStart):
    started, stopped = hours.start(body.client, body.case_no, body.note, body.billable)
    return {"running": started, "stopped": stopped}


@app.post("/api/timer/stop")
def timer_stop():
    return {"stopped": hours.stop()}


@app.get("/api/entries")
def entries_list(frm: Optional[str] = None, to: Optional[str] = None):
    t = hours.today()
    return hours.entries(_day(frm, t), _day(to, t))


@app.post("/api/entries")
def entries_add(body: EntryIn):
    _day(body.date, None)
    return hours.add_manual(body.client, body.case_no, body.note, body.date, body.minutes,
                            body.start_time, body.billable)


@app.patch("/api/entries/{eid}")
def entries_patch(eid: int, body: EntryPatch):
    return _found(hours.update(eid, **_fields(body)))


@app.delete("/api/entries/{eid}")
def entries_delete(eid: int):
    _found(hours.delete(eid))
    return {"ok": True}


@app.get("/api/totals")
def totals(day: Optional[str] = None):
    return hours.totals(_day(day, hours.today()))


@app.get("/api/export.csv")
def export(frm: Optional[str] = None, to: Optional[str] = None):
    t = hours.today()
    ws = hours.week_start(t)
    data = hours.export_csv(_day(frm, ws), _day(to, ws + datetime.timedelta(days=6)))
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="work_tracker.csv"'})


@app.get("/api/tasks")
def tasks_list(done: bool = False):
    return tasks.listing(done)


@app.post("/api/tasks")
def tasks_add(body: TaskIn):
    return tasks.add(body.title, body.due, body.client, body.case_no)


@app.patch("/api/tasks/{tid}")
def tasks_patch(tid: int, body: TaskPatch):
    return _found(tasks.update(tid, **_fields(body)))


@app.post("/api/tasks/{tid}/done")
def tasks_done(tid: int, undo: bool = False):
    _found(tasks.done(tid, undo))
    return {"ok": True}


@app.post("/api/tasks/{tid}/snooze")
def tasks_snooze(tid: int):
    _found(tasks.snooze(tid))
    return {"ok": True}


@app.delete("/api/tasks/{tid}")
def tasks_delete(tid: int):
    _found(tasks.delete(tid))
    return {"ok": True}


@app.post("/api/test-nudge")
def test_nudge():
    try:
        nudger.test()
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


nudger.start()
