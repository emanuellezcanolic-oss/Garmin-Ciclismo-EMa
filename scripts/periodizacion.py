"""Macro-periodización de la temporada, anclada al estado REAL del atleta.

Emanuel no arranca de cero: ya tiene una base consolidada (CTL ~60) y viene
entrenando en serio, con dos problemas que muestran sus datos: demasiada
intensidad (polarización ~63/7/31) y alta monotonía. Por eso el macrociclo no
"reconstruye" fitness: parte de su CTL actual, ordena la distribución hacia
80/20, mete semanas de descarga para cortar la monotonía y recién después
sube la carga.

Estructura clásica en bloques de 4 semanas (3 de carga + 1 de descarga),
basada en Galán-Rioja & Seiler (periodización y distribución de intensidad):
  Base → Construcción → Pico → Transición.

Cada semana define: foco, % de volumen respecto de TU carga de referencia,
días de calidad recomendados, y el techo de intensidad alta (guardarraíl 80/20
por fase). El planificador diario lo usa como marco, pero la readiness del día
siempre puede bajar la exigencia.
"""

from datetime import date

# Lunes de arranque del macrociclo estructurado.
SEASON_START = date(2026, 8, 17)
TOTAL_WEEKS = 12

# Especificación por semana global (1..12). deload = semana de descarga.
# vol_pct: % del volumen de referencia (tu carga crónica semanal).
# dias_calidad: sesiones duras recomendadas en la semana.
# cap_high: techo del % de tiempo semanal en intensidad alta (guardarraíl 80/20).
_SEMANAS = {
    1:  ("Base", "descarga", 60, 0, 12,
         "Descarga inicial: venís fatigado (TSB muy negativo), así que la temporada arranca "
         "absorbiendo la carga que ya traés. Todo Z1–Z2, sin días duros."),
    2:  ("Base", "carga", 95, 1, 18,
         "Base aeróbica: subir el volumen en Z2 y ordenar la distribución hacia 80/20 "
         "(venís con demasiada intensidad). Un solo día de calidad."),
    3:  ("Base", "carga", 105, 1, 18,
         "Base aeróbica: seguimos acumulando Z2. La consistencia es la que construye, no las sesiones heroicas."),
    4:  ("Base", "descarga", 65, 0, 12,
         "Descarga de fin de bloque: bajamos volumen para asimilar y cortar la monotonía. Buen momento para test de umbral."),
    5:  ("Construcción", "carga", 100, 2, 28,
         "Construcción: entra la calidad específica de MTB — HIT 4×4 a VO2max (lo que más rinde en MTB) "
         "más un día de umbral. Dos días duros, el resto Z2."),
    6:  ("Construcción", "carga", 105, 2, 28,
         "Construcción: sostener 2 días de calidad (VO2max + umbral) sobre una base de volumen Z2."),
    7:  ("Construcción", "carga", 110, 2, 30,
         "Construcción: pico de carga del bloque. Máximo estímulo de calidad sin romper el 80/20."),
    8:  ("Construcción", "descarga", 65, 1, 15,
         "Descarga de fin de bloque: bajar volumen, mantener un toque de intensidad. Test de umbral para ver progreso."),
    9:  ("Pico", "carga", 90, 2, 28,
         "Pico: baja el volumen y sube la especificidad. Intervalos más cortos y específicos, simulacros de terreno MTB."),
    10: ("Pico", "carga", 85, 2, 28,
         "Pico: afinar la forma. Menos volumen, calidad filosa, más descanso entre sesiones duras."),
    11: ("Pico", "carga", 75, 2, 25,
         "Pico / puesta a punto: volumen bajo, chispa alta. Llegás fresco y rápido."),
    12: ("Transición", "descarga", 45, 0, 12,
         "Transición: recuperación activa. Cortar, descomprimir cabeza y cuerpo antes del próximo macrociclo."),
}

_FOCO_EVIDENCIA = {
    "Base": ["base_aerobica_z2", "polarizacion_80_20"],
    "Construcción": ["hit_vo2max", "umbral_obla", "polarizacion_80_20"],
    "Pico": ["umbral_obla", "hit_vo2max"],
    "Transición": ["recuperacion_multivariable"],
}


def semana_global(today):
    if today < SEASON_START:
        return 1
    return (today - SEASON_START).days // 7 + 1


def fase_actual(today, ctl=None, chronic_weekly=None):
    """Devuelve la fase de hoy con objetivos personalizados a TUS números."""
    wk = semana_global(today)
    ciclo = ((wk - 1) // TOTAL_WEEKS)          # cuántos macrociclos completos pasaron
    wk_in = ((wk - 1) % TOTAL_WEEKS) + 1        # semana dentro del macrociclo (1..12)

    fase, tipo, vol_pct, dias_calidad, cap_high, detalle = _SEMANAS[wk_in]
    deload = (tipo == "descarga")
    semana_en_bloque = ((wk_in - 1) % 4) + 1

    vol_ref = chronic_weekly or 500
    objetivo_tss = round(vol_ref * vol_pct / 100)

    # texto que reconoce de dónde partís
    base_txt = ""
    if ctl:
        base_txt = f" Partís de una base ya hecha (CTL ~{round(ctl)}), no de cero."

    ciclo_txt = f" (macrociclo {ciclo + 1})" if ciclo else ""

    return {
        "fase": fase,
        "tipo": tipo,
        "deload": deload,
        "semana_global": wk,
        "semana_en_macrociclo": wk_in,
        "semana_en_bloque": semana_en_bloque,
        "total_semanas": TOTAL_WEEKS,
        "vol_pct": vol_pct,
        "objetivo_tss": objetivo_tss,
        "dias_calidad": dias_calidad,
        "cap_high": cap_high,
        "foco": detalle + base_txt + ciclo_txt,
        "evidencia": _FOCO_EVIDENCIA.get(fase, []),
    }


def mapa_temporada(today):
    """Mapa de bloques para la app, con el bloque actual marcado."""
    wk_in = ((semana_global(today) - 1) % TOTAL_WEEKS) + 1
    bloques = [
        ("Base", "1–4", "Volumen Z2 y ordenar el 80/20"),
        ("Construcción", "5–8", "HIT VO2max + umbral, subir carga"),
        ("Pico", "9–11", "Afinar: menos volumen, más chispa"),
        ("Transición", "12", "Recuperar y descomprimir"),
    ]
    out = []
    for nombre, semanas, foco in bloques:
        lo, hi = semanas.split("–") if "–" in semanas else (semanas, semanas)
        activo = int(lo) <= wk_in <= int(hi)
        out.append({"nombre": nombre, "semanas": semanas, "foco": foco, "activo": activo})
    return out
