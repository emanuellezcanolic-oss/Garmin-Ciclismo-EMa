"""Fase 2: carga de entrenamiento.

- TSS por salida: real si hay potencia + FTP; si no, estimado por FC (TRIMP de
  Banister normalizado a "una hora en umbral = 100 puntos", es decir hrTSS).
- CTL (fitness, constante 42 días), ATL (fatiga, 7 días) y TSB (forma) con el
  modelo estándar de decaimiento exponencial (Banister / Coggan).
- ACWR: carga aguda (7 días) / crónica (promedio semanal de 28 días).
- Tendencias de HRV y training readiness (7 vs 30 días).
"""

import json
import math
from datetime import date, timedelta

from backend.db import get_db, get_all_settings

CTL_DAYS = 42
ATL_DAYS = 7

# TRIMP de Banister por hora pedaleando en el umbral (HRr = 0.85):
# 60 min * 0.85 * 0.64 * e^(1.92*0.85)  ->  se usa para convertir TRIMP a hrTSS
_TRIMP_THRESHOLD_HOUR = 60 * 0.85 * 0.64 * math.exp(1.92 * 0.85)


def _settings():
    s = get_all_settings()

    def _int(key):
        try:
            return int(float(s.get(key)))
        except (TypeError, ValueError):
            return None

    return {
        "hr_max": _int("hr_max"),
        "hr_rest": _int("hr_rest"),
        "ftp": _int("ftp"),
        "has_power_meter": s.get("has_power_meter") == "1",
    }


def compute_activity_load(act: dict, hr_max, hr_rest, ftp):
    """Devuelve (trimp, tss, metodo) para una actividad. None si faltan datos."""
    duration_s = act.get("moving_s") or act.get("duration_s")
    if not duration_s:
        return None, None, None

    trimp = None
    avg_hr = act.get("avg_hr")
    if hr_max and hr_rest and avg_hr and hr_max > hr_rest:
        hrr = (avg_hr - hr_rest) / (hr_max - hr_rest)
        hrr = max(0.0, min(1.0, hrr))
        trimp = (duration_s / 60) * hrr * 0.64 * math.exp(1.92 * hrr)

    # TSS real con potencia
    np_watts = act.get("norm_power") or act.get("avg_power")
    if ftp and np_watts:
        intensity = np_watts / ftp
        tss = duration_s * np_watts * intensity / (ftp * 3600) * 100
        return trimp, round(tss, 1), "power"

    # hrTSS estimado desde TRIMP
    if trimp is not None:
        tss = trimp / _TRIMP_THRESHOLD_HOUR * 100
        return round(trimp, 1), round(tss, 1), "hr"

    return None, None, None


def recompute_all_loads() -> dict:
    """Recalcula TRIMP/TSS de todas las actividades con la config actual."""
    cfg = _settings()
    updated, skipped = 0, 0
    with get_db() as db:
        rows = db.execute("SELECT * FROM activities").fetchall()
        for r in rows:
            trimp, tss, _ = compute_activity_load(dict(r), cfg["hr_max"], cfg["hr_rest"], cfg["ftp"])
            if tss is None:
                skipped += 1
                continue
            db.execute(
                "UPDATE activities SET trimp=?, tss=? WHERE activity_id=?",
                (trimp, tss, r["activity_id"]),
            )
            updated += 1
    return {"updated": updated, "skipped": skipped, "settings": cfg}


def daily_load_series(days: int = 120) -> list[dict]:
    """Serie diaria de carga con CTL/ATL/TSB, desde la primera actividad."""
    with get_db() as db:
        rows = db.execute(
            "SELECT date(start_time) d, SUM(COALESCE(tss, 0)) load FROM activities "
            "WHERE start_time IS NOT NULL GROUP BY date(start_time) ORDER BY d"
        ).fetchall()
    if not rows:
        return []

    loads = {r["d"]: r["load"] or 0 for r in rows}
    start = date.fromisoformat(rows[0]["d"])
    end = date.today()

    series = []
    ctl, atl = 0.0, 0.0
    d = start
    while d <= end:
        load = loads.get(d.isoformat(), 0.0)
        tsb = ctl - atl  # forma del día: fitness - fatiga ANTES del entreno de hoy
        ctl += (load - ctl) / CTL_DAYS
        atl += (load - atl) / ATL_DAYS
        series.append(
            {
                "date": d.isoformat(),
                "load": round(load, 1),
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(tsb, 1),
            }
        )
        d += timedelta(days=1)

    return series[-days:]


