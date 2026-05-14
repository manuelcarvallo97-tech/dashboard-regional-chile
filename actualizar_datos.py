import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
"""
Actualizador inteligente de datos
===================================
Lógica:
  - BCE Empleo: descarga solo desde el último período disponible en DB
  - LeyStop: descarga solo desde el último id_semana disponible en DB + 1
  - Si no hay datos nuevos, no hace nada
  - Al final regenera el dashboard y sube a GitHub

Uso: python actualizar_datos.py
"""

import sqlite3, requests, json, time, logging, subprocess, hashlib, math
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH  = "bcn_indicadores.db"
BASE_URL_BCE = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
BASE_URL_LS  = "https://leystop.carabineros.cl"

# ── Credenciales ──────────────────────────────────────────────────────────────
def leer_creds():
    creds = {}
    for fname in [".env", "env.local"]:
        p = Path(__file__).parent / fname
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
    return creds


# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE — sincronización incremental
# ══════════════════════════════════════════════════════════════════════════════
class SupaREST:
    def __init__(self, url, service_key):
        self.base = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def upsert(self, tabla, rows, on_conflict=None):
        if not rows: return True
        headers = dict(self.headers)
        prefer = "resolution=merge-duplicates,return=minimal"
        if on_conflict:
            prefer += f",on_conflict={on_conflict}"
        headers["Prefer"] = prefer
        r = requests.post(
            f"{self.base}/{tabla}",
            headers=headers,
            data=json.dumps(rows, ensure_ascii=False, default=str),
            timeout=60, verify=False,
        )
        if r.status_code not in (200, 201):
            log.error(f"  Supabase HTTP {r.status_code} en {tabla}: {r.text[:300]}")
            return False
        return True

def clean_supa(row):
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}

def sync_empleo_supabase(sb, conn, desde_periodo):
    cursor = conn.execute("""
        SELECT serie_id, nombre_region, indicador, unidad, periodo, valor
        FROM registros_bce_empleo WHERE periodo >= ?
        ORDER BY nombre_region, periodo
    """, (desde_periodo,))
    cols = [d[0] for d in cursor.description]
    rows = [clean_supa(dict(zip(cols, r))) for r in cursor.fetchall()]
    if not rows:
        log.info("  Supabase empleo: sin filas nuevas"); return 0
    if sb.upsert("registros_bce_empleo", rows, on_conflict="serie_id,periodo"):
        log.info(f"  Supabase empleo: ✓ {len(rows)} filas"); return len(rows)
    return 0

def sync_leystop_supabase(sb, conn, desde_id_semana):
    cursor = conn.execute("""
        SELECT id, nombre, semana, anno, fecha_desde_iso, fecha_hasta_iso
        FROM leystop_semanas WHERE id >= ?
    """, (desde_id_semana,))
    cols = [d[0] for d in cursor.description]
    semanas = [clean_supa(dict(zip(cols, r))) for r in cursor.fetchall()]
    if semanas:
        sb.upsert("leystop_semanas", semanas, on_conflict="id")
        log.info(f"  Supabase semanas: ✓ {len(semanas)} semanas")
    cursor = conn.execute("""
        SELECT id_semana, id_region, nombre_region, semana, fecha_desde_iso, fecha_hasta_iso, anno,
               tasa_registro, casos_total, casos_anno_fecha, casos_anno_fecha_anterior, var_anno_fecha,
               var_ultima_semana, var_28dias, casos_ultima_semana, casos_28dias,
               mayor_registro_1, pct_1, mayor_registro_2, pct_2, mayor_registro_3, pct_3,
               mayor_registro_4, pct_4, mayor_registro_5, pct_5,
               controles, controles_identidad, controles_vehicular,
               fiscalizaciones, fiscal_alcohol, fiscal_bancaria,
               incautaciones, incaut_fuego, incaut_blancas,
               allanamientos_anno, vehiculos_recuperados_anno, decomisos_anno
        FROM registros_leystop WHERE id_semana >= ?
        ORDER BY id_semana, id_region
    """, (desde_id_semana,))
    cols = [d[0] for d in cursor.description]
    rows = [clean_supa(dict(zip(cols, r))) for r in cursor.fetchall()]
    if not rows:
        log.info("  Supabase leystop: sin filas nuevas"); return 0
    if sb.upsert("registros_leystop", rows, on_conflict="id_semana,id_region"):
        log.info(f"  Supabase leystop: ✓ {len(rows)} filas"); return len(rows)
    return 0

