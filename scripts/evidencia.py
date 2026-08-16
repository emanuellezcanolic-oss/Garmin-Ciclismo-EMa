"""Base de evidencia del proyecto.

Convierte lo leído (artículos de Entrenamiento Óptimo + papers científicos que
aportó Emanuel, resumidos en NOTAS_METODOLOGIA.md) en datos que el planificador
consulta en cada decisión y que la app muestra. Así cada recomendación queda
trazada a su fuente y la metodología deja de vivir solo en un archivo de notas.

Cada principio: título, qué dice (principio), fuente y categoría. PLAN_EVIDENCIA
mapea cada tipo de sesión a los principios en los que se apoya.
"""

EVIDENCIA = {
    # ---------------- Distribución de la intensidad ----------------
    "polarizacion_80_20": {
        "cat": "Distribución",
        "titulo": "Polarización ~80/20",
        "principio": "La mayor parte del tiempo en baja intensidad (Z1–Z2) y una porción menor en alta. "
                     "En ciclistas de MTB el modelo polarizado mejoró más el VO2max que el entrenamiento por bloques.",
        "fuente": "Seiler; Hebisz 2021 (MTB, 8 sem); Galán-Rioja & Seiler (revisión)",
    },
    "base_aerobica_z2": {
        "cat": "Distribución",
        "titulo": "Base aeróbica en Z2",
        "principio": "El grueso del volumen en Z2 construye la base aeróbica y la durabilidad, con bajo costo de fatiga. "
                     "Consistencia por encima de sesiones heroicas.",
        "fuente": "Seiler; Entrenamiento Óptimo",
    },
    # ---------------- Calidad (el ~20% duro) ----------------
    "hit_vo2max": {
        "cat": "Calidad",
        "titulo": "HIT a VO2max (4×4 min)",
        "principio": "Para MTB, el trabajo de calidad se apoya sobre todo en intervalos aeróbicos de alta intensidad "
                     "(tipo 4×4 min cerca del VO2max). Lo que manda es maximizar el TIEMPO cerca del VO2max.",
        "fuente": "Inoue (SIT vs HIT, HIT ~83% mejor para MTB); Schoenmakers 2026 (T@VO2max)",
    },
    "sit_anaerobico": {
        "cat": "Calidad",
        "titulo": "Sprint Interval (SIT) para MTB",
        "principio": "Los sprints all-out mejoran la potencia máxima, la tolerancia anaeróbica y la toma de decisiones "
                     "bajo fatiga. Estímulo secundario y específico del MTB (intensidad variable, decisiones rápidas).",
        "fuente": "Hebisz 2022; Inoue 2012 (anaeróbico ↔ rendimiento XCO)",
    },
    "umbral_obla": {
        "cat": "Calidad",
        "titulo": "Trabajo de umbral (OBLA / VT2)",
        "principio": "Los mejores en XCO tienen más potencia en el umbral y terminan más rápido. Entrenar la zona de "
                     "umbral (tempo / sweet spot) y conocer VT1–VT2 afina las zonas y mejora el rendimiento.",
        "fuente": "Viana 2018 (pacing XCO); Hebisz 2021 (VT1/VT2)",
    },
    # ---------------- Recuperación / carga ----------------
    "recuperacion_multivariable": {
        "cat": "Recuperación",
        "titulo": "Decidir con varias señales, no una",
        "principio": "El plan del día integra HRV, FC en reposo, sueño, estrés, forma (TSB) y RPE. El monitoreo "
                     "subjetivo pesa tanto o más que el objetivo.",
        "fuente": "Saw 2016; Entrenamiento Óptimo (monitoreo multivariable)",
    },
    "monotonia_foster": {
        "cat": "Recuperación",
        "titulo": "Monotonía y strain",
        "principio": "Cargar siempre parecido (alta monotonía) sube el riesgo de enfermedad y sobreentrenamiento. "
                     "Hay que alternar días duros y suaves.",
        "fuente": "Foster (monotonía/strain)",
    },
    "acwr_gabbett": {
        "cat": "Recuperación",
        "titulo": "Progresión de carga segura (ACWR)",
        "principio": "La carga aguda (7 días) no debería dispararse respecto de la crónica (mes). Se mantiene el ACWR "
                     "por debajo de ~1.3 para progresar sin lesionarse.",
        "fuente": "Gabbett (ACWR)",
    },
    "sit_test_umbral": {
        "cat": "Tests",
        "titulo": "Test de umbral de Friel",
        "principio": "El test de 30 min a tope (FC media de los últimos 20 min = LTHR) recalibra las zonas de FC. "
                     "Se hace en frescura, cada ~4 semanas, como checkpoint objetivo.",
        "fuente": "Friel",
    },
    "doble_umbral": {
        "cat": "Tests",
        "titulo": "Doble umbral VT1/VT2",
        "principio": "Ubicar el primer umbral (aeróbico) y el segundo (anaeróbico) afina el techo real de Z2 y la "
                     "frontera de umbral, base del modelo de 3 zonas.",
        "fuente": "Hebisz 2021; Entrenamiento Óptimo (LT1/LT2)",
    },
    # ---------------- Nutrición e hidratación ----------------
    "nutricion_intra": {
        "cat": "Nutrición",
        "titulo": "Combustible por hora en fondos",
        "principio": "Hasta 2.5 h: 30–60 g de hidratos/hora. Más de 2.5 h: 60–90 g/h con maltodextrina:fructosa 2:1. "
                     "En fondos muy largos, 10–15 g de proteína/h. Cafeína 3–6 mg/kg. Practicar la nutrición en los entrenos.",
        "fuente": "Oosthuyse, Muros & Zabala (nutrición MTB/ciclocross)",
    },
    "hidratacion": {
        "cat": "Nutrición",
        "titulo": "Hidratación (clave en calor)",
        "principio": "Una caída aguda de peso >2% baja el rendimiento; la hidratación es determinante, sobre todo con calor. "
                     "Se refuerzan líquidos y sodio en días de carga y de calor.",
        "fuente": "ACSM (2% masa corporal); de Moura (hidratación MTB en calor)",
    },
    # ---------------- Composición corporal ----------------
    "composicion_corporal": {
        "cat": "Composición",
        "titulo": "Composición ↔ rendimiento",
        "principio": "Más grasa se asocia a tiempos más lentos; más masa muscular e hidratación, a tiempos más rápidos. "
                     "Bajar grasa preservando músculo mejora directamente el rendimiento (y la potencia/kg en MTB). "
                     "El trabajo interválico ayuda a reducir grasa sin romper el 80/20.",
        "fuente": "de Moura (83 ciclistas MTB); Poon 2024 (interválico y composición)",
    },
    # ---------------- Técnica ----------------
    "cadencia_libre": {
        "cat": "Técnica",
        "titulo": "Cadencia libre + variedad",
        "principio": "La cadencia libremente elegida está bien. Sumar bloques de cadencia alta da soltura; la evidencia "
                     "para prescribir cadencia baja/torque como pilar es débil (queda como variedad opcional).",
        "fuente": "Hansen & Rønnestad 2020 (revisión); Mater 2021",
    },
    # ---------------- Marco general ----------------
    "especificidad_mtb": {
        "cat": "Marco",
        "titulo": "Especificidad MTB",
        "principio": "Entrenar para las demandas del MTB con desnivel: fuerza-resistencia en subida y durabilidad en "
                     "fondos largos, además de la intensidad variable propia del cross-country.",
        "fuente": "Entrenamiento Óptimo; Oosthuyse",
    },
}

