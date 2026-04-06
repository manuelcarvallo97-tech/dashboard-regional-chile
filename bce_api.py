"""
Banco Central de Chile - API BDE (v2 corregido)
================================================
Descarga estadísticas regionales desde la Base de Datos Estadísticos (BDE).
La API NO usa token — user/pass van directo en cada request.

Pasos recomendados:
    1. python bce_api.py --buscar          # Busca y guarda catálogo de series regionales
    2. python bce_api.py --ver-catalogo    # Muestra qué series hay disponibles
    3. python bce_api.py                   # Descarga todas las series del catálogo
    4. python bce_api.py --resumen         # Resumen de lo descargado
    5. python bce_api.py --exportar-excel  # Exporta a Excel
"""

import requests
import pandas as pd
import sqlite3
import logging
import argparse
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import os

# ── Configuración ─────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BDE_USER = os.getenv("BDE_USER")
BDE_PASS = os.getenv("BDE_PASS")
DB_PATH  = "bcn_indicadores.db"
API_BASE = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

# Palabras clave para filtrar series regionales del catálogo
PALABRAS_REGIONALES = [
    "región", "region", "regional",
    "arica", "tarapacá", "antofagasta", "atacama", "coquimbo",
    "valparaíso", "metropolitana", "o'higgins", "ohiggins",
    "maule", "ñuble", "biobío", "biobio", "araucanía", "araucania",
    "los ríos", "los rios", "los lagos", "aysén", "aysen", "magallanes",
]

# Frecuencias a descargar (puedes comentar las que no necesites)
FRECUENCIAS = [
    "QUARTERLY",   # Trimestral — PIB regional, etc.
    "ANNUAL",      # Anual — muchos indicadores regionales
    "MONTHLY",     # Mensual — algunos indicadores
]

# ── Verificar credenciales ────────────────────────────────────────────────────

def verificar_credenciales():
    if not BDE_USER or not BDE_PASS:
        raise ValueError(
            "\nFaltan credenciales en el archivo .env\n"
            "Asegúrate de que el archivo .env tenga:\n"
            "  BDE_USER=tu_email@ejemplo.com\n"
            "  BDE_PASS=tucontraseña\n"
        )
    log.info("Credenciales cargadas: %s", BDE_USER)


# ── Base de datos ─────────────────────────────────────────────────────────────

def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bce_catalogo (
            series_id       TEXT PRIMARY KEY,
            frecuencia      TEXT,
            titulo_esp      TEXT,
            primera_obs     TEXT,
            ultima_obs      TEXT,
            actualizado     TEXT,
            es_regional     INTEGER DEFAULT 1,
            fecha_catalogo  TEXT
        );

        CREATE TABLE IF NOT EXISTS registros_bce (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id       TEXT    NOT NULL,
            titulo          TEXT,
            periodo         TEXT    NOT NULL,
            valor           REAL,
            unidad          TEXT    DEFAULT '',
            fuente          TEXT    DEFAULT 'Banco Central de Chile - BDE',
            fecha_descarga  TEXT    NOT NULL,
            UNIQUE(series_id, periodo)
        );
    """)
    conn.commit()


# ── API: Buscar series ────────────────────────────────────────────────────────

def buscar_series_frecuencia(frecuencia):
    """Descarga el catálogo completo de una frecuencia via SearchSeries."""
    params = {
        "user":      BDE_USER,
        "pass":      BDE_PASS,
        "function":  "SearchSeries",
        "frequency": frecuencia,
    }
    try:
        r = requests.get(API_BASE, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if data is None:
            log.error("La API devolvió null para frecuencia %s. Verifica tus credenciales.", frecuencia)
            return []
        if data.get("Codigo") != 0:
            log.error("Error API [%s]: %s", frecuencia, data.get("Descripcion"))
            return []
        return data.get("SeriesInfos", [])
    except Exception as e:
        log.error("Error descargando catálogo %s: %s", frecuencia, e)
        return []


def es_serie_regional(titulo):
    """Retorna True si el título de la serie menciona alguna región."""
    t = str(titulo).lower()
    return any(p in t for p in PALABRAS_REGIONALES)


def buscar_y_guardar_catalogo(db_path=DB_PATH):
    """
    Descarga el catálogo completo del BDE, filtra las series regionales
    y las guarda en la tabla bce_catalogo.
    """
    verificar_credenciales()
    conn = sqlite3.connect(db_path)
    init_db(conn)

    fecha = datetime.now().isoformat(timespec="seconds")
    total_regional = 0

    for freq in FRECUENCIAS:
        log.info("Buscando series %s...", freq)
        series = buscar_series_frecuencia(freq)
        log.info("  → %d series totales encontradas", len(series))

        regionales = [s for s in series if es_serie_regional(s.get("spanishTitle", ""))]
        log.info("  → %d series regionales filtradas", len(regionales))

        conn.executemany("""
            INSERT OR REPLACE INTO bce_catalogo
                (series_id, frecuencia, titulo_esp, primera_obs,
                 ultima_obs, actualizado, es_regional, fecha_catalogo)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, [
            (
                s.get("seriesId"),
                s.get("frequencyCode"),
                s.get("spanishTitle"),
                s.get("firstObservation"),
                s.get("lastObservation"),
                s.get("updatedAt"),
                fecha,
            )
            for s in regionales
        ])
        conn.commit()
        total_regional += len(regionales)
        time.sleep(1)  # pausa entre frecuencias

    log.info("=" * 50)
    log.info("Total series regionales en catálogo: %d", total_regional)
    conn.close()


