// Dashboard estático: lee data.json (generado por GitHub Actions) y renderiza.

const $ = (id) => document.getElementById(id) || { };  // nunca null: evita que un id faltante rompa toda la página

const KIND_EMOJI = {
  descanso: "😴", suave: "🟢", resistencia: "🚴", tempo: "🟡", intensidad: "🔥",
};
const ALERT_ICONS = { warning: "⚠️", serious: "🟠", critical: "🛑" };

function fmtDur(secs) {
  if (!secs) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.round((secs % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

function tile(label, value, sub) {
  return `<div class="tile"><span class="tile-label">${label}</span>
    <span class="tile-value">${value ?? "—"}</span><span class="tile-sub">${sub || ""}</span></div>`;
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

  $("updated").textContent = "Actualizado: " + data.generated_at.slice(0, 16).replace("T", " ");
  $("updated").className = "badge ok";

  // ---- plan de hoy
  const p = data.plan || {};
  $("plan-title").textContent = `${KIND_EMOJI[p.kind] || "📋"} Plan de hoy (${data.today.date}): ${p.title}`;
  $("plan-steps").innerHTML = (p.steps || [])
    .map((s) => `<div class="step"><strong>${s.phase}:</strong> ${s.desc}</div>`)
    .join("");
  $("plan-why").innerHTML = (p.why || []).map((w) => `<li>${w}</li>`).join("");

  let extra = "";
  if (p.push && p.push.status === "ok") {
    extra += `<div class="step">⌚ <strong>Enviado a tu Garmin</strong>: este entreno ya está en tu calendario de Garmin Connect (vía intervals.icu).</div>`;
  }
  if (p.route) {
    extra += `<div class="step">🗺️ <strong>Ruta sugerida:</strong> ${p.route.name} — ${p.route.distance_km} km, ${p.route.elevation_m} m de desnivel (${p.route.reason}). ${p.route.challenge}</div>`;
  }
  if (p.nutrition && p.nutrition.length) {
    extra += `<details><summary>🍽️ Nutrición de hoy (plan Lic. Zalazar)</summary><ul>` +
      p.nutrition.map((n) => `<li>${n}</li>`).join("") + `</ul></details>`;
  }
  $("plan-extra").innerHTML = extra;

  const health = data.health || {};
  const hflags = health.flags || [];
  $("health-flags").innerHTML = hflags.length
    ? hflags.map((a) => `<div class="alert alert-${a.level}">
        <span class="alert-icon">${ALERT_ICONS[a.level] || "ℹ️"}</span><span>${a.text}</span></div>`).join("")
    : `<div class="alert" style="background:#eef7ee"><span class="alert-icon">✅</span>
       <span>Sin desvíos en tus señales (FC en reposo, HRV, sueño y estrés dentro de tu rango habitual).</span></div>`;
  $("health-suggestions").innerHTML = (health.suggestions || [])
    .map((s) => `<li>${s}</li>`).join("");

  const q = data.quality || {};
  const qb = $("quality-body");
  if (qb) {
    let html = "";
    const pol = q.polarization;
    if (pol) {
      const okPolar = pol.low_pct >= 75 && pol.high_pct <= 25;
      html += `<div class="step"><strong>Distribución de intensidad (7 días):</strong>
        suave ${pol.low_pct}% · medio ${pol.mid_pct}% · duro ${pol.high_pct}%.
        ${okPolar ? "✅ Reparto polarizado (~80/20), como los de élite (Seiler)."
                  : "⚠️ Alejado del 80/20: demasiado tiempo en intensidad media/alta. Sumá más Z2 suave."}</div>`;
    } else {
      html += `<div class="step"><strong>Distribución de intensidad:</strong> sin datos de tiempo en zonas todavía.</div>`;
    }
    if (q.monotony != null) {
      const risky = q.monotony > 2;
      html += `<div class="step"><strong>Monotonía (Foster):</strong> ${q.monotony}
        ${risky ? "🟠 Alta (>2): tu carga es muy repetitiva, sube el riesgo de enfermedad/sobreentrenamiento. Variá días duros y suaves."
                : "✅ Buena variación día a día."}
        · <strong>Strain:</strong> ${q.strain ?? "—"} (carga semanal ${q.week_load ?? "—"} TSS).</div>`;
    }
    const dc = q.decoupling;
    if (dc) {
      const good = dc.value < 5;
      html += `<div class="step"><strong>Desacople aeróbico (última salida larga):</strong> ${dc.value}%
        ${good ? "✅ <5%: buena base aeróbica y durabilidad."
               : "⚠️ >5%: se te desacopla el pulso en salidas largas (fatiga, deshidratación o falta de base). Más fondo en Z2."}
        <span class="tile-sub">(${dc.name || ""}, ${dc.date || ""})</span></div>`;
    }
    const sj = data.subjective;
    if (sj && sj.rpe_filled) {
      html += `<div class="step"><strong>Sensaciones (del reloj):</strong>
        cargás el esfuerzo percibido en ${sj.rpe_filled}/${sj.rpe_total} salidas ✅.
        Última: RPE ${sj.last_rpe}/10 (${sj.last_date}).
        Carga subjetiva 7 días (sRPE): ${sj.srpe_7d ?? "—"}. Cruza con tu carga por pulso para detectar fatiga oculta.</div>`;
    } else if (sj) {
      html += `<div class="step"><strong>Sensaciones (del reloj):</strong> todavía no venís cargando el esfuerzo percibido (RPE) al terminar. Si lo marcás en el reloj, lo uso automáticamente.</div>`;
    }
    if (sj && sj.cadence_avg) {
      html += `<div class="step"><strong>Cadencia media (últimas salidas):</strong> ${sj.cadence_avg} rpm.
        La cadencia libre está bien; sumar algún bloque de cadencia variada da estímulos distintos, pero no es un pilar (evidencia débil para cadencia baja — Hansen 2020).</div>`;
    }
    qb.innerHTML = html || `<p class="hint">Juntando datos para las métricas de calidad.</p>`;
  }

  const TESTS = [
    ["Umbral 30 min (Friel)", "Tu FC de umbral (LTHR) y recalibra tus zonas. El patrón oro de campo."],
    ["20 min (umbral)", "Versión más corta del test de umbral, algo menos precisa."],
    ["5 min máximo", "Capacidad aeróbica máxima (proxy de VO2máx)."],
    ["Cooper 12 min", "VO2máx estimado por la distancia en 12 min. En terreno llano."],
    ["Sprint Interval (SIT) MTB", "6×30s a tope: potencia máxima y decisión bajo fatiga (Hebisz 2022, específico MTB)."],
    ["Recuperación de FC (HRR)", "Cuánto baja tu pulso en 1 min tras un esfuerzo duro: marcador de forma."],
  ];
  const tl = $("tests-list");
  if (tl) tl.innerHTML = TESTS.map(
    ([n, d]) => `<div class="step"><strong>${n}:</strong> ${d}</div>`).join("");

  const lthr = data.lthr || null;
  if (!lthr) {
    $("lthr-body").innerHTML = `<p class="hint">Todavía no hay salidas para estimar el umbral.</p>`;
  } else if (lthr.error) {
    $("lthr-body").innerHTML = `<p class="hint">${lthr.error}</p>`;
  } else {
    const z = lthr.zones || {};
    $("lthr-body").innerHTML =
      `<div class="tiles">
        <div class="tile"><span class="tile-label">LTHR estimado</span><span class="tile-value">${lthr.lthr} lpm</span><span class="tile-sub">mejor 20 min sostenido</span></div>
        <div class="tile"><span class="tile-label">FC media salida</span><span class="tile-value">${lthr.avg_hr}</span><span class="tile-sub">máx ${lthr.max_hr} lpm</span></div>
      </div>
      <div class="table-wrap"><table><thead><tr><th>Zona</th><th>FC (lpm)</th></tr></thead><tbody>` +
      Object.entries(z).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("") +
      `</tbody></table></div>
      <p class="hint" style="margin-top:8px"><b>PROVISORIO — todavía no fijado como referencia.</b> ${lthr.note} Salida usada: ${lthr.name || ""} (${lthr.date || ""}).</p>`;
  }

  $("goals-body").innerHTML = (data.goals || [])
    .map((g) => `<tr>
      <td>${g.metric}</td><td>${g.current ?? "—"}</td><td>${g.target ?? "—"}</td>
      <td>${g.by ?? "—"}</td><td style="white-space:normal">${g.note}</td>
    </tr>`)
    .join("");

  // ---- alertas
  $("alerts").innerHTML = (data.alerts || [])
    .map((a) => `<div class="alert alert-${a.level}">
      <span class="alert-icon">${ALERT_ICONS[a.level] || "ℹ️"}</span><span>${a.text}</span></div>`)
    .join("");

  // ---- tiles de carga
  const t = data.today || {};
  $("load-tiles").innerHTML =
    tile("Fitness (CTL)", t.ctl, "carga crónica 42 días") +
    tile("Fatiga (ATL)", t.atl, "carga aguda 7 días") +
    tile("Forma (TSB)", t.tsb != null ? (t.tsb > 0 ? "+" : "") + t.tsb : null, "fitness − fatiga") +
    tile("ACWR", t.acwr, t.acute_7d != null ? `aguda ${t.acute_7d} / crónica ${t.chronic_weekly}` : "aguda / crónica");

  $("trend-tiles").innerHTML =
    tile("HRV última noche", t.hrv != null ? Math.round(t.hrv) + " ms" : null,
      `prom. 7d: ${t.hrv7 ?? "—"} · baseline 30d: ${t.hrv30 ?? "—"}`) +
    tile("FC en reposo", t.resting_hr != null ? Math.round(t.resting_hr) : null,
      `7d: ${t.rhr7 ?? "—"} · 30d: ${t.rhr30 ?? "—"}`) +
    tile("Sueño anoche", fmtDur(t.sleep_secs),
      t.sleep_score != null ? `score ${Math.round(t.sleep_score)}` : "") +
    tile("Training readiness", t.readiness != null ? Math.round(t.readiness) : null, "de Garmin") +
    tile("Peso", t.weight != null ? t.weight + " kg" : null,
      t.weight7 != null
        ? `prom. 7d: ${t.weight7} kg` +
          (t.weight_delta30 != null ? ` · ${t.weight_delta30 > 0 ? "+" : ""}${t.weight_delta30} kg vs. mes previo` : "")
        : "cargalo en Garmin Connect") +
    tile("VO2max (Garmin)", t.vo2max != null ? t.vo2max : null,
      t.vo2max_delta90 != null
        ? `${t.vo2max_delta90 > 0 ? "+" : ""}${t.vo2max_delta90} en 90 días`
        : "estimado por tu reloj") +
    tile("Estrés (Garmin)", t.stress != null ? Math.round(t.stress) : null,
      t.stress7 != null ? `promedio 7d: ${t.stress7}` : "0-100, menor es mejor");

  // ---- gráfico y tabla
  renderLoadChart(data.series || []);
  $("load-table-body").innerHTML = (data.series || [])
    .slice(-30).reverse()
    .map((x) => `<tr><td>${x.date}</td><td>${x.load}</td><td>${x.ctl}</td><td>${x.atl}</td><td>${x.tsb}</td></tr>`)
    .join("");

  // ---- salidas
  $("rides-body").innerHTML = (data.rides || [])
    .map((r) => `<tr>
      <td>${r.date}</td><td>${r.name || "—"}</td>
      <td>${(r.type || "").replace(/([A-Z])/g, " $1").trim()}</td>
      <td>${r.distance_km ? r.distance_km + " km" : "—"}</td>
      <td>${fmtDur(r.moving_time_s)}</td>
      <td>${r.elevation_m ? Math.round(r.elevation_m) + " m" : "—"}</td>
      <td>${r.avg_hr ? Math.round(r.avg_hr) : "—"}</td>
      <td>${r.load ? Math.round(r.load) : "—"}</td>
    </tr>`)
    .join("");

  $("footer-note").textContent =
    `Datos vía intervals.icu (sincronizado con tu Garmin). Se actualiza solo cada 3 horas. ` +
    `${data.counts.rides_180d} salidas y ${data.counts.wellness_days} días de bienestar en los últimos 6 meses.`;
}

$("toggle-load-table").addEventListener("click", () => {
  const wrap = $("load-table-wrap");
  wrap.classList.toggle("hidden");
  $("toggle-load-table").textContent = wrap.classList.contains("hidden") ? "Ver tabla" : "Ocultar tabla";
});

const SERIES = [
  { key: "ctl", name: "Fitness", color: "var(--series-ctl)", width: 2.5 },
  { key: "atl", name: "Fatiga", color: "var(--series-atl)", width: 2 },
  { key: "tsb", name: "Forma", color: "var(--series-tsb)", width: 2 },
];

function renderLoadChart(series) {
  const el = $("load-chart");
  if (!series.length) {
    el.innerHTML = `<p class="hint">Sin datos de carga todavía.</p>`;
    return;
  }
  const W = 800, H = 260, padL = 44, padR = 60, padT = 12, padB = 26;
  const xs = series.map((_, i) => padL + (i * (W - padL - padR)) / Math.max(1, series.length - 1));
  const values = series.flatMap((p) => [p.ctl, p.atl, p.tsb]);
  const yMin = Math.min(0, ...values), yMax = Math.max(10, ...values);
  const y = (v) => padT + ((yMax - v) / (yMax - yMin || 1)) * (H - padT - padB);

  const step = Math.max(10, Math.ceil((yMax - yMin) / 5 / 10) * 10);
  let grid = "", labels = "";
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) {
    grid += `<line x1="${padL}" x2="${W - padR}" y1="${y(v)}" y2="${y(v)}"
             stroke="${v === 0 ? "var(--axis)" : "var(--grid)"}" stroke-width="1"/>`;
    labels += `<text x="${padL - 6}" y="${y(v) + 3}" text-anchor="end" font-size="10"
               fill="var(--text-muted)">${v}</text>`;
  }
  const every = Math.max(1, Math.floor(series.length / 6));
  series.forEach((p, i) => {
    if (i % every === 0) {
      labels += `<text x="${xs[i]}" y="${H - 8}" text-anchor="middle" font-size="10"
                 fill="var(--text-muted)">${p.date.slice(5)}</text>`;
    }
  });

  let lines = "", endLabels = "";
  const usedY = [];
  for (const s of SERIES) {
    const pts = series.map((p, i) => `${xs[i].toFixed(1)},${y(p[s.key]).toFixed(1)}`).join(" ");
    lines += `<polyline points="${pts}" fill="none" stroke="${s.color}"
              stroke-width="${s.width}" stroke-linejoin="round" stroke-linecap="round"/>`;
    let ly = y(series[series.length - 1][s.key]) + 3;
    while (usedY.some((u) => Math.abs(u - ly) < 12)) ly += 12;
    usedY.push(ly);
    endLabels += `<circle cx="${W - padR + 6}" cy="${ly - 3}" r="3.5" fill="${s.color}"/>
      <text x="${W - padR + 13}" y="${ly}" font-size="10" fill="var(--text-secondary)">${s.name}</text>`;
  }

  el.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolución de fitness, fatiga y forma">
      ${grid}${labels}${lines}${endLabels}
      <line id="crosshair" y1="${padT}" y2="${H - padB}" stroke="var(--axis)" stroke-width="1" style="display:none"/>
    </svg>
    <div class="chart-tooltip" id="load-tooltip"></div>`;

  const svg = el.querySelector("svg");
  const cross = el.querySelector("#crosshair");
  const tip = $("load-tooltip");
  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const mx = ((ev.clientX - rect.left) / rect.width) * W;
    let i = Math.round(((mx - padL) / (W - padL - padR)) * (series.length - 1));
    i = Math.max(0, Math.min(series.length - 1, i));
    const p = series[i];
    cross.style.display = "";
    cross.setAttribute("x1", xs[i]);
    cross.setAttribute("x2", xs[i]);
    tip.style.display = "block";
    tip.innerHTML =
      `<strong>${p.date}</strong>` +
      SERIES.map(
        (s) => `<div class="tt-row"><span class="dot" style="background:${s.color}"></span>
                ${s.name}<span class="tt-val">${p[s.key]}</span></div>`
      ).join("") +
      `<div class="tt-row">Carga del día<span class="tt-val">${p.load}</span></div>`;
    const px = (xs[i] / W) * rect.width;
    tip.style.left = Math.min(px + 12, rect.width - tip.offsetWidth - 4) + "px";
    tip.style.top = "18px";
  });
  svg.addEventListener("mouseleave", () => {
    cross.style.display = "none";
    tip.style.display = "none";
  });
}

init().catch((err) => {
  console.error("Error al renderizar el dashboard:", err);
  const u = document.getElementById("updated");
  if (u) u.textContent = "Error al mostrar los datos (recargá la página)";
});
