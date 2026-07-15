import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
"""
Actualizador inteligente de datos
===================================
Lógica:
  - BCE Empleo: descarga solo desde el último período disponible en DB
  - LeyStop: descarga solo desde el último id_semana disponible en DB + 1
  - Delitos (registros_leystop_delitos): mismas semanas nuevas que LeyStop,
    reutilizando el array "registros" que ya trae la misma respuesta
  - Si no hay datos nuevos, no hace nada
  - Al final regenera el dashboard y sube a GitHub

Uso: python actualizar_datos.py
"""

import sqlite3, requests, json, time, logging, subprocess, hashlib, math, unicodedata, re
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
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        # on_conflict es un query param de PostgREST, NO va en el header Prefer.
        # Bug real: con on_conflict en Prefer, PostgREST no sabe qué constraint usar
        # para el ON CONFLICT y cae a un INSERT plano -> 409 "duplicate key" apenas
        # se reenvía una fila que ya existe (pasó desapercibido en empleo/leystop/
        # delitos porque esos syncs solo mandan filas genuinamente nuevas; BCE
        # reenvía historial completo de las series pendientes y sí choca).
        url = f"{self.base}/{tabla}"
        if on_conflict:
            url += f"?on_conflict={on_conflict}"
        r = requests.post(
            url,
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

def sync_delitos_supabase(sb, conn, desde_id_semana):
    cursor = conn.execute("""
        SELECT id_semana, id_region, nombre_region, nombre_delito, es_dmcs,
               ultima_semana_ant, ultima_semana, dias28_ant, dias28,
               anno_fecha_ant, anno_fecha, umbral
        FROM registros_leystop_delitos WHERE id_semana >= ?
        ORDER BY id_semana, id_region
    """, (desde_id_semana,))
    cols = [d[0] for d in cursor.description]
    rows = [clean_supa(dict(zip(cols, r))) for r in cursor.fetchall()]
    if not rows:
        log.info("  Supabase delitos: sin filas nuevas"); return 0
    if sb.upsert("registros_leystop_delitos", rows, on_conflict="id_semana,id_region,nombre_delito"):
        log.info(f"  Supabase delitos: ✓ {len(rows)} filas"); return len(rows)
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
# BCE CATÁLOGO + PIB REGIONAL — solo series con ultima_obs nueva
# ══════════════════════════════════════════════════════════════════════════════
FRECUENCIAS_BCE = ["QUARTERLY", "ANNUAL", "MONTHLY"]

PALABRAS_REGIONALES = [
    "región", "region", "regional",
    "arica", "tarapacá", "antofagasta", "atacama", "coquimbo",
    "valparaíso", "metropolitana", "o'higgins", "ohiggins",
    "maule", "ñuble", "biobío", "biobio", "araucanía", "araucania",
    "los ríos", "los rios", "los lagos", "aysén", "aysen", "magallanes",
]

def es_serie_regional(titulo):
    t = str(titulo).lower()
    return any(p in t for p in PALABRAS_REGIONALES)

def buscar_series_frecuencia(user, pwd, frecuencia):
    """Descarga el catálogo completo de una frecuencia via SearchSeries."""
    try:
        r = requests.get(BASE_URL_BCE, params={
            "user": user, "pass": pwd,
            "function": "SearchSeries", "frequency": frecuencia,
        }, timeout=60)
        data = r.json()
        if data is None or data.get("Codigo") != 0:
            log.warning(f"BCE catálogo [{frecuencia}]: {data.get('Descripcion') if data else 'null'}")
            return []
        return data.get("SeriesInfos", [])
    except Exception as e:
        log.warning(f"BCE catálogo [{frecuencia}]: {e}")
        return []

# Mapeo de nombres de región para estandarizar (títulos BCE)
REGION_MAP = {
    "metropolitana de santiago":        "Metropolitana de Santiago",
    "región metropolitana de santiago": "Metropolitana de Santiago",
    "region metropolitana de santiago": "Metropolitana de Santiago",
    "región metropolitana":             "Metropolitana de Santiago",
    "rm":                               "Metropolitana de Santiago",
    "arica y parinacota":               "Arica y Parinacota",
    "region of arica and parinacota":   "Arica y Parinacota",
    "tarapacá":                         "Tarapacá",
    "tarapaca":                         "Tarapacá",
    "antofagasta":                      "Antofagasta",
    "atacama":                          "Atacama",
    "coquimbo":                         "Coquimbo",
    "valparaíso":                       "Valparaíso",
    "valparaiso":                       "Valparaíso",
    "libertador general bernardo o`higgins": "O'Higgins",
    "libertador general bernardo ohiggins":  "O'Higgins",
    "libertador gral. bernardo o'higgins":   "O'Higgins",
    "libertador bernardo o'higgins":         "O'Higgins",
    "o'higgins":                        "O'Higgins",
    "ohiggins":                         "O'Higgins",
    "maule":                            "Maule",
    "ñuble":                            "Ñuble",
    "nuble":                            "Ñuble",
    "biobío":                           "Biobío",
    "biobio":                           "Biobío",
    "la araucanía":                     "La Araucanía",
    "la araucania":                     "La Araucanía",
    "araucanía":                        "La Araucanía",
    "los ríos":                         "Los Ríos",
    "los rios":                         "Los Ríos",
    "los lagos":                        "Los Lagos",
    "aysén del general carlos ibáñez del campo": "Aysén",
    "aysén del gral. carlos ibáñez del campo":   "Aysén",
    "aysén":                            "Aysén",
    "aysen":                            "Aysén",
    "magallanes y de la antártica chilena": "Magallanes",
    "magallanes y antártica chilena":    "Magallanes",
    "magallanes":                       "Magallanes",
    "xv región":                        "Arica y Parinacota",
    "xiv región  de los ríos":          "Los Ríos",
    "xiv región":                       "Los Ríos",
    "xii región":                       "Magallanes",
    "xi región":                        "Aysén",
    "x región":                         "Los Lagos",
    "ix región":                        "La Araucanía",
    "viii región":                      "Biobío",
    "vii región":                       "Maule",
    "vi región":                        "O'Higgins",
    "v región":                         "Valparaíso",
    "iv región":                        "Coquimbo",
    "iii región":                       "Atacama",
    "ii región":                        "Antofagasta",
    "i región":                         "Tarapacá",
    "rm región":                        "Metropolitana de Santiago",
}
REGIONES_LISTA_BCE = list(REGION_MAP.keys())

def normalizar_region(texto):
    t = texto.lower()
    for patron in sorted(REGIONES_LISTA_BCE, key=len, reverse=True):
        if patron in t:
            return REGION_MAP[patron]
    return None

def limpiar_titulo_bce(titulo):
    """Extrae (indicador, region, unidad) de un título BCE. Ver limpiar_datos.py."""
    if not titulo:
        return None, None, None
    t = str(titulo).strip()

    es_corriente = bool(re.search(r'precios corrientes', t, re.IGNORECASE))
    base_año = None
    match_base = re.search(r'base\s+(\d{4})', t, re.IGNORECASE)
    if match_base:
        base_año = match_base.group(1)

    unidad = None
    match_unidad = re.search(r'\(([^)]+)\)\s*$', t)
    if match_unidad:
        unidad = match_unidad.group(1).strip()
        t = t[:match_unidad.start()].strip().rstrip(',').strip()

    if es_corriente:
        if base_año:
            unidad = f"miles de millones de pesos corrientes (base {base_año})"
        else:
            unidad = "miles de millones de pesos corrientes"

    t = re.sub(r',?\s*referencia\s+\d{4}', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*base\s+\d{4}', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*BCCh?$', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*serie\s+\w+$', '', t, flags=re.IGNORECASE)
    t = t.strip().rstrip(',').strip()

    region = normalizar_region(t)

    indicador = t
    if region:
        for patron in sorted(REGIONES_LISTA_BCE, key=len, reverse=True):
            if REGION_MAP.get(patron) == region:
                for prefijo in ["región de ", "región del ", "región ", "region de ", "region del ", "region "]:
                    indicador = re.sub(re.escape(prefijo + patron), '', indicador, flags=re.IGNORECASE)
                indicador = re.sub(re.escape(patron), '', indicador, flags=re.IGNORECASE)

    indicador = re.sub(r',\s*,', ',', indicador)
    indicador = indicador.strip().strip(',').strip()
    partes = [p.strip() for p in indicador.split(',') if p.strip()]
    partes_limpias = []
    for p in partes:
        p_lower = p.lower()
        if any(x in p_lower for x in [
            'volumen a precios', 'contribución porcentual', 'precios corrientes',
            'precios constantes', 'encadenado', 'porcentual respecto',
            'igual periodo', 'año anterior'
        ]):
            continue
        partes_limpias.append(p)

    indicador = ', '.join(partes_limpias) if partes_limpias else (partes[0] if partes else t)
    indicador = indicador.strip().strip(',').strip()

    return indicador, region, unidad

def corregir_valor_bce(valor, unidad):
    """Porcentaje: el punto ya es decimal. Otros: el punto era separador de miles."""
    if valor is None:
        return valor
    if unidad and 'porcentaje' in str(unidad).lower():
        return valor
    val_str = str(valor)
    if '.' in val_str:
        decimales = val_str.split('.')[1]
        if len(decimales) == 3:
            return valor * 1000
    return valor

def construir_filas_bce(series_id, titulo, obs_list):
    indicador, region, unidad = limpiar_titulo_bce(titulo)
    filas = []
    for o in obs_list:
        if o.get("statusCode") != "OK":
            continue
        val_str = str(o.get("value", "")).replace(",", ".")
        if not val_str or val_str == "NaN":
            continue
        try:
            valor = float(val_str)
        except ValueError:
            continue
        periodo = o.get("indexDateString", "")
        if not periodo:
            continue
        filas.append({
            "series_id": series_id,
            "nombre_region": region,
            "indicador_limpio": indicador,
            "unidad_limpia": unidad,
            "periodo": periodo,
            "valor_corregido": corregir_valor_bce(valor, unidad),
        })
    return filas

def obtener_catalogo_supabase(supa_url, supa_key):
    """Trae {series_id: ultima_obs} actual desde Supabase (paginado) para detectar cambios."""
    catalogo = {}
    if not supa_url or not supa_key:
        return catalogo
    try:
        import urllib3; urllib3.disable_warnings()
        offset, page = 0, 1000
        while True:
            r = requests.get(
                f"{supa_url}/rest/v1/bce_catalogo",
                headers={
                    "apikey": supa_key, "Authorization": f"Bearer {supa_key}",
                    "Range-Unit": "items", "Range": f"{offset}-{offset+page-1}",
                },
                params={"select": "series_id,ultima_obs"},
                timeout=30, verify=False,
            )
            if r.status_code not in (200, 206):
                log.warning(f"  Supabase bce_catalogo GET: HTTP {r.status_code}")
                break
            data = r.json()
            for row in data:
                catalogo[row["series_id"]] = row.get("ultima_obs")
            if len(data) < page:
                break
            offset += page
    except Exception as e:
        log.warning(f"Supabase obtener_catalogo_supabase: {e}")
    return catalogo

def _guardar_bce_catalogo_local(conn, filas):
    for fila in filas:
        conn.execute("""INSERT OR REPLACE INTO bce_catalogo
            (series_id, frecuencia, titulo_esp, primera_obs, ultima_obs, actualizado, es_regional, fecha_catalogo)
            VALUES (?,?,?,?,?,?,?,?)""",
            (fila["series_id"], fila["frecuencia"], fila["titulo_esp"], fila["primera_obs"],
             fila["ultima_obs"], fila["actualizado"], fila["es_regional"], fila["fecha_catalogo"]))
    conn.commit()

def _guardar_bce_datos_local(conn, filas):
    for fila in filas:
        conn.execute("""INSERT OR REPLACE INTO registros_bce
            (series_id, nombre_region, indicador_limpio, unidad_limpia, periodo, valor_corregido)
            VALUES (?,?,?,?,?,?)""",
            (fila["series_id"], fila["nombre_region"], fila["indicador_limpio"],
             fila["unidad_limpia"], fila["periodo"], fila["valor_corregido"]))
    conn.commit()

def actualizar_bce(conn, user, pwd, supa_url, supa_key, sb):
    """
    Refresca bce_catalogo completo (barato: 3 requests) y descarga con GetSeries
    SOLO las series cuyo ultima_obs cambió respecto a lo que ya hay en Supabase
    (serie nueva o con dato más reciente). Evita revisar las ~3.655 series enteras
    en cada corrida.

    IMPORTANTE — resumable: bce_catalogo (con el ultima_obs nuevo) y registros_bce
    de una serie se sincronizan a Supabase JUNTOS, por lotes, durante el loop —
    no al final. Si el job se corta a mitad de camino (backlog inicial grande,
    puede superar el timeout), lo ya sincronizado no se pierde y esa serie deja
    de aparecer como "pendiente" — la siguiente corrida retoma justo donde quedó,
    usando el propio catálogo como cursor de resume (sin estado adicional).
    """
    log.info("BCE: consultando catálogo actual en Supabase para detectar cambios...")
    catalogo_viejo = obtener_catalogo_supabase(supa_url, supa_key)
    log.info(f"  {len(catalogo_viejo)} series ya conocidas en Supabase")

    fecha = datetime.now().isoformat(timespec="seconds")
    catalogo_estable = []  # ultima_obs sin cambios -> se puede subir de inmediato, sin riesgo
    pendientes = []        # (series_id, titulo, fila_catalogo) con dato nuevo o serie nueva

    for freq in FRECUENCIAS_BCE:
        log.info(f"  Buscando series {freq}...")
        series = buscar_series_frecuencia(user, pwd, freq)
        regionales = [s for s in series if es_serie_regional(s.get("spanishTitle", ""))]
        log.info(f"    {len(regionales)}/{len(series)} series regionales")
        for s in regionales:
            sid = s.get("seriesId")
            ultima_obs = s.get("lastObservation")
            fila = {
                "series_id": sid, "frecuencia": s.get("frequencyCode"),
                "titulo_esp": s.get("spanishTitle"), "primera_obs": s.get("firstObservation"),
                "ultima_obs": ultima_obs, "actualizado": s.get("updatedAt"),
                "es_regional": 1, "fecha_catalogo": fecha,
            }
            if sid not in catalogo_viejo or catalogo_viejo.get(sid) != ultima_obs:
                pendientes.append((sid, s.get("spanishTitle", ""), fila))
            else:
                catalogo_estable.append(fila)
        time.sleep(1)

    log.info(f"BCE Catálogo: {len(catalogo_estable) + len(pendientes)} series regionales, {len(pendientes)} con dato nuevo o serie nueva")

    # Las que no cambiaron: guardar y sincronizar ya (idempotente, sin riesgo de
    # marcar como "al día" algo que no se descargó).
    _guardar_bce_catalogo_local(conn, catalogo_estable)
    if sb and catalogo_estable:
        sync_bce_catalogo_supabase(sb, catalogo_estable)

    total_filas = 0
    LOTE = 100
    lote_catalogo, lote_filas = [], []

    for i, (sid, titulo, fila_cat) in enumerate(pendientes):
        obs = get_serie_bce(user, pwd, sid, "2010-01-01")
        filas = construir_filas_bce(sid, titulo, obs) if obs else []

        if filas:
            _guardar_bce_datos_local(conn, filas)
            total_filas += len(filas)
            lote_filas.extend(filas)
        _guardar_bce_catalogo_local(conn, [fila_cat])
        lote_catalogo.append(fila_cat)

        ultimo = (i == len(pendientes) - 1)
        if sb and ((i + 1) % LOTE == 0 or ultimo):
            sync_bce_datos_supabase(sb, lote_filas)
            sync_bce_catalogo_supabase(sb, lote_catalogo)
            log.info(f"  [{i+1}/{len(pendientes)}] lote sincronizado a Supabase ({len(lote_filas)} filas)")
            lote_filas, lote_catalogo = [], []

        time.sleep(0.3)  # límite BDE: 5 req/seg

    log.info(f"BCE: {total_filas} registros nuevos/actualizados, {len(pendientes)} series revisadas")
    return total_filas

def sync_bce_catalogo_supabase(sb, catalogo_nuevo):
    if not catalogo_nuevo:
        log.info("  Supabase catálogo BCE: sin filas"); return 0
    rows = [clean_supa(f) for f in catalogo_nuevo]
    ok_total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        if sb.upsert("bce_catalogo", batch, on_conflict="series_id"):
            ok_total += len(batch)
    log.info(f"  Supabase catálogo BCE: ✓ {ok_total} filas")
    return ok_total

def sync_bce_datos_supabase(sb, filas_bce):
    if not filas_bce:
        log.info("  Supabase BCE: sin filas nuevas"); return 0
    rows = [clean_supa(f) for f in filas_bce]
    ok_total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        if sb.upsert("registros_bce", batch, on_conflict="series_id,periodo"):
            ok_total += len(batch)
    log.info(f"  Supabase BCE: ✓ {ok_total} filas")
    return ok_total

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

def ultimo_id_semana_delitos(conn=None):
    """Retorna el último id_semana en registros_leystop_delitos (DB local o Supabase)."""
    if conn is not None:
        r = conn.execute("SELECT MAX(id_semana) FROM registros_leystop_delitos").fetchone()
        return r[0] if r and r[0] else 159
    creds = leer_creds()
    url = creds.get("SUPABASE_URL", "")
    key = creds.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return 159
    try:
        import urllib3; urllib3.disable_warnings()
        r = requests.get(
            f"{url}/rest/v1/registros_leystop_delitos",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "id_semana", "order": "id_semana.desc", "limit": "1"},
            timeout=15, verify=False,
        )
        data = r.json()
        if data and data[0].get("id_semana"):
            return data[0]["id_semana"]
    except Exception as e:
        log.warning(f"Supabase ultimo_id_semana_delitos: {e}")
    return 159

def guardar_delitos(conn, sem, id_region, registros):
    """Guarda el array registros[] (desglose por tipo de delito) para una semana/región."""
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
            log.warning(f"    Insert delito {nombre}: {e}")
    conn.commit()
    return n

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
    ultimo_delitos = ultimo_id_semana_delitos(conn)
    log.info(f"LeyStop: último id_semana en DB = {ultimo}")
    log.info(f"Delitos: último id_semana en DB = {ultimo_delitos}")

    s = crear_sesion_ls()
    semanas = get_semanas_ls(s)
    if not semanas:
        log.warning("LeyStop: no se pudieron obtener semanas")
        return 0, 0, []

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
        return 0, 0, []

    log.info(f"LeyStop: {len(nuevas)} semanas nuevas a descargar ({nuevas[0]['id']}→{nuevas[-1]['id']})")

    total = 0
    total_delitos = 0
    for i, sem in enumerate(nuevas):
        n_sem = 0
        n_sem_delitos = 0
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
                        # Delitos: mismo request, solo si es semana nueva para esa tabla
                        if sem["id"] > ultimo_delitos:
                            arr = data.get("registros", [])
                            if arr:
                                n_sem_delitos += guardar_delitos(conn, sem, id_reg, arr)
            except Exception as e:
                log.warning(f"  Error {url}: {e}")
            time.sleep(1.5)  # Pausa conservadora para no ser baneado

        total += n_sem
        total_delitos += n_sem_delitos
        log.info(f"  [{i+1}/{len(nuevas)}] {sem.get('nombre')} → {n_sem}/16 regiones, {n_sem_delitos} delitos")
        time.sleep(2)  # Pausa entre semanas

    log.info(f"LeyStop: {total} registros nuevos")
    log.info(f"Delitos: {total_delitos} registros nuevos")
    return total, total_delitos, nuevas

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

    # Estas tablas son mas nuevas que bcn_indicadores.db y pueden faltar tanto en
    # modo nube como en el .db committeado al repo (ej: registros_leystop_delitos
    # solo la crea cargar_historico_delitos.py, corrido a mano en otra copia local).
    # IF NOT EXISTS es no-op si la tabla ya existe con datos.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS registros_leystop_delitos (
            id_semana INTEGER, anno INTEGER, semana TEXT,
            fecha_desde_iso TEXT, fecha_hasta_iso TEXT,
            id_region INTEGER, nombre_region TEXT, nombre_delito TEXT, es_dmcs INTEGER DEFAULT 0,
            ultima_semana_ant INTEGER, ultima_semana INTEGER,
            dias28_ant INTEGER, dias28 INTEGER,
            anno_fecha_ant INTEGER, anno_fecha INTEGER, umbral REAL,
            PRIMARY KEY (id_semana, id_region, nombre_delito)
        );
        CREATE TABLE IF NOT EXISTS bce_catalogo (
            series_id TEXT PRIMARY KEY, frecuencia TEXT, titulo_esp TEXT,
            primera_obs TEXT, ultima_obs TEXT, actualizado TEXT,
            es_regional INTEGER DEFAULT 1, fecha_catalogo TEXT
        );
        CREATE TABLE IF NOT EXISTS registros_bce (
            series_id TEXT, nombre_region TEXT, indicador_limpio TEXT,
            unidad_limpia TEXT, periodo TEXT, valor_corregido REAL,
            PRIMARY KEY (series_id, periodo)
        );
    """)
    conn.commit()

    total_nuevos = 0

    # Capturar estado ANTES de actualizar
    # Si es DB temporal (nube), consulta Supabase para saber desde dónde continuar
    if db_existe:
        periodo_antes        = ultimo_periodo_empleo(conn)
        id_semana_antes      = ultimo_id_semana(conn)
        id_semana_del_antes  = ultimo_id_semana_delitos(conn)
    else:
        periodo_antes        = ultimo_periodo_empleo()          # consulta Supabase
        id_semana_antes      = ultimo_id_semana()               # consulta Supabase
        id_semana_del_antes  = ultimo_id_semana_delitos()       # consulta Supabase
        log.info(f"  Último período empleo en Supabase: {periodo_antes}")
        log.info(f"  Último id_semana en Supabase: {id_semana_antes}")
        log.info(f"  Último id_semana delitos en Supabase: {id_semana_del_antes}")

    # ── BCE Empleo ────────────────────────────────────────────────────────────────────────
    log.info("\n── BCE Empleo Regional ──")
    try:
        n = actualizar_empleo(conn, bde_user, bde_pass)
        total_nuevos += n
    except Exception as e:
        log.error(f"Error BCE: {e}")

    # ── LeyStop + Delitos ─────────────────────────────────────────────────────────────────
    log.info("\n── LeyStop Seguridad ──")
    try:
        n, n_delitos, _nuevas = actualizar_leystop(conn)
        total_nuevos += n + n_delitos
    except Exception as e:
        log.error(f"Error LeyStop: {e}")

    # sb se crea temprano porque actualizar_bce() sincroniza por lotes durante el
    # loop (no al final) -- si el backlog inicial es grande y el job se corta por
    # timeout, lo ya sincronizado no se pierde.
    import urllib3; urllib3.disable_warnings()
    sb = SupaREST(supa_url, supa_key) if (supa_url and supa_key) else None
    if not sb:
        log.warning("Sin credenciales Supabase en .env — datos NO se sincronizarán")

    # ── BCE Catálogo + PIB Regional ──────────────────────────────────────────────────────
    log.info("\n── BCE Catálogo + Series Regionales ──")
    try:
        n_bce = actualizar_bce(conn, bde_user, bde_pass, supa_url, supa_key, sb)
        total_nuevos += n_bce
    except Exception as e:
        log.error(f"Error BCE catálogo/series: {e}")

    # ── Supabase — empleo/leystop/delitos (BCE ya se sincronizó por lotes arriba) ────
    if total_nuevos > 0 and sb:
        log.info("\n── Sincronizando Supabase (empleo / leystop / delitos) ──")
        try:
            sync_empleo_supabase(sb, conn, periodo_antes)
            sync_leystop_supabase(sb, conn, id_semana_antes)
            sync_delitos_supabase(sb, conn, id_semana_del_antes)
            log.info("✓ Supabase sincronizado")
        except Exception as e:
            log.error(f"Error Supabase: {e}")

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
