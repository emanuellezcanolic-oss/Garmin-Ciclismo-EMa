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
      await Promise.all([loadActivities(), loadDaily(), loadSettings()]);
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
        <td>${d.resting_hr ?? "—"}</td>
        <td>${d.hrv_last_night ? d.hrv_last_night + " ms" : "—"}</td>
        <td>${d.hrv_status || "—"}</td>
        <td>${fmtDur(d.sleep_seconds)}</td>
        <td>${d.sleep_score ?? "—"}</td>
        <td>${d.training_readiness ?? "—"}</td>
        <td>${d.body_battery_min != null ? `${d.body_battery_min}–${d.body_battery_max}` : "—"}</td>
      </tr>`
    )
    .join("");
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