# ══════════════════════════════════════════════════════════════════════════════
# BCE EMPLEO — solo períodos nuevos
# ══════════════════════════════════════════════════════════════════════════════
REGIONES_BCE = {
    "11":"Tarapacá","12":"Antofagasta","13":"Atacama","14":"Coquimbo",
    "15":"Valparaíso","16":"O'Higgins","17":"Maule","18N":"Biobío",
    "19":"La Araucanía","20":"Los Lagos","21":"Aysén","22":"Magallanes",
    "23":"Metropolitana de Santiago","24":"Los Ríos","25":"Arica y Parinacota","26":"Ñuble",
}

def ultimo_periodo_empleo(conn=None):
    """Retorna el último período de empleo en la DB local o en Supabase."""
    if conn is not None:
        r = conn.execute("SELECT MAX(periodo) FROM registros_bce_empleo").fetchone()
        return r[0] if r and r[0] else "2010-01"
    # Sin DB local (GitHub Actions) → consultar Supabase
    creds = leer_creds()
    url = creds.get("SUPABASE_URL", "")
    key = creds.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return "2010-01"
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(
            f"{url}/rest/v1/registros_bce_empleo",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "periodo", "order": "periodo.desc", "limit": "1"},
            timeout=15, verify=False,
        )
        data = r.json()
        if data and data[0].get("periodo"):
            return data[0]["periodo"]
    except Exception as e:
        log.warning(f"Supabase ultimo_periodo_empleo: {e}")
    return "2010-01"

def get_serie_bce(user, pwd, serie_id, firstdate):
    try:
        r = requests.get(BASE_URL_BCE, params={
            "user": user, "pass": pwd, "function": "GetSeries",
            "timeseries": serie_id, "firstdate": firstdate,
        }, timeout=30)
        data = r.json()
        if data.get("Codigo") == 0 and data.get("Series", {}).get("Obs"):
            return data["Series"]["Obs"]
    except Exception as e:
        log.warning(f"BCE error {serie_id}: {e}")
    return []

def guardar_empleo(conn, serie_id, region, indicador, unidad, obs):
    n = 0
    for o in obs:
        if o.get("statusCode") != "OK": continue
        val_str = o.get("value", "")
        if not val_str or val_str == "NaN": continue
        try:
            val = float(val_str.replace(",", "."))
            p = o["indexDateString"].split("-")
            periodo = f"{p[2]}-{p[1]}"
        except: continue
        try:
            conn.execute("""INSERT OR REPLACE INTO registros_bce_empleo
                (serie_id, nombre_region, indicador, unidad, periodo, valor)
                VALUES (?,?,?,?,?,?)""",
                (serie_id, region, indicador, unidad, periodo, val))
            n += 1
        except: pass
    conn.commit()
    return n

def actualizar_empleo(conn, user, pwd):
    ultimo = ultimo_periodo_empleo(conn)
    # Convertir 2026-02 → 2026-02-01 para firstdate
    anio, mes = ultimo.split("-")
    # Pedir desde el mes siguiente al último
    mes_sig = int(mes) + 1
    anio_sig = int(anio)
    if mes_sig > 12:
        mes_sig = 1
        anio_sig += 1
    firstdate = f"{anio_sig}-{mes_sig:02d}-01"

    log.info(f"BCE Empleo: último período en DB = {ultimo}, descargando desde {firstdate}")

    total = 0
    for cod, region in REGIONES_BCE.items():
        for tipo, unidad, ind in [
            ("DES.TAS", "Porcentaje", "Tasa de desocupación"),
            ("OCU.PMT", "Miles de personas", "Ocupados"),
        ]:
            serie_id = f"F049.{tipo}.INE9.{cod}.M"
            obs = get_serie_bce(user, pwd, serie_id, firstdate)
            if obs:
                n = guardar_empleo(conn, serie_id, region, ind, unidad, obs)
                total += n
                if n > 0:
                    log.info(f"  ✓ {region} — {ind}: {n} nuevos períodos")
            time.sleep(0.2)

    log.info(f"BCE Empleo: {total} registros nuevos")
    return total

# ══════════════════════════════════════════════════════════════════════════════
# LEYSTOP — solo semanas nuevas
# ══════════════════════════════════════════════════════════════════════════════
REGIONES_LS = {
    1:"Tarapacá",2:"Antofagasta",3:"Atacama",4:"Coquimbo",
    5:"Valparaíso",6:"O'Higgins",7:"Maule",8:"Biobío",
    9:"La Araucanía",10:"Los Lagos",11:"Aysén",12:"Magallanes",
    13:"Metropolitana de Santiago",14:"Los Ríos",15:"Arica y Parinacota",16:"Ñuble",
}

