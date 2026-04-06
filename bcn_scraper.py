"""
BCN SIIT - Scraper de Reportes Regionales (v2 - corregido)
===========================================================
Descarga los indicadores de las 16 regiones desde:
https://www.bcn.cl/siit/reportesregionales/

Uso:
    python bcn_scraper.py                   # 16 regiones, año 2025
    python bcn_scraper.py --anno 2023       # Año específico
    python bcn_scraper.py --anno todos      # 2021, 2023 y 2025
    python bcn_scraper.py --region 13       # Solo una región (prueba)
    python bcn_scraper.py --resumen         # Ver datos ya guardados
    python bcn_scraper.py --exportar-excel  # Exportar a Excel
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
import sqlite3
import time
import logging
import argparse
from datetime import datetime

# ── Configuración ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REGIONES = {
    1:  "Arica y Parinacota",
    2:  "Tarapacá",
    3:  "Antofagasta",
    4:  "Atacama",
    5:  "Coquimbo",
    6:  "Valparaíso",
    7:  "Metropolitana de Santiago",
    8:  "O'Higgins",
    9:  "Maule",
    10: "Ñuble",
    11: "Biobío",
    12: "La Araucanía",
    13: "Los Ríos",
    14: "Los Lagos",
    15: "Aysén",
    16: "Magallanes",
}

AÑOS_DISPONIBLES = [2021, 2023, 2025]

SECCIONES = {
    "demografia":         "v-pills-1",
    "grupos_vulnerables": "v-pills-2",
    "educacion":          "v-pills-3",
    "salud":              "v-pills-4",
    "trabajo_prevision":  "v-pills-5",
    "vivienda":           "v-pills-6",
    "economico":          "v-pills-7",
    "seguridad":          "v-pills-8",
    "infraestructura":    "v-pills-9",
    "electoral":          "v-pills-10",
}

DB_PATH  = "bcn_indicadores.db"
BASE_URL = "https://www.bcn.cl/siit/reportesregionales/reporte_final.html"
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Base de datos ─────────────────────────────────────────────────────────────

def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regiones (
            cod_region  INTEGER PRIMARY KEY,
            nombre      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS registros_bcn (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_region      INTEGER NOT NULL,
            nombre_region   TEXT    NOT NULL,
            anno            INTEGER NOT NULL,
            seccion         TEXT    NOT NULL,
            subtabla        TEXT,
            indicador       TEXT    NOT NULL,
            nivel           TEXT,
            valor           REAL,
            valor_texto     TEXT,
            fuente          TEXT,
            fecha_descarga  TEXT    NOT NULL,
            FOREIGN KEY (cod_region) REFERENCES regiones(cod_region)
        );

        CREATE INDEX IF NOT EXISTS idx_region_anno
            ON registros_bcn (cod_region, anno);
    """)
    conn.executemany(
        "INSERT OR IGNORE INTO regiones VALUES (?, ?)",
        REGIONES.items()
    )
    conn.commit()
    log.info("Base de datos lista: %s", DB_PATH)


# ── Descarga ──────────────────────────────────────────────────────────────────

def descargar(anno, cod_region):
    url = f"{BASE_URL}?anno={anno}&cod_region={cod_region}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except requests.RequestException as e:
        log.error("Error región %s año %s: %s", cod_region, anno, e)
        return None


# ── Parsing ───────────────────────────────────────────────────────────────────

def detectar_nivel(texto):
    """Detecta si una celda corresponde a nivel regional o nacional."""
    t = str(texto).lower().strip()
    if any(p in t for p in ["país", "pais", "nacional", "chile"]):
        return "nacional"
    if t.startswith("región") or t.startswith("region"):
        return "regional"
    # Muchas tablas BCN tienen el nombre de la región directamente
    # sin la palabra "región" — lo tratamos como regional por descarte
    if t and t not in ["nivel territorial", "nan", ""]:
        return "regional"
    return None


