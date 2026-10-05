"""FastAPI Stage Analysis PWA — dry_run assistant; PIN-gated mutations."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastapi.exceptions import RequestValidationError

from . import bot_bridge, broker_keys
from .config import APP_ROOT, pin_matches

STATIC = APP_ROOT / "static"

app = FastAPI(title="Stage Analysis", version="1.0.1", docs_url=None, redoc_url=None)


class NoStoreAPIMiddleware(BaseHTTPMiddleware):
    """Prevent browsers / proxies from caching API JSON (daily tickets must refresh)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoStoreAPIMiddleware)


@app.exception_handler(RequestValidationError)
async def _hide_validation_body(request: Request, exc: RequestValidationError):
    """Do not echo request bodies (broker secrets) in 422 responses."""
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})



class BrokerKeysBody(BaseModel):
    adapter: str = Field(..., min_length=1, max_length=64)
    mode: str = Field(..., min_length=1, max_length=16)
    api_key: str = Field(default="", max_length=4096)
    api_secret: str = Field(default="", max_length=4096)


class TicketBody(BaseModel):
    ticket_id: str = Field(..., min_length=3)


def _require_pin(
    x_app_pin: Optional[str] = None,
    pin_query: Optional[str] = None,
) -> None:
    provided = x_app_pin or pin_query
    if not pin_matches(provided):
        raise HTTPException(status_code=401, detail="Invalid or missing PIN")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "stage-pwa",
        "dry_run_policy": "never_flip",
    }


@app.get("/api/dashboard")
def dashboard(
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
    pin: Optional[str] = Query(default=None),
):
    _require_pin(x_app_pin, pin)
    try:
        return bot_bridge.build_dashboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/ticket/{ticket_id}")
def ticket_detail(
    ticket_id: str,
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
    pin: Optional[str] = Query(default=None),
):
    _require_pin(x_app_pin, pin)
    try:
        ticket, data, path = bot_bridge.find_ticket(ticket_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="ticket not found") from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    approved = ticket_id in bot_bridge.approved_ticket_ids()
    return {
        "ticket": ticket,
        "approved": approved,
        "manual_entry_preview": bot_bridge.manual_entry_preview(ticket),
        "dry_run": bool(data.get("dry_run", True)),
        "proposed_path": str(path),
    }


@app.post("/api/approve")
def approve(
    body: TicketBody,
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
):
    _require_pin(x_app_pin, None)
    result = bot_bridge.run_bot("approve", body.ticket_id)
    if not result["ok"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "approve failed",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"],
            },
        )
    return {
        "ok": True,
        "ticket_id": body.ticket_id,
        "stdout": result["stdout"],
        "approved": True,
    }


@app.post("/api/execute")
def execute(
    body: TicketBody,
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
):
    """Calls bot.py execute — with dry_run true this only prints manual entry."""
    _require_pin(x_app_pin, None)
    result = bot_bridge.run_bot("execute", body.ticket_id)
    return {
        "ok": result["ok"],
        "ticket_id": body.ticket_id,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "dry_run": True,
        "note": "dry_run stays true — no live Schwab order from this PWA",
    }


@app.get("/api/positions-stage")
def positions_stage(
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
    pin: Optional[str] = Query(default=None),
):
    _require_pin(x_app_pin, pin)
    try:
        return bot_bridge.load_positions_stage()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/beta")
def beta(
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
    pin: Optional[str] = Query(default=None),
):
    _require_pin(x_app_pin, pin)
    try:
        return bot_bridge.load_positions_beta()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e



@app.get("/api/broker-keys")
def broker_keys_status(
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
    pin: Optional[str] = Query(default=None),
):
    """Masked status only. Never returns the API secret or the full API key."""
    _require_pin(x_app_pin, pin)
    return broker_keys.public_status()


@app.post("/api/broker-keys")
def broker_keys_save(
    body: BrokerKeysBody,
    x_app_pin: Optional[str] = Header(default=None, alias="X-App-Pin"),
):
    """Store keys locally. Does not place orders or flip dry_run / trading."""
    _require_pin(x_app_pin, None)
    try:
        return broker_keys.save_keys(body.adapter, body.mode, body.api_key, body.api_secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/dashboard")
def desktop_dashboard():
    return FileResponse(STATIC / "dashboard.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(
        STATIC / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/sw.js")
def service_worker():
    # Avoid stale SW registration; browsers revalidate often with no-cache.
    return FileResponse(
        STATIC / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"},
    )


@app.get("/icon.svg")
def icon():
    return FileResponse(STATIC / "icon.svg", media_type="image/svg+xml")


# Mount static last so API routes win; also expose /static/*
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
