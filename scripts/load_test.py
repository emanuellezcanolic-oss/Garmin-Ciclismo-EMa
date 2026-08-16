"""Carga un test de condición física como entreno estructurado en tu Garmin.

Corre en GitHub Actions (workflow "Cargar test", con menú desplegable).
Crea el evento WORKOUT en intervals.icu, que lo sincroniza solo con Garmin
Connect. Los tests están basados en protocolos validados de la literatura.
"""

import os
import sys
from datetime import date, timedelta

import requests

API = "https://intervals.icu/api/v1"
ATHLETE = os.environ.get("ATHLETE_ID", "i650204")
KEY = os.environ["INTERVALS_API_KEY"]
AUTH = ("API_KEY", KEY)

# ---- Catálogo de tests validados (basados en frecuencia cardíaca) ----
TESTS = {
    "lthr_30": {
        "name": "Test de Umbral 30 min (Friel)",
        "mide": "FC de umbral (LTHR) = FC media de los últimos 20 min. Recalibra tus zonas.",
        "text": ("Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n- 5m Z3 HR\n\n"
                 "Test 30 min a tope SOSTENIBLE (como una crono) - apretá LAP al minuto 10\n- 30m Z4 HR\n\n"
                 "Vuelta a la calma\n- 5m Z2 HR\n- 10m Z1 HR"),
        "tip": "Terreno: subida constante o camino sin cortes. Ritmo que puedas mantener los 30 min completos.",
    },
    "test_20": {
        "name": "Test de 20 min (umbral)",
        "mide": "Umbral (LTHR ≈ FC media de los 20 min). Más corto que el de 30, algo menos preciso.",
        "text": ("Calentamiento\n- 5m Z1 HR\n- 5m Z2 HR\n- 5m Z3 HR\n\n"
                 "Test 20 min a tope sostenible\n- 20m Z4 HR\n\n"
                 "Vuelta a la calma\n- 5m Z2 HR\n- 10m Z1 HR"),
        "tip": "Arrancá parejo, no salgas demasiado fuerte los primeros minutos.",
    },
    "test_5": {
        "name": "Test de 5 min máximo (VO2máx / potencia aeróbica)",
        "mide": "Capacidad aeróbica máxima (proxy de VO2máx/MAP). FC máx y ritmo sostenido 5 min.",
        "text": ("Calentamiento\n- 10m Z1 HR\n- 5m Z2 HR\n- 3m Z4 HR\n- 5m Z1 HR\n\n"
                 "Test 5 min al MÁXIMO que puedas sostener\n- 5m Z5 HR\n\n"
                 "Vuelta a la calma\n- 10m Z1 HR"),
        "tip": "Dalo todo pero dosificado para llegar entero al minuto 5.",
    },
    "cooper_12": {
        "name": "Test de Cooper 12 min",
        "mide": "VO2máx estimado por la DISTANCIA recorrida en 12 min. Clásico validado.",
        "text": ("Calentamiento\n- 10m Z1 HR\n- 5m Z2 HR\n\n"
                 "Test Cooper 12 min a ritmo máximo constante\n- 12m Z5 HR\n\n"
                 "Vuelta a la calma\n- 10m Z1 HR"),
        "tip": "En terreno LLANO y sin cortes. Lo que importa es la distancia total en los 12 min.",
    },
    "sit": {
        "name": "Sprint Interval Training (SIT) — MTB",
        "mide": "Potencia máxima y tolerancia anaeróbica; mejora la toma de decisiones bajo fatiga (Hebisz 2022, específico MTB).",
        "text": ("Calentamiento\n- 10m Z1 HR\n- 5m Z2 HR\n- 3x 20s fuerte / 40s suave\n- 3m Z1 HR\n\n"
                 "6x SPRINT ALL-OUT\n- 30s Z5 HR (a tope, todo lo que tengas)\n- 4m Z1 HR (recuperación completa)\n\n"
                 "Vuelta a la calma\n- 10m Z1 HR"),
        "tip": "Cada sprint es MÁXIMO desde el arranque. La recuperación larga (4 min) es a propósito: hay que llegar entero a cada sprint. En MTB, hacelos en llano o subida suave.",
    },
    "hrr": {
        "name": "Test de recuperación de FC (HRR)",
        "mide": "Cuánto baja tu FC en 1 min tras un esfuerzo duro. Marcador de forma y del sistema nervioso.",
        "text": ("Calentamiento\n- 10m Z1 HR\n- 5m Z2 HR\n\n"
                 "Esfuerzo duro 3 min\n- 3m Z5 HR\n\n"
                 "PARÁ y quedate quieto - anotá tu FC justo al frenar y al minuto (la caída es tu HRR)\n- 1m Z1 HR\n\n"
                 "Vuelta a la calma\n- 10m Z1 HR"),
        "tip": "Una caída de más de 25-30 lpm en el primer minuto es señal de buena forma.",
    },
    "vt_step": {
        "name": "Test de umbrales VT1/VT2 (escalonado + prueba del habla)",
        "mide": ("Ubica tus DOS umbrales: VT1 (aeróbico, donde la respiración se agita por "
                 "primera vez) y VT2 (anaeróbico, donde ya no podés hablar). Con la prueba del "
                 "habla + la FC de cada escalón fijamos las fronteras reales de tus zonas."),
        "text": ("Calentamiento\n- 10m Z1 HR\n- 5m Z2 HR\n\n"
                 "Escalón 1 — charlá una frase larga en voz alta\n- 4m Z2 HR\n\n"
                 "Escalón 2 — ¿todavía frases completas?\n- 4m Z3 HR\n\n"
                 "Escalón 3 — si ya cortás las frases, tu VT1 quedó atrás (anotá la FC)\n- 4m Z4 HR\n\n"
                 "Escalón 4 — si solo salen palabras sueltas, ese es tu VT2 (anotá la FC)\n- 4m Z5 HR\n\n"
                 "Vuelta a la calma\n- 5m Z2 HR\n- 10m Z1 HR"),
        "tip": ("En cada escalón intentá decir en voz alta una frase larga (ej: una estrofa). "
                "VT1 = el último escalón donde podés hablar cómodo y seguido. "
                "VT2 = el último donde apenas te salen 2-3 palabras. Anotá la FC de esos dos "
                "escalones: son las fronteras de tus zonas. Hacelo en subida constante o llano sin cortes."),
    },
}


