"""
sync_to_workos.py
=================
Sincroniza datos desde tu Supabase (fuente) al Supabase de Diego (Work-OS).

Transforma tus tablas al formato que espera el Work-OS:
  registros_bce_empleo  → regional_metrics  (tasa_desocupacion, pib_regional)
  registros_leystop     → security_weekly   (snapshot semanal por región)

NO modifica tus tablas. Solo lee de tu Supabase y escribe en el de Diego.

Uso:
    python sync_to_workos.py               # sync completo
    python sync_to_workos.py --tabla empleo
    python sync_to_workos.py --tabla leystop
    python sync_to_workos.py --dry-run
    python sync_to_workos.py --desde 2025-01-01   # solo desde esta fecha

Variables en .env:
    SUPABASE_URL          → tu Supabase (fuente)
    SUPABASE_SERVICE_KEY  → tu service role key
    WORKOS_SUPABASE_URL          → Supabase de Diego
    WORKOS_SUPABASE_SERVICE_KEY  → service role key de Diego
"""

import requests, json, math, sys, argparse, logging
from datetime import date, datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BATCH = 200

# ── Mapeo región: nombre → region_id numérico (INE_CODE de Diego) ─────────────
# Fuente: lib/regions.ts de Work-OS
REGION_ID = {
    "Tarapacá":                    1,
    "Antofagasta":                 2,
    "Atacama":                     3,
    "Coquimbo":                    4,
    "Valparaíso":                  5,
    "O'Higgins":                   6,
    "Maule":                       7,
    "Biobío":                      8,
    "La Araucanía":                9,
    "Los Lagos":                  10,
    "Aysén":                      11,
    "Magallanes":                 12,
    "Metropolitana de Santiago":  13,
    "Los Ríos":                   14,
    "Arica y Parinacota":         15,
    "Ñuble":                      16,
}

# ── Credenciales ─────────────────────────────────────────────────────────────
def leer_creds():
    from pathlib import Path
    creds = {}
    for fname in [".env", "env.local"]:
        p = Path(__file__).parent / fname
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
    return creds

# ── Cliente REST genérico ─────────────────────────────────────────────────────
class SupaREST:
    def __init__(self, url, key, nombre=""):
        self.base = url.rstrip("/") + "/rest/v1"
        self.nombre = nombre
        self.headers_read = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        self.headers_write = {
            **self.headers_read,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def select(self, tabla, params=""):
        url = f"{self.base}/{tabla}?{params}"
        r = requests.get(url, headers=self.headers_read, timeout=60, verify=False)
        if r.status_code != 200:
            log.error(f"[{self.nombre}] GET {tabla}: HTTP {r.status_code} — {r.text[:200]}")
            return []
        return r.json()

    def upsert(self, tabla, rows):
        r = requests.post(
            f"{self.base}/{tabla}",
            headers=self.headers_write,
            data=json.dumps(rows, ensure_ascii=False, default=str),
            timeout=60,
            verify=False,
        )
        if r.status_code not in (200, 201):
            log.error(f"[{self.nombre}] UPSERT {tabla}: HTTP {r.status_code} — {r.text[:300]}")
            return False
        return True

# ── Helpers ───────────────────────────────────────────────────────────────────
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]

def safe_float(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def periodo_a_date(periodo: str) -> str:
    """Convierte 'YYYY-MM' → 'YYYY-MM-01' (primer día del período)."""
    parts = periodo.split("-")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]}-01"
    return periodo

