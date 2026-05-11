"""
migrate_to_supabase.py
======================
Migra todos los datos históricos desde SQLite (bcn_indicadores.db)
hacia Supabase via API REST.

Solo usa librerías ya instaladas: requests, sqlite3, json, pathlib.
NO requiere instalar el SDK de supabase.

Variables en .env:
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY=sb_secret_...   ← service_role key

Uso:
    python migrate_to_supabase.py
    python migrate_to_supabase.py --tabla empleo   # solo una tabla
    python migrate_to_supabase.py --dry-run        # sin escribir nada
"""

import sqlite3, requests, json, math, sys, argparse, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH    = "bcn_indicadores.db"
CASEN_PATH = "casen_regiones.json"
BATCH      = 200

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

class SupaREST:
    def __init__(self, url, service_key):
        self.base = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def upsert(self, tabla, rows):
        r = requests.post(
            f"{self.base}/{tabla}",
            headers=self.headers,
            data=json.dumps(rows, ensure_ascii=False, default=str),
            timeout=60,
            verify=False,
        )
        if r.status_code not in (200, 201):
            log.error(f"  HTTP {r.status_code} en {tabla}: {r.text[:300]}")
            return False
        return True

def clean_row(row):
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]

def migrate_table(sb, conn, sql, tabla, dry_run):
    cursor = conn.execute(sql)
    cols = [d[0] for d in cursor.description]
    rows = [clean_row(dict(zip(cols, r))) for r in cursor.fetchall()]
    log.info(f"  {tabla}: {len(rows)} filas")
    if dry_run or not rows:
        return len(rows)
    batches = list(chunks(rows, BATCH))
    ok = 0
    for i, batch in enumerate(batches):
        log.info(f"    batch {i+1}/{len(batches)} ({len(batch)} filas)...")
        if sb.upsert(tabla, batch):
            ok += len(batch)
        else:
            raise RuntimeError(f"Fallo en batch {i+1} de {tabla}")
    log.info(f"  ✓ {ok} filas insertadas")
    return ok

def migrate_casen(sb, dry_run):
    p = Path(CASEN_PATH)
    if not p.exists():
        log.warning(f"  No se encontró {CASEN_PATH} — saltando")
        return 0
    raw = json.loads(p.read_text(encoding="utf-8"))
    rows = []
    skip = {"años", "años_sal", "años_prob", "años_ges", "regiones"}
    for region, contenido in raw.items():
        if region in skip or not isinstance(contenido, dict):
            continue
        primera = next(iter(contenido.values()), None)
        if isinstance(primera, dict):
            for anno, datos in contenido.items():
                try:
                    rows.append({"region": region, "anno": int(anno), "datos": datos})
                except (ValueError, TypeError):
                    rows.append({"region": region, "anno": None, "datos": {anno: datos}})
        else:
            rows.append({"region": region, "anno": None, "datos": contenido})
    log.info(f"  casen_regiones: {len(rows)} filas")
    if dry_run or not rows:
        return len(rows)
    ok = 0
    for i, batch in enumerate(list(chunks(rows, BATCH))):
        batch_s = [{"region": r["region"], "anno": r["anno"], "datos": json.dumps(r["datos"], ensure_ascii=False)} for r in batch]
        log.info(f"    batch {i+1} ({len(batch)} filas)...")
        if sb.upsert("casen_regiones", batch_s):
            ok += len(batch)
        else:
            raise RuntimeError("Fallo en batch CASEN")
    log.info(f"  ✓ {ok} filas insertadas")
    return ok

MIGRACIONES = {
    "regiones":     ("SELECT cod_region, nombre FROM regiones", "regiones"),
    "bcn":          ("SELECT cod_region, nombre_region, anno, seccion, subtabla, indicador, nivel, valor, valor_texto, fuente, fecha_descarga FROM registros_bcn", "registros_bcn"),
    "bce_catalogo": ("SELECT series_id, frecuencia, titulo_esp, primera_obs, ultima_obs, actualizado, es_regional, fecha_catalogo FROM bce_catalogo", "bce_catalogo"),
    "pib":          ("SELECT series_id, nombre_region, indicador_limpio, unidad_limpia, periodo, valor_corregido FROM registros_bce ORDER BY nombre_region, periodo", "registros_bce"),
    "empleo":       ("SELECT serie_id, nombre_region, indicador, unidad, periodo, valor FROM registros_bce_empleo ORDER BY nombre_region, periodo", "registros_bce_empleo"),
    "semanas":      ("SELECT id, nombre, semana, anno, fecha_desde_iso, fecha_hasta_iso FROM leystop_semanas ORDER BY id", "leystop_semanas"),
    "leystop":      ("""SELECT id_semana, id_region, nombre_region, semana, fecha_desde_iso, fecha_hasta_iso, anno,
                         tasa_registro, casos_total, casos_anno_fecha, casos_anno_fecha_anterior, var_anno_fecha,
                         var_ultima_semana, var_28dias, casos_ultima_semana, casos_28dias,
                         mayor_registro_1, pct_1, mayor_registro_2, pct_2, mayor_registro_3, pct_3,
                         mayor_registro_4, pct_4, mayor_registro_5, pct_5,
                         controles, controles_identidad, controles_vehicular,
                         fiscalizaciones, fiscal_alcohol, fiscal_bancaria,
                         incautaciones, incaut_fuego, incaut_blancas,
                         allanamientos_anno, vehiculos_recuperados_anno, decomisos_anno
                         FROM registros_leystop ORDER BY id_semana, id_region""", "registros_leystop"),
    "delitos":      ("""SELECT id_semana, id_region, nombre_region, nombre_delito, es_dmcs,
                         ultima_semana_ant, ultima_semana, dias28_ant, dias28, anno_fecha_ant, anno_fecha, umbral
                         FROM registros_leystop_delitos ORDER BY id_semana, id_region""", "registros_leystop_delitos"),
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tabla", help="Migrar solo: " + "|".join(MIGRACIONES.keys()) + "|casen")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    creds = leer_creds()
    url = creds.get("SUPABASE_URL")
    key = creds.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en .env")
        sys.exit(1)

    import urllib3; urllib3.disable_warnings()

    sb   = SupaREST(url, key)
    conn = sqlite3.connect(DB_PATH)

    log.info(f"{'[DRY RUN] ' if args.dry_run else ''}Migrando {DB_PATH} → Supabase")

    total = 0
    for key in ["regiones", "bcn", "bce_catalogo", "pib", "empleo", "semanas", "leystop", "delitos"]:
        if args.tabla and args.tabla != key:
            continue
        sql, tabla_sb = MIGRACIONES[key]
        log.info(f"\n── {key.upper()} ──")
        try:
            total += migrate_table(sb, conn, sql, tabla_sb, args.dry_run)
        except sqlite3.OperationalError as e:
            log.warning(f"  Tabla no existe en SQLite ({e}) — saltando")
        except RuntimeError:
            log.error("  Abortando"); break

    conn.close()

    if not args.tabla or args.tabla == "casen":
        log.info("\n── CASEN ──")
        total += migrate_casen(sb, args.dry_run)

    log.info(f"\n{'='*50}")
    log.info(f"Total: {total} filas {'(dry run)' if args.dry_run else 'migradas'}")

if __name__ == "__main__":
    main()
