// PELOTÓN — dashboard estático. Lee data.json (generado por GitHub Actions).

const $ = (id) => document.getElementById(id) || {};
const REPO = "emanuellezcanolic-oss/Garmin-Ciclismo-EMa";
let RIDES = [];

// progreso hacia un objetivo (qué tan lejos estás)
function goalProgress(g) {
  if (g.current == null || g.target == null || g.start == null) return null;
  const u = g.unit ? " " + g.unit : "";
  if (g.dir === "keep") {
    const d = Math.round((g.current - g.start) * 10) / 10;
    return { keep: true, pct: d >= 0 ? 100 : 72, txt: d >= 0 ? "✓ mantenida" : `▼ ${d}${u}` };
  }
  const span = g.target - g.start;
  let pct = span ? ((g.current - g.start) / span) * 100 : 0;
  pct = Math.max(0, Math.min(100, pct));
  const left = Math.round(Math.abs(g.target - g.current) * 10) / 10;
  return { pct, txt: pct >= 100 ? "✓ cumplido" : `faltan ${left}${u}` };
}

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

  // ---- periodización
  renderPeriodizacion(data.periodizacion);

  // ---- composición corporal
  renderComposicion(t);

  // ---- salud / estudios + medidas
  renderSalud(data.salud);
  renderMedidas(data.medidas);

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

  // ---- objetivos (con barra de progreso: qué tan lejos del objetivo)
  $("goals-body").innerHTML = (data.goals || []).map((g) => {
    const p = goalProgress(g);
    const cell = p
      ? `<div class="goal-prog"><div class="gp-bar"><span class="${p.keep ? "keep" : ""}" style="width:${p.pct}%"></span></div>
          <span class="gp-txt">${p.txt}</span></div>`
      : `<span class="hint">—</span>`;
    return `<tr><td>${g.metric}</td><td>${g.current ?? "—"}</td><td>${g.target ?? "—"}</td>
      <td>${cell}</td><td style="white-space:normal">${g.note}</td></tr>`;
  }).join("");

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

  // ---- salidas (filas desplegables: tocá una para ver su dashboard)
  RIDES = data.rides || [];
  $("rides-body").innerHTML = RIDES.map((r, i) => `<tr class="ride-row" data-ride="${i}">
      <td>${r.date}</td><td>${r.name || "—"}</td>
      <td>${(r.type || "").replace(/([A-Z])/g, " $1").trim()}</td>
      <td>${r.distance_km ? r.distance_km + " km" : "—"}</td><td>${fmtDur(r.moving_time_s)}</td>
      <td>${r.elevation_m ? Math.round(r.elevation_m) + " m" : "—"}</td>
      <td>${r.avg_hr ? Math.round(r.avg_hr) : "—"}</td>
      <td>${r.load ? Math.round(r.load) : "—"} <span class="ride-caret">▸</span></td></tr>`).join("");
  wireRideRows();

  $("footer-note").textContent =
    `Datos vía intervals.icu (sincronizado con tu Garmin). Se actualiza solo cada 3 horas. ` +
    `${data.counts.rides_180d} salidas y ${data.counts.wellness_days} días de bienestar en 6 meses.`;
}