# ═════════════════════════════════════════════════════════════════════════════
# SYNC 1: Empleo (tasa_desocupacion) → regional_metrics
# ═════════════════════════════════════════════════════════════════════════════
def sync_empleo(src: SupaREST, dst: SupaREST, desde: str, dry_run: bool) -> int:
    """
    Lee registros_bce_empleo de tu Supabase.
    Escribe en regional_metrics de Diego con metric_name = 'tasa_desocupacion'.
    Solo sincroniza tasa de desocupación (no ocupados — Diego no usa ese campo).
    """
    log.info("  Leyendo empleo desde tu Supabase...")

    # Leer de fuente (paginado)
    registros = []
    offset = 0
    limit = 1000
    while True:
        params = (
            f"indicador=eq.Tasa de desocupación"
            f"&periodo=gte.{desde[:7]}"  # desde YYYY-MM
            f"&select=nombre_region,periodo,valor"
            f"&limit={limit}&offset={offset}"
        )
        batch = src.select("registros_bce_empleo", params)
        if not batch:
            break
        registros.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    log.info(f"  {len(registros)} registros de tasa_desocupacion")
    if not registros:
        return 0

    # Transformar al formato de Diego
    rows = []
    for r in registros:
        region_id = REGION_ID.get(r.get("nombre_region"))
        if region_id is None:
            log.warning(f"  Región no mapeada: {r.get('nombre_region')}")
            continue
        periodo = r.get("periodo", "")
        valor = safe_float(r.get("valor"))
        if valor is None:
            continue
        rows.append({
            "region_id":   region_id,
            "metric_name": "tasa_desocupacion",
            "value":       valor,
            "period":      periodo_a_date(periodo),
            "source_url":  "https://si3.bcentral.cl",
            "updated_at":  datetime.utcnow().isoformat(),
        })

    log.info(f"  → {len(rows)} filas a escribir en regional_metrics")
    if dry_run or not rows:
        return len(rows)

    ok = 0
    for i, batch in enumerate(list(chunks(rows, BATCH))):
        log.info(f"    batch {i+1}/{math.ceil(len(rows)/BATCH)}...")
        if dst.upsert("regional_metrics", batch):
            ok += len(batch)
        else:
            raise RuntimeError("Fallo upsert regional_metrics (empleo)")
    log.info(f"  ✓ {ok} filas sincronizadas")
    return ok

# ═════════════════════════════════════════════════════════════════════════════
# SYNC 2: PIB regional → regional_metrics
# ═════════════════════════════════════════════════════════════════════════════
def sync_pib(src: SupaREST, dst: SupaREST, desde: str, dry_run: bool) -> int:
    """
    Lee registros_bce de tu Supabase (PIB trimestral en miles MM CLP corrientes).
    Escribe en regional_metrics con metric_name = 'pib_regional'.
    Solo toma unidad 'Miles de millones de pesos encadenados volumen' o corrientes base 2018.
    """
    log.info("  Leyendo PIB desde tu Supabase...")

    registros = []
    offset = 0
    limit = 1000
    while True:
        params = (
            f"periodo=gte.{desde[:7]}"
            f"&select=nombre_region,periodo,valor_corregido,unidad_limpia"
            f"&limit={limit}&offset={offset}"
        )
        batch = src.select("registros_bce", params)
        if not batch:
            break
        registros.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    # Filtrar por unidad en Python (PostgREST no maneja bien paréntesis en eq.)
    registros = [r for r in registros if r.get("unidad_limpia","").lower().find("base 2018") >= 0]
    log.info(f"  {len(registros)} registros de pib_regional (base 2018)")
    if not registros:
        return 0

    rows = []
    for r in registros:
        region_id = REGION_ID.get(r.get("nombre_region"))
        if region_id is None:
            continue
        valor = safe_float(r.get("valor_corregido"))
        if valor is None:
            continue
        rows.append({
            "region_id":   region_id,
            "metric_name": "pib_regional",
            "value":       valor,
            "period":      periodo_a_date(r.get("periodo", "")),
            "source_url":  "https://si3.bcentral.cl",
            "updated_at":  datetime.utcnow().isoformat(),
        })

    log.info(f"  → {len(rows)} filas a escribir en regional_metrics (PIB)")
    if dry_run or not rows:
        return len(rows)

    ok = 0
    for i, batch in enumerate(list(chunks(rows, BATCH))):
        log.info(f"    batch {i+1}/{math.ceil(len(rows)/BATCH)}...")
        if dst.upsert("regional_metrics", batch):
            ok += len(batch)
        else:
            raise RuntimeError("Fallo upsert regional_metrics (PIB)")
    log.info(f"  ✓ {ok} filas sincronizadas")
    return ok