def parse_from_issue():
    """Extrae el test y la fecha del título/cuerpo de un issue de GitHub.

    La app web abre un issue pre-cargado con título 'cargar-test: <clave>' y,
    opcionalmente, 'Fecha: YYYY-MM-DD' en el cuerpo. Así el atleta elige el
    test desde la app sin exponer ninguna clave secreta.
    """
    import re

    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")
    blob = f"{title}\n{body}"

    key = None
    m = re.search(r"cargar-test\s*[:=]?\s*([a-z0-9_]+)", blob, re.IGNORECASE)
    if m:
        key = m.group(1).strip().lower()
    if key not in TESTS:  # buscar cualquier clave conocida en el texto
        for k in TESTS:
            if re.search(rf"\b{k}\b", blob, re.IGNORECASE):
                key = k
                break

    fecha = ""
    md = re.search(r"(\d{4}-\d{2}-\d{2})", blob)
    if md:
        fecha = md.group(1)
    return key, fecha


def main():
    from_issue = "--from-issue" in sys.argv

    if from_issue:
        key, fecha = parse_from_issue()
        if key not in TESTS:
            print(f"::error::No reconocí ningún test en el issue. Opciones: {', '.join(TESTS)}")
            sys.exit(1)
    else:
        key = os.environ.get("TEST", "lthr_30")
        fecha = os.environ.get("FECHA", "").strip()
        if key not in TESTS:
            print(f"Test desconocido: {key}. Opciones: {', '.join(TESTS)}")
            sys.exit(1)
    t = TESTS[key]

    if not fecha:
        fecha = (date.today() + timedelta(days=1)).isoformat()  # por defecto: mañana

    body = {
        "category": "WORKOUT",
        "start_date_local": f"{fecha}T00:00:00",
        "type": "Ride",
        "name": f"🧪 {t['name']}",
        "description": t["text"] + f"\n\n📋 Qué mide: {t['mide']}\n💡 {t['tip']}",
    }
    r = requests.post(f"{API}/athlete/{ATHLETE}/events", auth=AUTH, json=body, timeout=60)
    print(f"Cargando '{t['name']}' para el {fecha}: HTTP {r.status_code}")
    print(r.text[:300])

    # Exponer resultado para el workflow (comentario en el issue)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"ok={'true' if r.ok else 'false'}\n")
            f.write(f"test_name={t['name']}\n")
            f.write(f"fecha={fecha}\n")

    if not r.ok:
        sys.exit(1)
    print("OK — el test va a aparecer en tu Garmin Connect (y en el reloj) en unos minutos.")


if __name__ == "__main__":
    main()
