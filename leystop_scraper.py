"""
LeyStop Scraper v6
===================
Fix: headers completos para evitar WAF, renovación de sesión robusta
"""

import sqlite3, requests, json, time, logging, argparse
from urllib.parse import unquote

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH  = "bcn_indicadores.db"
BASE_URL = "https://leystop.carabineros.cl"

REGIONES = {
    1:"Tarapacá", 2:"Antofagasta", 3:"Atacama", 4:"Coquimbo",
    5:"Valparaíso", 6:"O'Higgins", 7:"Maule", 8:"Biobío",
    9:"La Araucanía", 10:"Los Lagos", 11:"Aysén", 12:"Magallanes",
    13:"Metropolitana de Santiago", 14:"Los Ríos", 15:"Arica y Parinacota", 16:"Ñuble",
}

def crear_sesion():
    s = requests.Session()
    # Headers exactos del cURL que me pasaste
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-US,es-419;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://leystop.carabineros.cl/estadistica",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })

    # Visitar página principal para obtener cookies
    r = s.get(f"{BASE_URL}/estadistica", timeout=30)
    log.info(f"Página principal: {r.status_code}")

    # Actualizar XSRF token
    xsrf = s.cookies.get("XSRF-TOKEN", "")
    if xsrf:
        s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
        log.info("XSRF token OK")

    return s

def renovar_sesion(s):
    """Renueva cookies visitando la página de estadísticas"""
    try:
        r = s.get(f"{BASE_URL}/estadistica", timeout=30)
        xsrf = s.cookies.get("XSRF-TOKEN", "")
        if xsrf:
            s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
        log.info(f"  Sesión renovada ({r.status_code})")
    except Exception as e:
        log.warning(f"  Error renovando sesión: {e}")

def get_json(s, url, intento=1):
    try:
        r = s.get(f"{BASE_URL}{url}", timeout=30)
        if r.status_code == 200:
            ct = r.headers.get("Content-Type","")
            if "json" in ct or r.text.strip().startswith(("[","{")):
                return r.json()
            else:
                # WAF bloqueó — esperar y reintentar
                if intento <= 3:
                    espera = intento * 5
                    log.warning(f"WAF block {url} (intento {intento}) — esperando {espera}s...")
                    time.sleep(espera)
                    renovar_sesion(s)
                    time.sleep(2)
                    return get_json(s, url, intento+1)
                log.warning(f"Sin datos tras 3 intentos: {url}")
        else:
            log.debug(f"[{r.status_code}] {url}")
    except Exception as e:
        log.warning(f"Error {url}: {e}")
    return None

