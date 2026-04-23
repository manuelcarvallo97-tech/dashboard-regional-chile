@echo off
chcp 65001 >nul
echo.
echo ========================================================
echo  Desarrollo Dashboard Regional Chile — rama dev
echo  División de Coordinación Interministerial
echo ========================================================
echo.
cd /d "%~dp0"

:: ── Verificar que estamos en rama dev ────────────────────────
for /f %%i in ('git rev-parse --abbrev-ref HEAD') do set RAMA=%%i
if not "%RAMA%"=="dev" (
    echo [!] Estás en la rama "%RAMA%", no en "dev".
    echo     Cambiando a dev...
    git checkout dev
    if errorlevel 1 (
        echo ERROR: no se pudo cambiar a dev. Crea la rama primero:
        echo   git checkout -b dev
        echo   git push origin dev
        pause
        exit /b 1
    )
)

:: ── Pedir descripción del cambio ─────────────────────────────
echo.
set /p DESCRIPCION="Describe brevemente el cambio (Enter para 'Actualización dashboard'): "
if "%DESCRIPCION%"=="" set DESCRIPCION=Actualizacion dashboard

:: ── 1. Actualizar README changelog ──────────────────────────
echo.
echo [1/4] Actualizando README...
python actualizar_readme.py "%DESCRIPCION%"

:: ── 2. Generar dashboard ──────────────────────────────────────
echo.
echo [2/4] Generando dashboard.html...
python generar_dashboard.py
if errorlevel 1 (
    echo ERROR en generar_dashboard.py
    pause
    exit /b 1
)

:: ── 2. Aplicar parche PDF si existe ──────────────────────────
if exist parche_pdf_dashboard.py (
    echo.
    echo [3/4] Aplicando parche PDF...
    python parche_pdf_dashboard.py
    if errorlevel 1 (
        echo AVISO: parche PDF falló, continuando sin él...
    )
) else (
    echo [3/4] parche_pdf_dashboard.py no encontrado, saltando...
)

:: ── 3. Subir a GitHub rama dev ────────────────────────────────
echo.
echo [4/4] Subiendo a GitHub rama dev...
git add -f dashboard.html generar_dashboard.py README.md
:: Agregar otros scripts si fueron modificados
if exist actualizar_datos.py     git add -f actualizar_datos.py
if exist cargar_historico_delitos.py git add -f cargar_historico_delitos.py
if exist parche_pdf_dashboard.py git add -f parche_pdf_dashboard.py

git commit --allow-empty -m "dev: %DESCRIPCION% [%date% %time%]"
git push origin dev
if errorlevel 1 (
    echo ERROR al hacer push. Verifica cable de red.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Cambio subido a rama dev.
echo.
echo  Para ver el dashboard localmente abre dashboard.html
echo.
echo  Cuando esté aprobado, pasa a producción con:
echo    git checkout main
echo    git merge dev
echo    git push origin main
echo    git checkout dev
echo ========================================================
echo.
pause
