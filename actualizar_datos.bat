@echo off
chcp 65001 >nul
echo.
echo ========================================================
echo  Actualizador Dashboard Regional Chile
echo  División de Coordinación Interministerial
echo ========================================================
echo.

cd /d "%~dp0"

:: ── 1. Actualizar datos (BCE + LeyStop) ──────────────────────
echo [1/4] Descargando datos nuevos...
python actualizar_datos.py
if errorlevel 1 (
    echo ERROR en actualizar_datos.py
    pause
    exit /b 1
)

:: ── 2. Generar dashboard base ─────────────────────────────────
echo.
echo [2/4] Generando dashboard.html...
python generar_dashboard.py
if errorlevel 1 (
    echo ERROR en generar_dashboard.py
    pause
    exit /b 1
)

:: ── 3. Agregar boton Minuta PDF ───────────────────────────────
echo.
echo [3/4] Agregando boton Minuta Regional PDF...
python parche_pdf_dashboard.py
if errorlevel 1 (
    echo ERROR en parche_pdf_dashboard.py
    pause
    exit /b 1
)

:: ── 4. Subir a GitHub Pages ───────────────────────────────────
echo.
echo [4/4] Subiendo a GitHub Pages...
git add -f dashboard.html pdf_minuta.js
git commit --allow-empty -m "Actualizacion %date% %time%"
git push origin main
if errorlevel 1 (
    echo ERROR al hacer push. Verifica conexion y cable de red.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Listo. Dashboard publicado en GitHub Pages.
echo  https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html
echo ========================================================
echo.
pause
