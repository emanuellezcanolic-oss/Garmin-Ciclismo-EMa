# 🚵 Entrenador de Ciclismo (Garmin + evidencia)

App web personal que se conecta a tu cuenta de Garmin Connect, sincroniza tus
datos (salidas en bici, HRV, sueño, training readiness, FC en reposo, body
battery) y — en fases siguientes — calcula tu carga de entrenamiento
(CTL/ATL/TSB, ACWR), genera planes ajustados a tu recuperación, los sube a
Garmin y recomienda rutas MTB.

**Estado actual: Fase 1 completa** — autenticación con Garmin + sincronización
de datos + panel web para verlos.

## Cómo usarla (paso a paso)

Necesitás tener Python 3.10 o más nuevo instalado ([python.org](https://www.python.org/downloads/)).

1. **Abrí una terminal en la carpeta del proyecto** y ejecutá una sola vez:

   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```

   (En Windows, en vez de `cp` usá `copy .env.example .env`.)

2. **Editá el archivo `.env`** con el Bloc de notas o similar. Podés dejar
   `GARMIN_EMAIL` y `GARMIN_PASSWORD` vacíos y loguearte desde la página web,
   o completarlos para que se conecte solo. Las API keys de rutas y clima se
   usan recién en fases siguientes.

3. **Arrancá el servidor:**

   ```bash
   uvicorn backend.main:app --reload
   ```

4. **Abrí el navegador en** <http://localhost:8000>

5. En la página: iniciá sesión con tu cuenta de Garmin (si Garmin te manda un
   código por email, la página te lo va a pedir), tocá **Sincronizar ahora**, y
   completá tus datos (FC máxima, FC en reposo, si tenés potenciómetro) en la
   sección "Mis datos" — se necesitan para calcular zonas y carga en la fase 2.

La sesión de Garmin queda guardada en la carpeta `.garmin_tokens`, así que no
te pide login cada vez. Mientras el servidor esté corriendo, sincroniza solo
una vez por día (configurable con `SYNC_INTERVAL_HOURS` en `.env`).

## Estructura

```
backend/
  main.py           # API FastAPI + servidor del frontend
  garmin_client.py  # login Garmin (con MFA) y manejo de sesión
  sync.py           # sincronización de actividades y métricas diarias
  db.py             # esquema SQLite y helpers
frontend/
  index.html / app.js / style.css   # panel web simple
coach.db            # base de datos local (se crea sola, no va a git)
.env                # tus credenciales y API keys (no va a git)
```

## Fases del proyecto

1. ✅ Autenticación Garmin + sincronización de datos
2. ⬜ Métricas de carga: TRIMP/TSS por salida, CTL/ATL/TSB, ACWR, tendencias HRV
3. ⬜ Generación del plan diario/semanal basado en recuperación y progresión
4. ⬜ Subida del plan como workout estructurado a Garmin + programación
5. ⬜ Recomendación de rutas MTB con Openrouteservice (+ clima con OpenWeather)