// ---------- composición corporal ----------
// ---------- salud / estudios ----------
function renderSalud(salud) {
  const el = $("salud-body");
  if (!el) return;
  if (!Array.isArray(salud) || !salud.length) {
    el.innerHTML = `<p class="hint">Todavía no hay estudios cargados.</p>`;
    return;
  }
  el.innerHTML = salud.map((s) => {
    const r = s.resumen || {};
    const kpis = [
      ["FC máx", r.fc_max_alcanzada, "lpm", r.fc_max_pct || ""],
      ["FC reposo", r.fc_reposo, "lpm", ""],
      ["PA máx", r.pa_max, "", "reposo " + (r.pa_reposo || "—")],
      ["METS máx", r.mets_max, "", "VO2 ~" + (r.vo2_estimado_carga || "—")],
      ["HRR 1 min", r.hrr_1min, "lpm", "recuperación"],
      ["Carga máx", r.carga_max, "", r.protocolo || ""],
    ].filter((k) => k[1] != null && k[1] !== "");
    const kpiHtml = kpis.map((k) =>
      `<div class="rm-tile"><span class="rm-label">${k[0]}</span>
        <span class="rm-value">${k[1]}${k[2] ? " " + k[2] : ""}</span><span class="rm-sub">${k[3]}</span></div>`).join("");
    const etapas = (s.etapas || []).map((e) =>
      `<tr><td>${e.etapa}</td><td>${e.dur}</td><td>${e.carga}</td><td>${e.mets}</td><td>${e.fc}</td><td>${e.pa}</td><td>${e.st}</td></tr>`).join("");
    // zonas informativas por %FCmáx del estudio
    const hrmax = r.fc_max_alcanzada;
    let zonas = "";
    if (hrmax) {
      const z = [["Z1 recuperación", .5, .6], ["Z2 aeróbico", .6, .7], ["Z3 tempo", .7, .8], ["Z4 umbral", .8, .9], ["Z5 VO2máx", .9, 1]];
      zonas = `<div class="rd-block"><div class="rd-title">Zonas por %FC máx (${hrmax} lpm) — informativo</div>
        <div class="table-wrap"><table><thead><tr><th>Zona</th><th>%FCmáx</th><th>FC (lpm)</th></tr></thead><tbody>` +
        z.map(([n, a, b]) => `<tr><td>${n}</td><td>${Math.round(a*100)}–${Math.round(b*100)}%</td><td>${Math.round(hrmax*a)}–${Math.round(hrmax*b)}</td></tr>`).join("") +
        `</tbody></table></div><p class="hint" style="margin-top:6px">Referencia por FC máx. Tus zonas de entrenamiento siguen basadas en el umbral (LTHR); confirmá con el test de 30 min.</p></div>`;
    }
    return `<article class="card estudio">
      <div class="card-eyebrow">${s.fecha} · ${s.centro || ""}</div>
      <h2>${s.tipo}</h2>
      <p class="hint">${s.medico || ""}${s.indicaciones ? " · " + s.indicaciones : ""}
        ${s.antropometria ? ` · ${s.antropometria.edad} años · ${s.antropometria.peso_kg} kg · ${s.antropometria.talla_cm} cm · IMC ${s.antropometria.imc}` : ""}</p>
      <div class="ride-metrics">${kpiHtml}</div>
      <div class="rd-block"><div class="rd-title">Etapas del esfuerzo</div>
        <div class="table-wrap"><table><thead><tr><th>Etapa</th><th>Dur.</th><th>Carga</th><th>METS</th><th>FC</th><th>PA</th><th>ST</th></tr></thead>
        <tbody>${etapas}</tbody></table></div></div>
      ${(s.conclusiones_informe || []).length ? `<div class="rd-block"><div class="rd-title">Conclusiones del informe (Dr. Moriniго)</div><ul class="hint-list">${s.conclusiones_informe.map((c) => `<li>${c}</li>`).join("")}</ul></div>` : ""}
      ${(s.analisis_entrenador || []).length ? `<div class="rd-block sal-analisis"><div class="rd-title">🫀 Análisis del entrenador (cardiología deportiva)</div><ul class="hint-list">${s.analisis_entrenador.map((c) => `<li>${c}</li>`).join("")}</ul></div>` : ""}
      ${(s.datos_entrenamiento || []).length ? `<div class="rd-block"><div class="rd-title">📌 Datos para tu entrenamiento</div><ul class="hint-list">${s.datos_entrenamiento.map((c) => `<li>${c}</li>`).join("")}</ul></div>` : ""}
      ${zonas}
      ${s.disclaimer ? `<p class="hint" style="margin-top:12px;border-left:2px solid var(--amber);padding-left:10px">${s.disclaimer}</p>` : ""}
    </article>`;
  }).join("");
}

