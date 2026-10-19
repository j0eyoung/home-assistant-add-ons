"""Add-on web server: JSON API (v1 backend) plus the static page. Served through Home Assistant ingress under a
per-install path prefix, so the page only uses relative URLs (fetch("api/state"))."""
import datetime
import ipaddress
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import appliances
import db
import files
import ha
import ics
import publish
import reminders
import tasks
import toner

HERE = os.path.dirname(os.path.abspath(__file__))


def _version():
    try:
        with open(os.path.join(HERE, "config.yaml")) as f:
            return re.search(r'^version:\s*"?([^"\n]+)"?', f.read(), re.M).group(1)
    except Exception:
        return "dev"


VERSION = _version()

db.init_db()
tasks.seed_presets()
app = FastAPI(title="Home Maintenance Log", docs_url=None, redoc_url=None, openapi_url=None)

# Only Home Assistant's ingress proxy (172.30.32.2, already logged in to HA) may talk to the add-on.
INGRESS = ipaddress.ip_address("172.30.32.2")
MAX_BODY = 1_000_000
MAX_UPLOAD = files.MAX_BYTES + 100_000


@app.middleware("http")
async def only_home_assistant(request: Request, call_next):
    if os.getenv("SUPERVISOR_TOKEN"):
        try:
            ok = ipaddress.ip_address(request.client.host) == INGRESS
        except Exception:
            ok = False
        if not ok:
            return JSONResponse({"detail": "Open Home Maintenance from Home Assistant."}, status_code=403)
    limit = MAX_UPLOAD if request.url.path.endswith("/files") else MAX_BODY
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


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "static", "index.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read().replace("__V__", VERSION), headers={"Cache-Control": "no-cache"})


def _date(v):
    if v:
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            raise HTTPException(422, "Dates look like 2026-10-19.")
    return v


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    interval_value: int = Field(ge=1, le=1200)
    interval_unit: str = "months"
    last_done: Optional[str] = None
    notes: str = Field("", max_length=2000)
    appliance_id: Optional[int] = None
    active_months: Optional[str] = Field(None, max_length=40)


class TaskPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    interval_value: Optional[int] = Field(None, ge=1, le=1200)
    interval_unit: Optional[str] = None
    last_done: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)
    appliance_id: Optional[int] = None
    active_months: Optional[str] = Field(None, max_length=40)


class DoneIn(BaseModel):
    note: str = Field("", max_length=2000)
    cost: Optional[float] = Field(None, ge=0)
    parts: str = Field("", max_length=500)
    on: Optional[str] = None


class SnoozeIn(BaseModel):
    days: int = Field(tasks.SNOOZE_DAYS, ge=1, le=365)


class ApplianceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brand: Optional[str] = Field(None, max_length=120)
    model: Optional[str] = Field(None, max_length=120)
    serial: Optional[str] = Field(None, max_length=120)
    purchase_date: Optional[str] = None
    warranty_end: Optional[str] = None
    store: Optional[str] = Field(None, max_length=120)
    price: Optional[float] = Field(None, ge=0)
    lifespan_years: Optional[float] = Field(None, gt=0, le=100)
    notes: Optional[str] = Field(None, max_length=2000)


class AppliancePatch(ApplianceIn):
    name: Optional[str] = Field(None, min_length=1, max_length=120)


class ShutoffIn(BaseModel):
    kind: str = "water"
    name: str = Field(min_length=1, max_length=120)
    location: str = Field("", max_length=500)
    notes: str = Field("", max_length=2000)


class ShutoffPatch(BaseModel):
    kind: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    location: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)


class TonerIn(BaseModel):
    entities: list[str] = Field(max_length=12)
    threshold: Optional[int] = Field(None, ge=1, le=90)
    printer_model: Optional[str] = Field(None, max_length=120)


def _task_or_404(task_id):
    t = tasks.get(task_id)
    if not t:
        raise HTTPException(404, "No such task.")
    return t


