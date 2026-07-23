@echo off
rem Doble click en este archivo para instalar y arrancar el Entrenador de Ciclismo.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo IMPORTANTE: al instalarlo, marca la casilla "Add Python to PATH".
    pause
    exit /b 1
)

rem Actualizar la app desde GitHub automaticamente (si hay internet)
where git >nul 2>nul
if not errorlevel 1 (
    echo Buscando actualizaciones...
    git pull --ff-only
)
echo Version instalada:
git log -1 --oneline 2>nul

if not exist .env (
    copy .env.example .env >nul
    echo Se creo el archivo .env con la configuracion inicial.
)

echo Instalando dependencias (la primera vez tarda un par de minutos)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo ============================================================
echo  Arrancando el servidor...
echo  DEJA ESTA VENTANA ABIERTA mientras uses la app.
echo  Se va a abrir el navegador en http://localhost:8000
echo  Para cerrar todo: cerra esta ventana.
echo ============================================================
echo.

start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
python -m uvicorn backend.main:app

pause
