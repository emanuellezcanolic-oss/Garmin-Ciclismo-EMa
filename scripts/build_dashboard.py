"""Genera el dashboard estático a partir de la API de intervals.icu.

Corre en GitHub Actions. Lee actividades y datos de bienestar (que
intervals.icu sincroniza solo desde Garmin), calcula métricas de carga,
genera el plan del día con justificación, y escribe docs/data.json.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

API = "https://intervals.icu/api/v1"
ATHLETE = os.environ.get("ATHLETE_ID", "i650204")
KEY = os.environ["INTERVALS_API_KEY"]
AUTH = ("API_KEY", KEY)

# Hora local de Argentina (UTC-3, sin horario de verano)
TZ = timezone(timedelta(hours=-3))
TODAY = datetime.now(TZ).date()

CYCLING_TYPES = {
    "Ride", "MountainBikeRide", "GravelRide", "VirtualRide", "EBikeRide",
    "EMountainBikeRide", "TrackRide", "Handcycle", "Velomobile",
}


def get(path, **params):
    r = requests.get(f"{API}{path}", auth=AUTH, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_all():
    oldest = (TODAY - timedelta(days=180)).isoformat()
    newest = TODAY.isoformat()

    wellness = get(f"/athlete/{ATHLETE}/wellness", oldest=oldest, newest=newest)
    activities = get(
        f"/athlete/{ATHLETE}/activities",
        oldest=oldest + "T00:00:00",
        newest=newest + "T23:59:59",
    )
    try:
        athlete = get(f"/athlete/{ATHLETE}")
    except Exception as e:
        print(f"AVISO: no pude leer el perfil del atleta: {e}")
        athlete = {}
    return wellness, activities, athlete


def num(x):
    return x if isinstance(x, (int, float)) else None


def build(wellness, activities, athlete):
    # ---------- bienestar diario (intervals.icu ya trae ctl/atl calculados)
    days = {}
    for w in sorted(wellness, key=lambda w: w.get("id", "")):
        d = w.get("id")
        if not d:
            continue
        days[d] = {
            "date": d,
            "ctl": num(w.get("ctl")),
            "atl": num(w.get("atl")),
            "hrv": num(w.get("hrv")),
            "resting_hr": num(w.get("restingHR")),
            "sleep_secs": num(w.get("sleepSecs")),
            "sleep_score": num(w.get("sleepScore")),
            "readiness": num(w.get("readiness")),
        }

    # ---------- actividades de ciclismo
    rides = []
    load_by_day = {}
    for a in activities:
        if a.get("type") not in CYCLING_TYPES:
            continue
        start = (a.get("start_date_local") or "")[:10]
        load = num(a.get("icu_training_load")) or 0
        load_by_day[start] = load_by_day.get(start, 0) + load
        rides.append({
            "id": a.get("id"),
            "date": start,
            "name": a.get("name"),
            "type": a.get("type"),
            "distance_km": round((num(a.get("distance")) or 0) / 1000, 1),
            "moving_time_s": num(a.get("moving_time")),
            "elevation_m": num(a.get("total_elevation_gain")),
            "avg_hr": num(a.get("average_heartrate")),
            "max_hr": num(a.get("max_heartrate")),
            "avg_watts": num(a.get("average_watts")),
            "np_watts": num(a.get("icu_weighted_avg_watts")),
            "load": load,
            "intensity": num(a.get("icu_intensity")),
        })
    rides.sort(key=lambda r: r["date"], reverse=True)

    # ---------- serie de los últimos 120 días para el gráfico
    series = []
    d = TODAY - timedelta(days=120)
    last_ctl, last_atl = None, None
    while d <= TODAY:
        ds = d.isoformat()
        w = days.get(ds, {})
        ctl, atl = w.get("ctl"), w.get("atl")
        if ctl is None:
            ctl = last_ctl
        if atl is None:
            atl = last_atl
        last_ctl, last_atl = ctl, atl
        if ctl is not None and atl is not None:
            series.append({
                "date": ds,
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(ctl - atl, 1),
                "load": round(load_by_day.get(ds, 0), 1),
            })
        d += timedelta(days=1)

    # ---------- ACWR
    def day_load(offset):
        return load_by_day.get((TODAY - timedelta(days=offset)).isoformat(), 0)

    acute = sum(day_load(i) for i in range(7))
    chronic_total = sum(day_load(i) for i in range(28))
    chronic = chronic_total / 4 if chronic_total else 0
    acwr = round(acute / chronic, 2) if chronic > 0 else None

    # ---------- tendencias HRV / FC reposo / sueño
    def recent(key, n, until_today=True):
        vals = []
        for i in range(n):
            w = days.get((TODAY - timedelta(days=i)).isoformat())
            if w and w.get(key) is not None:
                vals.append(w[key])
        return vals

    def avg(v):
        return round(sum(v) / len(v), 1) if v else None

    hrv7, hrv30 = avg(recent("hrv", 7)), avg(recent("hrv", 30))
    rhr7, rhr30 = avg(recent("resting_hr", 7)), avg(recent("resting_hr", 30))
    today_w = days.get(TODAY.isoformat(), {})
    yesterday_w = days.get((TODAY - timedelta(days=1)).isoformat(), {})
    hrv_today = today_w.get("hrv") or yesterday_w.get("hrv")
    sleep_today = today_w.get("sleep_secs")
    sleep_score_today = today_w.get("sleep_score")
    readiness_today = today_w.get("readiness")

    current = series[-1] if series else {}
    ctl_now, atl_now = current.get("ctl"), current.get("atl")
    tsb_now = current.get("tsb")

    # ---------- plan del día (fase 3: decisión basada en datos)
    plan = make_plan(
        tsb=tsb_now, acwr=acwr, acute=acute, chronic=chronic,
        hrv_today=hrv_today, hrv30=hrv30, sleep_secs=sleep_today,
        sleep_score=sleep_score_today, readiness=readiness_today,
        load_recent=[day_load(i) for i in range(7)],
    )

    # ---------- alertas
    alerts = []
    if acwr is not None and acwr > 1.5:
        alerts.append({"level": "critical",
                       "text": f"ACWR {acwr}: la carga de 7 días ({acute:.0f}) supera en más de 50% tu "
                               f"promedio semanal del mes ({chronic:.0f}). Riesgo alto — bajá el volumen."})
    elif acwr is not None and acwr > 1.3:
        alerts.append({"level": "serious",
                       "text": f"ACWR {acwr}: estás subiendo la carga rápido (aguda {acute:.0f} vs "
                               f"crónica {chronic:.0f}/semana). Zona de precaución 1.3–1.5."})
    if tsb_now is not None and tsb_now < -20:
        alerts.append({"level": "serious",
                       "text": f"TSB {tsb_now}: fatiga acumulada alta. Priorizá recuperación."})
    if hrv7 and hrv30 and (hrv7 - hrv30) / hrv30 < -0.07:
        alerts.append({"level": "warning",
                       "text": f"HRV 7 días ({hrv7} ms) más de 7% por debajo del baseline de 30 días "
                               f"({hrv30} ms): recuperación incompleta o estrés."})

    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "athlete": {"id": ATHLETE, "name": athlete.get("name")},
        "today": {
            "date": TODAY.isoformat(),
            "ctl": ctl_now, "atl": atl_now, "tsb": tsb_now,
            "acwr": acwr, "acute_7d": round(acute, 0), "chronic_weekly": round(chronic, 0),
            "hrv": hrv_today, "hrv7": hrv7, "hrv30": hrv30,
            "resting_hr": today_w.get("resting_hr") or yesterday_w.get("resting_hr"),
            "rhr7": rhr7, "rhr30": rhr30,
            "sleep_secs": sleep_today, "sleep_score": sleep_score_today,
            "readiness": readiness_today,
        },
        "plan": plan,
        "alerts": alerts,
        "series": series,
        "rides": rides[:60],
        "counts": {"rides_180d": len(rides), "wellness_days": len(days)},
    }


def make_plan(tsb, acwr, acute, chronic, hrv_today, hrv30, sleep_secs,
              sleep_score, readiness, load_recent):
    """Decide el entreno de hoy y lo justifica con los números."""
    # Sin historial suficiente no se recomienda nada: sería inventar.
    if not chronic or chronic <= 0:
        return {
            "kind": "sin_datos",
            "title": "Recopilando tus datos…",
            "steps": [{
                "phase": "Todavía no hay recomendación",
                "desc": "No hay suficiente historial de salidas para calcular tu carga crónica. "
                        "Importá tus datos viejos desde intervals.icu (Ajustes → Conexiones → "
                        "tarjeta Garmin → 'Importar todos los datos de Garmin') y esperá unos minutos. "
                        "Con ~4 semanas de historial el plan se activa solo.",
            }],
            "est_load": 0,
            "why": ["Sin carga crónica (promedio de las últimas 4 semanas) no se puede dosificar "
                    "un entreno de forma segura ni útil."],
        }
    why = []
    flags_bad = 0

    if hrv_today is not None and hrv30:
        pct = (hrv_today - hrv30) / hrv30 * 100
        if pct < -10:
            flags_bad += 2
            why.append(f"HRV de anoche {hrv_today:.0f} ms, {abs(pct):.0f}% por debajo de tu baseline ({hrv30:.0f} ms) → recuperación pobre.")
        elif pct < -5:
            flags_bad += 1
            why.append(f"HRV de anoche {hrv_today:.0f} ms, algo por debajo de tu baseline ({hrv30:.0f} ms).")
        else:
            why.append(f"HRV de anoche {hrv_today:.0f} ms, en línea con tu baseline ({hrv30:.0f} ms) → recuperación OK.")

    if sleep_secs is not None:
        h = sleep_secs / 3600
        if h < 6:
            flags_bad += 2
            why.append(f"Dormiste {h:.1f} h (<6 h) → el cuerpo no descansó lo suficiente.")
        elif h < 7:
            flags_bad += 1
            why.append(f"Dormiste {h:.1f} h, un poco justo.")
        else:
            why.append(f"Dormiste {h:.1f} h → bien.")

    if readiness is not None:
        if readiness < 40:
            flags_bad += 2
            why.append(f"Training readiness de Garmin: {readiness:.0f}/100 (bajo).")
        elif readiness < 60:
            flags_bad += 1
            why.append(f"Training readiness de Garmin: {readiness:.0f}/100 (moderado).")
        else:
            why.append(f"Training readiness de Garmin: {readiness:.0f}/100 (bueno).")

    if tsb is not None:
        if tsb < -25:
            flags_bad += 2
            why.append(f"TSB {tsb}: fatiga acumulada muy alta.")
        elif tsb < -10:
            flags_bad += 1
            why.append(f"TSB {tsb}: venís con fatiga acumulada.")
        else:
            why.append(f"TSB {tsb}: forma/frescura razonable.")

    # presupuesto de carga para no pasar ACWR 1.3
    budget = None
    if chronic:
        budget = max(0, 1.3 * chronic - sum(load_recent[:6]))
        why.append(f"Presupuesto de carga para hoy sin pasar ACWR 1.3: ~{budget:.0f} TSS "
                   f"(llevás {sum(load_recent[:6]):.0f} en los últimos 6 días, crónica {chronic:.0f}/sem).")

    # ---------- decisión
    if flags_bad >= 3:
        kind = "descanso"
        title = "Descanso o recuperación activa"
        steps = [
            {"phase": "Opción A", "desc": "Descanso total."},
            {"phase": "Opción B", "desc": "Rodillo o vuelta muy suave 30–40 min en Z1 (poder conversar sin esfuerzo), cadencia alta, terreno llano."},
        ]
        est = 20
    elif flags_bad == 2:
        kind = "suave"
        title = "Rodaje regenerativo Z1–Z2"
        steps = [
            {"phase": "Calentamiento", "desc": "10 min en Z1, cadencia cómoda."},
            {"phase": "Bloque principal", "desc": "30–45 min en Z2 baja, terreno llano o rodillo. Nada de subidas fuertes hoy."},
            {"phase": "Vuelta a la calma", "desc": "5–10 min en Z1."},
        ]
        est = 40
    elif tsb is not None and tsb < -10:
        kind = "resistencia"
        title = "Fondo aeróbico Z2"
        steps = [
            {"phase": "Calentamiento", "desc": "15 min progresivos Z1 → Z2."},
            {"phase": "Bloque principal", "desc": "60–90 min en Z2 sostenida. En MTB: sendero rodador, subidas largas sentado a ritmo constante, sin picos."},
            {"phase": "Vuelta a la calma", "desc": "10 min en Z1."},
        ]
        est = 75
    elif tsb is not None and tsb > 5:
        kind = "intensidad"
        title = "Intervalos VO2máx 4×4 (día de calidad)"
        steps = [
            {"phase": "Calentamiento", "desc": "15 min Z1–Z2 + 3 aceleraciones de 30 s."},
            {"phase": "Bloque principal", "desc": "4 × 4 min en Z5 (esfuerzo duro, respiración muy exigida) con 4 min suaves en Z1 entre series. En MTB: una subida de 4+ min repetida."},
            {"phase": "Vuelta a la calma", "desc": "10–15 min en Z1."},
        ]
        est = 80
    else:
        kind = "tempo"
        title = "Tempo / Sweet Spot 3×10"
        steps = [
            {"phase": "Calentamiento", "desc": "15 min Z1–Z2."},
            {"phase": "Bloque principal", "desc": "3 × 10 min en Z3–Z4 baja (ritmo exigente pero sostenible, frases cortas al hablar) con 5 min en Z1 entre bloques. En MTB: subida constante o tramo rodador sin cortes."},
            {"phase": "Vuelta a la calma", "desc": "10 min en Z1."},
        ]
        est = 70

    if budget is not None and est > budget and kind in ("intensidad", "tempo", "resistencia"):
        why.append(f"El entreno se acorta para respetar el presupuesto de ~{budget:.0f} TSS.")

    return {"kind": kind, "title": title, "steps": steps, "est_load": est, "why": why}


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    try:
        wellness, activities, athlete = fetch_all()
    except requests.HTTPError as e:
        print(f"ERROR llamando a intervals.icu: {e.response.status_code} {e.response.text[:300]}")
        sys.exit(1)

    print(f"wellness: {len(wellness)} días | actividades: {len(activities)}")
    if wellness:
        print("campos wellness:", sorted(wellness[-1].keys()))
    if activities:
        print("campos actividad:", sorted(activities[0].keys())[:40])

    data = build(wellness, activities, athlete)
    path = os.path.join(out_dir, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"OK → {path}")
    print(f"hoy: {json.dumps(data['today'], ensure_ascii=False)}")
    print(f"plan: {data['plan']['title']}")


if __name__ == "__main__":
    main()
