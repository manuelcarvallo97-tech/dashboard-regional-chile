# actualizar_y_publicar.ps1
# Actualiza datos, regenera dashboard y publica en GitHub/Vercel
# Requiere: cable de red (WiFi del Ministerio bloquea LeyStop, BCE y GitHub)

$base = "c:\Users\manuel.carvallo\OneDrive - interior.gob.cl\Documentos\Scrap"
$log  = "$base\actualizar.log"
Set-Location $base

$env:PYTHONUTF8 = "1"
$inicio = Get-Date -Format "yyyy-MM-dd HH:mm"
"" | Add-Content $log
"=== Inicio $inicio ===" | Add-Content $log

# 1. Descargar datos nuevos
Write-Host "Actualizando datos (LeyStop + BCE)..."
python actualizar_datos.py 2>&1 | Tee-Object -Append -FilePath $log

# 2. Regenerar dashboard.html con datos embebidos
Write-Host "Regenerando dashboard..."
python generar_dashboard.py 2>&1 | Tee-Object -Append -FilePath $log

# 3. Publicar si hay cambios
git add -f dashboard.html
$hay_cambios = git status --porcelain

if ($hay_cambios) {
    $semana = python -c "import sqlite3; c=sqlite3.connect('bcn_indicadores.db'); print(c.execute('SELECT MAX(id_semana) FROM registros_leystop').fetchone()[0])"
    git commit -m "Actualizacion semana $semana automatica"
    git push origin main
    "Publicado semana $semana" | Add-Content $log
    Write-Host "Dashboard publicado - semana $semana"
} else {
    "Sin cambios nuevos" | Add-Content $log
    Write-Host "Sin datos nuevos - nada que publicar"
}

"=== Fin $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Add-Content $log
