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

from evidencia import evidencia_para_plan, evidencia_agrupada
from periodizacion import fase_actual, mapa_temporada
try:
    import dfa as dfa_mod
except Exception as _e:  # numpy podría no estar
    dfa_mod = None
    print(f"AVISO: módulo DFA no disponible ({_e})")

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

# ---- Preferencias del atleta (Emanuel) — calibran el planificador ----
DIAS_OBJETIVO = 6            # días/semana que quiere entrenar (5 carga + 1 recuperación)
DUR_NORMAL = "60-90 min"     # día normal entre semana
DUR_LARGO = "2-3 h"          # fondo largo (fin de semana)
DUR_SUAVE = "45-60 min"      # días fáciles / recuperación activa (nada de 20-30 min)
DIA_LARGO = (5, 6)           # sáb/dom = día de fondo largo (weekday(): lun=0 … dom=6)


def get(path, **params):
    r = requests.get(f"{API}{path}", auth=AUTH, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


WORKOUT_PREFIX = "🤖 Plan del día"


def upsert_workout(plan):
    """Crea/actualiza el entreno de hoy en intervals.icu.

    intervals.icu lo sincroniza solo con Garmin Connect (la opción 'Cargar
    entrenamientos planificados' está activada), así el plan aparece en el
    reloj sin intervención. Falla con un aviso, nunca rompe el dashboard.
    """
    today = TODAY.isoformat()
    try:
        events = requests.get(
            f"{API}/athlete/{ATHLETE}/events", auth=AUTH, timeout=60,
            params={"oldest": today, "newest": today, "category": "WORKOUT"},
        ).json()
        mine = [e for e in events if isinstance(e, dict)
                and (e.get("name") or "").startswith(WORKOUT_PREFIX)]
    except Exception as e:
        print(f"AVISO: no pude listar eventos: {e}")
        return {"status": "error", "detail": str(e)}

    # días de descanso o sin datos: borrar el entreno si existía
    if plan["kind"] in ("descanso", "sin_datos"):
        for ev in mine:
            try:
                requests.delete(f"{API}/athlete/{ATHLETE}/events/{ev['id']}",
                                auth=AUTH, timeout=60)
                print(f"Entreno {ev['id']} borrado (hoy toca {plan['kind']})")
            except Exception as e:
                print(f"AVISO: no pude borrar evento {ev.get('id')}: {e}")
        return {"status": "sin_workout", "reason": plan["kind"]}

    workout_text = plan.get("workout_text", "")
    body = {
        "category": "WORKOUT",
        "start_date_local": f"{today}T00:00:00",
        "type": "Ride",
        "name": f"{WORKOUT_PREFIX}: {plan['title']}",
        "description": workout_text,
    }
    try:
        if mine:
            r = requests.put(f"{API}/athlete/{ATHLETE}/events/{mine[0]['id']}",
                             auth=AUTH, json=body, timeout=60)
        else:
            r = requests.post(f"{API}/athlete/{ATHLETE}/events",
                              auth=AUTH, json=body, timeout=60)
        print(f"Workout {'actualizado' if mine else 'creado'}: HTTP {r.status_code} "
              f"→ {r.text[:200]}")
        return {"status": "ok" if r.ok else "error", "http": r.status_code}
    except Exception as e:
        print(f"AVISO: no pude subir el workout: {e}")
        return {"status": "error", "detail": str(e)}


def training_quality(activities, load_by_day):
    """Métricas de calidad basadas en evidencia (con FC, sin potenciómetro):
    - Distribución de intensidad / polarización (Seiler ~80/20)
    - Monotonía y Strain de Foster (riesgo de enfermedad/sobreentrenamiento)
    - Desacople aeróbico de la última salida larga (durabilidad; TrainingPeaks)
    """
    from statistics import pstdev

    # ---- distribución de zonas de FC, últimos 7 días
    cutoff = (TODAY - timedelta(days=6)).isoformat()
    low = mid = high = 0.0
    zt_found = False
    for a in activities:
        if (a.get("type") not in CYCLING_TYPES):
            continue
        if (a.get("start_date_local") or "")[:10] < cutoff:
            continue
        zt = a.get("icu_hr_zone_times") or a.get("hr_zone_times") or a.get("icu_zone_times")
        if isinstance(zt, list) and zt:
            zt_found = True
            low += sum(zt[:2])
            mid += zt[2] if len(zt) > 2 else 0
            high += sum(zt[3:]) if len(zt) > 3 else 0
    polar = None
    if zt_found and (low + mid + high) > 0:
        tot = low + mid + high
        polar = {
            "low_pct": round(low / tot * 100),
            "mid_pct": round(mid / tot * 100),
            "high_pct": round(high / tot * 100),
        }

    # ---- monotonía y strain de Foster, últimos 7 días
    loads = [load_by_day.get((TODAY - timedelta(days=i)).isoformat(), 0.0) for i in range(7)]
    week_load = sum(loads)
    mean = week_load / 7
    sd = pstdev(loads) if len(loads) > 1 else 0
    monotony = round(mean / sd, 2) if sd > 0 else None
    strain = round(week_load * monotony) if monotony else None

    # ---- desacople aeróbico de la última salida larga (>60 min)
    decoupling = None
    for a in sorted(activities, key=lambda x: x.get("start_date_local") or "", reverse=True):
        if a.get("type") not in CYCLING_TYPES:
            continue
        if (a.get("moving_time") or 0) < 3600:
            continue
        d = a.get("decoupling")
        if isinstance(d, (int, float)):
            decoupling = {"value": round(d, 1), "name": a.get("name"),
                          "date": (a.get("start_date_local") or "")[:10]}
            break

    return {
        "polarization": polar,
        "monotony": monotony,
        "strain": strain,
        "week_load": round(week_load),
        "decoupling": decoupling,
    }


def estimate_lthr(rides):
    """Estima el umbral de FC (LTHR) desde la última salida.

    Baja la serie de pulso y calcula el mejor promedio sostenido de 20 min
    (proxy del LTHR de Friel = FC media de los últimos 20 min de un test
    máximo de 30 min). Sólo es válido si la salida fue un esfuerzo duro y
    parejo; si fue suave, lo indica.
    """
    if not rides:
        return None
    r = rides[0]
    aid = r.get("id")
    try:
        streams = get(f"/activity/{aid}/streams", types="time,heartrate")
    except Exception as e:
        print(f"LTHR: no pude bajar streams de {aid}: {e}")
        return {"error": "no pude leer la serie de pulso de la última salida"}

    hr, tm = None, None
    if isinstance(streams, list):
        for s in streams:
            if s.get("type") == "heartrate":
                hr = s.get("data")
            elif s.get("type") == "time":
                tm = s.get("data")
    if not hr:
        return {"error": "la última salida no tiene datos de frecuencia cardíaca"}

    hr = [h for h in hr if isinstance(h, (int, float)) and h > 0]
    n = len(hr)
    if n < 300:
        return {"error": "la última salida es demasiado corta para estimar el umbral"}

    # frecuencia de muestreo: por defecto 1 Hz; si hay tiempo, la deduzco
    dt = 1.0
    if tm and len(tm) >= 2:
        diffs = [tm[i + 1] - tm[i] for i in range(min(len(tm), n) - 1) if tm[i + 1] > tm[i]]
        if diffs:
            diffs.sort()
            dt = diffs[len(diffs) // 2] or 1.0

    def best_window(minutes):
        w = max(1, int(minutes * 60 / dt))
        if n < w:
            return None
        # media móvil con suma acumulada -> O(n)
        s = sum(hr[:w])
        best = s
        for i in range(w, n):
            s += hr[i] - hr[i - w]
            if s > best:
                best = s
        return best / w

    best20 = best_window(20)
    best30 = best_window(30)
    avg = sum(hr) / n
    hmax = max(hr)
    intensity = r.get("intensity")

    if best20 is None:
        return {"error": "la salida dura menos de 20 minutos; no alcanza para el test"}

    lthr = round(best20)
    # icu_intensity viene como porcentaje (IF×100): ~90 = esfuerzo duro
    note = ("Estimado desde una salida pareja (no un test máximo formal): tomalo como piso. "
            "Para el valor exacto, hacé el test de 30 min a tope.")
    if intensity is not None and intensity < 75:
        note = ("⚠️ Esta salida fue de intensidad baja (más bien Z2): no sirve para estimar el umbral. "
                "El número casi seguro subestima tu LTHR real. Hacé el test de 30 min a tope.")
    elif intensity is not None and intensity >= 85:
        note = (f"Salida exigente (IF {intensity:.0f}%): el estimado es confiable, muy cerca de tu LTHR real. "
                "Podés confirmarlo con el test de 30 min a tope cuando quieras.")

    # zonas de FC de Friel a partir del LTHR
    zones = {
        "Z1 recuperación": f"< {round(lthr*0.81)}",
        "Z2 aeróbico": f"{round(lthr*0.81)}–{round(lthr*0.89)}",
        "Z3 tempo": f"{round(lthr*0.90)}–{round(lthr*0.93)}",
        "Z4 umbral": f"{round(lthr*0.94)}–{round(lthr*0.99)}",
        "Z5 VO2max": f"> {round(lthr*1.00)}",
    }
    return {
        "date": r.get("date"), "name": r.get("name"),
        "lthr": lthr, "best20": round(best20), "best30": round(best30) if best30 else None,
        "avg_hr": round(avg), "max_hr": round(hmax), "intensity": intensity,
        "zones": zones, "note": note,
    }


def rr_stream(aid, sample=False):
    """Baja los intervalos RR (latido a latido, en ms) de una salida.

    Con la banda HRM 600 el stream 'hrv' trae los RR. Devuelve (rr_ms, hr) o
    (None, None) si la salida no tiene RR. `sample=True` imprime el formato del
    stream (para verificar en el log del workflow)."""
    try:
        streams = get(f"/activity/{aid}/streams", types="time,heartrate,hrv")
    except Exception as e:
        print(f"DFA: no pude bajar streams RR de {aid}: {e}")
        return None, None
    if not isinstance(streams, list):
        return None, None
    rr = hr = None
    for s in streams:
        t = s.get("type")
        if t in ("hrv", "rr", "rrIntervals"):
            rr = s.get("data")
        elif t == "heartrate":
            hr = s.get("data")
    if sample and rr:
        head = [x for x in rr[:12]]
        print(f"DFA muestra RR de {aid}: n={len(rr)} primeros={head} "
              f"(unidad {'s' if head and max(x for x in head if x) < 5 else 'ms'})")
    if not rr:
        return None, None
    # intervals.icu puede entregar RR en segundos o milisegundos: normalizo a ms
    vals = [x for x in rr if isinstance(x, (int, float)) and x > 0]
    if vals and (sum(vals) / len(vals)) < 5:  # media <5 → está en segundos
        rr = [x * 1000 if isinstance(x, (int, float)) else x for x in rr]
    return rr, hr


def compute_dfa(rides, max_downloads=6):
    """DFA a1 sobre las últimas salidas con RR (banda HRM 600).

    - AeT (VT1) = FC donde a1≈0.75 (techo real de Z2), de la salida más reciente
      que cruce el umbral; arma la tendencia con las demás.
    - last_alpha1 = a1 del tramo fácil de la última salida (durabilidad/fatiga).
    - Devuelve None si ninguna salida trae RR (banda no usada esa vez).
    """
    if dfa_mod is None or not rides:
        return None
    trend = []
    last_alpha1 = None
    last_interp = ""
    aet_hr = vt2_hr = None
    quality = "sin datos"
    source_date = None
    downloads = 0
    for i, r in enumerate(rides):
        if downloads >= max_downloads:
            break
        rr, hr = rr_stream(r.get("id"), sample=(downloads == 0))
        if not rr:
            continue
        downloads += 1
        res = dfa_mod.analizar(rr, hr)
        # anota la salida (misma referencia que va en data["rides"]) con su α1
        r["dfa_alpha1"] = res.get("last_alpha1")
        if res.get("aet_hr"):
            r["dfa_aet_hr"] = res.get("aet_hr")
        if last_alpha1 is None and res.get("last_alpha1") is not None:
            last_alpha1 = res["last_alpha1"]
            last_interp = dfa_mod.interpretar(last_alpha1)
        aet = res.get("aet_hr")
        if aet:
            trend.append({"date": r.get("date"), "aet": aet})
            if aet_hr is None:  # la más reciente válida = AeT actual
                aet_hr = aet
                vt2_hr = res.get("vt2_hr")
                quality = res.get("quality", "baja")
                source_date = r.get("date")
    if last_alpha1 is None and not aet_hr:
        return None
    trend = list(reversed(trend))  # cronológico para el sparkline
    note = ("El valor más confiable sale del test de rampa suave con la banda puesta. "
            "AeT = techo real de tu Z2 (α1≈0.75); α1 de la última salida mide durabilidad "
            "(≥0.9 muy fresco · ~0.75 en umbral · <0.5 intenso).")
    out = {
        "aet_hr": aet_hr, "vt2_hr": vt2_hr,
        "last_alpha1": last_alpha1, "interpretacion": last_interp,
        "trend": trend, "quality": quality,
        "source": source_date, "rides_with_rr": downloads, "note": note,
    }
    print(f"DFA: {json.dumps(out, ensure_ascii=False)}")
    return out


def suggest_route(plan, rides):
    """Recomienda una ruta propia ya hecha que encaje con el entreno de hoy.

    Series/tempo → la más llana; fondo → la más larga/con subidas.
    Incluye el objetivo de superar la vez anterior.
    """
    candidates = [r for r in rides if r.get("distance_km") and r["distance_km"] >= 10
                  and r.get("elevation_m") is not None and r.get("moving_time_s")]
    if not candidates or plan["kind"] in ("descanso", "sin_datos"):
        return None

    def hilliness(r):
        return r["elevation_m"] / r["distance_km"]  # m de subida por km

    if plan["kind"] in ("intensidad", "tempo"):
        pick = min(candidates, key=hilliness)
        reason = (f"tu ruta más rodadora ({hilliness(pick):.0f} m de desnivel por km): "
                  "ideal para hacer los bloques sin cortes")
    elif plan["kind"] == "resistencia":
        pick = max(candidates, key=lambda r: (r["distance_km"], hilliness(r)))
        reason = "tu ruta más larga: perfecta para el fondo en Z2"
    else:  # suave
        pick = min(candidates, key=lambda r: r["distance_km"])
        reason = "tu ruta más corta, para rodar suave sin exigirte"

    mins = pick["moving_time_s"] / 60
    return {
        "name": pick.get("name"),
        "date": pick.get("date"),
        "distance_km": pick.get("distance_km"),
        "elevation_m": round(pick.get("elevation_m") or 0),
        "last_time_min": round(mins),
        "reason": reason,
        "challenge": f"La última vez ({pick.get('date')}) la hiciste en {round(mins)} min "
                     f"— si el plan es de calidad, intentá mejorar ese tiempo en los tramos duros.",
    }


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


COMP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "composicion.json")
SALUD_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "salud.json")
MEDIDAS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "medidas.json")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"AVISO: no pude leer {os.path.basename(path)} ({e})")
        return default


