"""Add-on web server: the briefing page in static/ plus the JSON behind it. Served through Home Assistant ingress under a
per-install path prefix, so the page only uses relative URLs (fetch("api/briefing"))."""
import ipaddress
import os
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import sections

HERE = os.path.dirname(os.path.abspath(__file__))


def _version():
    try:
        with open(os.path.join(HERE, "config.yaml")) as f:
            return re.search(r'^version:\s*"?([^"\n]+)"?', f.read(), re.M).group(1)
    except Exception:
        return "dev"


VERSION = _version()

app = FastAPI(title="Daily Briefing", docs_url=None, redoc_url=None, openapi_url=None)

# Only Home Assistant's ingress proxy (172.30.32.2, already logged in to HA) may talk to the add-on.
# Outside Home Assistant (local development) everything is allowed.
INGRESS = ipaddress.ip_address("172.30.32.2")


@app.middleware("http")
async def only_home_assistant(request: Request, call_next):
    if os.getenv("SUPERVISOR_TOKEN"):
        try:
            ok = ipaddress.ip_address(request.client.host) == INGRESS
        except Exception:
            ok = False
        if not ok:
            return JSONResponse({"detail": "Open Daily Briefing from Home Assistant."}, status_code=403)
    return await call_next(request)


class NoCacheStatic(StaticFiles):
    """ETag revalidation (a cheap 304) so the page picks up new JS right after an add-on update."""
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


@app.get("/api/briefing")
def briefing():
    """The latest briefing (built by the background loop); built now when the loop has not run yet."""
    data = sections.latest() or sections.refresh()
    return JSONResponse({**data, "version": VERSION}, headers={"Cache-Control": "no-store"})


@app.get("/api/dashboard.yaml")
def dashboard():
    """The ready-made TV dashboard, to paste into a Home Assistant dashboard's raw configuration editor."""
    with open(os.path.join(HERE, "dashboard.yaml"), encoding="utf-8") as f:
        return PlainTextResponse(f.read())


sections.start()