def _sync():
    """Pushes the new task states to Home Assistant right away (a failure is only logged)."""
    try:
        publish.sync()
    except Exception as e:
        print(f"Publishing to Home Assistant failed: {e}", flush=True)


@app.get("/api/state")
def state():
    return {"version": VERSION, "tasks": tasks.all_rows(), "toner": toner.status(),
            "appliances": appliances.all_rows(), "shutoffs": appliances.shutoffs(),
            "storage_ready": files.bucket_ready(),
            "phone": bool(ha.notify_service()), "in_home_assistant": ha.available()}


@app.get("/api/presets")
def presets():
    have = {t["name"].lower() for t in tasks.all_rows()}
    return [{"name": n, "interval_value": v, "interval_unit": u, "active_months": m, "added": n.lower() in have}
            for n, v, u, m in tasks.PRESETS]


@app.post("/api/tasks")
def add_task(body: TaskIn):
    _date(body.last_done)
    try:
        t = tasks.add(body.name, body.interval_value, body.interval_unit, body.last_done, body.notes,
                      appliance_id=body.appliance_id, active_months=body.active_months)
    except ValueError as e:
        raise HTTPException(422, str(e))
    _sync()
    return t


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch):
    _task_or_404(task_id)
    fields = body.model_dump(exclude_none=True)
    _date(fields.get("last_done"))
    try:
        t = tasks.update(task_id, **fields)
    except ValueError as e:
        raise HTTPException(422, str(e))
    _sync()
    return t


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    if not tasks.remove(task_id):
        raise HTTPException(404, "No such task.")
    _sync()
    return {"ok": True}


@app.post("/api/tasks/{task_id}/done")
def done_task(task_id: int, body: DoneIn):
    _task_or_404(task_id)
    on = datetime.date.fromisoformat(_date(body.on)) if body.on else None
    t = tasks.done(task_id, body.note, body.cost, on, body.parts)
    _sync()
    return t


@app.post("/api/tasks/{task_id}/snooze")
def snooze_task(task_id: int, body: SnoozeIn):
    _task_or_404(task_id)
    t = tasks.snooze(task_id, body.days)
    _sync()
    return t


@app.get("/api/tasks/{task_id}/history")
def task_history(task_id: int):
    _task_or_404(task_id)
    return tasks.history(task_id)


@app.get("/api/digest")
def digest():
    """What the Monday summary would say."""
    d = tasks.digest()
    return {**d, "message": reminders.digest_message(d)}