def sync_peso_medidas(medidas, weight_last):
    """Mantiene la medida 'peso' en sincronía con el último peso conocido."""
    if weight_last:
        for m in medidas:
            if m.get("key") == "peso":
                m["value"] = weight_last
    return medidas


def merge_manual_composition(days):
    """Fusiona las mediciones de composición cargadas a mano (balanza Femmto)
    en el diccionario de días, para que el resto del pipeline (tendencias,
    objetivos, guardarraíl REDs) las use como si vinieran de Garmin."""
    try:
        with open(COMP_PATH, encoding="utf-8") as f:
            entries = json.load(f)
    except Exception as e:
        print(f"AVISO: sin composición manual ({e})")
        return
    for e in sorted(entries, key=lambda x: x.get("date", "")):
        d = e.get("date")
        if not d:
            continue
        day = days.setdefault(d, {"date": d})
        for k in ("weight", "body_fat", "fat_mass", "lean", "muscle"):
            v = e.get(k)
            if v is not None and day.get(k) is None:
                day[k] = v
        if day.get("lean") is None and day.get("weight") and day.get("fat_mass") is not None:
            day["lean"] = round(day["weight"] - day["fat_mass"], 1)
    last = max(entries, key=lambda x: x.get("date", "")) if entries else {}
    print(f"Composición manual: {len(entries)} medición(es); última {last.get('date')} "
          f"→ grasa {last.get('body_fat')}% · músculo {last.get('muscle')} kg")
    return last


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
            "weight": num(w.get("weight")),
            "body_fat": num(w.get("bodyFat")),
            "fat_mass": num(w.get("fatTotal")),
            "vo2max": num(w.get("vo2max")),
            "stress": num(w.get("stress")),
            "hydration_ml": num(w.get("hydrationVolume")) or num(w.get("hydration")),
        }
        # masa magra (músculo + resto no graso): de fatTotal si está, si no de %grasa
        wt, bf, fm = days[d]["weight"], days[d]["body_fat"], days[d]["fat_mass"]
        if wt and fm is not None:
            days[d]["lean"] = round(wt - fm, 1)
        elif wt and bf is not None:
            days[d]["fat_mass"] = round(wt * bf / 100, 1)
            days[d]["lean"] = round(wt * (1 - bf / 100), 1)
        else:
            days[d]["lean"] = None
        days[d]["muscle"] = None

    # ---------- fusionar composición manual (balanza Femmto): la balanza no
    # sincroniza sola con Garmin, así que estas mediciones se cargan a mano.
    # Rellenan lo que intervals no trajo; si algún día la balanza llega a
    # Garmin, ese dato real tiene prioridad.
    comp_meta = merge_manual_composition(days) or {}

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
            "rpe": num(a.get("perceived_exertion") or a.get("icu_rpe")),
            "feel": num(a.get("feel")),
            "cadence": num(a.get("average_cadence")),
            "calories": num(a.get("calories")),
            "decoupling": num(a.get("decoupling")),
            "respiration": num(a.get("average_respiration") or a.get("avg_respiration")
                               or a.get("respiration")),
            "zone_times": (a.get("icu_hr_zone_times") or a.get("hr_zone_times")
                           or a.get("icu_zone_times") or None),
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
    vo2s = recent("vo2max", 90)
    vo2_last = round(vo2s[0], 1) if vo2s else None
    vo2_delta90 = round(vo2s[0] - vo2s[-1], 1) if len(vo2s) >= 2 else None
    weights = recent("weight", 90)
    weight_last = round(weights[0], 1) if weights else None
    weight7 = avg(weights[:7]) if weights else None
    # cambio en ~30 días: promedio de la semana más vieja disponible vs. la última
    weight_delta30 = None
    if len(weights) >= 8:
        old = weights[7:35] or weights[7:]
        weight_delta30 = round((sum(weights[:7]) / len(weights[:7])) - (sum(old) / len(old)), 1)

    # ---- composición corporal (de la balanza inteligente, vía Garmin)
    def delta30(series):
        if len(series) < 8:
            return None
        old = series[7:35] or series[7:]
        return round((sum(series[:7]) / len(series[:7])) - (sum(old) / len(old)), 1)

    bfs = recent("body_fat", 90)
    body_fat_last = round(bfs[0], 1) if bfs else None
    body_fat7 = avg(bfs[:7]) if bfs else None
    body_fat_delta30 = delta30(bfs)
    leans = recent("lean", 90)
    lean_last = round(leans[0], 1) if leans else None
    lean7 = avg(leans[:7]) if leans else None
    lean_delta30 = delta30(leans)
    fats = recent("fat_mass", 90)
    fat_mass_last = round(fats[0], 1) if fats else None
    fat_mass_delta30 = delta30(fats)
    muscles = recent("muscle", 90)
    muscle_last = round(muscles[0], 1) if muscles else None
    muscle_delta30 = delta30(muscles)

    # valores de partida (el dato más viejo disponible) para medir progreso a objetivos
    body_fat_start = round(bfs[-1], 1) if bfs else None
    weight_start = round(weights[-1], 1) if weights else None
    vo2_start = round(vo2s[-1], 1) if vo2s else None

    # ritmo de pérdida de peso semana a semana (%/sem) para el guardarraíl REDs
    weight_wk_pct = None
    if len(weights) >= 14:
        last7, prev7 = sum(weights[:7]) / 7, sum(weights[7:14]) / 7
        if prev7:
            weight_wk_pct = round((last7 - prev7) / prev7 * 100, 2)

    stress7 = avg(recent("stress", 7))
    rhr3 = avg(recent("resting_hr", 3))
    hrv3 = avg(recent("hrv", 3))
    stress3 = avg(recent("stress", 3))
    sleep3 = avg(recent("sleep_secs", 3))
    today_w = days.get(TODAY.isoformat(), {})
    yesterday_w = days.get((TODAY - timedelta(days=1)).isoformat(), {})
    hrv_today = today_w.get("hrv") or yesterday_w.get("hrv")
    sleep_today = today_w.get("sleep_secs")
    sleep_score_today = today_w.get("sleep_score")
    readiness_today = today_w.get("readiness")

    current = series[-1] if series else {}
    ctl_now, atl_now = current.get("ctl"), current.get("atl")
    tsb_now = current.get("tsb")

    rhr_last = today_w.get("resting_hr") or yesterday_w.get("resting_hr")
    hydration_today = today_w.get("hydration_ml") or yesterday_w.get("hydration_ml")
    health = health_signals(rhr3, rhr30, rhr_last, hrv3, hrv30,
                            stress3, stress7, sleep3, tsb_now,
                            weight_last, weight7, hydration_today, day_load(1),
                            weight_wk_pct=weight_wk_pct)
    print(f"Composición: {json.dumps({'body_fat': body_fat_last, 'fat_mass': fat_mass_last, 'lean': lean_last, 'muscle': muscle_last, 'bf_delta30': body_fat_delta30, 'lean_delta30': lean_delta30, 'weight_wk_pct': weight_wk_pct}, ensure_ascii=False)}")

    # ---------- calidad (se calcula antes del plan para respetar el 80/20)
    quality = training_quality(activities, load_by_day)
    print(f"Calidad: {json.dumps(quality, ensure_ascii=False)}")

    # ---------- macro-periodización (marco de la temporada, anclado a tu CTL)
    fase = fase_actual(TODAY, ctl=ctl_now, chronic_weekly=chronic if chronic else None)
    print(f"Periodización: {json.dumps(fase, ensure_ascii=False)}")

    # ---------- checklist de sobreentrenamiento (semáforo) — antes del plan,
    # para que los días fáciles respeten "lo que diga el semáforo"
    overtraining = overtraining_check(
        rhr3, rhr30, hrv3, hrv30, tsb_now, quality.get("monotony"), acwr, sleep3)
    print(f"Sobreentrenamiento: {json.dumps(overtraining, ensure_ascii=False)}")

    # ---------- plan del día (fase 3: decisión basada en datos)
    plan = make_plan(
        tsb=tsb_now, acwr=acwr, acute=acute, chronic=chronic,
        hrv_today=hrv_today, hrv30=hrv30, sleep_secs=sleep_today,
        sleep_score=sleep_score_today, readiness=readiness_today,
        load_recent=[day_load(i) for i in range(7)],
        polar=quality.get("polarization"), fase=fase,
        ot_level=overtraining.get("level"),
    )
    plan["route"] = suggest_route(plan, rides)
    plan["nutrition"] = nutrition_tips(plan["kind"], weight=weight_last)
    plan["evidencia"] = evidencia_para_plan(plan["kind"])
    plan["fase"] = {"nombre": fase["fase"], "semana_global": fase["semana_global"],
                    "total_semanas": fase["total_semanas"], "deload": fase["deload"]}
    lthr_est = estimate_lthr(rides)
    if lthr_est:
        print(f"LTHR estimado: {json.dumps(lthr_est, ensure_ascii=False)}")

    # ---- carga subjetiva (sRPE) desde el RPE/Feel que cargás en el reloj
    rpe_rides = [r for r in rides if r.get("rpe") and r.get("moving_time_s")]
    srpe_7d = sum(r["rpe"] * (r["moving_time_s"] / 60) for r in rpe_rides
                  if r["date"] >= (TODAY - timedelta(days=6)).isoformat())
    last_rpe = next((r for r in rides if r.get("rpe")), None)
    cads = [r["cadence"] for r in rides[:10] if r.get("cadence")]
    cadence_avg = round(sum(cads) / len(cads)) if cads else None
    subjective = {
        "rpe_filled": len(rpe_rides),
        "rpe_total": len(rides),
        "last_rpe": last_rpe.get("rpe") if last_rpe else None,
        "last_feel": last_rpe.get("feel") if last_rpe else None,
        "last_date": last_rpe.get("date") if last_rpe else None,
        "srpe_7d": round(srpe_7d) if srpe_7d else None,
        "cadence_avg": cadence_avg,
    }
    print(f"Subjetivo (RPE/Feel): {json.dumps(subjective, ensure_ascii=False)}")

    # ---- DFA a1 (banda HRM 600): umbral aeróbico por variabilidad + durabilidad
    dfa = compute_dfa(rides)

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
            "weight": weight_last, "weight7": weight7, "weight_delta30": weight_delta30,
            "body_fat": body_fat_last, "body_fat7": body_fat7, "body_fat_delta30": body_fat_delta30,
            "fat_mass": fat_mass_last, "fat_mass_delta30": fat_mass_delta30,
            "lean": lean_last, "lean7": lean7, "lean_delta30": lean_delta30,
            "muscle": muscle_last, "muscle_delta30": muscle_delta30,
            "comp_date": comp_meta.get("date"), "comp_source": comp_meta.get("source"),
            "vo2max": vo2_last, "vo2max_delta90": vo2_delta90,
            "stress": today_w.get("stress") or yesterday_w.get("stress"), "stress7": stress7,
        },
        "plan": plan,
        "goals": make_goals({
            "ctl": ctl_now, "vo2max": vo2_last, "weight": weight_last,
            "body_fat": body_fat_last, "lean": lean_last,
            "ctl_start": series[0]["ctl"] if series else ctl_now,
            "vo2max_start": vo2_start, "weight_start": weight_start,
            "body_fat_start": body_fat_start,
        }),
        "health": health,
        "overtraining": overtraining,
        "lthr": lthr_est,
        "dfa": dfa,
        "quality": quality,
        "subjective": subjective,
        "alerts": alerts,
        "periodizacion": {"actual": fase, "mapa": mapa_temporada(TODAY)},
        "salud": load_json(SALUD_PATH, []),
        "medidas": sync_peso_medidas(load_json(MEDIDAS_PATH, []), weight_last),
        "evidencia": evidencia_agrupada(),
        "series": series,
        "rides": rides[:60],
        "counts": {"rides_180d": len(rides), "wellness_days": len(days)},
    }


