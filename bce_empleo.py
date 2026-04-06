"""
BCE Empleo Regional v2
=======================
IDs confirmados del catálogo BCE:
  Tasa desocupación: F049.DES.TAS.INE9.{cod}.M  (códigos 11-26)
  Ocupados (miles):  F049.OCU.PMT.INE9.{cod}.M  (códigos 11-26)
  Fuerza de trabajo: buscar con patrón F049.FDT o similar

Uso: python bce_empleo.py
"""

import sqlite3, requests, json, time, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH  = "bcn_indicadores.db"

# Leer credenciales
creds = {}
for fname in [".env", "env.local"]:
    p = Path(__file__).parent / fname
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=",1)
                creds[k.strip()] = v.strip()

USER = creds.get("BDE_USER","")
PASS = creds.get("BDE_PASS","")
BASE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

# Mapeo código BCE (11-26) → nombre región
REGIONES = {
    "11": "Tarapacá",
    "12": "Antofagasta",
    "13": "Atacama",
    "14": "Coquimbo",
    "15": "Valparaíso",
    "16": "O'Higgins",
    "17": "Maule",
    "18N": "Biobío",           # 18N porque hubo split con Ñuble
    "19": "La Araucanía",
    "20": "Los Lagos",
    "21": "Aysén",
    "22": "Magallanes",
    "23": "Metropolitana de Santiago",
    "24": "Los Ríos",
    "25": "Arica y Parinacota",
    "26": "Ñuble",
}

# Series a descargar — IDs confirmados del catálogo
SERIES = []
for cod, region in REGIONES.items():
    SERIES.append({
        "serie_id": f"F049.DES.TAS.INE9.{cod}.M",
        "nombre_region": region,
        "indicador": "Tasa de desocupación",
        "unidad": "Porcentaje",
    })
    SERIES.append({
        "serie_id": f"F049.OCU.PMT.INE9.{cod}.M",
        "nombre_region": region,
        "indicador": "Ocupados",
        "unidad": "Miles de personas",
    })

# Buscar también Fuerza de trabajo con variantes de ID
FDT_IDS = {
    "11": ["F049.FDT.PMT.INE9.11.M", "F049.ACT.FDT.INE9.11.M", "F049.DES.FDT.INE9.11.M"],
    "23": ["F049.FDT.PMT.INE9.23.M", "F049.ACT.FDT.INE9.23.M", "F049.DES.FDT.INE9.23.M"],
}

def get_serie(serie_id, firstdate="2010-01-01"):
    try:
        r = requests.get(BASE_URL, params={
            "user": USER, "pass": PASS,
            "function": "GetSeries",
            "timeseries": serie_id,
            "firstdate": firstdate,
        }, timeout=30)
        data = r.json()
        if data.get("Codigo") == 0:
            s = data.get("Series",{})
            if s.get("Obs"):
                return s
        return None
    except Exception as e:
        log.warning(f"Error {serie_id}: {e}")
        return None

