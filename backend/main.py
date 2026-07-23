"""Entrenador de ciclismo personal — API FastAPI.

Fase 1: autenticación con Garmin Connect + sincronización de datos.
Correr con:  uvicorn backend.main:app --reload
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # antes de importar módulos que leen variables de entorno

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend import garmin_client, metrics, sync  # noqa: E402
from backend.db import (  # noqa: E402
    get_all_settings,
    get_db,
    init_db,
    rows_to_dicts,
    set_setting,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("coach")

app = FastAPI(title="Entrenador de Ciclismo")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ---------------------------------------------------------------- modelos

class LoginBody(BaseModel):
    email: str
    password: str


class MfaBody(BaseModel):
    code: str


class SyncBody(BaseModel):
    days_activities: int = 90
    days_daily: int = 30


class SettingsBody(BaseModel):
    hr_max: int | None = None
    hr_rest: int | None = None
    has_power_meter: bool | None = None
    ftp: int | None = None


# ---------------------------------------------------------------- auth

@app.post("/api/auth/login")
def auth_login(body: LoginBody):
    try:
        garmin_client.login(body.email, body.password)
        return {"status": "ok", "name": garmin_client.profile_name()}
    except garmin_client.MfaRequired:
        return {"status": "mfa_required"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Login falló: {e}")


@app.post("/api/auth/mfa")
def auth_mfa(body: MfaBody):
    try:
        garmin_client.submit_mfa(body.code)
        return {"status": "ok", "name": garmin_client.profile_name()}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Código MFA rechazado: {e}")


@app.post("/api/auth/logout")
def auth_logout():
    garmin_client.logout()
    return {"status": "ok"}


@app.get("/api/status")
def status():
    client = None
    try:
        client = garmin_client.get_client()
    except garmin_client.MfaRequired:
        return {"authenticated": False, "mfa_pending": True}
    except Exception as e:
        logger.warning("Error obteniendo cliente Garmin: %s", e)

    with get_db() as db:
        n_acts = db.execute("SELECT COUNT(*) c FROM activities").fetchone()["c"]
        n_days = db.execute("SELECT COUNT(*) c FROM daily_metrics").fetchone()["c"]
        last = db.execute(
            "SELECT finished_at, ok FROM sync_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return {
        "authenticated": client is not None,
        "name": garmin_client.profile_name() if client else None,
        "activities_in_db": n_acts,
        "days_in_db": n_days,
        "last_sync": dict(last) if last else None,
    }


# ---------------------------------------------------------------- sync

@app.post("/api/sync")
def do_sync(body: SyncBody | None = None):
    body = body or SyncBody()
    try:
        g = garmin_client.get_client()
    except garmin_client.MfaRequired:
        raise HTTPException(status_code=401, detail="Garmin pide código MFA: logueate desde la web")
    if g is None:
        raise HTTPException(status_code=401, detail="No hay sesión de Garmin: logueate primero")
    result = sync.run_full_sync(g, body.days_activities, body.days_daily)
    result["loads"] = metrics.recompute_all_loads()
    return result


# ---------------------------------------------------------------- datos

@app.get("/api/activities")
def list_activities(limit: int = 50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM activities ORDER BY start_time DESC LIMIT ?", (limit,)
        ).fetchall()
    return rows_to_dicts(rows)


@app.get("/api/daily")
def list_daily(days: int = 30):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return rows_to_dicts(rows)


# ---------------------------------------------------------------- ajustes

@app.get("/api/settings")
def read_settings():
    return get_all_settings()


@app.post("/api/settings")
def write_settings(body: SettingsBody):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        if isinstance(value, bool):
            value = "1" if value else "0"
        set_setting(key, value)
    metrics.recompute_all_loads()
    return get_all_settings()


# ------------------------------------------------- métricas de carga

@app.get("/api/metrics/summary")
def metrics_summary():
    return metrics.summary()


@app.get("/api/metrics/load")
def metrics_load(days: int = 120):
    return metrics.daily_load_series(days)


# ---------------------------------------------------------------- frontend

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ------------------------------------------------- sync automático diario

async def _auto_sync_loop():
    interval_h = float(os.getenv("SYNC_INTERVAL_HOURS", "24"))
    if interval_h <= 0:
        return
    while True:
        await asyncio.sleep(interval_h * 3600)
        try:
            g = garmin_client.get_client()
            if g is not None:
                logger.info("Sincronización automática...")
                result = await asyncio.to_thread(sync.run_full_sync, g, 14, 7)
                logger.info("Sync automática terminada: %s", result)
        except Exception as e:
            logger.warning("Sync automática falló: %s", e)


@app.on_event("startup")
async def on_startup():
    init_db()
    asyncio.create_task(_auto_sync_loop())