def nutrition_tips(kind, weight=None):
    """Guía nutricional del día según el entreno, basada en la estrategia de
    la Lic. Zalazar (plan personal del atleta): fórmulas de comidas, timing
    pre/intra/post y regla de las 3R. En días fáciles suma el marco de déficit
    moderado con proteína alta para perder grasa preservando músculo."""
    base = [
        "Agua: 3 litros en el día (orina clara como control).",
        "Almuerzo y cena: 50% del plato de verduras (3 colores, al menos 1 tipo B) + proteína magra + hidratos de calidad (legumbres/granos de tu guía).",
    ]
    # objetivo de proteína para preservar músculo en el déficit (1.6-2.0 g/kg)
    prot = ""
    if weight:
        prot = (f" Apuntá a ~{round(weight*1.6)}-{round(weight*2.0)} g de proteína en el día "
                "(repartida en las comidas): es lo que preserva el músculo cuando comés en déficit "
                "(ISSN; Mettler 2010; Witard 2019).")
    if kind in ("descanso", "sin_datos", "suave"):
        return base + [
            "Día liviano = ventana para el déficit: hidratos en cantidad INFERIOR en almuerzo; sin extras energéticos (frutos secos/pasta de maní solo si hay hambre real)." + prot,
            "Priorizá proteína en cada comida y el Z2 suave: es el mejor quema-grasa sostenible sin robarle recuperación al entrenamiento.",
            "Desayuno/merienda: fruta + proteína + lácteo descremado + hidrato integral.",
        ]
    if kind == "resistencia":
        return base + [
            "CENA de la noche anterior al fondo: hidratos en cantidad SUPERIOR y de fácil digestión (arroz o fideos de arroz) + huevos o queso magro. Carga previa 24 h: 7-12 g de hidratos por kg (Oosthuyse, nutrición MTB).",
            "Desayuno 2 h antes: pan blanco o discos de arroz + mermelada/membrillo + 1 huevo + 1 fruta. Si tenés menos de 1 h: sacá proteína y fibra.",
            "DURANTE (dosis por hora, evidencia MTB — Oosthuyse): hasta 2.5 h de salida → 30-60 g de hidratos/hora; si pasás de 2.5 h → 60-90 g/hora combinando fuentes (maltodextrina + fructosa ~2:1) para absorber más sin cortar la panza.",
            "En fondos MUY largos (>3-4 h) sumá 10-15 g de proteína/hora: reduce el daño muscular. En calor, la bebida con hidratos + sodio (una pizca de sal) también cuida la hidratación.",
            "Café/cafeína antes o a mitad de salida larga: 3-6 mg por kg de peso mejora el rendimiento y baja la percepción de esfuerzo.",
            "Traducción práctica a tu comida real: 1 cuadradito de membrillo ≈ 30 g de hidratos; 40 g de pasas ≈ 30 g. Para llegar a 60 g/hora en fondos largos: 1 membrillo + 1 puñado de pasas o 1 isotónica cada hora.",
            "Post (3R): rehidratar con agua (1.5-2 L en la primera hora y media) + 2 frutas + 1 scoop de proteína; después la comida principal. Ventana 1-2 h: ~1-1.2 g hidratos/kg + 20-30 g de proteína.",
        ]
    # intensidad / tempo / test
    return base + [
        "Pre entreno intenso: NADA de lácteos antes de la bici; proteína de fácil digestión (huevo o pescado) en la comida previa; ingesta completa 1:30-2 h antes.",
        "Llevá por las dudas: un cuadradito de membrillo o puñado de pasas. Café pre entreno recomendado: 3-6 mg de cafeína por kg (para vos ~1 taza cargada o 2 comunes) 45-60 min antes mejora rendimiento y baja el esfuerzo percibido.",
        "Post (3R): agua + 1 fruta apenas bajás de la bici + proteína (huevo, claras o scoop).",
    ]