def ultimo_id_semana(conn=None):
    """Retorna el último id_semana en la DB local o en Supabase."""
    if conn is not None:
        r = conn.execute("SELECT MAX(id_semana) FROM registros_leystop").fetchone()
        return r[0] if r and r[0] else 159
    # Sin DB local (GitHub Actions) → consultar Supabase
    creds = leer_creds()
    url = creds.get("SUPABASE_URL", "")
    key = creds.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return 159
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(
            f"{url}/rest/v1/registros_leystop",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "id_semana", "order": "id_semana.desc", "limit": "1"},
            timeout=15, verify=False,
        )
        data = r.json()
        if data and data[0].get("id_semana"):
            return data[0]["id_semana"]
    except Exception as e:
        log.warning(f"Supabase ultimo_id_semana: {e}")
    return 159

def crear_sesion_ls():
    from urllib.parse import unquote
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-US,es-419;q=0.9,es;q=0.8",
        "Referer": "https://leystop.carabineros.cl/estadistica",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    })
    r = s.get(f"{BASE_URL_LS}/estadistica", timeout=30, verify=False)
    xsrf = s.cookies.get("XSRF-TOKEN", "")
    if xsrf:
        from urllib.parse import unquote
        s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
    return s

def get_semanas_ls(s):
    try:
        r = s.get(f"{BASE_URL_LS}/estadistica", timeout=30, verify=False)
        from urllib.parse import unquote
        xsrf = s.cookies.get("XSRF-TOKEN", "")
        if xsrf:
            s.headers["X-XSRF-TOKEN"] = unquote(xsrf)
        r2 = s.get(f"{BASE_URL_LS}/api/semanas", timeout=30, verify=False)
        if r2.status_code == 200:
            return r2.json()
    except Exception as e:
        log.error(f"LeyStop semanas: {e}")
    return []

def parsear_ls(data, id_semana, sem_info, id_region):
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
        "id_region": id_region, "nombre_region": REGIONES_LS.get(id_region, str(id_region)),
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

def guardar_ls(conn, reg):
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
        log.warning(f"Insert LS: {e}")
        return False

