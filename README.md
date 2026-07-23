# 🚵 Entrenador de Ciclismo (Garmin + evidencia)

App web personal que se conecta a tu cuenta de Garmin Connect, sincroniza tus
datos (salidas en bici, HRV, sueño, training readiness, FC en reposo, body
battery) y — en fases siguientes — calcula tu carga de entrenamiento
(CTL/ATL/TSB, ACWR), genera planes ajustados a tu recuperación, los sube a
Garmin y recomienda rutas MTB.

**Estado actual: Fase 1 completa** — autenticación con Garmin + sincronización
de datos + panel web para verlos.

## Cómo usarla en Windows (la primera vez)

Necesitás Python instalado (ya lo tenés si `pip` te funciona en la terminal).

1. **Abrí Git CMD** y pegá estas líneas, una por una (descarga el proyecto a
   tu escritorio):

   ```
   cd %USERPROFILE%\Desktop
   git clone -b claude/garmin-cycling-coach-5sfipu https://github.com/emanuellezcanolic-oss/Garmin-Ciclismo-EMa.git
   ```

2. **Abrí la carpeta `Garmin-Ciclismo-EMa` que apareció en tu escritorio y
   hacé doble click en `iniciar.bat`.** Ese archivo instala todo, arranca el
   servidor y te abre el navegador solo. Dejá la ventana negra abierta
   mientras uses la app.

3. En la página: iniciá sesión con tu cuenta de Garmin (si Garmin te manda un
   código por email, la página te lo va a pedir), tocá **Sincronizar ahora**, y
   completá tus datos (FC máxima, FC en reposo, si tenés potenciómetro) en la
   sección "Mis datos" — se necesitan para calcular zonas y carga en la fase 2.

**Las próximas veces**: solo doble click en `iniciar.bat`. Nada más.

Para actualizar la app cuando haya cambios nuevos: abrí Git CMD y pegá

```
cd %USERPROFILE%\Desktop\Garmin-Ciclismo-EMa
git pull
```

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