def make_goals(today):
    """Objetivos con plazo, calculados desde los valores actuales."""
    goals = []
    horizon = (TODAY + timedelta(weeks=12)).isoformat()
    ctl = today.get("ctl")
    if ctl is not None:
        start = today.get("ctl_start") or ctl
        goals.append({
            "metric": "Fitness (CTL)", "unit": "",
            "current": ctl, "start": round(start, 1), "target": round(min(start + 14, 85)), "by": horizon, "dir": "up",
            "note": "Subida segura: ~5-7 puntos por mes, sin pasar ACWR 1.3.",
        })
    vo2 = today.get("vo2max")
    if vo2 is not None:
        start = today.get("vo2max_start") or vo2
        goals.append({
            "metric": "VO2max (est. Garmin)", "unit": "",
            "current": vo2, "start": start, "target": round(start * 1.06, 1), "by": horizon, "dir": "up",
            "note": "+6% en 12 semanas es realista entrenando polarizado; el techo lo pone la genética, y a ese techo se llega tras años, no meses.",
        })
    w = today.get("weight")
    if w is not None:
        start = today.get("weight_start") or w
        goals.append({
            "metric": "Peso", "unit": "kg",
            "current": w, "start": start, "target": round(start - 7, 1), "by": horizon, "dir": "down",
            "note": "-0.5%/semana: el objetivo es bajar GRASA, no músculo. En MTB cada kg de grasa menos es potencia/kg gratis.",
        })
    else:
        goals.append({
            "metric": "Peso", "current": None, "target": None, "by": None,
            "note": "Cargá tu peso en Garmin Connect (2-3 veces/semana, en ayunas) y el objetivo se calcula solo.",
        })
    bf = today.get("body_fat")
    if bf is not None:
        start = today.get("body_fat_start") or bf
        goals.append({
            "metric": "% de grasa", "unit": "%",
            "current": bf, "start": start, "target": round(max(start - 5, 12), 1), "by": horizon, "dir": "down",
            "note": "Es la grasa la que baja tu potencia/kg, no el músculo (Arriel 2020; de Moura 2025). Bajar ~5 puntos es un objetivo realista y seguro (~0.5%/sem de peso).",
        })
    else:
        goals.append({
            "metric": "% de grasa", "current": None, "target": None, "by": None,
            "note": "Pesate en tu balanza Femmto 2-3 veces/semana (en ayunas): cuando el % de grasa llegue a intervals.icu, el objetivo se calcula solo.",
        })
    lean = today.get("lean")
    if lean is not None:
        goals.append({
            "metric": "Masa magra (músculo)", "unit": "kg",
            "current": lean, "start": lean, "target": lean, "by": horizon, "dir": "keep",
            "note": "Objetivo: MANTENERLA (o subir levemente) mientras baja la grasa. Se logra con proteína 1.6-2.0 g/kg y sin déficit en días duros (ISSN; IOC-REDs).",
        })
    goals.append({
        "metric": "Umbral (LTHR)",
        "current": None, "target": None, "by": None,
        "note": "Se mide con el test de 30 min cada 4 semanas: es el checkpoint objetivo de progreso.",
    })
    return goals


