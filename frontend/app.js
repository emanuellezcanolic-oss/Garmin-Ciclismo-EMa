// Frontend simple del entrenador de ciclismo (fase 1: auth + sync)

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

// ---------------------------------------------------------------- estado

async function refreshStatus() {
  const badge = $("status-badge");
  try {
    const st = await api("/api/status");
    if (st.authenticated) {
      badge.textContent = `Conectado: ${st.name || "Garmin"}`;
      badge.className = "badge ok";
      $("login-card").classList.add("hidden");
      $("dashboard").classList.remove("hidden");
      const last = st.last_sync
        ? `Última sincronización: ${st.last_sync.finished_at} (${st.last_sync.ok ? "OK" : "con errores"})`
        : "Todavía no sincronizaste nada.";
      $("sync-info").textContent =
        `${st.activities_in_db} salidas y ${st.days_in_db} días de métricas en la base. ${last}`;
      await Promise.all([loadActivities(), loadDaily(), loadSettings(), loadMetrics()]);
    } else {
      badge.textContent = "Sin conexión con Garmin";
      badge.className = "badge off";
      $("login-card").classList.remove("hidden");
      $("dashboard").classList.add("hidden");
      if (st.mfa_pending) showMfa();
    }
  } catch (e) {
    badge.textContent = "Error: " + e.message;
    badge.className = "badge off";
  }
}

// ---------------------------------------------------------------- login

function showMfa() {
  $("login-form").classList.add("hidden");
  $("mfa-form").classList.remove("hidden");
}

$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("login-error").classList.add("hidden");
  const btn = ev.target.querySelector("button");
  btn.disabled = true;
  btn.textContent = "Conectando…";
  try {
    const res = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("login-email").value,
        password: $("login-password").value,
      }),
    });
    if (res.status === "mfa_required") showMfa();
    else await refreshStatus();
  } catch (e) {
    $("login-error").textContent = e.message;
    $("login-error").classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.textContent = "Iniciar sesión";
  }
});

$("mfa-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("login-error").classList.add("hidden");
  try {
    await api("/api/auth/mfa", {
      method: "POST",
      body: JSON.stringify({ code: $("mfa-code").value }),
    });
    await refreshStatus();
  } catch (e) {
    $("login-error").textContent = e.message;
    $("login-error").classList.remove("hidden");
  }
});

$("logout-btn").addEventListener("click", async () => {
  if (!confirm("¿Cerrar la sesión de Garmin y borrar los tokens guardados?")) return;
  await api("/api/auth/logout", { method: "POST" });
  location.reload();
});

// ---------------------------------------------------------------- sync

$("sync-btn").addEventListener("click", async () => {
  const btn = $("sync-btn");
  btn.disabled = true;
  btn.textContent = "Sincronizando… (puede tardar unos minutos)";
  $("sync-result").textContent = "";
  try {
    const res = await api("/api/sync", {
      method: "POST",
      body: JSON.stringify({
        days_activities: parseInt($("sync-days-act").value, 10) || 90,
        days_daily: parseInt($("sync-days-daily").value, 10) || 30,
      }),
    });
    const a = res.activities || {};
    const d = res.daily || {};
    $("sync-result").textContent = res.error
      ? `Error: ${res.error}`
      : `Listo. Salidas nuevas: ${a.cycling_new ?? 0}, actualizadas: ${a.cycling_updated ?? 0}. ` +
        `Días de métricas bajados: ${d.days_synced ?? 0}${d.errors ? ` (${d.errors} con error)` : ""}.`;
    await refreshStatus();
  } catch (e) {
    $("sync-result").textContent = "Error: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Sincronizar ahora";
  }
});

// ---------------------------------------------------------------- datos

