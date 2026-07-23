"""Sincronización de datos desde Garmin Connect a la base local."""

import json
import logging
from datetime import date, datetime, timedelta

from backend.db import get_db

logger = logging.getLogger(__name__)

# typeKeys de Garmin que consideramos ciclismo (incluye MTB)
def _is_cycling(type_key: str) -> bool:
    tk = (type_key or "").lower()
    return "biking" in tk or "cycling" in tk or tk in ("virtual_ride", "bmx")


def sync_activities(g, days_back: int = 90) -> dict:
    """Baja las actividades de ciclismo de los últimos `days_back` días."""
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = date.today().isoformat()
    activities = g.get_activities_by_date(start, end) or []
    new, updated = 0, 0

    with get_db() as db:
        known = {r["activity_id"] for r in db.execute("SELECT activity_id FROM activities")}

    for act in activities:
        type_key = (act.get("activityType") or {}).get("typeKey", "")
        if not _is_cycling(type_key):
            continue
        act_id = act["activityId"]
        is_new = act_id not in known

        # tiempo en zonas de FC (llamada extra por actividad, solo si es nueva)
        hr_zones = None
        if is_new:
            try:
                zones = g.get_activity_hr_in_timezones(act_id) or []
                hr_zones = {str(z.get("zoneNumber")): z.get("secsInZone", 0) for z in zones}
            except Exception as e:
                logger.warning("Sin zonas de FC para actividad %s: %s", act_id, e)

        avg_power = act.get("avgPower") or act.get("averagePower")
        row = (
            act_id,
            act.get("startTimeLocal"),
            act.get("activityName"),
            type_key,
            act.get("distance"),
            act.get("duration"),
            act.get("movingDuration"),
            act.get("elevationGain"),
            act.get("averageHR"),
            act.get("maxHR"),
            avg_power,
            act.get("normPower") or act.get("normalizedPower"),
            1 if avg_power else 0,
            act.get("calories"),
            json.dumps(hr_zones) if hr_zones else None,
            json.dumps(act),
        )
        with get_db() as db:
            if is_new:
                db.execute(
                    """INSERT INTO activities
                       (activity_id, start_time, name, type_key, distance_m, duration_s,
                        moving_s, elevation_gain_m, avg_hr, max_hr, avg_power, norm_power,
                        has_power, calories, hr_zone_secs, raw_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    row,
                )
                new += 1
            else:
                db.execute(
                    """UPDATE activities SET start_time=?, name=?, type_key=?, distance_m=?,
                       duration_s=?, moving_s=?, elevation_gain_m=?, avg_hr=?, max_hr=?,
                       avg_power=?, norm_power=?, has_power=?, calories=?, raw_json=?,
                       synced_at=datetime('now')
                       WHERE activity_id=?""",
                    row[1:14] + (row[15], act_id),
                )
                updated += 1

    return {"cycling_new": new, "cycling_updated": updated, "total_seen": len(activities)}


def sync_daily_metrics(g, days_back: int = 30) -> dict:
    """Baja métricas diarias (HRV, sueño, readiness, FC reposo, body battery).

    Solo pide a Garmin los días que faltan en la base (más hoy y ayer, que
    pueden haber cambiado), para no gastar llamadas de más.
    """
    today = date.today()
    with get_db() as db:
        have = {r["date"] for r in db.execute("SELECT date FROM daily_metrics")}

    days_done, errors = 0, 0
    for i in range(days_back):
        d = today - timedelta(days=i)
        ds = d.isoformat()
        if ds in have and i > 1:  # hoy y ayer se refrescan siempre
            continue
        try:
            metrics = _fetch_day(g, ds)
        except Exception as e:
            logger.warning("Error bajando métricas de %s: %s", ds, e)
            errors += 1
            continue
        with get_db() as db:
            db.execute(
                """INSERT INTO daily_metrics
                   (date, resting_hr, hrv_last_night, hrv_weekly_avg, hrv_status,
                    sleep_seconds, sleep_score, training_readiness, readiness_status,
                    body_battery_max, body_battery_min, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET
                    resting_hr=excluded.resting_hr,
                    hrv_last_night=excluded.hrv_last_night,
                    hrv_weekly_avg=excluded.hrv_weekly_avg,
                    hrv_status=excluded.hrv_status,
                    sleep_seconds=excluded.sleep_seconds,
                    sleep_score=excluded.sleep_score,
                    training_readiness=excluded.training_readiness,
                    readiness_status=excluded.readiness_status,
                    body_battery_max=excluded.body_battery_max,
                    body_battery_min=excluded.body_battery_min,
                    raw_json=excluded.raw_json,
                    synced_at=datetime('now')""",
                (
                    ds,
                    metrics.get("resting_hr"),
                    metrics.get("hrv_last_night"),
                    metrics.get("hrv_weekly_avg"),
                    metrics.get("hrv_status"),
                    metrics.get("sleep_seconds"),
                    metrics.get("sleep_score"),
                    metrics.get("training_readiness"),
                    metrics.get("readiness_status"),
                    metrics.get("body_battery_max"),
                    metrics.get("body_battery_min"),
                    json.dumps(metrics.get("raw", {})),
                ),
            )
        days_done += 1

    return {"days_synced": days_done, "errors": errors}


def _fetch_day(g, ds: str) -> dict:
    """Pide a Garmin todas las métricas de un día. Cada bloque tolera fallos."""
    out = {"raw": {}}

    try:
        rhr = g.get_rhr_day(ds)
        out["raw"]["rhr"] = rhr
        vals = (((rhr or {}).get("allMetrics") or {}).get("metricsMap") or {}).get(
            "WELLNESS_RESTING_HEART_RATE"
        ) or []
        if vals:
            out["resting_hr"] = vals[0].get("value")
    except Exception as e:
        logger.debug("rhr %s: %s", ds, e)

    try:
        hrv = g.get_hrv_data(ds)
        out["raw"]["hrv"] = hrv
        summary = (hrv or {}).get("hrvSummary") or {}
        out["hrv_last_night"] = summary.get("lastNightAvg")
        out["hrv_weekly_avg"] = summary.get("weeklyAvg")
        out["hrv_status"] = summary.get("status")
    except Exception as e:
        logger.debug("hrv %s: %s", ds, e)

    try:
        sleep = g.get_sleep_data(ds)
        dto = (sleep or {}).get("dailySleepDTO") or {}
        out["sleep_seconds"] = dto.get("sleepTimeSeconds")
        score = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
        out["sleep_score"] = score
        out["raw"]["sleep"] = {"dailySleepDTO": dto}  # sin los arrays largos
    except Exception as e:
        logger.debug("sleep %s: %s", ds, e)

    try:
        tr = g.get_training_readiness(ds)
        out["raw"]["readiness"] = tr
        if isinstance(tr, list) and tr:
            out["training_readiness"] = tr[0].get("score")
            out["readiness_status"] = tr[0].get("level")
    except Exception as e:
        logger.debug("readiness %s: %s", ds, e)

    try:
        bb = g.get_body_battery(ds)
        out["raw"]["body_battery"] = bb
        if isinstance(bb, list) and bb:
            values = [
                v[1]
                for entry in bb
                for v in (entry.get("bodyBatteryValuesArray") or [])
                if isinstance(v, (list, tuple)) and len(v) > 1 and v[1] is not None
            ]
            if values:
                out["body_battery_max"] = max(values)
                out["body_battery_min"] = min(values)
    except Exception as e:
        logger.debug("body battery %s: %s", ds, e)

    return out


def run_full_sync(g, days_activities: int = 90, days_daily: int = 30) -> dict:
    started = datetime.now().isoformat(timespec="seconds")
    result = {"started_at": started}
    ok = True
    try:
        result["activities"] = sync_activities(g, days_activities)
        result["daily"] = sync_daily_metrics(g, days_daily)
    except Exception as e:
        ok = False
        result["error"] = str(e)
        logger.exception("Fallo la sincronización")
    result["finished_at"] = datetime.now().isoformat(timespec="seconds")
    with get_db() as db:
        db.execute(
            "INSERT INTO sync_log (started_at, finished_at, ok, detail) VALUES (?,?,?,?)",
            (started, result["finished_at"], 1 if ok else 0, json.dumps(result, default=str)),
        )
    return result
