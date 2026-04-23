import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
"""
Carga histórica de registros_leystop_delitos
=============================================
Descarga el array completo de delitos (21 tipos) para TODAS las semanas
disponibles en leystop_semanas, usando el Referer de la pestaña Registros.

Úsalo solo una vez para poblar la tabla desde cero.
El actualizador_datos.py se encarga de las semanas nuevas en adelante.

Uso:
    python cargar_historico_delitos.py
    python cargar_historico_delitos.py --desde 160   (solo desde id_semana 160)
    python cargar_historico_delitos.py --force        (re-descarga todo aunque ya exista)
"""

import sqlite3, requests, json, time, logging, argparse, unicodedata
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

DB_PATH     = "bcn_indicadores.db"
BASE_URL_LS = "https://leystop.carabineros.cl"

REGIONES_LS = {
    1:"Tarapacá", 2:"Antofagasta", 3:"Atacama", 4:"Coquimbo",
    5:"Valparaíso", 6:"O'Higgins", 7:"Maule", 8:"Biobío",
    9:"La Araucanía", 10:"Los Lagos", 11:"Aysén", 12:"Magallanes",
    13:"Metropolitana de Santiago", 14:"Los Ríos",
    15:"Arica y Parinacota", 16:"Ñuble",
}

# Los 11 DMCS — nombres exactos como vienen del JSON de LeyStop
DMCS_NOMBRES = {
    "HOMICIDIOS Y FEMICIDIOS",
    "VIOLACIONES Y DELITOS SEXUALES",
    "LESIONES GRAVES",
    "LESIONES MENOS GRAVES",
    "LESIONES LEVES",
    "ROBOS CON VIOLENCIA E INTIMIDACION",
    "ROBOS POR SORPRESA",
    "ROBOS EN LUGARES HABITADOS Y NO HABITADOS",
    "ROBOS DE VEHICULOS Y SUS ACCESORIOS",
    "OTROS ROBOS CON FUERZA EN LAS COSAS",
    "HURTOS",
}

def norm(s):
    """Normaliza texto: sin tildes, mayúsculas, para comparar DMCS."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper()

def crear_tabla(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS registros_leystop_delitos (
        id_semana       INTEGER,
        anno            INTEGER,
        semana          TEXT,
        fecha_desde_iso TEXT,
        fecha_hasta_iso TEXT,
        id_region       INTEGER,
        nombre_region   TEXT,
        nombre_delito   TEXT,
        es_dmcs         INTEGER DEFAULT 0,
        ultima_semana_ant INTEGER,
        ultima_semana   INTEGER,
        dias28_ant      INTEGER,
        dias28          INTEGER,
        anno_fecha_ant  INTEGER,
        anno_fecha      INTEGER,
        umbral          REAL,
        PRIMARY KEY (id_semana, id_region, nombre_delito)
    )""")
    conn.commit()

def crear_sesion_registros():
    """Sesión autenticada con Referer de pestaña Registros."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-US,es-419;q=0.9,es;q=0.8",
        "Referer": "https://leystop.carabineros.cl/estadistica/registros",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })
    s.get(f"{BASE_URL_LS}/estadistica", timeout=30, verify=False)
    xsrf = s.cookies.get("XSRF-TOKEN", "")
    if xsrf:
        s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
    return s

def semanas_en_db(conn, desde_id):
    """Retorna las semanas disponibles en leystop_semanas >= desde_id."""
    rows = conn.execute(
        "SELECT id, anno, semana, fecha_desde_iso, fecha_hasta_iso, nombre "
        "FROM leystop_semanas WHERE id >= ? ORDER BY id",
        (desde_id,)
    ).fetchall()
    return [{"id": r[0], "anno": r[1], "semana": r[2],
             "fecha_desde_iso": r[3], "fecha_hasta_iso": r[4],
             "nombre": r[5]} for r in rows]

def ya_descargado(conn, id_semana, id_region):
    """Verifica si ya hay registros para esa semana/región."""
    r = conn.execute(
        "SELECT COUNT(*) FROM registros_leystop_delitos WHERE id_semana=? AND id_region=?",
        (id_semana, id_region)
    ).fetchone()
    return r[0] > 0

def guardar_delitos(conn, sem, id_region, registros):
    """Guarda el array registros[] para una semana/región."""
    n = 0
    nombre_region = REGIONES_LS.get(id_region, str(id_region))
    for rec in registros:
        nombre = rec.get("nombre", "")
        es_dmcs = 1 if norm(nombre) in {norm(d) for d in DMCS_NOMBRES} else 0
        try:
            conn.execute("""INSERT OR REPLACE INTO registros_leystop_delitos
                (id_semana, anno, semana, fecha_desde_iso, fecha_hasta_iso,
                 id_region, nombre_region, nombre_delito, es_dmcs,
                 ultima_semana_ant, ultima_semana,
                 dias28_ant, dias28,
                 anno_fecha_ant, anno_fecha, umbral)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sem["id"], sem.get("anno"), sem.get("semana", ""),
                 sem.get("fecha_desde_iso", ""), sem.get("fecha_hasta_iso", ""),
                 id_region, nombre_region, nombre, es_dmcs,
                 rec.get("ultima_semana_anterior"), rec.get("ultima_semana"),
                 rec.get("ultimos_28_dias_anterior"), rec.get("ultimos_28_dias"),
                 rec.get("anno_a_la_fecha_anterior"), rec.get("anno_a_la_fecha"),
                 rec.get("umbral")))
            n += 1
        except Exception as e:
            log.warning(f"    Insert {nombre}: {e}")
    conn.commit()
    return n