// ---------- medidas corporales (con dibujo de cómo medir) ----------
const ARV = (x, y1, y2) => `<line x1="${x}" y1="${y1}" x2="${x}" y2="${y2}" class="ms-arrow"/><path class="ms-arrow" d="M${x-3} ${y1+6} L${x} ${y1} L${x+3} ${y1+6}"/><path class="ms-arrow" d="M${x-3} ${y2-6} L${x} ${y2} L${x+3} ${y2-6}"/>`;
const ARH = (y, x1, x2) => `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" class="ms-arrow"/><path class="ms-arrow" d="M${x1+6} ${y-3} L${x1} ${y} L${x1+6} ${y+3}"/><path class="ms-arrow" d="M${x2-6} ${y-3} L${x2} ${y} L${x2-6} ${y+3}"/>`;
const MS = {
  peso: `<circle cx="60" cy="62" r="34" class="ms-body"/><path class="ms-body" d="M40 62 A20 20 0 0 1 80 62"/><line x1="60" y1="62" x2="72" y2="50" class="ms-arrow"/><circle cx="60" cy="62" r="3" class="ms-arrow"/>`,
  altura: `<circle cx="42" cy="22" r="9" class="ms-body"/><path class="ms-body" d="M42 31 V66 M42 42 L28 56 M42 42 L56 56 M42 66 L32 100 M42 66 L52 100"/>${ARV(92, 13, 104)}`,
  pecho: `<path class="ms-body" d="M40 24 Q60 18 80 24 L82 92 Q60 100 38 92 Z"/><path class="ms-body" d="M40 24 L34 40 M80 24 L86 40" fill="none"/><ellipse cx="60" cy="44" rx="26" ry="7" class="ms-dash"/>${ARH(44, 30, 90)}`,
  cintura: `<path class="ms-body" d="M40 24 Q60 18 80 24 L82 92 Q60 100 38 92 Z"/><ellipse cx="60" cy="66" rx="24" ry="7" class="ms-dash"/>${ARH(66, 32, 88)}`,
  cadera: `<path class="ms-body" d="M42 24 L78 24 L84 96 L36 96 Z"/><ellipse cx="60" cy="86" rx="27" ry="7" class="ms-dash"/>${ARH(86, 30, 90)}`,
  entrepierna: `<path class="ms-body" d="M40 20 H80 V44 L72 104 M40 20 V44 L48 104 M60 30 V44"/>${ARV(96, 44, 104)}`,
  brazo: `<path class="ms-body" d="M40 24 L54 30 L66 64 L60 100"/><circle cx="40" cy="22" r="7" class="ms-body"/>${ARV(92, 30, 100)}`,
  biceps: `<path class="ms-body" d="M44 24 Q66 30 62 60 L58 100"/><ellipse cx="55" cy="44" rx="16" ry="6" class="ms-dash"/>${ARH(44, 40, 74)}`,
  pie: `<path class="ms-body" d="M26 74 Q22 58 40 56 L86 60 Q98 62 96 72 Q94 80 80 80 L36 80 Q28 80 26 74 Z"/>${ARH(96, 26, 96)}`,
  mano_largo: `<path class="ms-body" d="M44 104 L44 60 M52 104 L52 40 M60 104 L60 34 M68 104 L68 42 M40 72 Q30 66 34 78 L44 92 M44 104 L68 104"/>${ARV(96, 34, 104)}`,
  mano_contorno: `<path class="ms-body" d="M44 104 L44 56 M52 104 L52 40 M60 104 L60 36 M68 104 L68 44 M44 104 L68 104"/><line x1="38" y1="60" x2="74" y2="60" class="ms-dash"/>${ARH(60, 40, 74)}`,
  cabeza: `<circle cx="60" cy="52" r="30" class="ms-body"/><path class="ms-body" d="M50 60 Q60 68 70 60" fill="none"/><ellipse cx="60" cy="44" rx="31" ry="9" class="ms-dash"/>${ARH(44, 27, 93)}`,
};
function measureDiagram(key) {
  return `<svg class="ms-svg" viewBox="0 0 120 120" aria-hidden="true">${MS[key] || MS.peso}</svg>`;
}
function medidaIssueURL(medidas) {
  const lines = (medidas || []).filter((m) => m.key !== "peso")
    .map((m) => `${m.key}: ${m.value != null ? m.value : ""}`).join("\n");
  const body = `Cargá/actualizá tus medidas (en cm; dejá vacío lo que no tengas):\n\n${lines}\n\n` +
    `_Confirmá con "Submit new issue". El sistema las guarda y actualiza tu sección Medidas._`;
  return `https://github.com/${REPO}/issues/new?title=${encodeURIComponent("cargar-medidas")}&body=${encodeURIComponent(body)}`;
}
function renderMedidas(medidas) {
  const el = $("medidas-body");
  if (!el) return;
  const add = document.getElementById("medidas-add");
  if (add) add.href = medidaIssueURL(medidas);
  if (!Array.isArray(medidas) || !medidas.length) {
    el.innerHTML = `<p class="hint">Todavía no cargaste medidas. Tocá “Cargar / actualizar medidas”.</p>`;
    return;
  }
  const grupos = {};
  medidas.forEach((m) => { (grupos[m.grupo] = grupos[m.grupo] || []).push(m); });
  el.innerHTML = Object.entries(grupos).map(([grupo, items]) =>
    `<div class="med-group"><div class="med-group-title">${grupo}</div>
      <div class="med-grid">` +
      items.map((m) => `<div class="med-card">
        <div class="med-diagram">${measureDiagram(m.svg)}</div>
        <div class="med-info">
          <div class="med-top"><span class="med-label">${m.label}</span>
            <span class="med-value">${m.value != null ? m.value + " " + m.unit : "—"}</span></div>
          ${m.guia ? `<div class="med-guia">${m.guia}</div>` : ""}
          <div class="med-how">📐 ${m.como_medir}</div>
        </div>
      </div>`).join("") +
      `</div></div>`).join("");
}