function fmtDur(secs) {
  if (!secs) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.round((secs % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

async function loadActivities() {
  const acts = await api("/api/activities?limit=100");
  $("activities-table").querySelector("tbody").innerHTML = acts
    .map(
      (a) => `<tr>
        <td>${(a.start_time || "").slice(0, 16).replace("T", " ")}</td>
        <td>${a.name || "—"}</td>
        <td>${(a.type_key || "").replace(/_/g, " ")}</td>
        <td>${a.distance_m ? (a.distance_m / 1000).toFixed(1) + " km" : "—"}</td>
        <td>${fmtDur(a.duration_s)}</td>
        <td>${a.elevation_gain_m ? Math.round(a.elevation_gain_m) + " m" : "—"}</td>
        <td>${a.avg_hr ? Math.round(a.avg_hr) : "—"}</td>
        <td>${a.max_hr ? Math.round(a.max_hr) : "—"}</td>
        <td>${a.avg_power ? Math.round(a.avg_power) + " W" : "—"}</td>
        <td>${a.tss != null ? Math.round(a.tss) : "—"}</td>
      </tr>`
    )
    .join("");
}

async function loadDaily() {
  const days = await api("/api/daily?days=14");
  $("daily-table").querySelector("tbody").innerHTML = days
    .map(
      (d) => `<tr>
        <td>${d.date}</td>
        <td>${d.resting_hr != null ? Math.round(d.resting_hr) : "—"}</td>
        <td>${d.hrv_last_night != null ? Math.round(d.hrv_last_night) + " ms" : "—"}</td>
        <td>${d.hrv_status || "—"}</td>
        <td>${fmtDur(d.sleep_seconds)}</td>
        <td>${d.sleep_score != null ? Math.round(d.sleep_score) : "—"}</td>
        <td>${d.training_readiness != null ? Math.round(d.training_readiness) : "—"}</td>
        <td>${d.body_battery_min != null ? `${Math.round(d.body_battery_min)}–${Math.round(d.body_battery_max)}` : "—"}</td>
      </tr>`
    )
    .join("");
}

// ------------------------------------------------- carga de entrenamiento

const ALERT_ICONS = { warning: "⚠️", serious: "🟠", critical: "🛑" };
let loadSeries = [];

async function loadMetrics() {
  const [summary, series] = await Promise.all([
    api("/api/metrics/summary"),
    api("/api/metrics/load?days=120"),
  ]);
  loadSeries = series;

  const t = summary.today || {};
  $("tile-ctl").textContent = t.ctl != null ? t.ctl : "—";
  $("tile-atl").textContent = t.atl != null ? t.atl : "—";
  $("tile-tsb").textContent = t.tsb != null ? (t.tsb > 0 ? "+" : "") + t.tsb : "—";
  $("tile-acwr").textContent = summary.acwr != null ? summary.acwr : "—";
  if (summary.acute_load_7d != null && summary.chronic_weekly_load != null) {
    $("tile-acwr-sub").textContent =
      `aguda ${Math.round(summary.acute_load_7d)} / crónica ${Math.round(summary.chronic_weekly_load)} TSS`;
  }

  $("load-alerts").innerHTML = (summary.alerts || [])
    .map(
      (a) => `<div class="alert alert-${a.level}">
        <span class="alert-icon">${ALERT_ICONS[a.level] || "ℹ️"}</span><span>${a.text}</span>
      </div>`
    )
    .join("");

  const tr = summary.trend || {};
  const trendTile = (label, value, sub) =>
    `<div class="tile"><span class="tile-label">${label}</span>
     <span class="tile-value">${value ?? "—"}</span><span class="tile-sub">${sub}</span></div>`;
  $("trend-tiles").innerHTML =
    trendTile("HRV última noche", tr.hrv_last != null ? tr.hrv_last + " ms" : null,
      `prom. 7d: ${tr.hrv_avg7 ?? "—"} · baseline 30d: ${tr.hrv_avg30 ?? "—"}`) +
    trendTile("Training readiness", tr.readiness_last,
      `promedio 7 días: ${tr.readiness_avg7 ?? "—"}`) +
    trendTile("FC en reposo", tr.rhr_last,
      `promedio 30 días: ${tr.rhr_avg30 ?? "—"}`);

  renderLoadChart(series);
  $("load-table-body").innerHTML = series
    .slice(-30)
    .reverse()
    .map(
      (p) => `<tr><td>${p.date}</td><td>${p.load}</td><td>${p.ctl}</td><td>${p.atl}</td><td>${p.tsb}</td></tr>`
    )
    .join("");
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
    el.innerHTML = `<p class="hint">Todavía no hay salidas con TSS calculado. Sincronizá y completá tus datos de FC.</p>`;
    return;
  }
  const W = 800, H = 260, padL = 44, padR = 60, padT = 12, padB = 26;
  const xs = series.map((_, i) => padL + (i * (W - padL - padR)) / Math.max(1, series.length - 1));
  const values = series.flatMap((p) => [p.ctl, p.atl, p.tsb]);
  const yMin = Math.min(0, ...values), yMax = Math.max(10, ...values);
  const y = (v) => padT + ((yMax - v) / (yMax - yMin || 1)) * (H - padT - padB);

  // gridlines horizontales redondeadas
  const step = Math.max(10, Math.ceil((yMax - yMin) / 5 / 10) * 10);
  let grid = "", labels = "";
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) {
    grid += `<line x1="${padL}" x2="${W - padR}" y1="${y(v)}" y2="${y(v)}"
             stroke="${v === 0 ? "var(--axis)" : "var(--grid)"}" stroke-width="1"/>`;
    labels += `<text x="${padL - 6}" y="${y(v) + 3}" text-anchor="end" font-size="10"
               fill="var(--text-muted)">${v}</text>`;
  }
  // etiquetas de fecha (~6)
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
    // etiqueta directa al final de cada línea (evitando superposición)
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
      `<div class="tt-row">TSS del día<span class="tt-val">${p.load}</span></div>`;
    const px = (xs[i] / W) * rect.width;
    tip.style.left = Math.min(px + 12, rect.width - tip.offsetWidth - 4) + "px";
    tip.style.top = "18px";
  });
  svg.addEventListener("mouseleave", () => {
    cross.style.display = "none";
    tip.style.display = "none";
  });
}

// ---------------------------------------------------------------- ajustes

async function loadSettings() {
  const s = await api("/api/settings");
  if (s.hr_max) $("set-hr-max").value = s.hr_max;
  if (s.hr_rest) $("set-hr-rest").value = s.hr_rest;
  if (s.has_power_meter !== undefined) $("set-power").value = s.has_power_meter;
  if (s.ftp) $("set-ftp").value = s.ftp;
}

$("settings-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const body = {};
  if ($("set-hr-max").value) body.hr_max = parseInt($("set-hr-max").value, 10);
  if ($("set-hr-rest").value) body.hr_rest = parseInt($("set-hr-rest").value, 10);
  if ($("set-power").value !== "") body.has_power_meter = $("set-power").value === "1";
  if ($("set-ftp").value) body.ftp = parseInt($("set-ftp").value, 10);
  await api("/api/settings", { method: "POST", body: JSON.stringify(body) });
  $("settings-saved").textContent = "Guardado ✔";
  setTimeout(() => ($("settings-saved").textContent = ""), 3000);
});

refreshStatus();
