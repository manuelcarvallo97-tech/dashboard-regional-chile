@echo off
cd /d "C:\Users\manuel.carvallo\OneDrive - interior.gob.cl\Documentos\Scrap"

echo === %date% %time% - Iniciando actualización ===

echo [1/4] Actualizando empleo BCE...
python bce_empleo.py

echo [2/4] Actualizando seguridad LeyStop...
python leystop_scraper.py

echo [3/4] Generando dashboard...
python generar_dashboard.py

echo [4/4] Subiendo a GitHub...
git add dashboard.html
git commit -m "Actualizacion automatica %date%"
git push origin main

echo === Dashboard actualizado! ===
echo Ver en: https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html
pause
