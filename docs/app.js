// Dashboard estático: lee data.json (generado por GitHub Actions) y renderiza.

const $ = (id) => document.getElementById(id);

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

init();