def health_signals(rhr3, rhr30, rhr_last, hrv3, hrv30, stress3, stress7,
                   sleep3_secs, tsb, weight_last, weight7, hydration_ml,
                   yesterday_load, weight_wk_pct=None):
    """TAMIZAJE (no diagnóstico): marca desvíos respecto a la línea de base
    del propio atleta que ameritan atención o consulta médica.

    Umbrales de la literatura de monitoreo de carga (FC reposo, HRV, sueño).
    NUNCA afirma una enfermedad: sólo señala 'algo cambió, prestá atención'.
    """
    flags = []
    rhr_up = (rhr3 - rhr30) if (rhr3 is not None and rhr30 is not None) else None
    hrv_pct = ((hrv3 - hrv30) / hrv30 * 100) if (hrv3 and hrv30 and hrv30 > 0) else None

    # 1) Taquicardia en reposo (bandera roja objetiva)
    if rhr_last is not None and rhr_last > 100:
        flags.append({"level": "critical",
            "text": f"FC en reposo {rhr_last:.0f} lpm (por encima de 100 = taquicardia en reposo). "
                    "Si se mantiene o tenés síntomas (palpitaciones, mareo, falta de aire), consultá a un médico."})

    # 2) FC en reposo elevada vs tu baseline
    if rhr_up is not None and rhr_up >= 12:
        flags.append({"level": "serious",
            "text": f"Tu FC en reposo de los últimos 3 días ({rhr3:.0f} lpm) está {rhr_up:.0f} lpm por encima de "
                    f"tu baseline de 30 días ({rhr30:.0f}). Causas frecuentes: infección/gripe en curso, "
                    "sobreentrenamiento, deshidratación, alcohol o estrés. Si dura más de 3 días o te sentís mal, consultá a un médico."})
    elif rhr_up is not None and rhr_up >= 7:
        flags.append({"level": "warning",
            "text": f"FC en reposo algo elevada ({rhr3:.0f} vs baseline {rhr30:.0f} lpm, +{rhr_up:.0f}). "
                    "Suele ser fatiga, poco sueño, estrés o el inicio de un resfrío. Bajá la intensidad y vigilá."})

    # 3) HRV deprimida
    if hrv_pct is not None and hrv_pct <= -15:
        flags.append({"level": "serious",
            "text": f"Tu HRV de 3 días ({hrv3:.0f} ms) está {abs(hrv_pct):.0f}% por debajo de tu baseline "
                    f"({hrv30:.0f} ms): recuperación comprometida o estrés fisiológico marcado."})
    elif hrv_pct is not None and hrv_pct <= -10:
        flags.append({"level": "warning",
            "text": f"HRV por debajo de lo habitual ({hrv3:.0f} vs {hrv30:.0f} ms). Priorizá descanso y sueño."})

    # 4) Sueño insuficiente sostenido
    if sleep3_secs is not None and sleep3_secs < 6 * 3600:
        flags.append({"level": "warning",
            "text": f"Vienes durmiendo poco (promedio {sleep3_secs/3600:.1f} h en 3 días). "
                    "El sueño es donde el cuerpo repara: menos de 6 h sostenido sube el riesgo de lesión y enfermedad."})

    # 5) Estrés fisiológico alto (Garmin, 0-100)
    if stress3 is not None and stress3 > 55:
        flags.append({"level": "info",
            "text": f"Estrés promedio alto (últimos 3 días: {stress3:.0f}/100). Sumá recuperación activa, respiración y buena hidratación."})

    # 6) Patrón combinado sugestivo de sobreentrenamiento / enfermedad incubando
    if (rhr_up is not None and rhr_up >= 5 and hrv_pct is not None and hrv_pct <= -8
            and tsb is not None and tsb < -15):
        flags.append({"level": "serious",
            "text": "Patrón combinado: FC en reposo ↑, HRV ↓ y fatiga alta (TSB muy negativo) a la vez. "
                    "Es la firma clásica de sobreentrenamiento o de estar incubando algo. Tomate 2-3 días muy suaves; "
                    "si aparecen fiebre, dolores o malestar, consultá a un médico."})

    # 7) DESHIDRATACIÓN — pérdida aguda de peso >2% vs tu semana (umbral ACSM)
    if weight_last is not None and weight7 is not None and weight7 > 0:
        drop_pct = (weight7 - weight_last) / weight7 * 100
        if drop_pct >= 2:
            flags.append({"level": "warning",
                "text": f"Posible deshidratación: tu peso de hoy ({weight_last:.1f} kg) está {drop_pct:.1f}% por debajo "
                        f"de tu promedio de la semana ({weight7:.1f} kg). Por encima del 2% ya cae el rendimiento (ACSM). "
                        "Rehidratá con agua + sales y controlá el color de la orina."})

    # 8) Hidratación registrada por debajo de la meta
    if hydration_ml is not None and hydration_ml > 0 and hydration_ml < 2000:
        flags.append({"level": "info",
            "text": f"Tomaste {hydration_ml/1000:.1f} L registrados hoy, por debajo de tu meta de 3 L. Sumá líquidos."})

    # 9) BAJA DISPONIBILIDAD ENERGÉTICA (REDs): peso bajando rápido (>1%/sem)
    #    JUNTO CON señales de fatiga fisiológica. Red de seguridad para que el
    #    déficit no se convierta en pérdida de rendimiento/salud (IOC-REDs; Woods 2018).
    if weight_wk_pct is not None and weight_wk_pct <= -1.0 and (
            (rhr_up is not None and rhr_up >= 5) or (hrv_pct is not None and hrv_pct <= -8)):
        flags.append({"level": "serious",
            "text": f"Posible baja disponibilidad energética: estás bajando peso rápido "
                    f"({abs(weight_wk_pct):.1f}%/semana, más que el objetivo de 0.5%) y con señales de fatiga "
                    "(FC en reposo ↑ o HRV ↓). Comé MÁS, sobre todo alrededor de los días de carga: el déficit "
                    "va solo en días suaves. Bajar demasiado rápido hace perder músculo y rendimiento, no grasa."})

    # ---------- sugerencias de hidratación (siempre visibles, contextuales)
    suggestions = [
        "Meta: 3 L de agua en el día; más en días de calor o de fondo largo.",
        "Control de orina: amarillo pálido = bien hidratado; oscura = tomá 250-500 mL y esperá 20 min.",
    ]
    if yesterday_load is not None and yesterday_load >= 100:
        suggestions.append("Ayer fue día de carga alta: reponé líquidos Y sales hoy (isotónica o agua con una pizca de sal y limón).")
    if hydration_ml is not None and hydration_ml >= 3000:
        suggestions.insert(0, f"✅ Vas bien: {hydration_ml/1000:.1f} L registrados hoy.")

    return {"flags": flags, "suggestions": suggestions}