def main():
    parser = argparse.ArgumentParser(description="Carga histórica de delitos LeyStop")
    parser.add_argument("--desde", type=int, default=0,
                        help="ID semana desde donde empezar (default: todas)")
    parser.add_argument("--force", action="store_true",
                        help="Re-descarga aunque ya existan datos")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    crear_tabla(conn)

    semanas = semanas_en_db(conn, args.desde)
    if not semanas:
        log.error("No hay semanas en leystop_semanas. Corre actualizar_datos.py primero.")
        conn.close()
        return

    log.info("=" * 55)
    log.info(f"Carga histórica delitos — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"Semanas a procesar: {len(semanas)} "
             f"({semanas[0]['nombre']} → {semanas[-1]['nombre']})")
    log.info(f"Modo force: {'SÍ' if args.force else 'NO (salta semanas ya descargadas)'}")
    log.info("=" * 55)

    total_registros = 0
    total_skipped   = 0

    for i, sem in enumerate(semanas):
        n_sem = 0
        skipped = 0

        # Renovar sesión cada 5 semanas para evitar expiración de cookies
        if i % 5 == 0:
            s = crear_sesion_registros()
            log.info(f"Sesión renovada (semana {i+1}/{len(semanas)})")

        for id_reg in REGIONES_LS:
            # Saltar si ya está descargado y no es force
            if not args.force and ya_descargado(conn, sem["id"], id_reg):
                skipped += 1
                continue

            url = f"{BASE_URL_LS}/api/estadistica/{sem['id']}/REGION/{id_reg}"
            try:
                r = s.get(url, timeout=30, verify=False)
                if r.status_code == 200:
                    ct = r.headers.get("Content-Type", "")
                    if "json" in ct or r.text.strip().startswith("{"):
                        data = r.json()
                        arr = data.get("registros", [])
                        if arr:
                            n = guardar_delitos(conn, sem, id_reg, arr)
                            n_sem += n
                        else:
                            log.debug(f"  Sin array registros: semana {sem['id']} región {id_reg}")
                elif r.status_code == 429:
                    log.warning("  Rate limit (429) — esperando 30s...")
                    time.sleep(30)
                elif r.status_code == 403:
                    log.warning("  Bloqueado (403) — WAF activo. Espera unos minutos.")
                    time.sleep(60)
                    s = crear_sesion_registros()  # Renovar sesión
            except Exception as e:
                log.warning(f"  Error {url}: {e}")

            time.sleep(1.5)  # Pausa conservadora entre regiones

        total_registros += n_sem
        total_skipped   += skipped

        status = f"✓ {n_sem} registros"
        if skipped > 0:
            status += f" ({skipped} ya existían)"
        log.info(f"  [{i+1:3d}/{len(semanas)}] {sem['nombre']} → {status}")

        time.sleep(2)  # Pausa entre semanas

    conn.close()

    log.info("")
    log.info("=" * 55)
    log.info(f"Carga completada.")
    log.info(f"  Registros guardados : {total_registros}")
    log.info(f"  Regiones saltadas   : {total_skipped} (ya existían)")
    log.info("")
    log.info("Siguiente paso: python generar_dashboard.py")
    log.info("=" * 55)

if __name__ == "__main__":
    main()
