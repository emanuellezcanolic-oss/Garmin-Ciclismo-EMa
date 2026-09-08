"""DFA alpha-1 (Detrended Fluctuation Analysis) sobre intervalos RR.

Con la banda de pecho HRM 600 las salidas traen RR latido a latido, lo que
permite estimar el umbral aeróbico de campo (VT1) sin lactato ni laboratorio.

Método (Rogers et al. 2021): se calcula DFA a1 en ventanas cortas; a medida
que sube la intensidad, a1 baja. a1 ≈ 0.75 marca el umbral aeróbico (VT1, techo
real de Z2) y a1 ≈ 0.5 el umbral anaeróbico (VT2). También sirve como marcador
de durabilidad/fatiga: a1 alto en Z2 = fresco; si cae antes de lo habitual = fatiga.
"""

import numpy as np


def _clean_rr(rr):
    """Filtra artefactos: RR fisiológicos (300-2000 ms) y saltos <5% vs. previo."""
    out = []
    prev = None
    for v in rr:
        if v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v < 300 or v > 2000:
            continue
        if prev is not None and abs(v - prev) / prev > 0.05:
            prev = v  # actualiza referencia pero no lo usa (latido corregido)
            continue
        out.append(v)
        prev = v
    return out


def alpha1(rr, nmin=4, nmax=16):
    """DFA alpha-1 (orden 1) de una serie corta de RR (ms). None si no alcanza."""
    rr = np.asarray(rr, dtype=float)
    n = len(rr)
    if n < nmax * 2:
        return None
    y = np.cumsum(rr - rr.mean())  # perfil integrado
    scales = list(range(nmin, nmax + 1))
    F = []
    for s in scales:
        nseg = n // s
        if nseg < 1:
            continue
        rms = []
        for i in range(nseg):
            seg = y[i * s:(i + 1) * s]
            x = np.arange(s)
            coef = np.polyfit(x, seg, 1)
            fit = np.polyval(coef, x)
            rms.append(np.sqrt(np.mean((seg - fit) ** 2)))
        if rms:
            F.append(np.mean(rms))
    if len(F) < 3:
        return None
    logs = np.log(scales[:len(F)])
    logF = np.log(np.array(F) + 1e-9)
    slope = np.polyfit(logs, logF, 1)[0]
    return float(slope)


def curva(rr_ms, hr, win_sec=120, step_sec=20):
    """Devuelve puntos (fc_media, a1) por ventana temporal deslizante.

    rr_ms: lista de intervalos RR (ms). hr: lista de FC alineada por latido
    (misma longitud que rr) o None (se deriva 60000/RR)."""
    rr = _clean_rr(rr_ms)
    if len(rr) < 60:
        return []
    t = np.cumsum(rr) / 1000.0  # segundos acumulados por latido
    inst_hr = 60000.0 / np.asarray(rr)
    pts = []
    win_ms = win_sec * 1000
    start = 0.0
    tmax = t[-1]
    while start + win_sec <= tmax:
        lo, hi = start, start + win_sec
        idx = np.where((t >= lo) & (t < hi))[0]
        if len(idx) >= 40:
            seg = [rr[i] for i in idx]
            a = alpha1(seg)
            if a is not None:
                fc = float(np.mean(inst_hr[idx]))
                pts.append((round(fc, 1), round(a, 3)))
        start += step_sec
    return pts


def estimar_umbrales(pts):
    """De la curva (fc, a1) estima AeT (a1=0.75) y VT2 (a1=0.5) por interpolación."""
    if len(pts) < 5:
        return {"aet_hr": None, "vt2_hr": None, "quality": "insuficiente", "points": len(pts)}
    fc = np.array([p[0] for p in pts])
    a1 = np.array([p[1] for p in pts])
    order = np.argsort(fc)
    fc, a1 = fc[order], a1[order]
    # ajuste lineal a1 = m*fc + b (a1 baja al subir fc)
    m, b = np.polyfit(fc, a1, 1)

    def hr_para(target):
        # cruce real por interpolación si existe; si no, por la recta
        for i in range(1, len(fc)):
            y0, y1 = a1[i - 1], a1[i]
            if (y0 - target) * (y1 - target) <= 0 and y0 != y1:
                f = (target - y0) / (y1 - y0)
                return round(float(fc[i - 1] + f * (fc[i] - fc[i - 1])))
        if m < -1e-4:
            hr = (target - b) / m
            if fc.min() - 10 <= hr <= fc.max() + 10:
                return round(float(hr))
        return None

    ss = np.sum((a1 - (m * fc + b)) ** 2)
    st = np.sum((a1 - a1.mean()) ** 2)
    r2 = 1 - ss / st if st > 0 else 0
    aet = hr_para(0.75)
    q = "buena" if (aet and len(pts) >= 10 and r2 > 0.3) else ("baja" if aet else "no cruzó umbral")
    return {"aet_hr": aet, "vt2_hr": hr_para(0.5), "quality": q,
            "points": len(pts), "r2": round(float(r2), 2), "slope": round(float(m), 4)}


def analizar(rr_ms, hr=None):
    """Análisis completo de una salida: umbrales + a1 del tramo fácil inicial."""
    pts = curva(rr_ms, hr)
    res = estimar_umbrales(pts)
    # a1 del arranque (primeros ~20 min = primeras ventanas) como durabilidad
    inicio = [p[1] for p in pts[:min(len(pts), 60)]]
    res["last_alpha1"] = round(float(np.mean(inicio)), 2) if inicio else None
    res["curva"] = pts
    return res


def interpretar(a1):
    if a1 is None:
        return ""
    if a1 >= 0.9:
        return "muy fácil / fresco (bien por debajo del umbral aeróbico)"
    if a1 >= 0.75:
        return "en el entorno del umbral aeróbico (Z2 alta)"
    if a1 >= 0.5:
        return "por encima del umbral aeróbico (trabajo de intensidad)"
    return "alta intensidad (por encima del umbral anaeróbico)"