def overtraining_check(rhr3, rhr30, hrv3, hrv30, tsb, monotony, acwr, sleep3_secs):
    """Semáforo de sobreentrenamiento: junta las señales validadas de monitoreo
    de carga en un tablero único (verde/ámbar/rojo). No diagnostica: resume si
    el cuerpo está asimilando bien o pidiendo freno.

    Cada ítem: 0 = ok (verde), 1 = atención (ámbar), 2 = alerta (rojo).
    Umbrales de la literatura de monitoreo (FC reposo, HRV, TSB, monotonía de
    Foster, ACWR de Gabbett, sueño)."""
    items = []

    def add(label, level, detail):
        items.append({"label": label, "level": level, "detail": detail})

    # 1) FC en reposo vs baseline
    if rhr3 is not None and rhr30 is not None:
        d = rhr3 - rhr30
        if d >= 10:
            add("FC en reposo", 2, f"+{d:.0f} lpm sobre tu baseline ({rhr3:.0f} vs {rhr30:.0f}). Muy elevada.")
        elif d >= 5:
            add("FC en reposo", 1, f"+{d:.0f} lpm sobre tu baseline ({rhr3:.0f} vs {rhr30:.0f}). Algo alta.")
        else:
            add("FC en reposo", 0, f"En rango ({rhr3:.0f} vs baseline {rhr30:.0f} lpm).")

    # 2) HRV vs baseline
    if hrv3 and hrv30 and hrv30 > 0:
        pct = (hrv3 - hrv30) / hrv30 * 100
        if pct <= -10:
            add("HRV", 2, f"{abs(pct):.0f}% por debajo de tu baseline ({hrv3:.0f} vs {hrv30:.0f} ms). Recuperación comprometida.")
        elif pct <= -5:
            add("HRV", 1, f"{abs(pct):.0f}% por debajo de tu baseline ({hrv3:.0f} vs {hrv30:.0f} ms).")
        else:
            add("HRV", 0, f"En rango ({hrv3:.0f} vs baseline {hrv30:.0f} ms).")

    # 3) TSB (forma / fatiga acumulada)
    if tsb is not None:
        if tsb < -30:
            add("Forma (TSB)", 2, f"{tsb:.0f}: fatiga acumulada muy alta.")
        elif tsb < -20:
            add("Forma (TSB)", 1, f"{tsb:.0f}: venís bastante cargado.")
        else:
            add("Forma (TSB)", 0, f"{tsb:.0f}: fatiga bajo control.")

    # 4) Monotonía de Foster (variación día a día)
    if monotony is not None:
        if monotony > 2:
            add("Monotonía", 2, f"{monotony}: carga muy repetitiva (>2). Sube el riesgo de enfermedad.")
        elif monotony >= 1.5:
            add("Monotonía", 1, f"{monotony}: poca variación entre días (1.5–2).")
        else:
            add("Monotonía", 0, f"{monotony}: buena alternancia de días duros y suaves.")

    # 5) ACWR (aguda/crónica, Gabbett)
    if acwr is not None:
        if acwr > 1.5:
            add("Carga (ACWR)", 2, f"{acwr}: subiste la carga demasiado rápido (>1.5).")
        elif acwr > 1.3:
            add("Carga (ACWR)", 1, f"{acwr}: zona de precaución (1.3–1.5).")
        else:
            add("Carga (ACWR)", 0, f"{acwr}: progresión de carga segura.")

    # 6) Sueño (promedio 3 días)
    if sleep3_secs is not None:
        h = sleep3_secs / 3600
        if h < 6:
            add("Sueño", 2, f"{h:.1f} h de promedio (3 días): insuficiente para recuperar.")
        elif h < 7:
            add("Sueño", 1, f"{h:.1f} h de promedio: un poco justo.")
        else:
            add("Sueño", 0, f"{h:.1f} h de promedio: bien.")

    reds = sum(1 for i in items if i["level"] == 2)
    ambers = sum(1 for i in items if i["level"] == 1)
    if reds >= 2:
        level, summary = "red", "Varias señales en rojo: el cuerpo pide freno. 2–3 días muy suaves y revisá sueño e hidratación."
    elif reds == 1 or ambers >= 2:
        level, summary = "amber", "Algunas señales pidiendo atención. Bajá un cambio hoy y priorizá recuperación."
    elif not items:
        level, summary = "amber", "Todavía sin datos suficientes para el semáforo (faltan FC reposo/HRV/sueño)."
    else:
        level, summary = "green", "Todas las señales en verde: estás asimilando bien la carga. Vía libre para entrenar."

    return {"level": level, "summary": summary, "items": items,
            "reds": reds, "ambers": ambers}


