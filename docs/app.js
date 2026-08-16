// PELOTÓN — dashboard estático. Lee data.json (generado por GitHub Actions).

const $ = (id) => document.getElementById(id) || {};
const REPO = "emanuellezcanolic-oss/Garmin-Ciclismo-EMa";

const KIND_TAG = {
  descanso: "descanso", suave: "recuperación", resistencia: "base",
  tempo: "tempo", intensidad: "calidad", test: "test", sin_datos: "—",
};
const KIND_EMOJI = { descanso: "😴", suave: "🟢", resistencia: "🚴", tempo: "🟡", intensidad: "🔥", test: "🧪" };
const ALERT_ICONS = { info: "ℹ️", warning: "⚠️", serious: "🟠", critical: "🛑", ok: "✅" };

const TESTS = [
  ["lthr_30", "Umbral 30 min (Friel)", "Tu FC de umbral (LTHR); recalibra tus zonas. El patrón oro de campo."],
  ["vt_step", "Umbrales VT1/VT2 (escalonado)", "Ubica tus DOS umbrales con la prueba del habla + FC. El más completo."],
  ["test_20", "20 min (umbral)", "Versión más corta del test de umbral, algo menos precisa."],
  ["test_5", "5 min máximo", "Capacidad aeróbica máxima (proxy de VO2máx / potencia aeróbica)."],
  ["cooper_12", "Cooper 12 min", "VO2máx estimado por la distancia en 12 min. En terreno llano."],
  ["sit", "Sprint Interval (SIT) · MTB", "6×30s a tope: potencia máxima y decisión bajo fatiga (Hebisz 2022)."],
  ["hrr", "Recuperación de FC (HRR)", "Cuánto baja tu pulso en 1 min tras un esfuerzo duro: marcador de forma."],
];

