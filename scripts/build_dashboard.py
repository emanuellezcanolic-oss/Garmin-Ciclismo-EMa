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
            "vo2max": num(w.get("vo2max")),
            "stress": num(w.get("stress")),
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
    health = health_signals(rhr3, rhr30, rhr_last, hrv3, hrv30,
                            stress3, stress7, sleep3, tsb_now)

    # ---------- plan del día (fase 3: decisión basada en datos)
    plan = make_plan(
        tsb=tsb_now, acwr=acwr, acute=acute, chronic=chronic,
        hrv_today=hrv_today, hrv30=hrv30, sleep_secs=sleep_today,
        sleep_score=sleep_score_today, readiness=readiness_today,
        load_recent=[day_load(i) for i in range(7)],
    )
    plan["route"] = suggest_route(plan, rides)
    plan["nutrition"] = nutrition_tips(plan["kind"])

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
            "vo2max": vo2_last, "vo2max_delta90": vo2_delta90,
            "stress": today_w.get("stress") or yesterday_w.get("stress"), "stress7": stress7,
        },
        "plan": plan,
        "goals": make_goals({
            "ctl": ctl_now, "vo2max": vo2_last, "weight": weight_last,
        }),
        "health": health,
        "alerts": alerts,
        "series": series,
        "rides": rides[:60],
        "counts": {"rides_180d": len(rides), "wellness_days": len(days)},
    }


def nutrition_tips(kind):
    """Guía nutricional del día según el entreno, basada en la estrategia de
    la Lic. Zalazar (plan personal del atleta): fórmulas de comidas, timing
    pre/intra/post y regla de las 3R."""
    base = [
        "Agua: 3 litros en el día (orina clara como control).",
        "Almuerzo y cena: 50% del plato de verduras (3 colores, al menos 1 tipo B) + proteína magra + hidratos de calidad (legumbres/granos de tu guía).",
    ]
    if kind in ("descanso", "sin_datos", "suave"):
        return base + [
            "Día liviano: hidratos en cantidad INFERIOR en almuerzo; sin extras energéticos (frutos secos/pasta de maní solo si hay hambre real).",
            "Desayuno/merienda: fruta + proteína + lácteo descremado + hidrato integral.",
        ]
    if kind == "resistencia":
        return base + [
            "CENA de la noche anterior al fondo: hidratos en cantidad SUPERIOR y de fácil digestión (arroz o fideos de arroz) + huevos o queso magro.",
            "Desayuno 2 h antes: pan blanco o discos de arroz + mermelada/membrillo + 1 huevo + 1 fruta. Si tenés menos de 1 h: sacá proteína y fibra.",
            "Si pedaleás más de 2 h: una ingesta cada 45 min (membrillo 40 g, pasas/arándanos 40 g, o isotónica). Más de 3 h: sumá ingestas complejas (sandwich de queso magro o de batata).",
            "Post (3R): rehidratar con agua (1.5-2 L en la primera hora y media) + 2 frutas + 1 scoop de proteína; después la comida principal.",
        ]
    # intensidad / tempo / test
    return base + [
        "Pre entreno intenso: NADA de lácteos antes de la bici; proteína de fácil digestión (huevo o pescado) en la comida previa; ingesta completa 1:30-2 h antes.",
        "Llevá por las dudas: un cuadradito de membrillo o puñado de pasas. Café pre entreno: recomendado.",
        "Post (3R): agua + 1 fruta apenas bajás de la bici + proteína (huevo, claras o scoop).",
    ]


