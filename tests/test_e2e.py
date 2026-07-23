"""Revisión end-to-end de toda la app con un Garmin simulado.

Prueba el flujo completo por la API HTTP real (FastAPI TestClient):
login → MFA → guardado de tokens → restauración de sesión → sync →
métricas → settings → recálculo. Falla ruidosamente si algo no anda.
"""

import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="coach_e2e_")
os.environ["DB_PATH"] = str(Path(tmp) / "test.db")
os.environ["GARMIN_TOKEN_DIR"] = str(Path(tmp) / "tokens")
os.environ["GARMIN_EMAIL"] = ""
os.environ["GARMIN_PASSWORD"] = ""
os.environ["SYNC_INTERVAL_HOURS"] = "0"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import garmin_client  # noqa: E402


# ------------------------------------------------------------ Garmin falso

class FakeClient:
    """Imita garminconnect.client.Client (v0.3.x): dump/load de tokens."""

    def dump(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "oauth_token.json").write_text('{"fake": "token"}')

    def load(self, path):
        if not (Path(path) / "oauth_token.json").exists():
            raise FileNotFoundError("no tokens")


class FakeGarmin:
    """Imita la API pública de garminconnect.Garmin 0.3.2 (sin .garth)."""

    mfa_pending_logins = 0  # cuántos logins piden MFA antes de entrar

    def __init__(self, email=None, password=None, is_cn=False, prompt_mfa=None, return_on_mfa=False):
        self.email = email
        self.password = password
        self.return_on_mfa = return_on_mfa
        self.client = FakeClient()

    def login(self, tokenstore=None):
        if tokenstore:  # restauración de sesión guardada
            self.client.load(tokenstore)
            return (None, None)
        if self.email == "ema@test.com" and self.password == "correcta":
            if FakeGarmin.mfa_pending_logins > 0:
                FakeGarmin.mfa_pending_logins -= 1
                return ("needs_mfa", None)
            return (None, None)
        raise Exception("Unauthorized")

    def resume_login(self, client_state, mfa_code):
        if mfa_code != "123456":
            raise Exception("Código inválido")
        return (None, None)

    def get_full_name(self):
        return "Emanuel Test"

    # ---- datos con la MISMA estructura que devuelve Garmin real ----

    def get_activities_by_date(self, start, end, activitytype=None):
        acts = []
        for i in range(10):
            d = date.today() - timedelta(days=i * 3)
            acts.append({
                "activityId": 9000 + i,
                "activityName": f"Vuelta MTB {i}",
                "startTimeLocal": f"{d.isoformat()} 08:30:00",
                "activityType": {"typeKey": "mountain_biking" if i % 2 else "cycling"},
                "distance": 25000.0 + i * 1000,
                "duration": 5400.0 + i * 300,
                "movingDuration": 5100.0 + i * 280,
                "elevationGain": 450.0 + i * 40,
                "averageHR": 142.0,
                "maxHR": 171.0,
                "calories": 900.0,
            })
        # una que NO es ciclismo: debe ser ignorada
        acts.append({
            "activityId": 9999,
            "activityName": "Caminata",
            "startTimeLocal": f"{date.today().isoformat()} 19:00:00",
            "activityType": {"typeKey": "walking"},
            "distance": 3000.0, "duration": 2400.0,
        })
        return acts

    def get_activity_hr_in_timezones(self, activity_id):
        return [
            {"zoneNumber": 1, "secsInZone": 600.0},
            {"zoneNumber": 2, "secsInZone": 1800.0},
            {"zoneNumber": 3, "secsInZone": 1500.0},
            {"zoneNumber": 4, "secsInZone": 900.0},
            {"zoneNumber": 5, "secsInZone": 300.0},
        ]

    def get_rhr_day(self, ds):
        return {"allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 52}]}}}

    def get_hrv_data(self, ds):
        return {"hrvSummary": {"lastNightAvg": 48, "weeklyAvg": 50, "status": "BALANCED"}}

    def get_sleep_data(self, ds):
        return {"dailySleepDTO": {"sleepTimeSeconds": 25200,
                                  "sleepScores": {"overall": {"value": 78}}}}

    def get_training_readiness(self, ds):
        return [{"score": 67, "level": "MODERATE"}]

    def get_body_battery(self, ds, end=None):
        return [{"bodyBatteryValuesArray": [[0, 95], [1, 40], [2, 20]]}]


def check(cond, msg):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        raise SystemExit(f"REVISION FALLO en: {msg}")


# ------------------------------------------------------------ tests

garmin_client.Garmin = FakeGarmin  # reemplazar la clase real

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend.db import init_db  # noqa: E402

init_db()
c = TestClient(app)

# 1. estado inicial: sin sesión
r = c.get("/api/status").json()
check(r["authenticated"] is False, "estado inicial sin sesión")

# 2. login con contraseña incorrecta → 401
r = c.post("/api/auth/login", json={"email": "ema@test.com", "password": "mala"})
check(r.status_code == 401, "contraseña incorrecta devuelve error 401")

# 3. login correcto que pide MFA
FakeGarmin.mfa_pending_logins = 1
r = c.post("/api/auth/login", json={"email": "ema@test.com", "password": "correcta"}).json()
check(r["status"] == "mfa_required", "login pide MFA cuando Garmin lo exige")

# 4. código MFA incorrecto → 401
r = c.post("/api/auth/mfa", json={"code": "000000"})
check(r.status_code == 401, "código MFA incorrecto devuelve error 401")

# 5. reintentar login (el estado MFA quedó consumido) y completar MFA bien
c.post("/api/auth/login", json={"email": "ema@test.com", "password": "correcta"})
r = c.post("/api/auth/mfa", json={"code": "123456"})
check(r.status_code == 200 and r.json()["status"] == "ok", "MFA correcto completa el login")
check((Path(os.environ["GARMIN_TOKEN_DIR"]) / "oauth_token.json").exists(),
      "los tokens de sesión quedaron guardados en disco")

# 6. estado autenticado
r = c.get("/api/status").json()
check(r["authenticated"] is True and r["name"] == "Emanuel Test", "estado autenticado con nombre")

# 7. reinicio del servidor: la sesión se restaura desde tokens sin pedir login
garmin_client._client = None
r = c.get("/api/status").json()
check(r["authenticated"] is True, "sesión restaurada desde tokens tras reinicio")

# 8. sincronización
r = c.post("/api/sync", json={"days_activities": 60, "days_daily": 10})
check(r.status_code == 200, "sync devuelve 200")
sy = r.json()
check(sy["activities"]["cycling_new"] == 10, f"10 salidas de ciclismo nuevas (fue {sy['activities']})")
check(sy["activities"]["total_seen"] == 11, "la caminata fue vista pero no guardada")
check(sy["daily"]["days_synced"] == 10, f"10 días de métricas (fue {sy['daily']})")

# 9. actividades guardadas con sus campos
acts = c.get("/api/activities").json()
check(len(acts) == 10, "10 actividades en la base")
a = acts[0]
check(a["elevation_gain_m"] is not None and a["avg_hr"] == 142.0, "desnivel y FC guardados")
check(a["hr_zone_secs"]["2"] == 1800.0, "tiempo en zonas de FC guardado")

# 10. métricas diarias guardadas
days = c.get("/api/daily?days=10").json()
check(len(days) == 10, "10 días de métricas en la base")
d0 = days[0]
check(d0["resting_hr"] == 52 and d0["hrv_last_night"] == 48, "FC reposo y HRV guardados")
check(d0["sleep_seconds"] == 25200 and d0["training_readiness"] == 67, "sueño y readiness guardados")
check(d0["body_battery_max"] == 95 and d0["body_battery_min"] == 20, "body battery min/max")

# 11. sin FC máx/reposo el TSS no se inventa y hay alerta
s = c.get("/api/metrics/summary").json()
check(not s["settings_ok"] and any("FC máxima" in al["text"] for al in s["alerts"]),
      "sin FC máx/reposo: alerta de datos faltantes y sin TSS inventado")

# 12. al guardar settings se recalcula la carga
r = c.post("/api/settings", json={"hr_max": 185, "hr_rest": 52, "has_power_meter": False})
check(r.status_code == 200, "guardar settings")
acts = c.get("/api/activities").json()
check(all(a["tss"] is not None and a["tss"] > 0 for a in acts), "TSS calculado para todas las salidas")

# 13. resumen de métricas completo
s = c.get("/api/metrics/summary").json()
check(s["settings_ok"] and s["has_data"], "resumen con datos")
check(s["today"]["ctl"] > 0 and s["today"]["atl"] > 0, f"CTL/ATL positivos ({s['today']})")
check(s["trend"]["hrv_last"] == 48, "tendencia HRV presente")
serie = c.get("/api/metrics/load?days=120").json()
check(len(serie) >= 28, f"serie de carga con {len(serie)} días")

# 14. re-sync no duplica
r = c.post("/api/sync", json={"days_activities": 60, "days_daily": 10}).json()
check(r["activities"]["cycling_new"] == 0 and r["activities"]["cycling_updated"] == 10,
      "segunda sync actualiza sin duplicar")

# 15. logout borra la sesión
c.post("/api/auth/logout")
check(not Path(os.environ["GARMIN_TOKEN_DIR"]).exists(), "logout borra los tokens")
r = c.get("/api/status").json()
check(r["authenticated"] is False, "estado sin sesión tras logout")

# 16. frontend servido
r = c.get("/")
check(r.status_code == 200 and "Entrenador" in r.text, "página principal servida")
r = c.get("/static/app.js")
check(r.status_code == 200, "app.js servido")

print("\n✅ TODAS LAS PRUEBAS PASARON")
