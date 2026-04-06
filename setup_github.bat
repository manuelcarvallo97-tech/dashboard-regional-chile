@echo off
cd /d "C:\Users\manuel.carvallo\OneDrive - interior.gob.cl\Documentos\Scrap"

echo === Configurando Git ===
git config --global user.email "manuel.carvallo@interior.gob.cl"
git config --global user.name "Manuel Carvallo"

echo === Inicializando repositorio local ===
git init
git remote remove origin 2>nul
git remote add origin https://github.com/manuelcarvallo97-tech/dashboard-regional-chile.git
git branch -M main

echo === Subiendo todos los archivos ===
git add .
git commit -m "Subida inicial completa"
git push -u origin main

echo === Listo! Abre https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html ===
pause