// ---------- navegación por secciones (sidebar) ----------
function wireNav() {
  const items = document.querySelectorAll(".nav-item");
  const show = (view) => {
    document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== "view-" + view; });
    items.forEach((i) => i.classList.toggle("active", i.dataset.view === view));
    try { localStorage.setItem("peloton-view", view); } catch (e) {}
    window.scrollTo(0, 0);
  };
  items.forEach((i) => i.addEventListener("click", () => show(i.dataset.view)));
  let start = "panel";
  try { start = localStorage.getItem("peloton-view") || "panel"; } catch (e) {}
  if (!document.getElementById("view-" + start)) start = "panel";
  show(start);
}

function renderComposicion(t) {
  const el = $("composicion-body");
  if (!el) return;
  const hasData = t && (t.body_fat != null || t.lean != null || t.fat_mass != null);
  if (!hasData) {
    el.innerHTML = `<p class="hint">Todavía no llega tu composición corporal. Pesate en tu balanza
      <b>Femmto</b> 2-3 veces por semana (en ayunas, sincronizada a Garmin): cuando el % de grasa y
      la masa magra lleguen a intervals.icu, esta tarjeta se activa sola y le pone objetivos.</p>`;
    return;
  }
  // delta: para grasa, bajar es bueno; para músculo, subir es bueno
  const delta = (v, goodDown) => {
    if (v == null) return `<span class="c-delta">—</span>`;
    const good = goodDown ? v < 0 : v > 0;
    const arrow = v < 0 ? "▼" : v > 0 ? "▲" : "•";
    const cls = v === 0 ? "" : good ? "good" : "bad";
    return `<span class="c-delta ${cls}">${arrow} ${v > 0 ? "+" : ""}${v} vs mes</span>`;
  };
  const box = (label, val, unit, d, goodDown) =>
    `<div class="comp-kpi"><span class="ck-label">${label}</span>
      <span class="ck-value">${val != null ? val : "—"}<small>${val != null ? " " + unit : ""}</small></span>
      ${delta(d, goodDown)}</div>`;
  const fecha = t.comp_date ? ` · medición ${t.comp_date}${t.comp_source ? " (" + t.comp_source + ")" : ""}` : "";
  el.innerHTML =
    `<div class="comp-grid comp-grid-4">
      ${box("% de grasa", t.body_fat, "%", t.body_fat_delta30, true)}
      ${box("Masa grasa", t.fat_mass, "kg", t.fat_mass_delta30, true)}
      ${box("Masa magra", t.lean, "kg", t.lean_delta30, false)}
      ${box("Músculo (MME)", t.muscle, "kg", t.muscle_delta30, false)}
    </div>
    <p class="hint" style="margin-top:12px">Es la <b>grasa</b> la que baja tu potencia/kg, no el músculo
    (Arriel 2020; de Moura 2025). El plan: bajar grasa <b>preservando músculo</b> — mirá la tendencia de
    semanas, no el número de un día${fecha}.</p>
    <a class="test-tile comp-add" target="_blank" rel="noopener" href="${pesoIssueURL()}" style="max-width:320px">
      <span class="t-name">➕ Cargar medición de la balanza</span>
      <span class="t-desc">Se abre GitHub con una plantilla; completás peso, % grasa, masa grasa y músculo, confirmás y se suma solo.</span>
      <span class="t-cta">Cargar composición →</span></a>`;
}
function pesoIssueURL() {
  const hoy = new Date().toISOString().slice(0, 10);
  const title = "cargar-peso";
  const body = `Medición de la balanza. Completá los valores (dejá lo que no tengas):\n\n` +
    `fecha: ${hoy}\npeso: \ngrasa: \nmasa_grasa: \nmusculo: \n\n` +
    `_Confirmá con "Submit new issue". El sistema la suma a tu seguimiento y cierra este aviso._`;
  return `https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

// ---------- periodización ----------
function renderPeriodizacion(pz) {
  if (!pz || !pz.actual) return;
  const f = pz.actual;
  const deload = f.deload
    ? `<span class="fase-badge deload">semana de descarga</span>`
    : `<span class="fase-badge">carga</span>`;
  $("fase-actual").innerHTML = `
    <div class="fase-top">
      <div>
        <span class="fase-name">${f.fase}</span>
        <span class="fase-week">semana ${f.semana_global} / ${f.total_semanas}</span>
      </div>
      ${deload}
    </div>
    <p class="fase-foco">${f.foco}</p>
    <div class="fase-targets">
      <div class="ft"><span class="ft-val">${f.vol_pct}%</span><span class="ft-lbl">volumen ref.</span></div>
      <div class="ft"><span class="ft-val">${f.objetivo_tss}</span><span class="ft-lbl">objetivo TSS/sem</span></div>
      <div class="ft"><span class="ft-val">${f.dias_calidad}</span><span class="ft-lbl">días de calidad</span></div>
      <div class="ft"><span class="ft-val">≤${f.cap_high}%</span><span class="ft-lbl">techo intensidad</span></div>
    </div>`;
  $("season-map").innerHTML = (pz.mapa || [])
    .map((b) => `<div class="seg ${b.activo ? "active" : ""}">
      <span class="seg-name">${b.nombre}</span>
      <span class="seg-weeks">sem ${b.semanas}</span>
      <span class="seg-foco">${b.foco}</span>
    </div>`).join("");
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

// ---------- dashboard por salida ----------
function wireRideRows() {
  const rb = document.getElementById("rides-body");
  if (!rb) return;
  rb.onclick = (e) => {
    const row = e.target.closest(".ride-row");
    if (!row) return;
    const open = rb.querySelector(".ride-detail");
    const openFor = open ? open.dataset.for : null;
    rb.querySelectorAll(".ride-detail").forEach((d) => d.remove());
    rb.querySelectorAll(".ride-row.open").forEach((r) => r.classList.remove("open"));
    if (openFor === row.dataset.ride) return;             // ya estaba abierta → cerrar
    row.classList.add("open");
    const tr = document.createElement("tr");
    tr.className = "ride-detail";
    tr.dataset.for = row.dataset.ride;
    tr.innerHTML = `<td colspan="8">${renderRideDetail(RIDES[+row.dataset.ride])}</td>`;
    row.after(tr);
  };
}

function metricTile(label, value, sub) {
  if (value == null || value === "" || value === "—") return "";
  return `<div class="rm-tile"><span class="rm-label">${label}</span>
    <span class="rm-value">${value}</span><span class="rm-sub">${sub || ""}</span></div>`;
}

function zoneDist(zt) {
  if (!Array.isArray(zt) || !zt.length) return null;
  const tot = zt.reduce((a, b) => a + (b || 0), 0);
  if (tot <= 0) return null;
  const low = (zt[0] || 0) + (zt[1] || 0);
  const mid = zt[2] || 0;
  const high = zt.slice(3).reduce((a, b) => a + (b || 0), 0);
  return { tot, low_pct: Math.round(low / tot * 100), mid_pct: Math.round(mid / tot * 100), high_pct: Math.round(high / tot * 100) };
}

function renderZoneBar(zt) {
  const dist = zoneDist(zt);
  if (!dist) return `<p class="hint">Esta salida no trae tiempo en zonas de FC.</p>`;
  const zc = ["z1", "z2", "z3", "z4", "z5", "z5", "z5"];
  const seg = zt.map((s, i) => {
    const p = Math.round((s || 0) / dist.tot * 100);
    return p > 0 ? `<div class="zseg ${zc[i] || "z5"}" style="width:${p}%" title="Z${i + 1}: ${p}%">${p >= 8 ? "Z" + (i + 1) : ""}</div>` : "";
  }).join("");
  return `<div class="zone-bar">${seg}</div>
    <div class="zone-legend"><span>Suave ${dist.low_pct}%</span><span>Medio ${dist.mid_pct}%</span><span>Duro ${dist.high_pct}%</span></div>`;
}

function rideReading(r) {
  const d = zoneDist(r.zone_times);
  if (!d) return "";
  let tipo, ok;
  if (d.high_pct >= 15) { tipo = "Salida de calidad: bastante tiempo en Z4/Z5 (umbral/VO2max)."; ok = false; }
  else if (d.mid_pct >= 25) { tipo = "Trabajo de tempo/umbral: mucho tiempo en Z3."; ok = false; }
  else { tipo = "Base aeróbica: mayormente Z1–Z2, bajo costo de fatiga."; ok = true; }
  const pol = d.low_pct >= 80 ? "Respetó el reparto 80/20 ✅." : "Cargó intensidad: contá esto como parte de tu 20% duro.";
  return `<p class="ride-read">${tipo} ${pol}</p>`;
}

function renderRideDetail(r) {
  if (!r) return "";
  const IF = r.intensity != null ? Math.round(r.intensity) + "%" : null;
  const grid =
    metricTile("Distancia", r.distance_km != null ? r.distance_km + " km" : null) +
    metricTile("Tiempo", fmtDur(r.moving_time_s)) +
    metricTile("Desnivel", r.elevation_m != null ? Math.round(r.elevation_m) + " m" : null) +
    metricTile("FC promedio", r.avg_hr != null ? Math.round(r.avg_hr) : null, r.max_hr != null ? "máx " + Math.round(r.max_hr) : "") +
    metricTile("Carga (TSS)", r.load ? Math.round(r.load) : null) +
    metricTile("Intensidad (IF)", IF, "esfuerzo relativo") +
    metricTile("Cadencia", r.cadence != null ? Math.round(r.cadence) + " rpm" : null) +
    metricTile("Calorías", r.calories != null ? Math.round(r.calories) + " kcal" : null) +
    metricTile("RPE / sensación", r.rpe != null ? r.rpe + "/10" : null, r.feel != null ? "feel " + r.feel + "/5" : "") +
    metricTile("Desacople", r.decoupling != null ? r.decoupling.toFixed(1) + "%" : null, r.decoupling != null ? (r.decoupling < 5 ? "buena durabilidad" : "se te desacopló") : "") +
    metricTile("Potencia media", r.avg_watts != null ? Math.round(r.avg_watts) + " W" : null, r.np_watts != null ? "NP " + Math.round(r.np_watts) : "");
  return `<div class="ride-panel">
    <div class="ride-metrics">${grid}</div>
    <div class="rd-block"><div class="rd-title">Intensidad de la salida (tiempo en zonas de FC)</div>${renderZoneBar(r.zone_times)}</div>
    ${rideReading(r)}
  </div>`;
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

wireNav();

init().catch((err) => {
  console.error("Error al renderizar el dashboard:", err);
  const u = document.getElementById("updated");
  if (u) u.textContent = "Error al mostrar los datos (recargá la página)";
});