def actualizar_leystop(conn):
    ultimo = ultimo_id_semana(conn)
    log.info(f"LeyStop: último id_semana en DB = {ultimo}")

    s = crear_sesion_ls()
    semanas = get_semanas_ls(s)
    if not semanas:
        log.warning("LeyStop: no se pudieron obtener semanas")
        return 0

    # Guardar catálogo de semanas
    for x in semanas:
        conn.execute("""INSERT OR REPLACE INTO leystop_semanas
            (id,nombre,anno,semana,fecha_desde,fecha_hasta,fecha_desde_iso,fecha_hasta_iso)
            VALUES (?,?,?,?,?,?,?,?)""",
            (x["id"],x.get("nombre"),x.get("anno"),x.get("semana"),
             x.get("fecha_desde"),x.get("fecha_hasta"),
             x.get("fecha_desde_iso"),x.get("fecha_hasta_iso")))
    conn.commit()

    # Solo semanas nuevas (mayores al último id en DB)
    nuevas = sorted([s for s in semanas if s["id"] > ultimo], key=lambda x: x["id"])

    if not nuevas:
        log.info("LeyStop: no hay semanas nuevas")
        return 0

    log.info(f"LeyStop: {len(nuevas)} semanas nuevas a descargar ({nuevas[0]['id']}→{nuevas[-1]['id']})")

    total = 0
    for i, sem in enumerate(nuevas):
        n_sem = 0
        # Renovar sesión antes de cada semana
        s2 = crear_sesion_ls()
        for id_reg in REGIONES_LS:
            url = f"{BASE_URL_LS}/api/estadistica/{sem['id']}/REGION/{id_reg}"
            try:
                r = s2.get(url, timeout=30, verify=False)
                if r.status_code == 200:
                    ct = r.headers.get("Content-Type","")
                    if "json" in ct or r.text.strip().startswith("{"):
                        data = r.json()
                        reg = parsear_ls(data, sem["id"], sem, id_reg)
                        if reg and guardar_ls(conn, reg):
                            n_sem += 1
            except Exception as e:
                log.warning(f"  Error {url}: {e}")
            time.sleep(1.5)  # Pausa conservadora para no ser baneado

        total += n_sem
        log.info(f"  [{i+1}/{len(nuevas)}] {sem.get('nombre')} → {n_sem}/16 regiones")
        time.sleep(2)  # Pausa entre semanas

    log.info(f"LeyStop: {total} registros nuevos")
    return total

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    log.info("=" * 50)
    log.info(f"Actualizador inteligente — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)

    creds = leer_creds()
    bde_user = creds.get("BDE_USER", "")
    bde_pass = creds.get("BDE_PASS", "")
    supa_url = creds.get("SUPABASE_URL", "")
    supa_key = creds.get("SUPABASE_SERVICE_KEY", "")

    if not bde_user:
        log.error("Sin credenciales BCE en .env")
        return

    # Detectar si hay DB local o si corremos en GitHub Actions (nube)
    db_existe = Path(DB_PATH).exists()
    if db_existe:
        conn = sqlite3.connect(DB_PATH)
        log.info("Modo local (SQLite disponible)")
    else:
        # GitHub Actions: crear DB temporal con las tablas mínimas necesarias
        log.info("Modo nube (sin SQLite local) — creando DB temporal en memoria")
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS registros_bce_empleo (
                serie_id TEXT, nombre_region TEXT, indicador TEXT,
                unidad TEXT, periodo TEXT, valor REAL,
                PRIMARY KEY (serie_id, periodo)
            );
            CREATE TABLE IF NOT EXISTS registros_leystop (
                id_semana INTEGER, id_region INTEGER, nombre_region TEXT,
                semana INTEGER, fecha_desde_iso TEXT, fecha_hasta_iso TEXT, anno INTEGER,
                tasa_registro REAL, casos_total INTEGER, casos_anno_fecha INTEGER,
                casos_anno_fecha_anterior INTEGER, var_anno_fecha REAL,
                var_ultima_semana REAL, var_28dias REAL,
                casos_ultima_semana INTEGER, casos_28dias INTEGER,
                mayor_registro_1 TEXT, pct_1 REAL, mayor_registro_2 TEXT, pct_2 REAL,
                mayor_registro_3 TEXT, pct_3 REAL, mayor_registro_4 TEXT, pct_4 REAL,
                mayor_registro_5 TEXT, pct_5 REAL,
                controles INTEGER, controles_identidad INTEGER, controles_vehicular INTEGER,
                fiscalizaciones INTEGER, fiscal_alcohol INTEGER, fiscal_bancaria INTEGER,
                incautaciones INTEGER, incaut_fuego INTEGER, incaut_blancas INTEGER,
                decomisos_ultima_semana REAL, decomisos_anno REAL,
                allanamientos_ultima_semana INTEGER, allanamientos_anno INTEGER,
                vehiculos_recuperados_semana INTEGER, vehiculos_recuperados_anno INTEGER, raw TEXT,
                PRIMARY KEY (id_semana, id_region)
            );
            CREATE TABLE IF NOT EXISTS leystop_semanas (
                id INTEGER PRIMARY KEY, nombre TEXT, anno INTEGER, semana INTEGER,
                fecha_desde TEXT, fecha_hasta TEXT, fecha_desde_iso TEXT, fecha_hasta_iso TEXT
            );
        """)

    total_nuevos = 0

    # Capturar estado ANTES de actualizar
    # Si es DB temporal (nube), consulta Supabase para saber desde dónde continuar
    if db_existe:
        periodo_antes   = ultimo_periodo_empleo(conn)
        id_semana_antes = ultimo_id_semana(conn)
    else:
        periodo_antes   = ultimo_periodo_empleo()   # consulta Supabase
        id_semana_antes = ultimo_id_semana()        # consulta Supabase
        log.info(f"  Último período empleo en Supabase: {periodo_antes}")
        log.info(f"  Último id_semana en Supabase: {id_semana_antes}")

    # ── BCE Empleo ────────────────────────────────────────────────────────────────────────
    log.info("\n── BCE Empleo Regional ──")
    try:
        n = actualizar_empleo(conn, bde_user, bde_pass)
        total_nuevos += n
    except Exception as e:
        log.error(f"Error BCE: {e}")

    # ── LeyStop ────────────────────────────────────────────────────────────────────────────
    log.info("\n── LeyStop Seguridad ──")
    try:
        n = actualizar_leystop(conn)
        total_nuevos += n
    except Exception as e:
        log.error(f"Error LeyStop: {e}")

    # ── Supabase — sincronizacion incremental ──────────────────────────────────────
    if total_nuevos > 0 and supa_url and supa_key:
        log.info("\n── Sincronizando Supabase ──")
        try:
            import urllib3; urllib3.disable_warnings()
            sb = SupaREST(supa_url, supa_key)
            sync_empleo_supabase(sb, conn, periodo_antes)
            sync_leystop_supabase(sb, conn, id_semana_antes)
            log.info("✓ Supabase sincronizado")
        except Exception as e:
            log.error(f"Error Supabase: {e}")
    elif total_nuevos > 0:
        log.warning("Sin credenciales Supabase en .env — datos NO sincronizados")

    if conn is not None:
        conn.close()

    # ── Resultado ───────────────────────────────────────────────────────────────────────
    log.info(f'\n{"="*50}')
    log.info(f"Total registros nuevos: {total_nuevos}")
    if total_nuevos > 0:
        log.info("✓ SQLite + Supabase actualizados. El dashboard refleja los cambios de inmediato.")
    else:
        log.info("Sin datos nuevos")
    log.info("=" * 50)

if __name__ == "__main__":
    main()