def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS registros_bce_empleo (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        serie_id        TEXT,
        nombre_region   TEXT,
        indicador       TEXT,
        unidad          TEXT,
        periodo         TEXT,
        valor           REAL,
        fuente          TEXT DEFAULT 'Banco Central de Chile / INE',
        fecha_descarga  TEXT DEFAULT (date('now')),
        UNIQUE(serie_id, periodo))""")
    conn.commit()

def guardar(conn, serie_id, region, indicador, unidad, obs):
    n = 0
    for o in obs:
        if o.get("statusCode") != "OK": continue
        val_str = o.get("value","")
        if not val_str or val_str == "NaN": continue
        try:
            val = float(val_str.replace(",","."))
        except:
            continue
        # Fecha DD-MM-YYYY → YYYY-MM
        try:
            p = o["indexDateString"].split("-")
            periodo = f"{p[2]}-{p[1]}"
        except:
            continue
        try:
            conn.execute("""INSERT OR REPLACE INTO registros_bce_empleo
                (serie_id, nombre_region, indicador, unidad, periodo, valor)
                VALUES (?,?,?,?,?,?)""",
                (serie_id, region, indicador, unidad, periodo, val))
            n += 1
        except: pass
    conn.commit()
    return n

def main():
    log.info("=== BCE Empleo Regional ===")
    log.info(f"Usuario: {USER}")
    log.info(f"Series a descargar: {len(SERIES)}")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    total = 0

    # Descargar tasa desocupación y ocupados
    for i, s in enumerate(SERIES):
        serie = get_serie(s["serie_id"])
        if serie:
            n = guardar(conn, s["serie_id"], s["nombre_region"],
                       s["indicador"], s["unidad"], serie["Obs"])
            total += n
            ult = serie["Obs"][-1]["indexDateString"] if serie["Obs"] else "?"
            log.info(f"  [{i+1}/{len(SERIES)}] ✓ {s['nombre_region']} — {s['indicador']}: {n} obs (hasta {ult})")
        else:
            log.info(f"  [{i+1}/{len(SERIES)}] ✗ {s['nombre_region']} — {s['indicador']} ({s['serie_id']})")
        time.sleep(0.2)

    # Intentar fuerza de trabajo con distintos patrones
    log.info("\n── Buscando Fuerza de trabajo ──")
    fdt_encontrado = False
    serie_test = get_serie("F049.FDT.PMT.INE9.11.M")
    if serie_test:
        log.info("  Patrón F049.FDT.PMT.INE9.{cod}.M ✓")
        patron_fdt = "F049.FDT.PMT.INE9.{cod}.M"
        fdt_encontrado = True
    else:
        # Buscar en catálogo
        log.info("  Buscando en catálogo...")
        r = requests.get(BASE_URL, params={
            "user": USER, "pass": PASS,
            "function": "SearchSeries", "frequency": "MONTHLY"
        }, timeout=60)
        series_cat = r.json().get("SeriesInfos",[])
        fdt_series = [s for s in series_cat if
                      "fuerza de trabajo" in s.get("spanishTitle","").lower() and
                      "ine9" in s.get("seriesId","").lower()]
        if fdt_series:
            log.info(f"  Encontradas {len(fdt_series)} series de fuerza de trabajo:")
            for s in fdt_series[:5]:
                log.info(f"    {s['seriesId']}: {s['spanishTitle']}")
            # Guardar para referencia
            with open("bce_fdt_series.json","w",encoding="utf-8") as f:
                json.dump(fdt_series, f, ensure_ascii=False, indent=2)
        else:
            log.info("  No encontradas series de fuerza de trabajo con INE9")

    if fdt_encontrado:
        for cod, region in REGIONES.items():
            serie_id = f"F049.FDT.PMT.INE9.{cod}.M"
            serie = get_serie(serie_id)
            if serie:
                n = guardar(conn, serie_id, region, "Fuerza de trabajo", "Miles de personas", serie["Obs"])
                total += n
                log.info(f"  ✓ {region}: {n} obs")
            time.sleep(0.2)

    conn.close()
    log.info(f"\n=== Listo: {total} registros ===")

    conn2 = sqlite3.connect(DB_PATH)
    t = conn2.execute("SELECT COUNT(*) FROM registros_bce_empleo").fetchone()[0]
    log.info(f"Total en DB: {t} filas")
    print("\nPor indicador y región:")
    for row in conn2.execute("""SELECT indicador, nombre_region, COUNT(*) n, MIN(periodo), MAX(periodo)
        FROM registros_bce_empleo GROUP BY indicador, nombre_region ORDER BY indicador, nombre_region"""):
        print(f"  {row[0]} | {row[1]}: {row[2]} obs ({row[3]}→{row[4]})")
    conn2.close()

if __name__ == "__main__":
    main()