def make_goals(today):
    """Objetivos con plazo, calculados desde los valores actuales."""
    goals = []
    horizon = (TODAY + timedelta(weeks=12)).isoformat()
    ctl = today.get("ctl")
    if ctl is not None:
        goals.append({
            "metric": "Fitness (CTL)",
            "current": ctl, "target": round(min(ctl + 10, 90)), "by": horizon,
            "note": "Subida segura: ~5-7 puntos por mes, sin pasar ACWR 1.3.",
        })
    vo2 = today.get("vo2max")
    if vo2 is not None:
        goals.append({
            "metric": "VO2max (est. Garmin)",
            "current": vo2, "target": round(vo2 * 1.06, 1), "by": horizon,
            "note": "+6% en 12 semanas es realista entrenando polarizado; el techo lo pone la genética, y a ese techo se llega tras años, no meses.",
        })
    w = today.get("weight")
    if w is not None:
        goals.append({
            "metric": "Peso",
            "current": w, "target": round(w - 6, 1), "by": horizon,
            "note": "-0.5 kg/semana (0.4-0.5% del peso corporal): preserva músculo y rendimiento. En MTB cada kg menos es potencia/kg gratis.",
        })
    else:
        goals.append({
            "metric": "Peso",
            "current": None, "target": None, "by": None,
            "note": "Cargá tu peso en Garmin Connect (2-3 veces/semana, en ayunas) y el objetivo se calcula solo.",
        })
    goals.append({
        "metric": "Umbral (LTHR)",
        "current": None, "target": None, "by": None,
        "note": "Se mide con el test de 30 min cada 4 semanas: es el checkpoint objetivo de progreso.",
    })
    return goals


def health_signals(rhr3, rhr30, rhr_last, hrv3, hrv30, stress3, stress7,
                   sleep3_secs, tsb):
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

    return {
        "flags": flags,
        "disclaimer": ("Esto es un TAMIZAJE, no un diagnóstico. Detecta desvíos respecto a tu propia línea de base, "
                       "no enfermedades. La FC óptica del reloj no es un electrocardiograma y no detecta arritmias."),
        "red_flags": ("🚨 Consultá a un médico YA si tenés: dolor o presión en el pecho, palpitaciones, mareos o desmayos, "
                      "falta de aire inusual. Para alguien que entrena fuerte, un apto físico deportivo con ECG y ergometría es muy recomendable."),
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

    # frecuencia objetivo: 4-5 días/semana → con 5+ días ya pedaleados, toca descanso
    days_ridden = sum(1 for load in load_recent if load and load > 0)
    yesterday_load = load_recent[1] if len(load_recent) > 1 else 0
    if days_ridden >= 5 and flags_bad < 3:
        why.append(f"Ya pedaleaste {days_ridden} de los últimos 7 días (tu objetivo es 4-5): "
                   "el descanso de hoy es parte del plan, ahí es donde el cuerpo asimila.")
        return {
            "kind": "descanso",
            "title": "Día de descanso programado",
            "steps": [
                {"phase": "Opción A", "desc": "Descanso total."},
                {"phase": "Opción B", "desc": "Caminata o vuelta muy suave 20-30 min en Z1, solo para mover las piernas."},
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
    elif yesterday_load >= 120:
        kind = "resistencia"
        title = "Fondo aeróbico Z2 (ayer fue día fuerte)"
        why.append(f"Ayer acumulaste {yesterday_load:.0f} TSS: dos días duros seguidos no suman, "
                   "hoy se rueda en Z2.")
        steps = [
            {"phase": "Calentamiento", "desc": "15 min progresivos Z1 → Z2."},
            {"phase": "Bloque principal", "desc": "60-90 min en Z2 sostenida, sin picos."},
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

    # texto de workout en la sintaxis de intervals.icu (zonas de FC),
    # que intervals convierte en entreno estructurado y manda a Garmin
    warmup = "Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n- 5m Z3 HR\n"
    cooldown = "\nVuelta a la calma\n- 5m Z2 HR\n- 5m Z1 HR"
    workout_texts = {
        "suave": "Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n\nRodaje regenerativo\n- 30m Z2 HR\n" + cooldown,
        "resistencia": warmup + "\nFondo aeróbico\n- 40m Z2 HR\n- 20m Z3 HR\n- 15m Z2 HR\n" + cooldown,
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