def make_plan(tsb, acwr, acute, chronic, hrv_today, hrv30, sleep_secs,
              sleep_score, readiness, load_recent, polar=None, fase=None, ot_level=None):
    """Decide el entreno de hoy y lo justifica con los números."""
    # Sin historial suficiente no se recomienda nada: sería inventar.
    if not chronic or chronic <= 0:
        return {
            "kind": "sin_datos",
            "title": "Recopilando tus datos…",
            "steps": [{
                "phase": "Todavía no hay recomendación",
                "desc": "Tus salidas todavía no llegaron desde Garmin a intervals.icu. "
                        "La importación ya está en curso y Garmin las manda de a poco (puede "
                        "tardar horas) — no hace falta hacer nada, solo esperar. En cuanto "
                        "haya historial de salidas, el plan diario se activa solo.",
            }],
            "est_load": 0,
            "why": ["Sin carga crónica (promedio de las últimas 4 semanas) no se puede dosificar "
                    "un entreno de forma segura ni útil."],
        }
    why = []
    flags_bad = 0

    if fase:
        why.append(f"Fase de temporada: {fase.get('fase','')} · semana "
                   f"{fase.get('semana_global','?')}/{fase.get('total_semanas','?')}"
                   f"{' (descarga)' if fase.get('deload') else ''}. {fase.get('foco','')}")

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

    # frecuencia objetivo (preferencia del atleta): al llegar al tope de días
    # pedaleados de la semana, el día extra depende del semáforo:
    #   verde  → recuperación activa Z2 real (no descanso pelado)
    #   ámbar/rojo → descanso total
    days_ridden = sum(1 for load in load_recent if load and load > 0)
    yesterday_load = load_recent[1] if len(load_recent) > 1 else 0
    if days_ridden >= DIAS_OBJETIVO and flags_bad < 3:
        if ot_level == "green":
            why.append(f"Ya pedaleaste {days_ridden} de los últimos 7 días (tu objetivo son {DIAS_OBJETIVO}), "
                       "pero el semáforo está verde: en vez de parar del todo, rodaje suave regenerativo "
                       "que suma volumen aeróbico sin robar recuperación.")
            return {
                "kind": "suave",
                "title": f"Recuperación activa Z2 ({DUR_SUAVE})",
                "steps": [
                    {"phase": "Calentamiento", "desc": "10 min en Z1, cadencia cómoda."},
                    {"phase": "Bloque principal", "desc": f"{DUR_SUAVE} en Z2 baja, terreno llano o rodador. Tenés que poder charlar de corrido; nada de subidas fuertes."},
                    {"phase": "Vuelta a la calma", "desc": "5-10 min en Z1."},
                ],
                "est_load": 40, "why": why,
                "workout_text": "Calentamiento\n- 10m Z1 HR\n\nRodaje regenerativo\n- 45m Z2 HR\n\nVuelta a la calma\n- 5m Z1 HR",
            }
        why.append(f"Ya pedaleaste {days_ridden} de los últimos 7 días (tu objetivo son {DIAS_OBJETIVO}) "
                   "y el semáforo no está en verde: hoy toca descanso, ahí es donde el cuerpo asimila.")
        return {
            "kind": "descanso",
            "title": "Día de descanso programado",
            "steps": [
                {"phase": "Opción A", "desc": "Descanso total (recomendado hoy)."},
                {"phase": "Opción B", "desc": f"Si querés mover las piernas: rodaje MUY suave {DUR_SUAVE} en Z1, sin exigencia."},
            ],
            "est_load": 0, "why": why, "workout_text": "",
        }

    # semana de test (cada 4 semanas, miércoles): test de umbral de Friel,
    # solo en frescura — un test con fatiga da un umbral falso y arruina las zonas
    is_test_slot = TODAY.isocalendar()[1] % 4 == 0 and TODAY.weekday() == 2
    if is_test_slot and flags_bad == 0 and (tsb is None or tsb > -10):
        why.append("Toca test de umbral (cada 4 semanas): tus métricas de hoy muestran frescura, "
                   "condición necesaria para que el resultado sea válido y recalibrar tus zonas de FC.")
        return {
            "kind": "test",
            "title": "Test de umbral 30 min (protocolo Friel)",
            "steps": [
                {"phase": "Calentamiento", "desc": "15 min progresivos Z1 → Z3 con 2 aceleraciones cortas."},
                {"phase": "Test", "desc": "30 min al MÁXIMO ritmo que puedas SOSTENER completo (como una carrera individual). "
                                          "Apretá el botón LAP al minuto 10: tu FC promedio de los últimos 20 min es tu umbral (LTHR). "
                                          "Terreno: subida constante o camino sin cortes, sin tráfico."},
                {"phase": "Vuelta a la calma", "desc": "10-15 min en Z1."},
            ],
            "est_load": 95, "why": why,
            "workout_text": ("Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n- 5m Z3 HR\n\n"
                             "Test 30 min a tope sostenible - LAP al minuto 10\n- 30m Z4 HR\n\n"
                             "Vuelta a la calma\n- 5m Z2 HR\n- 10m Z1 HR"),
        }

    # presupuesto de carga para no pasar ACWR 1.3
    budget = None
    if chronic:
        budget = max(0, 1.3 * chronic - sum(load_recent[:6]))
        why.append(f"Presupuesto de carga para hoy sin pasar ACWR 1.3: ~{budget:.0f} TSS "
                   f"(llevás {sum(load_recent[:6]):.0f} en los últimos 6 días, crónica {chronic:.0f}/sem).")

    # ¿hoy es día de fondo largo? (fin de semana, por preferencia del atleta)
    es_dia_largo = TODAY.weekday() in DIA_LARGO
    fondo_dur = DUR_LARGO if es_dia_largo else DUR_NORMAL
    fondo_est = 135 if es_dia_largo else 75

    def fondo_steps(extra=""):
        bloque = (f"{fondo_dur} en Z2 sostenida. En MTB: sendero rodador, subidas largas "
                  "sentado a ritmo constante, sin picos." + (" " + extra if extra else ""))
        if es_dia_largo:
            bloque += " Es tu fondo largo: llevá comida e hidratación (ver nutrición)."
        return [
            {"phase": "Calentamiento", "desc": "15 min progresivos Z1 → Z2."},
            {"phase": "Bloque principal", "desc": bloque},
            {"phase": "Vuelta a la calma", "desc": "10 min en Z1."},
        ]

    # ---------- decisión
    if flags_bad >= 3:
        kind = "descanso"
        title = "Descanso o recuperación activa"
        steps = [
            {"phase": "Opción A", "desc": "Descanso total (recomendado)."},
            {"phase": "Opción B", "desc": f"Rodillo o vuelta muy suave {DUR_SUAVE} en Z1 (poder conversar sin esfuerzo), cadencia alta, terreno llano."},
        ]
        est = 20
    elif flags_bad == 2:
        kind = "suave"
        title = "Rodaje regenerativo Z1–Z2"
        steps = [
            {"phase": "Calentamiento", "desc": "10 min en Z1, cadencia cómoda."},
            {"phase": "Bloque principal", "desc": f"{DUR_SUAVE} en Z2 baja, terreno llano o rodillo. Nada de subidas fuertes hoy."},
            {"phase": "Vuelta a la calma", "desc": "5–10 min en Z1."},
        ]
        est = 45
    elif tsb is not None and tsb < -10:
        kind = "resistencia"
        title = "Fondo aeróbico Z2" + (" — LARGO" if es_dia_largo else "")
        steps = fondo_steps()
        est = fondo_est
    elif yesterday_load >= 120:
        kind = "resistencia"
        title = "Fondo aeróbico Z2 (ayer fue día fuerte)"
        why.append(f"Ayer acumulaste {yesterday_load:.0f} TSS: dos días duros seguidos no suman, "
                   "hoy se rueda en Z2.")
        steps = fondo_steps()
        est = fondo_est
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

    # ---- semana de descarga (deload) del macrociclo: nada de días duros,
    # se recorta el volumen para asimilar y cortar la monotonía.
    if fase and fase.get("deload") and kind in ("intensidad", "tempo"):
        why.append(f"Semana de descarga del bloque {fase.get('fase','')} (semana "
                   f"{fase.get('semana_global','?')}/{fase.get('total_semanas','?')}): "
                   "esta semana no hay días duros, se baja la carga para asimilar y romper la monotonía.")
        kind = "resistencia"
        title = "Fondo suave Z2 (semana de descarga)"
        steps = [
            {"phase": "Calentamiento", "desc": "10 min Z1 → Z2."},
            {"phase": "Bloque principal", "desc": "40–60 min en Z2 tranquila, terreno rodador, sin picos."},
            {"phase": "Vuelta a la calma", "desc": "10 min en Z1."},
        ]
        est = 55

    # ---- guardarraíl de polarización 80/20 (Seiler): si ya gastaste el
    # presupuesto de intensidad de la semana, hoy toca Z2 aunque estés fresco.
    # El techo depende de la fase (Base más estricta, Construcción más permisiva).
    cap_high = (fase or {}).get("cap_high", 30)
    if kind in ("intensidad", "tempo") and polar and polar.get("high_pct", 0) >= cap_high:
        why.append(f"Ya llevás {polar['high_pct']}% del tiempo de la semana en intensidad alta "
                   f"(techo de esta fase: {cap_high}%). Cambio el día de calidad por "
                   "fondo Z2: así protejo el 80/20 y llegás fresco a la próxima sesión dura.")
        kind = "resistencia"
        title = "Fondo aeróbico Z2 (protegiendo el 80/20)"
        steps = [
            {"phase": "Calentamiento", "desc": "15 min progresivos Z1 → Z2."},
            {"phase": "Bloque principal", "desc": "60–90 min en Z2 sostenida, sin picos. Respiración cómoda: tenés que poder hablar de corrido."},
            {"phase": "Vuelta a la calma", "desc": "10 min en Z1."},
        ]
        est = 75

    # ---- drills de cadencia opcionales en días de base (mejora economía;
    # suman técnica sin casi carga). La evidencia para cadencia baja es débil
    # (Hansen 2020), así que el foco es cadencia ALTA y pedaleo redondo.
    if kind in ("resistencia", "suave"):
        steps = steps + [{
            "phase": "Opcional — técnica de cadencia",
            "desc": ("Dentro del bloque suave, sumá 4 × (1 min a cadencia alta 100–110 rpm, "
                     "pedaleo redondo sin rebotar en el asiento / 2 min a cadencia normal). "
                     "Mejora la soltura y la economía; casi no agrega carga."),
        }]

    if budget is not None and est > budget and kind in ("intensidad", "tempo", "resistencia"):
        why.append(f"El entreno se acorta para respetar el presupuesto de ~{budget:.0f} TSS.")

    # texto de workout en la sintaxis de intervals.icu (zonas de FC),
    # que intervals convierte en entreno estructurado y manda a Garmin
    warmup = "Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n- 5m Z3 HR\n"
    cooldown = "\nVuelta a la calma\n- 5m Z2 HR\n- 5m Z1 HR"
    fondo_txt = ("\nFondo largo\n- 60m Z2 HR\n- 60m Z2 HR\n" if es_dia_largo
                 else "\nFondo aeróbico\n- 40m Z2 HR\n- 20m Z3 HR\n- 15m Z2 HR\n")
    workout_texts = {
        "suave": "Calentamiento\n- 10m Z1 HR\n\nRodaje regenerativo\n- 45m Z2 HR\n" + cooldown,
        "resistencia": warmup + fondo_txt + cooldown,
        "intensidad": warmup + "\nIntervalos VO2max 4x\n- 4m Z5 HR\n- 4m Z1 HR\n" + cooldown,
        "tempo": warmup + "\nBloques de tempo 3x\n- 10m Z4 HR\n- 5m Z1 HR\n" + cooldown,
    }

    return {"kind": kind, "title": title, "steps": steps, "est_load": est,
            "why": why, "workout_text": workout_texts.get(kind, "")}


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

    if os.environ.get("PUSH_WORKOUTS", "1") != "0":
        data["plan"]["push"] = upsert_workout(data["plan"])

    path = os.path.join(out_dir, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"OK → {path}")
    print(f"hoy: {json.dumps(data['today'], ensure_ascii=False)}")
    print(f"plan: {data['plan']['title']}")


if __name__ == "__main__":
    main()
