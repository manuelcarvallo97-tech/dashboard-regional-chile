"""
BCN Diagnóstico - Analiza la estructura real del HTML
Corre esto primero para ver cómo están organizadas las tablas
"""

import requests
from bs4 import BeautifulSoup

url = "https://www.bcn.cl/siit/reportesregionales/reporte_final.html?anno=2025&cod_region=13"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print("Descargando página...")
r = requests.get(url, headers=headers, timeout=30)
print(f"Status HTTP: {r.status_code}")
print(f"Tamaño HTML: {len(r.text)} caracteres\n")

soup = BeautifulSoup(r.text, "lxml")

# ── 1. Buscar todos los divs con id que contengan "pills" ──────────────────
print("=" * 60)
print("DIVS CON ID 'pills' o 'tab':")
print("=" * 60)
for div in soup.find_all("div", id=True):
    div_id = div.get("id", "")
    if "pills" in div_id or "tab" in div_id or "v-" in div_id:
        tablas_dentro = div.find_all("table")
        print(f"  id='{div_id}' → {len(tablas_dentro)} tablas dentro")

# ── 2. Contar todas las tablas en la página ───────────────────────────────
todas_tablas = soup.find_all("table")
print(f"\nTOTAL TABLAS EN LA PÁGINA: {len(todas_tablas)}")

# ── 3. Ver los primeros headings para entender estructura ──────────────────
print("\n" + "=" * 60)
print("HEADINGS (h4, h5, h6) Y CUÁNTAS TABLAS LES SIGUEN:")
print("=" * 60)
for h in soup.find_all(["h4", "h5", "h6"])[:20]:
    texto = h.get_text(strip=True)[:70]
    # Contar tablas hermanas que siguen
    tabla_siguiente = h.find_next("table")
    tiene_tabla = "✓ tabla siguiente" if tabla_siguiente else "✗ sin tabla"
    print(f"  [{h.name}] {texto}")
    print(f"         → {tiene_tabla}")

# ── 4. Mostrar las primeras 3 tablas con su contexto ──────────────────────
print("\n" + "=" * 60)
print("PRIMERAS 3 TABLAS (encabezados y primeras 2 filas):")
print("=" * 60)
for i, tabla in enumerate(todas_tablas[:3]):
    print(f"\n--- Tabla {i+1} ---")
    # Título más cercano antes de la tabla
    titulo = tabla.find_previous(["h5", "h6", "h4"])
    if titulo:
        print(f"Título anterior: {titulo.get_text(strip=True)[:80]}")

    filas = tabla.find_all("tr")
    for j, fila in enumerate(filas[:3]):
        celdas = [td.get_text(strip=True)[:25] for td in fila.find_all(["th", "td"])]
        print(f"  Fila {j+1}: {celdas}")

# ── 5. Guardar el HTML completo para inspeccionarlo ───────────────────────
with open("bcn_html_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\n\nHTML completo guardado en: bcn_html_raw.html")
print("Puedes abrirlo en el navegador para ver la estructura real.")