def parsear_tabla(tabla, seccion, subtabla, cod_region, anno, fuente):
    """Convierte una <table> HTML en registros normalizados."""
    fecha = datetime.now().isoformat(timespec="seconds")
    nombre_region = REGIONES[cod_region]
    registros = []

    filas = tabla.find_all("tr")
    if len(filas) < 2:
        return registros

    # ── Extraer encabezados ──────────────────────────────────────────────────
    # BCN usa a veces 2 filas de headers con colspan; tomamos la última fila
    # que no sea fila de datos (es decir, cuya primera celda no es nivel territorial)
    headers = []
    n_header_rows = 0

    for fila in filas:
        celdas = [c.get_text(strip=True) for c in fila.find_all(["th", "td"])]
        if not celdas:
            continue
        primer = celdas[0].lower()
        # Si la primera celda parece un nivel territorial, ya son datos
        if detectar_nivel(primer) is not None:
            break
        headers = celdas
        n_header_rows += 1

    if not headers:
        # Sin headers reconocibles, usar posición
        headers = [f"col_{i}" for i in range(
            len(filas[0].find_all(["th", "td"]))
        )]

    # ── Procesar filas de datos ───────────────────────────────────────────────
    for fila in filas[n_header_rows:]:
        celdas = [c.get_text(strip=True) for c in fila.find_all(["th", "td"])]
        if not celdas:
            continue

        nivel = detectar_nivel(celdas[0])
        if nivel is None:
            continue  # fila vacía o de sub-encabezado

        # Rellenar si hay menos celdas que headers (colspan)
        while len(celdas) < len(headers):
            celdas.append("")

        for j, indicador in enumerate(headers):
            if j == 0:
                continue  # primera columna = "Nivel Territorial"
            if not indicador or indicador.lower() in ["nan", ""]:
                continue

            valor_raw = celdas[j] if j < len(celdas) else ""

            # Convertir valor: BCN usa punto como miles y coma como decimal
            valor_num = None
            valor_txt = None
            limpio = (valor_raw
                      .replace(".", "")   # quitar separador de miles
                      .replace(",", ".")  # coma decimal → punto
                      .strip())
            try:
                valor_num = float(limpio)
            except ValueError:
                valor_txt = valor_raw if valor_raw else None

            registros.append({
                "cod_region":     cod_region,
                "nombre_region":  nombre_region,
                "anno":           anno,
                "seccion":        seccion,
                "subtabla":       subtabla,
                "indicador":      indicador,
                "nivel":          nivel,
                "valor":          valor_num,
                "valor_texto":    valor_txt,
                "fuente":         fuente,
                "fecha_descarga": fecha,
            })

    return registros


def extraer_fuente(tabla):
    """Busca el texto 'Fuente:' que sigue inmediatamente a la tabla."""
    sig = tabla.find_next_sibling()
    while sig:
        texto = sig.get_text(strip=True)
        if texto.lower().startswith("fuente"):
            return texto[:300]
        if sig.name in ["table", "h4", "h5", "h6"]:
            break
        sig = sig.find_next_sibling()
    return ""


def extraer_region(soup, cod_region, anno):
    """Extrae todos los registros de las 10 secciones de una región."""
    todos = []

    for seccion, div_id in SECCIONES.items():
        contenedor = soup.find("div", id=div_id)
        if not contenedor:
            continue

        tablas  = contenedor.find_all("table")
        titulos = contenedor.find_all("h6")

        for i, tabla in enumerate(tablas):
            subtabla = (titulos[i].get_text(strip=True)[:120]
                        if i < len(titulos) else f"tabla_{i+1}")
            fuente = extraer_fuente(tabla)
            recs   = parsear_tabla(tabla, seccion, subtabla, cod_region, anno, fuente)
            todos.extend(recs)

    return todos


# ── Persistencia ──────────────────────────────────────────────────────────────