# Qué principios respaldan cada tipo de sesión del planificador.
PLAN_EVIDENCIA = {
    "resistencia": ["base_aerobica_z2", "polarizacion_80_20", "especificidad_mtb", "nutricion_intra"],
    "suave":       ["recuperacion_multivariable", "polarizacion_80_20"],
    "descanso":    ["recuperacion_multivariable", "monotonia_foster"],
    "tempo":       ["umbral_obla", "polarizacion_80_20", "acwr_gabbett"],
    "intensidad":  ["hit_vo2max", "polarizacion_80_20", "composicion_corporal"],
    "test":        ["sit_test_umbral", "doble_umbral"],
    "sin_datos":   [],
}

CAT_ORDER = ["Distribución", "Calidad", "Recuperación", "Tests", "Nutrición", "Composición", "Técnica", "Marco"]


def _item(key):
    e = EVIDENCIA[key]
    return {"key": key, "titulo": e["titulo"], "principio": e["principio"],
            "fuente": e["fuente"], "cat": e["cat"]}


def evidencia_para_plan(kind):
    """Lista de principios (con fuente) que respaldan la sesión de hoy."""
    return [_item(k) for k in PLAN_EVIDENCIA.get(kind, [])]


def evidencia_agrupada():
    """Toda la base de evidencia agrupada por categoría, para la app."""
    grupos = []
    for cat in CAT_ORDER:
        items = [_item(k) for k, v in EVIDENCIA.items() if v["cat"] == cat]
        if items:
            grupos.append({"cat": cat, "items": items})
    return grupos