@app.get("/api/calendar.ics")
def calendar_ics():
    return Response(ics.calendar(), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="home-maintenance.ics"'})


@app.get("/api/toner")
def toner_status():
    return {"entities": toner.status(), "threshold": toner.setting("threshold"), "printer_model": toner.setting("printer_model")}


@app.put("/api/toner")
def toner_save(body: TonerIn):
    """Saves the picker's choice (kept in the database; it wins over the add-on options)."""
    bad = [e for e in body.entities if not re.fullmatch(r"sensor\.[a-z0-9_]+", e)]
    if bad:
        raise HTTPException(422, f"Not a sensor entity id: {bad[0]}")
    db.set_setting("toner_entities", body.entities)
    if body.threshold is not None:
        db.set_setting("toner_threshold", body.threshold)
    if body.printer_model is not None:
        db.set_setting("toner_printer_model", body.printer_model.strip())
    return toner_status()


@app.post("/api/toner/check")
def toner_check():
    return toner.check()


@app.get("/api/toner/sensors")
def toner_sensors():
    """Every sensor in Home Assistant, for the picker."""
    try:
        return ha.sensors()
    except Exception as e:
        raise HTTPException(502, f"Home Assistant did not answer: {e}")


def _appliance_or_404(appliance_id):
    a = appliances.get(appliance_id)
    if not a:
        raise HTTPException(404, "No such appliance.")
    return a


@app.get("/api/appliances")
def list_appliances():
    return [{**a, "files": files.list_for("appliance", a["id"])} for a in appliances.all_rows()]


@app.post("/api/appliances")
def add_appliance(body: ApplianceIn):
    fields = body.model_dump(exclude={"name"})
    _date(fields.get("purchase_date")), _date(fields.get("warranty_end"))
    return appliances.add(body.name, **fields)


@app.patch("/api/appliances/{appliance_id}")
def patch_appliance(appliance_id: int, body: AppliancePatch):
    _appliance_or_404(appliance_id)
    fields = body.model_dump(exclude_none=True)
    _date(fields.get("purchase_date")), _date(fields.get("warranty_end"))
    return appliances.update(appliance_id, **fields)


@app.delete("/api/appliances/{appliance_id}")
def delete_appliance(appliance_id: int):
    if not appliances.remove(appliance_id):
        raise HTTPException(404, "No such appliance.")
    return {"ok": True}


@app.get("/api/shutoffs")
def list_shutoffs():
    return [{**s, "files": files.list_for("shutoff", s["id"])} for s in appliances.shutoffs()]


@app.post("/api/shutoffs")
def add_shutoff(body: ShutoffIn):
    try:
        return appliances.add_shutoff(body.kind, body.name, body.location, body.notes)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.patch("/api/shutoffs/{shutoff_id}")
def patch_shutoff(shutoff_id: int, body: ShutoffPatch):
    try:
        s = appliances.update_shutoff(shutoff_id, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not s:
        raise HTTPException(404, "No such shutoff.")
    return s


@app.delete("/api/shutoffs/{shutoff_id}")
def delete_shutoff(shutoff_id: int):
    if not appliances.remove_shutoff(shutoff_id):
        raise HTTPException(404, "No such shutoff.")
    return {"ok": True}


async def _upload(owner_type, owner_id, filename, request):
    """The file is the raw request body (the page sends the camera photo or PDF as-is, with its content type)."""
    try:
        return files.save(owner_type, owner_id, filename, (request.headers.get("content-type") or "").split(";")[0].strip(),
                          await request.body())
    except files.NotConfigured as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/appliances/{appliance_id}/files")
async def upload_appliance_file(appliance_id: int, request: Request, filename: str = "receipt"):
    _appliance_or_404(appliance_id)
    return await _upload("appliance", appliance_id, filename, request)


@app.post("/api/shutoffs/{shutoff_id}/files")
async def upload_shutoff_file(shutoff_id: int, request: Request, filename: str = "photo"):
    if not db.rows("SELECT 1 FROM shutoffs WHERE id=?", (shutoff_id,)):
        raise HTTPException(404, "No such shutoff.")
    return await _upload("shutoff", shutoff_id, filename, request)


@app.get("/api/files/{file_id}")
def get_file(file_id: int):
    try:
        found = files.fetch(file_id)
    except files.NotConfigured as e:
        raise HTTPException(409, str(e))
    if not found:
        raise HTTPException(404, "No such file.")
    meta, body = found
    return Response(body, media_type=meta["content_type"],
                    headers={"Content-Disposition": f'inline; filename="{meta["filename"]}"', "Cache-Control": "private, max-age=3600"})


@app.delete("/api/files/{file_id}")
def delete_file(file_id: int):
    if not files.remove(file_id):
        raise HTTPException(404, "No such file.")
    return {"ok": True}


@app.post("/api/test/reminder")
def test_reminder():
    """Sends the most overdue task (or a sample) to the phone now, so the Done / Snooze buttons can be tried."""
    service = ha.notify_service()
    if not service:
        raise HTTPException(409, "No phone found. Set notify_service in the add-on's Configuration tab.")
    rows = tasks.all_rows()
    if not rows:
        raise HTTPException(404, "Add a task first.")
    try:
        ha.send_due(service, rows[0])
    except Exception as e:
        raise HTTPException(502, str(e))
    return rows[0]


reminders.start()