def insertar(conn, registros):
    if not registros:
        return
    conn.executemany("""
        INSERT INTO registros_bcn
            (cod_region, nombre_region, anno, seccion, subtabla,
             indicador, nivel, valor, valor_texto, fuente, fecha_descarga)
        VALUES
            (:cod_region, :nombre_region, :anno, :seccion, :subtabla,
             :indicador, :nivel, :valor, :valor_texto, :fuente, :fecha_descarga)
    """, registros)
    conn.commit()


# ── Orquestador ───────────────────────────────────────────────────────────────

def scrape(annos, regiones_list, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    init_db(conn)

    total   = 0
    n_total = len(annos) * len(regiones_list)
    n       = 0

    for anno in annos:
        for cod_region in regiones_list:
            n += 1
            nombre = REGIONES.get(cod_region, str(cod_region))
            log.info("[%d/%d] %s — %s", n, n_total, nombre, anno)

            soup = descargar(anno, cod_region)
            if not soup:
                continue

            recs = extraer_region(soup, cod_region, anno)
            insertar(conn, recs)
            total += len(recs)
            log.info("  → %d registros", len(recs))

            time.sleep(1.5)

    conn.close()
    log.info("=" * 50)
    log.info("Total registros guardados: %d", total)
    log.info("Base de datos: %s", db_path)


# ── Utilidades ────────────────────────────────────────────────────────────────

def resumen_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    print("\n=== Resumen base de datos BCN ===")

    print("\nRegistros por región y año:")
    df = pd.read_sql("""
        SELECT nombre_region AS region, anno, COUNT(*) AS registros
        FROM registros_bcn
        GROUP BY nombre_region, anno
        ORDER BY anno, nombre_region
    """, conn)
    print(df.to_string(index=False) if not df.empty else "  (sin datos aún)")

    print("\nRegistros por sección:")
    df2 = pd.read_sql("""
        SELECT seccion, COUNT(*) AS registros
        FROM registros_bcn
        GROUP BY seccion ORDER BY registros DESC
    """, conn)
    print(df2.to_string(index=False) if not df2.empty else "  (sin datos aún)")

    conn.close()


def exportar_excel(db_path=DB_PATH, salida="bcn_indicadores.xlsx"):
    """Exporta a Excel con una hoja por sección."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("""
        SELECT nombre_region AS region, anno, seccion, subtabla,
               indicador, nivel, valor, valor_texto, fuente
        FROM registros_bcn
        ORDER BY anno, nombre_region, seccion
    """, conn)
    conn.close()

    if df.empty:
        log.warning("No hay datos para exportar.")
        return

    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        resumen = (df.groupby(["region","anno","seccion"])["indicador"]
                   .count().reset_index())
        resumen.columns = ["region","anno","seccion","n_registros"]
        resumen.to_excel(writer, sheet_name="RESUMEN", index=False)
        for sec in df["seccion"].unique():
            df[df["seccion"] == sec].to_excel(
                writer, sheet_name=sec[:31], index=False
            )
    log.info("Exportado: %s", salida)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Scraper BCN Reportes Regionales")
    p.add_argument("--anno",   default="2025",
                   help="Año: 2021, 2023, 2025 o 'todos' (default: 2025)")
    p.add_argument("--region", type=int, default=None,
                   help="Código región 1-16 (default: todas)")
    p.add_argument("--db",     default=DB_PATH)
    p.add_argument("--resumen",        action="store_true")
    p.add_argument("--exportar-excel", action="store_true")
    args = p.parse_args()

    if args.resumen:
        resumen_db(args.db)
    elif args.exportar_excel:
        exportar_excel(args.db)
    else:
        if args.anno == "todos":
            annos = AÑOS_DISPONIBLES
        elif int(args.anno) in AÑOS_DISPONIBLES:
            annos = [int(args.anno)]
        else:
            log.error("Año inválido. Usa: 2021, 2023, 2025 o 'todos'")
            exit(1)

        regiones_list = [args.region] if args.region else list(REGIONES.keys())
        scrape(annos=annos, regiones_list=regiones_list, db_path=args.db)
        resumen_db(args.db)