# ═════════════════════════════════════════════════════════════════════════════
# SYNC 3: LeyStop → security_weekly
# ═════════════════════════════════════════════════════════════════════════════
def sync_leystop(src: SupaREST, dst: SupaREST, desde: str, dry_run: bool) -> int:
    """
    Lee registros_leystop de tu Supabase (snapshot semanal).
    Escribe en security_weekly de Diego.
    Solo la semana más reciente por región (último id_semana).
    En realidad sincroniza todas las semanas desde `desde`.
    """
    log.info("  Leyendo LeyStop desde tu Supabase...")

    registros = []
    offset = 0
    limit = 1000
    while True:
        params = (
            f"fecha_desde_iso=gte.{desde}"
            f"&select=id_region,nombre_region,fecha_desde_iso,fecha_hasta_iso,"
            f"semana,tasa_registro,var_ultima_semana,"
            f"mayor_registro_1,pct_1,mayor_registro_2,pct_2,mayor_registro_3,pct_3"
            f"&limit={limit}&offset={offset}"
        )
        batch = src.select("registros_leystop", params)
        if not batch:
            break
        registros.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    log.info(f"  {len(registros)} registros LeyStop")
    if not registros:
        return 0

    rows = []
    for r in registros:
        region_id = r.get("id_region")
        if region_id is None:
            continue
        rows.append({
            "region_id":     int(region_id),
            "fecha_desde":   r.get("fecha_desde_iso"),
            "fecha_hasta":   r.get("fecha_hasta_iso"),
            "semana":        r.get("semana"),
            "tasa_registro": safe_float(r.get("tasa_registro")),
            "var_semana_pct": safe_float(r.get("var_ultima_semana")),
            "delito_1":      r.get("mayor_registro_1"),
            "pct_1":         safe_float(r.get("pct_1")),
            "delito_2":      r.get("mayor_registro_2"),
            "pct_2":         safe_float(r.get("pct_2")),
            "delito_3":      r.get("mayor_registro_3"),
            "pct_3":         safe_float(r.get("pct_3")),
        })

    log.info(f"  → {len(rows)} filas a escribir en security_weekly")
    if dry_run or not rows:
        return len(rows)

    ok = 0
    for i, batch in enumerate(list(chunks(rows, BATCH))):
        log.info(f"    batch {i+1}/{math.ceil(len(rows)/BATCH)}...")
        if dst.upsert("security_weekly", batch):
            ok += len(batch)
        else:
            raise RuntimeError("Fallo upsert security_weekly")
    log.info(f"  ✓ {ok} filas sincronizadas")
    return ok

# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Sync tu Supabase → Work-OS Supabase")
    parser.add_argument("--tabla", choices=["empleo", "pib", "leystop"], help="Sync solo esta tabla")
    parser.add_argument("--dry-run", action="store_true", help="Sin escribir nada")
    parser.add_argument("--desde", default="2020-01-01", help="Fecha desde (YYYY-MM-DD), default 2020-01-01")
    args = parser.parse_args()

    import urllib3; urllib3.disable_warnings()

    creds = leer_creds()

    src_url = creds.get("SUPABASE_URL")
    src_key = creds.get("SUPABASE_SERVICE_KEY")
    dst_url = creds.get("WORKOS_SUPABASE_URL")
    dst_key = creds.get("WORKOS_SUPABASE_SERVICE_KEY")

    for var, val in [("SUPABASE_URL", src_url), ("SUPABASE_SERVICE_KEY", src_key),
                     ("WORKOS_SUPABASE_URL", dst_url), ("WORKOS_SUPABASE_SERVICE_KEY", dst_key)]:
        if not val:
            log.error(f"Falta {var} en .env")
            sys.exit(1)

    src = SupaREST(src_url, src_key, "TU-SUPABASE")
    dst = SupaREST(dst_url, dst_key, "WORK-OS")

    log.info(f"{'[DRY RUN] ' if args.dry_run else ''}Sync → Work-OS desde {args.desde}")

    total = 0
    tablas = [args.tabla] if args.tabla else ["empleo", "pib", "leystop"]

    for tabla in tablas:
        log.info(f"\n── {tabla.upper()} ──")
        try:
            if tabla == "empleo":
                total += sync_empleo(src, dst, args.desde, args.dry_run)
            elif tabla == "pib":
                total += sync_pib(src, dst, args.desde, args.dry_run)
            elif tabla == "leystop":
                total += sync_leystop(src, dst, args.desde, args.dry_run)
        except RuntimeError as e:
            log.error(f"  {e} — abortando")
            break

    log.info(f"\n{'='*50}")
    log.info(f"Total: {total} filas {'(dry run)' if args.dry_run else 'sincronizadas'}")

if __name__ == "__main__":
    main()