function fmtDur(secs) {
  if (!secs) return "—";
  const h = Math.floor(secs / 3600), m = Math.round((secs % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}
function kpi(label, value, sub) {
  return `<div class="kpi"><span class="k-label">${label}</span>
    <span class="k-value">${value ?? "—"}</span><span class="k-sub">${sub || ""}</span></div>`;
}
function tile(label, value, sub) {
  return `<div class="tile"><span class="tile-label">${label}</span>
    <span class="tile-value">${value ?? "—"}</span><span class="tile-sub">${sub || ""}</span></div>`;
}

// ---------- gauge de forma (TSB) ----------
function polarToXY(cx, cy, r, angleDeg) {
  const a = (angleDeg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}
function arcPath(cx, cy, r, a0, a1) {
  const [x0, y0] = polarToXY(cx, cy, r, a0);
  const [x1, y1] = polarToXY(cx, cy, r, a1);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  const sweep = a1 < a0 ? 1 : 0;
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${r} ${r} 0 ${large} ${sweep} ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}
function renderFormGauge(tsb) {
  const el = $("form-gauge");
  const MIN = -35, MAX = 20;
  const v = tsb == null ? MIN : Math.max(MIN, Math.min(MAX, tsb));
  const frac = (x) => (x - MIN) / (MAX - MIN);
  const ang = (x) => 180 - frac(x) * 180;           // MIN→180°(izq), MAX→0°(der)
  const cx = 120, cy = 118, r = 92;

  // segmentos de color (fatiga → forma → fresco)
  const segs = [
    [MIN, -20, "var(--red)"],
    [-20, -5, "var(--amber)"],
    [-5, 10, "var(--green)"],
    [10, MAX, "var(--ctl)"],
  ];
  let bg = "";
  for (const [a, b, c] of segs) {
    bg += `<path d="${arcPath(cx, cy, r, ang(a), ang(b))}" fill="none" stroke="${c}" stroke-width="13" stroke-linecap="butt" opacity="0.85"/>`;
  }
  const [nx, ny] = polarToXY(cx, cy, r - 6, ang(v));
  const label = tsb == null ? "—" : (tsb > 0 ? "+" : "") + Math.round(tsb);
  el.innerHTML = `
    <svg viewBox="0 0 240 150" role="img" aria-label="Forma (TSB) ${label}">
      ${bg}
      <line x1="${cx}" y1="${cy}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="6" fill="#fff"/>
      <text x="${cx}" y="96" text-anchor="middle" class="gauge-val" font-size="34" fill="#fff">${label}</text>
      <text x="26" y="140" text-anchor="middle" font-size="9" fill="var(--faint)">fatiga</text>
      <text x="214" y="140" text-anchor="middle" font-size="9" fill="var(--faint)">fresco</text>
    </svg>`;
}
function formStatus(tsb) {
  if (tsb == null) return ["—", ""];
  if (tsb > 8) return ["Fresco", "good"];
  if (tsb > -10) return ["Óptimo", "ok"];
  if (tsb > -22) return ["Cargado", "tired"];
  return ["Fatiga alta", "deep"];
}

// ---------- semáforo de sobreentrenamiento ----------
function renderSemaphore(ot) {
  if (!ot) { $("ot-summary").textContent = "Sin datos del semáforo todavía."; return; }
  $("ot-light").className = "sem-light " + (ot.level || "");
  $("ot-summary").textContent = ot.summary || "";
  $("ot-items").innerHTML = (ot.items || [])
    .map((i) => `<div class="ot-item"><span class="odot l${i.level}"></span>
      <span class="olabel">${i.label}</span><span class="odetail">${i.detail}</span></div>`).join("");
}

// ---------- barra de polarización ----------
function renderPolarBar(pol) {
  const el = $("polar-bar");
  if (!pol) { el.innerHTML = `<div style="padding:6px 10px;color:var(--muted);font-size:.78rem">Sin datos de tiempo en zonas todavía.</div>`; $("polar-verdict").textContent = ""; return; }
  const seg = (cls, pct) => pct > 0 ? `<div class="polar-seg ${cls}" style="width:${pct}%">${pct >= 8 ? pct + "%" : ""}</div>` : "";
  el.innerHTML = seg("low", pol.low_pct) + seg("mid", pol.mid_pct) + seg("high", pol.high_pct)
    + `<div class="polar-target-line" title="objetivo 80% suave"></div>`;
  const ok = pol.low_pct >= 75 && pol.high_pct <= 25;
  const v = $("polar-verdict");
  v.textContent = ok ? "✓ polarizado ~80/20" : "✗ demasiada intensidad";
  v.className = "polar-verdict " + (ok ? "good" : "bad");
}

async function init() {
  let data;
  try {
    const res = await fetch("data.json?t=" + Date.now());
    data = await res.json();
  } catch (e) {
    $("updated").textContent = "Sin datos todavía";
    $("plan-title").textContent = "Los datos aún no se generaron — esperá la primera ejecución.";
    return;
  }

  $("updated").textContent = "◉ " + data.generated_at.slice(0, 16).replace("T", " ");
  $("updated").className = "badge ok";

  const t = data.today || {};
  const p = data.plan || {};

  // ---- pill de forma
  const [fLabel, fCls] = formStatus(t.tsb);
  $("form-pill").textContent = fLabel;
  $("form-pill").className = "pill " + fCls;

  // ---- plan
  $("plan-kind-tag").textContent = KIND_TAG[p.kind] || "plan";
  $("plan-title").textContent = `${KIND_EMOJI[p.kind] || "📋"} ${p.title || "Plan de hoy"} · ${data.today.date}`;
  $("plan-steps").innerHTML = (p.steps || [])
    .map((s) => `<div class="step"><strong>${s.phase}:</strong> ${s.desc}</div>`).join("");
  $("plan-why").innerHTML = (p.why || []).map((w) => `<li>${w}</li>`).join("");

  let extra = "";
  if (p.push && p.push.status === "ok")
    extra += `<div class="step">⌚ <strong>Enviado a tu Garmin:</strong> este entreno ya está en tu calendario de Garmin Connect (vía intervals.icu).</div>`;
  if (p.route)
    extra += `<div class="step">🗺️ <strong>Ruta sugerida:</strong> ${p.route.name} — ${p.route.distance_km} km, ${p.route.elevation_m} m de desnivel (${p.route.reason}). ${p.route.challenge}</div>`;
  if (p.nutrition && p.nutrition.length)
    extra += `<details><summary>🍽️ Nutrición de hoy</summary><ul>` + p.nutrition.map((n) => `<li>${n}</li>`).join("") + `</ul></details>`;
  $("plan-extra").innerHTML = extra;

  // evidencia que respalda la sesión de hoy
  const pev = p.evidencia || [];
  if (pev.length) {
    $("plan-evidence").innerHTML = pev.map((e) =>
      `<div class="ev-item"><span class="ev-title">${e.titulo}</span>
        <span class="ev-src">${e.fuente}</span>
        <p class="ev-text">${e.principio}</p></div>`).join("");
  } else {
    $("plan-evidence-wrap").style.display = "none";
  }

  // ---- gauge + semáforo
  renderFormGauge(t.tsb);
  $("form-note").textContent = t.tsb == null ? "" :
    `TSB ${t.tsb > 0 ? "+" : ""}${t.tsb} = fitness (${t.ctl ?? "—"}) − fatiga (${t.atl ?? "—"}).`;
  renderSemaphore(data.overtraining);

  // ---- KPI strip
  $("load-tiles").innerHTML =
    kpi("Fitness · CTL", t.ctl, "carga crónica 42 d") +
    kpi("Fatiga · ATL", t.atl, "carga aguda 7 d") +
    kpi("Forma · TSB", t.tsb != null ? (t.tsb > 0 ? "+" : "") + t.tsb : null, "fitness − fatiga") +
    kpi("ACWR", t.acwr, t.acute_7d != null ? `${t.acute_7d} / ${t.chronic_weekly}` : "aguda / crónica");

  // ---- salud
  const hflags = (data.health || {}).flags || [];
  $("health-flags").innerHTML = hflags.length
    ? hflags.map((a) => `<div class="alert alert-${a.level}"><span class="alert-icon">${ALERT_ICONS[a.level] || "ℹ️"}</span><span>${a.text}</span></div>`).join("")
    : `<div class="alert alert-ok"><span class="alert-icon">✅</span><span>Sin desvíos en tus señales (FC en reposo, HRV, sueño y estrés dentro de tu rango habitual).</span></div>`;
  $("health-suggestions").innerHTML = ((data.health || {}).suggestions || []).map((s) => `<li>${s}</li>`).join("");

  // ---- calidad
  const q = data.quality || {};
  renderPolarBar(q.polarization);
  const qb = $("quality-body");
  if (qb) {
    let html = "";
    if (q.monotony != null) {
      const risky = q.monotony > 2;
      html += `<div class="step"><strong>Monotonía (Foster):</strong> ${q.monotony}
        ${risky ? "🟠 Alta (>2): carga muy repetitiva, sube el riesgo. Alterná días duros y suaves."
                : "✅ Buena variación día a día."}
        · <strong>Strain:</strong> ${q.strain ?? "—"} (carga semanal ${q.week_load ?? "—"} TSS).</div>`;
    }
    const dc = q.decoupling;
    if (dc) {
      const good = dc.value < 5;
      html += `<div class="step"><strong>Desacople aeróbico (última salida larga):</strong> ${dc.value}%
        ${good ? "✅ &lt;5%: buena base aeróbica y durabilidad."
               : "⚠️ &gt;5%: se te desacopla el pulso en salidas largas. Más fondo en Z2."}
        <span class="tile-sub">(${dc.name || ""}, ${dc.date || ""})</span></div>`;
    }
    const sj = data.subjective;
    if (sj && sj.rpe_filled)
      html += `<div class="step"><strong>Sensaciones (del reloj):</strong> cargás el esfuerzo percibido en ${sj.rpe_filled}/${sj.rpe_total} salidas ✅.
        Última: RPE ${sj.last_rpe}/10 (${sj.last_date}). Carga subjetiva 7 d (sRPE): ${sj.srpe_7d ?? "—"}.</div>`;
    else if (sj)
      html += `<div class="step"><strong>Sensaciones (del reloj):</strong> todavía no venís cargando el RPE al terminar. Si lo marcás en el reloj, lo uso solo.</div>`;
    if (sj && sj.cadence_avg)
      html += `<div class="step"><strong>Cadencia media (últimas salidas):</strong> ${sj.cadence_avg} rpm.
        La cadencia libre está bien; sumar bloques de cadencia alta da soltura, pero no es un pilar (evidencia débil para cadencia baja — Hansen 2020).</div>`;
    qb.innerHTML = html || `<p class="hint">Juntando datos para las métricas de calidad.</p>`;
  }

  // ---- LTHR + zonas con barras de color
  const lthr = data.lthr || null;
  const zclass = { "Z1 recuperación": "z1", "Z2 aeróbico": "z2", "Z3 tempo": "z3", "Z4 umbral": "z4", "Z5 VO2max": "z5" };
  if (!lthr) $("lthr-body").innerHTML = `<p class="hint">Todavía no hay salidas para estimar el umbral.</p>`;
  else if (lthr.error) $("lthr-body").innerHTML = `<p class="hint">${lthr.error}</p>`;
  else {
    const z = lthr.zones || {};
    const keys = Object.keys(z);
    const rows = keys.map((k, i) => {
      const w = 30 + (i * 68) / Math.max(1, keys.length - 1); // ancho creciente por zona
      return `<div class="zone-row"><span class="zname">${k}</span>
        <span class="zbar ${zclass[k] || "z2"}" style="width:${w}%"></span>
        <span class="zval">${z[k]}</span></div>`;
    }).join("");
    $("lthr-body").innerHTML =
      `<div class="tiles">
        <div class="tile"><span class="tile-label">LTHR estimado</span><span class="tile-value">${lthr.lthr}</span><span class="tile-sub">lpm · mejor 20 min</span></div>
        <div class="tile"><span class="tile-label">FC media salida</span><span class="tile-value">${lthr.avg_hr}</span><span class="tile-sub">máx ${lthr.max_hr} lpm</span></div>
      </div>
      <div class="zone-rows">${rows}</div>
      <p class="hint" style="margin-top:12px"><b>PROVISORIO — todavía no fijado como referencia.</b> ${lthr.note} Salida usada: ${lthr.name || ""} (${lthr.date || ""}).</p>`;
  }

  // ---- tests (tiles que abren un issue pre-cargado)
  renderTests();

  // ---- base científica
  const eb = $("evidence-body");
  const groups = data.evidencia || [];
  if (eb && groups.length) {
    eb.innerHTML = groups.map((g) =>
      `<div class="ev-group"><div class="ev-cat">${g.cat}</div>` +
      g.items.map((e) =>
        `<div class="ev-item"><span class="ev-title">${e.titulo}</span>
          <span class="ev-src">${e.fuente}</span>
          <p class="ev-text">${e.principio}</p></div>`).join("") +
      `</div>`).join("");
  } else if (eb) {
    eb.innerHTML = `<p class="hint">Base de evidencia cargándose.</p>`;
  }

  // ---- objetivos
  $("goals-body").innerHTML = (data.goals || [])
    .map((g) => `<tr><td>${g.metric}</td><td>${g.current ?? "—"}</td><td>${g.target ?? "—"}</td>
      <td>${g.by ?? "—"}</td><td style="white-space:normal">${g.note}</td></tr>`).join("");

  // ---- alertas de carga
  $("alerts").innerHTML = (data.alerts || [])
    .map((a) => `<div class="alert alert-${a.level}"><span class="alert-icon">${ALERT_ICONS[a.level] || "ℹ️"}</span><span>${a.text}</span></div>`).join("");

  // ---- gráfico
  renderLoadChart(data.series || []);
  $("load-table-body").innerHTML = (data.series || []).slice(-30).reverse()
    .map((x) => `<tr><td>${x.date}</td><td>${x.load}</td><td>${x.ctl}</td><td>${x.atl}</td><td>${x.tsb}</td></tr>`).join("");

  // ---- tendencias
  $("trend-tiles").innerHTML =
    tile("HRV última noche", t.hrv != null ? Math.round(t.hrv) + " ms" : null, `7d: ${t.hrv7 ?? "—"} · base 30d: ${t.hrv30 ?? "—"}`) +
    tile("FC en reposo", t.resting_hr != null ? Math.round(t.resting_hr) : null, `7d: ${t.rhr7 ?? "—"} · 30d: ${t.rhr30 ?? "—"}`) +
    tile("Sueño anoche", fmtDur(t.sleep_secs), t.sleep_score != null ? `score ${Math.round(t.sleep_score)}` : "") +
    tile("Readiness", t.readiness != null ? Math.round(t.readiness) : null, "de Garmin") +
    tile("Peso", t.weight != null ? t.weight + " kg" : null,
      t.weight7 != null ? `7d: ${t.weight7} kg` + (t.weight_delta30 != null ? ` · ${t.weight_delta30 > 0 ? "+" : ""}${t.weight_delta30} vs mes` : "") : "cargalo en Garmin") +
    tile("VO2max", t.vo2max != null ? t.vo2max : null, t.vo2max_delta90 != null ? `${t.vo2max_delta90 > 0 ? "+" : ""}${t.vo2max_delta90} en 90d` : "estimado Garmin") +
    tile("Estrés", t.stress != null ? Math.round(t.stress) : null, t.stress7 != null ? `7d: ${t.stress7}` : "0-100");

  // ---- salidas
  $("rides-body").innerHTML = (data.rides || [])
    .map((r) => `<tr><td>${r.date}</td><td>${r.name || "—"}</td>
      <td>${(r.type || "").replace(/([A-Z])/g, " $1").trim()}</td>
      <td>${r.distance_km ? r.distance_km + " km" : "—"}</td><td>${fmtDur(r.moving_time_s)}</td>
      <td>${r.elevation_m ? Math.round(r.elevation_m) + " m" : "—"}</td>
      <td>${r.avg_hr ? Math.round(r.avg_hr) : "—"}</td><td>${r.load ? Math.round(r.load) : "—"}</td></tr>`).join("");

  $("footer-note").textContent =
    `Datos vía intervals.icu (sincronizado con tu Garmin). Se actualiza solo cada 3 horas. ` +
    `${data.counts.rides_180d} salidas y ${data.counts.wellness_days} días de bienestar en 6 meses.`;
}

// ---------- tests: enlaces a issue pre-cargado ----------
function issueURL(key, dateStr) {
  const title = `cargar-test: ${key}`;
  let body = `Cargar el test **${key}** en mi Garmin.\n\n`;
  body += dateStr ? `Fecha: ${dateStr}\n` : `Fecha: (vacío = mañana)\n`;
  body += `\n_Confirmá tocando el botón verde "Submit new issue". El sistema lo carga en tu reloj y cierra este aviso solo._`;
  return `https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}
function renderTests() {
  const dateStr = ($("test-date").value || "").trim();
  const grid = $("tests-grid");
  if (!grid.innerHTML || renderTests._last !== dateStr) {
    grid.innerHTML = TESTS.map(([key, name, desc]) =>
      `<a class="test-tile" target="_blank" rel="noopener" href="${issueURL(key, dateStr)}">
        <span class="t-name">${name}</span><span class="t-desc">${desc}</span>
        <span class="t-cta">Cargar al reloj →</span></a>`).join("");
    renderTests._last = dateStr;
  }
}

// ---------- gráfico de carga ----------
const SERIES = [
  { key: "ctl", name: "Fitness", color: "var(--ctl)", width: 2.6, area: true },
  { key: "atl", name: "Fatiga", color: "var(--atl)", width: 2 },
  { key: "tsb", name: "Forma", color: "var(--tsb)", width: 2 },
];
function renderLoadChart(series) {
  const el = $("load-chart");
  if (!series.length) { el.innerHTML = `<p class="hint">Sin datos de carga todavía.</p>`; return; }
  const W = 820, H = 280, padL = 40, padR = 62, padT = 14, padB = 26;
  const xs = series.map((_, i) => padL + (i * (W - padL - padR)) / Math.max(1, series.length - 1));
  const values = series.flatMap((p) => [p.ctl, p.atl, p.tsb]);
  const yMin = Math.min(0, ...values), yMax = Math.max(10, ...values);
  const y = (v) => padT + ((yMax - v) / (yMax - yMin || 1)) * (H - padT - padB);

  const step = Math.max(10, Math.ceil((yMax - yMin) / 5 / 10) * 10);
  let grid = "", labels = "";
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) {
    grid += `<line x1="${padL}" x2="${W - padR}" y1="${y(v)}" y2="${y(v)}" stroke="${v === 0 ? "var(--axis)" : "var(--grid)"}" stroke-width="1"/>`;
    labels += `<text x="${padL - 6}" y="${y(v) + 3}" text-anchor="end" font-size="10" fill="var(--faint)">${v}</text>`;
  }
  const every = Math.max(1, Math.floor(series.length / 6));
  series.forEach((pt, i) => {
    if (i % every === 0) labels += `<text x="${xs[i]}" y="${H - 8}" text-anchor="middle" font-size="10" fill="var(--faint)">${pt.date.slice(5)}</text>`;
  });

  let areas = "", lines = "", endLabels = "";
  const usedY = [];
  for (const s of SERIES) {
    const pts = series.map((pt, i) => `${xs[i].toFixed(1)},${y(pt[s.key]).toFixed(1)}`).join(" ");
    if (s.area) {
      const base = y(Math.max(0, yMin));
      areas += `<polygon points="${xs[0].toFixed(1)},${base.toFixed(1)} ${pts} ${xs[xs.length - 1].toFixed(1)},${base.toFixed(1)}" fill="url(#ctlfill)" opacity="0.5"/>`;
    }
    lines += `<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="${s.width}" stroke-linejoin="round" stroke-linecap="round"/>`;
    let ly = y(series[series.length - 1][s.key]) + 3;
    while (usedY.some((u) => Math.abs(u - ly) < 12)) ly += 12;
    usedY.push(ly);
    endLabels += `<circle cx="${W - padR + 6}" cy="${ly - 3}" r="3.5" fill="${s.color}"/>
      <text x="${W - padR + 13}" y="${ly}" font-size="10" fill="var(--muted)">${s.name}</text>`;
  }

  el.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolución de fitness, fatiga y forma">
      <defs><linearGradient id="ctlfill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="var(--ctl)" stop-opacity="0.35"/>
        <stop offset="1" stop-color="var(--ctl)" stop-opacity="0"/>
      </linearGradient></defs>
      ${grid}${areas}${labels}${lines}${endLabels}
      <line id="crosshair" y1="${padT}" y2="${H - padB}" stroke="var(--axis)" stroke-width="1" style="display:none"/>
    </svg>
    <div class="chart-tooltip" id="load-tooltip"></div>`;

  const svg = el.querySelector("svg"), cross = el.querySelector("#crosshair"), tip = $("load-tooltip");
  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const mx = ((ev.clientX - rect.left) / rect.width) * W;
    let i = Math.round(((mx - padL) / (W - padL - padR)) * (series.length - 1));
    i = Math.max(0, Math.min(series.length - 1, i));
    const pt = series[i];
    cross.style.display = ""; cross.setAttribute("x1", xs[i]); cross.setAttribute("x2", xs[i]);
    tip.style.display = "block";
    tip.innerHTML = `<strong>${pt.date}</strong>` +
      SERIES.map((s) => `<div class="tt-row"><span class="dot" style="background:${s.color}"></span>${s.name}<span class="tt-val">${pt[s.key]}</span></div>`).join("") +
      `<div class="tt-row">Carga del día<span class="tt-val">${pt.load}</span></div>`;
    const px = (xs[i] / W) * rect.width;
    tip.style.left = Math.min(px + 12, rect.width - tip.offsetWidth - 4) + "px";
    tip.style.top = "18px";
  });
  svg.addEventListener("mouseleave", () => { cross.style.display = "none"; tip.style.display = "none"; });
}

// listeners
$("toggle-load-table").addEventListener("click", () => {
  const wrap = $("load-table-wrap");
  wrap.classList.toggle("hidden");
  $("toggle-load-table").textContent = wrap.classList.contains("hidden") ? "Ver tabla" : "Ocultar tabla";
});
const td = document.getElementById("test-date");
if (td) td.addEventListener("change", renderTests);

init().catch((err) => {
  console.error("Error al renderizar el dashboard:", err);
  const u = document.getElementById("updated");
  if (u) u.textContent = "Error al mostrar los datos (recargá la página)";
});