def _acwr(series: list[dict]):
    """ACWR = carga de los últimos 7 días / promedio semanal de los últimos 28."""
    if len(series) < 8:
        return None, None, None
    acute = sum(p["load"] for p in series[-7:])
    chronic_window = series[-28:]
    chronic = sum(p["load"] for p in chronic_window) / (len(chronic_window) / 7)
    if chronic <= 0:
        return round(acute, 0), None, None
    return round(acute, 0), round(chronic, 0), round(acute / chronic, 2)


def _hrv_trend():
    with get_db() as db:
        rows = db.execute(
            "SELECT date, hrv_last_night, training_readiness, resting_hr "
            "FROM daily_metrics ORDER BY date DESC LIMIT 30"
        ).fetchall()
    hrv = [r["hrv_last_night"] for r in rows if r["hrv_last_night"] is not None]
    readiness = [r["training_readiness"] for r in rows if r["training_readiness"] is not None]
    rhr = [r["resting_hr"] for r in rows if r["resting_hr"] is not None]

    def avg(xs):
        return round(sum(xs) / len(xs), 1) if xs else None

    return {
        "hrv_last": round(hrv[0], 1) if hrv else None,
        "hrv_avg7": avg(hrv[:7]),
        "hrv_avg30": avg(hrv),
        "readiness_last": round(readiness[0]) if readiness else None,
        "readiness_avg7": avg(readiness[:7]),
        "rhr_last": round(rhr[0]) if rhr else None,
        "rhr_avg30": avg(rhr),
    }


def summary() -> dict:
    cfg = _settings()
    missing = []
    if not cfg["hr_max"]:
        missing.append("hr_max")
    if not cfg["hr_rest"]:
        missing.append("hr_rest")

    series = daily_load_series(120)
    today = series[-1] if series else None
    acute, chronic, acwr = _acwr(series) if series else (None, None, None)
    trend = _hrv_trend()

    alerts = []
    if missing:
        alerts.append(
            {
                "level": "warning",
                "text": "Faltan tus datos de FC máxima y/o FC en reposo en 'Mis datos': "
                "sin eso no se puede estimar la carga (TSS) de las salidas sin potenciómetro.",
            }
        )
    if acwr is not None:
        if acwr > 1.5:
            alerts.append(
                {
                    "level": "critical",
                    "text": f"ACWR {acwr}: tu carga de esta semana ({acute:.0f} TSS) supera en más de un 50% "
                    f"tu promedio semanal del último mes ({chronic:.0f} TSS). Riesgo alto de lesión o "
                    "sobreentrenamiento — bajá el volumen esta semana.",
                }
            )
        elif acwr > 1.3:
            alerts.append(
                {
                    "level": "serious",
                    "text": f"ACWR {acwr}: estás subiendo la carga más rápido que lo recomendado "
                    f"(aguda {acute:.0f} vs crónica {chronic:.0f} TSS/semana). Zona de precaución (1.3–1.5).",
                }
            )
        elif acwr < 0.8:
            alerts.append(
                {
                    "level": "warning",
                    "text": f"ACWR {acwr}: esta semana entrenaste bastante menos que tu promedio "
                    "del mes — la forma se pierde si se sostiene mucho tiempo.",
                }
            )
    if today and today["tsb"] < -20:
        alerts.append(
            {
                "level": "serious",
                "text": f"TSB {today['tsb']}: fatiga acumulada alta (por debajo de -20). "
                "Priorizá recuperación o rodajes suaves.",
            }
        )
    hrv7, hrv30 = trend.get("hrv_avg7"), trend.get("hrv_avg30")
    if hrv7 and hrv30 and hrv30 > 0 and (hrv7 - hrv30) / hrv30 < -0.07:
        alerts.append(
            {
                "level": "warning",
                "text": f"Tu HRV promedio de 7 días ({hrv7} ms) está más de un 7% por debajo de tu "
                f"baseline de 30 días ({hrv30} ms): señal de recuperación incompleta o estrés.",
            }
        )

    return {
        "settings_ok": not missing,
        "missing_settings": missing,
        "has_data": bool(series),
        "today": today,
        "acute_load_7d": acute,
        "chronic_weekly_load": chronic,
        "acwr": acwr,
        "trend": trend,
        "alerts": alerts,
    }