def ver_catalogo(db_path=DB_PATH, frecuencia=None):
    """Muestra las series regionales guardadas en el catálogo."""
    conn = sqlite3.connect(db_path)
    query = "SELECT series_id, frecuencia, titulo_esp, primera_obs, ultima_obs FROM bce_catalogo WHERE es_regional=1"
    if frecuencia:
        query += f" AND frecuencia='{frecuencia.upper()}'"
    query += " ORDER BY frecuencia, titulo_esp"
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        print("\nNo hay series en el catálogo. Corre primero: python bce_api.py --buscar")
        return

    print(f"\n=== Catálogo series regionales BDE ({len(df)} series) ===")
    for freq in df["frecuencia"].unique():
        sub = df[df["frecuencia"] == freq]
        print(f"\n-- {freq} ({len(sub)} series) --")
        for _, row in sub.iterrows():
            print(f"  {row['series_id']:<45} {row['titulo_esp'][:70]}")


# ── API: Descargar datos de una serie ─────────────────────────────────────────

def descargar_serie(series_id, desde="2010-01-01", hasta=None):
    """Descarga los datos de una serie. Retorna lista de {periodo, valor}."""
    if hasta is None:
        hasta = datetime.now().strftime("%Y-%m-%d")

    params = {
        "user":        BDE_USER,
        "pass":        BDE_PASS,
        "function":    "GetSeries",
        "timeseries":  series_id,
        "firstdate":   desde,
        "lastdate":    hasta,
    }
    try:
        r = requests.get(API_BASE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        if data is None:
            log.warning("  → null para serie %s", series_id)
            return []
        if data.get("Codigo") != 0:
            log.warning("  → Error [%s]: %s", series_id, data.get("Descripcion"))
            return []

        obs_list = data.get("Series", {}).get("Obs", [])
        resultados = []
        for obs in obs_list:
            periodo   = obs.get("indexDateString", "")
            valor_str = str(obs.get("value", "")).replace(",", ".")
            try:
                valor = float(valor_str)
            except ValueError:
                valor = None
            if periodo and obs.get("statusCode") == "OK":
                resultados.append({"periodo": periodo, "valor": valor})

        return resultados

    except Exception as e:
        log.error("  → Excepción en %s: %s", series_id, e)
        return []


# ── Descarga masiva desde catálogo ────────────────────────────────────────────

def descargar_todo(db_path=DB_PATH, frecuencia=None, limite=None):
    """
    Descarga los datos de todas las series regionales del catálogo.
    - frecuencia: filtra por frecuencia (QUARTERLY, ANNUAL, MONTHLY)
    - limite: para pruebas, descarga solo las primeras N series
    """
    verificar_credenciales()
    conn = sqlite3.connect(db_path)
    init_db(conn)

    # Cargar catálogo
    query = "SELECT series_id, titulo_esp, frecuencia FROM bce_catalogo WHERE es_regional=1"
    if frecuencia:
        query += f" AND frecuencia='{frecuencia.upper()}'"
    query += " ORDER BY frecuencia, titulo_esp"
    df_cat = pd.read_sql(query, conn)

    if df_cat.empty:
        log.error("Catálogo vacío. Corre primero: python bce_api.py --buscar")
        conn.close()
        return

    if limite:
        df_cat = df_cat.head(limite)

    log.info("Descargando %d series del BDE...", len(df_cat))
    fecha = datetime.now().isoformat(timespec="seconds")
    total = 0

    for i, row in df_cat.iterrows():
        sid   = row["series_id"]
        titulo = row["titulo_esp"]
        log.info("[%d/%d] %s", i + 1, len(df_cat), titulo[:70])

        obs = descargar_serie(sid)
        if not obs:
            log.warning("  → Sin datos")
            continue

        registros = [
            {
                "series_id":      sid,
                "titulo":         titulo,
                "periodo":        o["periodo"],
                "valor":          o["valor"],
                "fecha_descarga": fecha,
            }
            for o in obs
        ]
        conn.executemany("""
            INSERT OR IGNORE INTO registros_bce
                (series_id, titulo, periodo, valor, fecha_descarga)
            VALUES
                (:series_id, :titulo, :periodo, :valor, :fecha_descarga)
        """, registros)
        conn.commit()
        total += len(registros)
        log.info("  → %d observaciones", len(registros))

        time.sleep(0.3)  # máx 5 requests/seg según términos del BDE

    conn.close()
    log.info("=" * 50)
    log.info("Total registros BCE guardados: %d", total)


# ── Resumen ───────────────────────────────────────────────────────────────────

def resumen_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    print("\n=== Resumen Banco Central (BDE) ===")

    df = pd.read_sql("""
        SELECT r.titulo, c.frecuencia,
               MIN(r.periodo) AS desde, MAX(r.periodo) AS hasta,
               COUNT(*) AS n_obs
        FROM registros_bce r
        LEFT JOIN bce_catalogo c ON c.series_id = r.series_id
        GROUP BY r.series_id
        ORDER BY c.frecuencia, r.titulo
    """, conn)

    if df.empty:
        print("  (sin datos aún)")
    else:
        print(f"  {len(df)} series descargadas")
        for freq in df["frecuencia"].dropna().unique():
            sub = df[df["frecuencia"] == freq]
            print(f"\n  {freq} ({len(sub)} series):")
            for _, row in sub.iterrows():
                print(f"    {row['titulo'][:60]:<62} {row['desde']} → {row['hasta']} ({row['n_obs']} obs)")

    conn.close()


# ── Exportar Excel ────────────────────────────────────────────────────────────

def exportar_excel(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)

    df = pd.read_sql("""
        SELECT r.titulo, c.frecuencia, r.periodo, r.valor, r.series_id
        FROM registros_bce r
        LEFT JOIN bce_catalogo c ON c.series_id = r.series_id
        ORDER BY c.frecuencia, r.titulo, r.periodo
    """, conn)
    conn.close()

    if df.empty:
        log.warning("Sin datos para exportar.")
        return

    salida = "bce_regional.xlsx"
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        # Hoja raw
        df.to_excel(writer, sheet_name="datos_raw", index=False)

        # Una hoja por frecuencia con pivot (series en columnas)
        for freq in df["frecuencia"].dropna().unique():
            df_f = df[df["frecuencia"] == freq][["titulo", "periodo", "valor"]]
            try:
                pivot = df_f.pivot_table(
                    index="periodo", columns="titulo", values="valor"
                ).reset_index()
                pivot.to_excel(writer, sheet_name=freq[:31], index=False)
            except Exception as e:
                log.warning("No se pudo pivotar %s: %s", freq, e)

    log.info("Exportado: %s", salida)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="API Banco Central - Series Regionales")
    p.add_argument("--buscar",         action="store_true",
                   help="Descarga el catálogo de series regionales del BDE")
    p.add_argument("--ver-catalogo",   action="store_true",
                   help="Muestra las series del catálogo guardado")
    p.add_argument("--resumen",        action="store_true",
                   help="Resumen de datos ya descargados")
    p.add_argument("--exportar-excel", action="store_true",
                   help="Exporta datos a Excel")
    p.add_argument("--frecuencia",     default=None,
                   help="Filtrar por frecuencia: QUARTERLY, ANNUAL, MONTHLY")
    p.add_argument("--limite",         type=int, default=None,
                   help="Descargar solo las primeras N series (para pruebas)")
    p.add_argument("--db",             default=DB_PATH)
    args = p.parse_args()

    if args.buscar:
        buscar_y_guardar_catalogo(args.db)
        ver_catalogo(args.db)
    elif args.ver_catalogo:
        ver_catalogo(args.db, args.frecuencia)
    elif args.resumen:
        resumen_db(args.db)
    elif args.exportar_excel:
        exportar_excel(args.db)
    else:
        descargar_todo(args.db, args.frecuencia, args.limite)
        resumen_db(args.db)