def init_db(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(registros_leystop)").fetchall()]
    if cols and "id_semana" not in cols:
        log.info("Recreando tabla registros_leystop...")
        conn.execute("DROP TABLE IF EXISTS registros_leystop")

    conn.execute("""CREATE TABLE IF NOT EXISTS leystop_semanas (
        id INTEGER PRIMARY KEY, nombre TEXT, anno INTEGER,
        semana TEXT, fecha_desde TEXT, fecha_hasta TEXT,
        fecha_desde_iso TEXT, fecha_hasta_iso TEXT)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS registros_leystop (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_semana INTEGER, anno INTEGER, semana TEXT,
        fecha_desde_iso TEXT, fecha_hasta_iso TEXT,
        id_region INTEGER, nombre_region TEXT,
        tasa_registro REAL, casos_total INTEGER,
        casos_ultima_semana INTEGER, casos_ultima_semana_anterior INTEGER,
        casos_28dias INTEGER, casos_28dias_anterior INTEGER,
        casos_anno_fecha INTEGER, casos_anno_fecha_anterior INTEGER,
        var_ultima_semana REAL, var_28dias REAL, var_anno_fecha REAL,
        mayor_registro_1 TEXT, pct_1 REAL,
        mayor_registro_2 TEXT, pct_2 REAL,
        mayor_registro_3 TEXT, pct_3 REAL,
        mayor_registro_4 TEXT, pct_4 REAL,
        mayor_registro_5 TEXT, pct_5 REAL,
        controles INTEGER, controles_identidad INTEGER, controles_vehicular INTEGER,
        fiscalizaciones INTEGER, fiscal_alcohol INTEGER, fiscal_bancaria INTEGER,
        incautaciones INTEGER, incaut_fuego INTEGER, incaut_blancas INTEGER,
        decomisos_ultima_semana REAL, decomisos_anno REAL,
        allanamientos_ultima_semana INTEGER, allanamientos_anno INTEGER,
        vehiculos_recuperados_semana INTEGER, vehiculos_recuperados_anno INTEGER,
        raw TEXT, fuente TEXT DEFAULT 'LeyStop Carabineros',
        fecha_descarga TEXT DEFAULT (date('now')),
        UNIQUE(id_semana, id_region))""")
    conn.commit()

def parsear(data, id_semana, sem_info, id_region):
    if not data or not isinstance(data, dict): return None

    def n(v):
        if v is None: return None
        try: return float(str(v).replace(",","."))
        except: return None
    def i(v):
        x = n(v); return int(x) if x is not None else None
    def var(a, b):
        try:
            a, b = float(a), float(b)
            return round((a-b)/b*100, 2) if b != 0 else None
        except: return None

    return {
        "id_semana": id_semana, "anno": sem_info.get("anno"),
        "semana": sem_info.get("semana",""),
        "fecha_desde_iso": sem_info.get("fecha_desde_iso",""),
        "fecha_hasta_iso": sem_info.get("fecha_hasta_iso",""),
        "id_region": id_region, "nombre_region": REGIONES.get(id_region, str(id_region)),
        "tasa_registro": n(data.get("tasa_de_registro")),
        "casos_total": i(data.get("casos")),
        "casos_ultima_semana": i(data.get("casos_ultima_semana")),
        "casos_ultima_semana_anterior": i(data.get("casos_ultima_semana_anterior")),
        "casos_28dias": i(data.get("casos_ultimos_28_dias")),
        "casos_28dias_anterior": i(data.get("casos_ultimos_28_dias_anterior")),
        "casos_anno_fecha": i(data.get("casos_anno_a_la_fecha")),
        "casos_anno_fecha_anterior": i(data.get("casos_anno_a_la_fecha_anterior")),
        "var_ultima_semana": var(data.get("casos_ultima_semana"), data.get("casos_ultima_semana_anterior")),
        "var_28dias": var(data.get("casos_ultimos_28_dias"), data.get("casos_ultimos_28_dias_anterior")),
        "var_anno_fecha": var(data.get("casos_anno_a_la_fecha"), data.get("casos_anno_a_la_fecha_anterior")),
        "mayor_registro_1": data.get("mayor_registro_1_nombre"), "pct_1": n(data.get("mayor_registro_1_valor")),
        "mayor_registro_2": data.get("mayor_registro_2_nombre"), "pct_2": n(data.get("mayor_registro_2_valor")),
        "mayor_registro_3": data.get("mayor_registro_3_nombre"), "pct_3": n(data.get("mayor_registro_3_valor")),
        "mayor_registro_4": data.get("mayor_registro_4_nombre"), "pct_4": n(data.get("mayor_registro_4_valor")),
        "mayor_registro_5": data.get("mayor_registro_5_nombre"), "pct_5": n(data.get("mayor_registro_5_valor")),
        "controles": i(data.get("controles")),
        "controles_identidad": i(data.get("controles_de_identidad")),
        "controles_vehicular": i(data.get("controles_vehiculares")),
        "fiscalizaciones": i(data.get("fiscalizaciones")),
        "fiscal_alcohol": i(data.get("fiscalizaciones_locales_alcohol")),
        "fiscal_bancaria": i(data.get("fiscalizaciones_entidades_comerciales_bancarias")),
        "incautaciones": i(data.get("incautaciones")),
        "incaut_fuego": i(data.get("incautaciones_armas_fuego")),
        "incaut_blancas": i(data.get("incautaciones_armas_blancas")),
        "decomisos_ultima_semana": n(data.get("decomisos_ultima_semana")),
        "decomisos_anno": n(data.get("decomisos_anno_a_la_fecha")),
        "allanamientos_ultima_semana": i(data.get("allanamientos_ultima_semana")),
        "allanamientos_anno": i(data.get("allanamientos_anno_a_la_fecha")),
        "vehiculos_recuperados_semana": i(data.get("vehiculos_recuperados_ultima_semana")),
        "vehiculos_recuperados_anno": i(data.get("vehiculos_recuperados_anno_a_la_fecha")),
        "raw": json.dumps(data, ensure_ascii=False),
    }

def guardar(conn, reg):
    try:
        conn.execute("""INSERT OR REPLACE INTO registros_leystop (
            id_semana, anno, semana, fecha_desde_iso, fecha_hasta_iso,
            id_region, nombre_region, tasa_registro, casos_total,
            casos_ultima_semana, casos_ultima_semana_anterior,
            casos_28dias, casos_28dias_anterior,
            casos_anno_fecha, casos_anno_fecha_anterior,
            var_ultima_semana, var_28dias, var_anno_fecha,
            mayor_registro_1, pct_1, mayor_registro_2, pct_2,
            mayor_registro_3, pct_3, mayor_registro_4, pct_4,
            mayor_registro_5, pct_5,
            controles, controles_identidad, controles_vehicular,
            fiscalizaciones, fiscal_alcohol, fiscal_bancaria,
            incautaciones, incaut_fuego, incaut_blancas,
            decomisos_ultima_semana, decomisos_anno,
            allanamientos_ultima_semana, allanamientos_anno,
            vehiculos_recuperados_semana, vehiculos_recuperados_anno, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(reg[k] for k in [
                "id_semana","anno","semana","fecha_desde_iso","fecha_hasta_iso",
                "id_region","nombre_region","tasa_registro","casos_total",
                "casos_ultima_semana","casos_ultima_semana_anterior",
                "casos_28dias","casos_28dias_anterior",
                "casos_anno_fecha","casos_anno_fecha_anterior",
                "var_ultima_semana","var_28dias","var_anno_fecha",
                "mayor_registro_1","pct_1","mayor_registro_2","pct_2",
                "mayor_registro_3","pct_3","mayor_registro_4","pct_4",
                "mayor_registro_5","pct_5",
                "controles","controles_identidad","controles_vehicular",
                "fiscalizaciones","fiscal_alcohol","fiscal_bancaria",
                "incautaciones","incaut_fuego","incaut_blancas",
                "decomisos_ultima_semana","decomisos_anno",
                "allanamientos_ultima_semana","allanamientos_anno",
                "vehiculos_recuperados_semana","vehiculos_recuperados_anno","raw"]))
        conn.commit()
        return True
    except Exception as e:
        log.warning(f"Insert error: {e}"); return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", type=int, default=160)
    parser.add_argument("--todos", action="store_true")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    log.info("=== LeyStop Scraper v6 ===")
    s = crear_sesion()

    semanas = get_json(s, "/api/semanas")
    if not semanas:
        log.error("Sin semanas — probando renovar sesión...")
        time.sleep(3)
        renovar_sesion(s)
        semanas = get_json(s, "/api/semanas")
    if not semanas:
        log.error("No se pudieron obtener semanas"); return

    filtradas = sorted(
        [x for x in semanas if (args.todos or x["id"] >= args.desde)],
        key=lambda x: x["id"])
    log.info(f"Semanas: {len(filtradas)} (id {filtradas[0]['id']}→{filtradas[-1]['id']})")

    conn = sqlite3.connect(args.db)
    init_db(conn)
    for x in semanas:
        conn.execute("""INSERT OR REPLACE INTO leystop_semanas
            (id,nombre,anno,semana,fecha_desde,fecha_hasta,fecha_desde_iso,fecha_hasta_iso)
            VALUES (?,?,?,?,?,?,?,?)""",
            (x["id"],x.get("nombre"),x.get("anno"),x.get("semana"),
             x.get("fecha_desde"),x.get("fecha_hasta"),
             x.get("fecha_desde_iso"),x.get("fecha_hasta_iso")))
    conn.commit()

    total = 0
    for i, sem in enumerate(filtradas):
        # Renovar sesión cada 3 semanas (~48 requests)
        if i > 0 and i % 1 == 0:
            renovar_sesion(s)
            time.sleep(1)

        n_sem = 0
        for id_reg in REGIONES:
            data = get_json(s, f"/api/estadistica/{sem['id']}/REGION/{id_reg}")
            if data:
                reg = parsear(data, sem["id"], sem, id_reg)
                if reg and guardar(conn, reg):
                    n_sem += 1
            time.sleep(1.0)

        total += n_sem
        log.info(f"  [{i+1}/{len(filtradas)}] {sem.get('nombre', sem['id'])} → {n_sem}/16 regiones")

    conn.close()
    log.info(f"\n=== Listo: {total} registros ===")
    conn2 = sqlite3.connect(args.db)
    t = conn2.execute("SELECT COUNT(*) FROM registros_leystop").fetchone()[0]
    log.info(f"Total en DB: {t} filas")
    print("\nPor año:")
    for row in conn2.execute("SELECT anno, COUNT(*) FROM registros_leystop GROUP BY anno ORDER BY anno"):
        print(f"  {row[0]}: {row[1]}")
    row = conn2.execute("""SELECT semana, nombre_region, tasa_registro, casos_anno_fecha,
        var_anno_fecha, mayor_registro_1 FROM registros_leystop
        WHERE id_region=13 ORDER BY id_semana DESC LIMIT 1""").fetchone()
    if row: print(f"\nEjemplo RM: {row}")
    conn2.close()

if __name__ == "__main__":
    main()
