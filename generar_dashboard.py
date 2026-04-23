"""
Generador Dashboard Regional Chile — Unificado
===============================================
Módulos:
  🛡 Seguridad Pública  (pestañas: Resumen | Evolución | Operativo)
  📈 PIB Regional       (pestañas: Evolución | Sectores | Resumen nacional)
  🏘 Censo 2024         (pestañas: Demografía | Vivienda | Educación | Conectividad y Servicios)

Fuentes:
  - bcn_indicadores.db   (tablas: registros_leystop, leystop_semanas, registros_bce, registros_bcn)
  - censo_regiones.json  (generado por preparar_censo.py)

Uso:
  python generar_dashboard.py
  → dashboard.html
"""

import sqlite3, json, math, pandas as pd
from pathlib import Path

DB_PATH    = "bcn_indicadores.db"
CENSO_PATH  = "censo_regiones.json"
CASEN_PATH  = "casen_regiones.json"

def q(sql):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def clean(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    return v

# ══════════════════════════════════════════════════════════════════════════════
# DATOS SEGURIDAD
# ══════════════════════════════════════════════════════════════════════════════
semanas = q("""
    SELECT DISTINCT r.id_semana, s.nombre, s.semana, s.fecha_desde_iso, s.fecha_hasta_iso, s.anno
    FROM registros_leystop r
    JOIN leystop_semanas s ON r.id_semana = s.id
    ORDER BY r.id_semana
""")

datos_seg = q("""
    SELECT r.id_semana, r.id_region, r.nombre_region, r.semana,
           r.fecha_desde_iso, r.fecha_hasta_iso, r.anno,
           r.tasa_registro, r.casos_total, r.casos_anno_fecha,
           r.casos_anno_fecha_anterior, r.var_anno_fecha,
           r.var_ultima_semana, r.var_28dias,
           r.casos_ultima_semana, r.casos_28dias,
           r.mayor_registro_1, r.pct_1,
           r.mayor_registro_2, r.pct_2,
           r.mayor_registro_3, r.pct_3,
           r.mayor_registro_4, r.pct_4,
           r.mayor_registro_5, r.pct_5,
           r.controles, r.controles_identidad, r.controles_vehicular,
           r.fiscalizaciones, r.fiscal_alcohol, r.fiscal_bancaria,
           r.incautaciones, r.incaut_fuego, r.incaut_blancas,
           r.allanamientos_anno, r.vehiculos_recuperados_anno, r.decomisos_anno
    FROM registros_leystop r
    ORDER BY r.id_semana, r.id_region
""")

regiones_seg = sorted(datos_seg['nombre_region'].unique().tolist())
semanas_clean = [{k: clean(v) for k,v in row.items()} for row in semanas.to_dict('records')]
datos_seg_clean = [{k: clean(v) for k,v in row.items()} for row in datos_seg.to_dict('records')]

# Delitos desagregados (tabla registros_leystop_delitos)
try:
    datos_delitos = q("""
        SELECT id_semana, id_region, nombre_region, nombre_delito, es_dmcs,
               ultima_semana_ant, ultima_semana,
               dias28_ant, dias28,
               anno_fecha_ant, anno_fecha, umbral
        FROM registros_leystop_delitos
        ORDER BY id_semana, id_region, nombre_delito
    """)
    datos_delitos_clean = [{k: clean(v) for k,v in row.items()} for row in datos_delitos.to_dict('records')]
    nombres_delitos = sorted(datos_delitos['nombre_delito'].unique().tolist()) if not datos_delitos.empty else []
    tiene_tabla_delitos = True
except Exception as e:
    datos_delitos_clean = []
    nombres_delitos = []
    tiene_tabla_delitos = False
    import sys; print(f"Aviso: tabla registros_leystop_delitos no disponible: {e}", file=sys.stderr)

# ══════════════════════════════════════════════════════════════════════════════
# DATOS PIB
# ══════════════════════════════════════════════════════════════════════════════
SECTORES_TRIM = ["PIB","PIB Producción de bienes","PIB Minería",
    "PIB Industria manufacturera","PIB Resto de bienes","PIB Comercio","PIB Servicios"]
# Sectores con datos encadenados anuales (series empalmadas, volumen a precios año anterior)
SECTORES_ENC_ANUAL = ["PIB","PIB Agropecuario-silvícola","PIB Minería",
    "PIB Industria manufacturera","PIB Construcción","PIB Comercio",
    "PIB Servicios financieros y empresariales","PIB Servicios personales",
    "PIB Administración pública","PIB Restaurantes y hoteles",
    "PIB Electricidad, gas y agua","PIB Pesca"]
# Mantenemos SECTORES_CORR solo como alias para compatibilidad interna
SECTORES_CORR = SECTORES_ENC_ANUAL
UNIDAD_CORR = "miles de millones de pesos corrientes (base 2018)"
UNIDAD_ENC  = "miles de millones de pesos encadenados"

# Regiones con datos encadenados base 2018 (serie .A o .T — Los Ríos solo tiene .T)
regiones_pib = q("""SELECT DISTINCT nombre_region FROM registros_bce
    WHERE nombre_region IS NOT NULL
    AND unidad_limpia='miles de millones de pesos encadenados'
    AND indicador_limpio='PIB'
    AND series_id LIKE '%.2018.%'
    ORDER BY nombre_region""")['nombre_region'].tolist()

def periodo_a_label(p, freq='anual'):
    try:
        partes = p.split('-')
        mes, año = int(partes[1]), partes[2]
        if freq == 'anual': return año
        trim = {1:'I',4:'II',7:'III',10:'IV'}[mes]
        return f"{trim}.{año}"
    except:
        return p

def sk(t):
    if '.' in str(t):
        tr, yr = t.split('.')
        return int(yr)*10 + {'I':1,'II':2,'III':3,'IV':4}.get(tr,0)
    try: return int(t)*10
    except: return 99999

def _extraer_mes(p):
    """Extrae el mes numérico del campo periodo (formato DD-MM-YYYY)."""
    try: return int(p.split('-')[1])
    except: return None

def _extraer_año(p):
    """Extrae el año del campo periodo (formato DD-MM-YYYY)."""
    try: return p.split('-')[2]
    except: return None

def leer_por_region(indicador_limpio, unidad_limpia, freq):
    # Filtrar directamente por sufijo de series_id:
    # .A = serie anual, .T = serie trimestral
    # Además preferir base 2018 cuando hay múltiples bases
    sufijo = '.A' if freq == 'anual' else '.T'
    df = q(f"""SELECT nombre_region, periodo, valor_corregido as valor, series_id
        FROM registros_bce
        WHERE indicador_limpio='{indicador_limpio}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NOT NULL AND valor_corregido IS NOT NULL
        AND series_id LIKE '%.{sufijo[1:]}'
        ORDER BY nombre_region, periodo, series_id DESC""")
    if df.empty: return {}
    df['mes'] = df['periodo'].apply(_extraer_mes)
    df['año'] = df['periodo'].apply(_extraer_año)
    df['label'] = df['periodo'].apply(lambda p: periodo_a_label(p, freq))
    # Si quedan duplicados por base (2013 vs 2018), preferir base 2018 (series_id con '2018')
    df['es_2018'] = df['series_id'].str.contains('2018').astype(int)
    df = df.sort_values(['nombre_region','label','es_2018'], ascending=[True,True,False])
    pr = {}
    for reg in df['nombre_region'].unique():
        sub = df[df['nombre_region'] == reg][['label','valor']].copy()
        sub = sub.drop_duplicates(subset='label', keep='first')
        pr[reg] = sub.set_index('label')['valor'].to_dict()
    return pr

def leer_nacional(indicador_limpio, unidad_limpia, freq):
    sufijo = '.A' if freq == 'anual' else '.T'
    df = q(f"""SELECT periodo, valor_corregido as valor, series_id
        FROM registros_bce
        WHERE indicador_limpio='{indicador_limpio}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NULL AND valor_corregido IS NOT NULL
        AND series_id LIKE '%.{sufijo[1:]}'
        ORDER BY periodo, series_id DESC""")
    if df.empty: return {}
    df['label'] = df['periodo'].apply(lambda p: periodo_a_label(p, freq))
    df['es_2018'] = df['series_id'].str.contains('2018').astype(int)
    df = df.sort_values(['label','es_2018'], ascending=[True,False])
    df = df.drop_duplicates(subset='label', keep='first')
    return df.set_index('label')['valor'].to_dict()

datos_trim = {}
for sector in SECTORES_TRIM:
    datos_trim[sector] = {}
    for clave, unidad in [('var_pct','Porcentaje'),('miles_enc', UNIDAD_ENC)]:
        pr = leer_por_region(sector, unidad, 'trimestral')
        if pr: datos_trim[sector][clave] = pr

extra_trim_enc   = leer_nacional('Extrarregional', UNIDAD_ENC, 'trimestral')
subtotal_trim_enc = leer_nacional('PIB subtotal regionalizado', UNIDAD_ENC, 'trimestral')

# ── Datos anuales: encadenados (volumen a precios año anterior, series empalmadas) ──
datos_enc_anual = {}
for sector in SECTORES_ENC_ANUAL:
    pr = leer_por_region(sector, UNIDAD_ENC, 'anual')
    if pr: datos_enc_anual[sector] = pr

# Algunas regiones (ej: Los Ríos) solo tienen serie .T en el BCE.
# Las completamos sumando los 4 trimestres de cada año.
def _completar_con_trimestres(sector, unidad_limpia):
    """Para regiones sin serie .A, construye anual sumando 4 trimestres .T."""
    df = q(f"""SELECT nombre_region, periodo, valor_corregido as valor
        FROM registros_bce
        WHERE indicador_limpio='{sector}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NOT NULL AND valor_corregido IS NOT NULL
        AND series_id LIKE '%.T'
        ORDER BY nombre_region, periodo""")
    if df.empty: return {}
    df['mes'] = df['periodo'].apply(_extraer_mes)
    df['año'] = df['periodo'].apply(_extraer_año)
    df = df[df['mes'].isin([1, 4, 7, 10])].copy()
    resultado = {}
    for (reg, año), g in df.groupby(['nombre_region', 'año']):
        if len(g) == 4:
            if reg not in resultado:
                resultado[reg] = {}
            resultado[reg][año] = round(g['valor'].sum(), 4)
    return resultado

# Detectar regiones con datos trimestrales pero sin anuales y completar
for sector in SECTORES_ENC_ANUAL:
    trim_data = _completar_con_trimestres(sector, UNIDAD_ENC)
    for reg, años in trim_data.items():
        if reg not in datos_enc_anual.get(sector, {}):
            if sector not in datos_enc_anual:
                datos_enc_anual[sector] = {}
            datos_enc_anual[sector][reg] = años

# Alias para no romper referencias internas
datos_corr = datos_enc_anual

# Extrarregional y Subtotal no tienen serie .A en base 2018 en el BCE.
# Se construyen sumando los 4 trimestres .T de cada año.
def _sum_trimestres_nacional(indicador_limpio, unidad_limpia):
    """Suma los 4 trimestres base 2018 de cada año para obtener un valor anual."""
    df = q(f"""SELECT periodo, valor_corregido as valor
        FROM registros_bce
        WHERE indicador_limpio='{indicador_limpio}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NULL AND valor_corregido IS NOT NULL
        AND series_id LIKE '%.T'
        ORDER BY periodo""")
    if df.empty: return {}
    df['mes'] = df['periodo'].apply(_extraer_mes)
    df['año'] = df['periodo'].apply(_extraer_año)
    df = df[df['mes'].isin([1, 4, 7, 10])].copy()
    # Sumar los 4 trimestres por año, solo si están los 4
    resultado = {}
    for año, g in df.groupby('año'):
        if len(g) == 4:
            resultado[año] = round(g['valor'].sum(), 4)
    return resultado

extra_enc_anual    = _sum_trimestres_nacional('Extrarregional', UNIDAD_ENC)
subtotal_enc_anual = _sum_trimestres_nacional('PIB subtotal regionalizado', UNIDAD_ENC)
extra_corr    = extra_enc_anual
subtotal_corr = subtotal_enc_anual

periodos_trim_raw = sorted(
    q("SELECT DISTINCT periodo FROM registros_bce WHERE indicador_limpio='PIB' AND unidad_limpia='Porcentaje' AND nombre_region IS NOT NULL")['periodo'].tolist())
trimestres = sorted(set(periodo_a_label(p,'trimestral') for p in periodos_trim_raw), key=sk)
años_trim  = sorted(set(t.split('.')[1] for t in trimestres))
años_enc_anual = sorted(set(yr for rd in datos_enc_anual.values() for rv in rd.values() for yr in rv.keys()))
años_corr = años_enc_anual

# ══════════════════════════════════════════════════════════════════════════════
# DATOS EMPLEO
# ══════════════════════════════════════════════════════════════════════════════
df_emp = q("SELECT nombre_region, periodo, indicador, valor FROM registros_bce_empleo ORDER BY nombre_region, periodo")

import math
def clean_emp(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    return v

regiones_emp = sorted(df_emp['nombre_region'].unique().tolist())
periodos_emp = sorted(df_emp['periodo'].unique().tolist())
años_emp = sorted(set(p[:4] for p in periodos_emp))

datos_emp = {}
for reg in regiones_emp:
    sub_t = df_emp[(df_emp['nombre_region']==reg)&(df_emp['indicador']=='Tasa de desocupación')].sort_values('periodo')
    sub_o = df_emp[(df_emp['nombre_region']==reg)&(df_emp['indicador']=='Ocupados')].sort_values('periodo')
    import pandas as pd
    merged = sub_t[['periodo','valor']].rename(columns={'valor':'tasa'}).merge(
        sub_o[['periodo','valor']].rename(columns={'valor':'ocupados'}), on='periodo')
    merged['ft'] = merged.apply(lambda r: round(r['ocupados']/(1-r['tasa']/100),1) if r['tasa'] is not None and r['tasa']<100 else None, axis=1)
    datos_emp[reg] = {
        'periodos': merged['periodo'].tolist(),
        'tasa':     [clean_emp(v) for v in merged['tasa'].tolist()],
        'ocupados': [clean_emp(v) for v in merged['ocupados'].tolist()],
        'ft':       [clean_emp(v) for v in merged['ft'].tolist()],
    }

# ══════════════════════════════════════════════════════════════════════════════
# JSON embebido
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# DATOS CENSO 2024
# ══════════════════════════════════════════════════════════════════════════════
censo_path = Path(CENSO_PATH)
if not censo_path.exists():
    raise FileNotFoundError(f"No se encuentra {CENSO_PATH}. Corre preparar_censo.py primero.")
with open(censo_path, encoding='utf-8') as f:
    censo_raw = json.load(f)

data_censo_json = json.dumps(censo_raw, ensure_ascii=False)

# CASEN 2024
casen_path = Path(CASEN_PATH)
if not casen_path.exists():
    raise FileNotFoundError(f"No se encuentra {CASEN_PATH}. Corre preparar_casen.py primero.")
with open(casen_path, encoding='utf-8') as f:
    casen_raw = json.load(f)
data_casen_json = json.dumps(casen_raw, ensure_ascii=False)

data_emp_json = json.dumps({
    'regiones': regiones_emp,
    'periodos': periodos_emp,
    'años': años_emp,
    'datos': datos_emp,
}, ensure_ascii=False)

data_seg_json = json.dumps({
    'semanas': semanas_clean,
    'datos': datos_seg_clean,
    'regiones': regiones_seg,
}, ensure_ascii=False)

data_delitos_json = json.dumps({
    'datos': datos_delitos_clean,
    'nombres_delitos': nombres_delitos,
    'tiene_datos': tiene_tabla_delitos,
}, ensure_ascii=False)

data_pib_json = json.dumps({
    'regiones': regiones_pib,
    'años_trim': años_trim,
    'años_enc_anual': años_enc_anual,
    'años_corr': años_enc_anual,          # alias para compatibilidad JS
    'trimestres': trimestres,
    'sectores_trim': SECTORES_TRIM,
    'sectores_enc_anual': SECTORES_ENC_ANUAL,
    'sectores_corr': SECTORES_ENC_ANUAL,  # alias
    'datos_trim': datos_trim,
    'datos_enc_anual': datos_enc_anual,   # encadenados anuales (fuente de verdad)
    'datos_corr': datos_enc_anual,        # alias
    'extra_trim_enc': extra_trim_enc,
    'extra_enc_anual': extra_enc_anual,
    'extra_corr': extra_enc_anual,        # alias
    'subtotal_trim_enc': subtotal_trim_enc,
    'subtotal_enc_anual': subtotal_enc_anual,
    'subtotal_corr': subtotal_enc_anual,  # alias
}, ensure_ascii=False)

# ══════════════════════════════════════════════════════════════════════════════
# HTML
# ══════════════════════════════════════════════════════════════════════════════
html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard Regional · Chile</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e}}

/* ── Header principal ── */
header{{background:#1a1a2e;color:white;padding:14px 32px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200;box-shadow:0 2px 8px rgba(0,0,0,.35)}}
header h1{{font-size:16px;font-weight:600;letter-spacing:.2px}}
header span{{font-size:11px;opacity:.6}}

/* ── Módulos (nav top-level) ── */
.mod-nav{{background:#16213e;display:flex;padding:0 32px;gap:2px;border-bottom:3px solid #0f3460}}
.mod-btn{{padding:11px 26px;font-size:13px;font-weight:600;cursor:pointer;color:rgba(255,255,255,.55);border-bottom:3px solid transparent;margin-bottom:-3px;transition:all .2s;white-space:nowrap;letter-spacing:.3px}}
.mod-btn:hover{{color:rgba(255,255,255,.85)}}
.mod-btn.active{{color:white;border-bottom-color:#38bdf8}}

/* ── Módulos (contenedores) ── */
.modulo{{display:none}}.modulo.active{{display:block}}

/* ── Sub-tabs por módulo ── */
.tabs{{background:white;border-bottom:2px solid #e8e8e8;padding:0 32px;display:flex;gap:4px}}
.tab-seg{{padding:12px 20px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab-seg:hover{{color:#16a34a}}.tab-seg.active{{color:#16a34a;border-bottom-color:#16a34a;font-weight:600}}
.tab-pib{{padding:12px 20px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab-pib:hover{{color:#2563eb}}.tab-pib.active{{color:#2563eb;border-bottom-color:#2563eb;font-weight:600}}
.tab-censo{{padding:12px 20px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab-censo:hover{{color:#7c3aed}}.tab-censo.active{{color:#7c3aed;border-bottom-color:#7c3aed;font-weight:600}}
.tab-emp{{padding:12px 20px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab-emp:hover{{color:#059669}}.tab-emp.active{{color:#059669;border-bottom-color:#059669;font-weight:600}}
.tab-casen{{padding:12px 20px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab-casen:hover{{color:#e11d48}}.tab-casen.active{{color:#e11d48;border-bottom-color:#e11d48;font-weight:600}}

/* ── Layout ── */
.content{{padding:24px 32px;max-width:1500px;margin:0 auto}}
.section{{display:none}}.section.active{{display:block}}

/* ── Filtros ── */
.filtros{{background:white;border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.fg{{display:flex;flex-direction:column;gap:5px}}
.fg label{{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.4px}}
.fg select{{padding:7px 12px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px;background:white;cursor:pointer;outline:none;min-width:160px}}
.fg select:focus{{border-color:#2563eb}}

/* ── Region bar PIB ── */
.region-bar{{background:white;border-bottom:1px solid #e0e0e0;padding:10px 32px;display:flex;align-items:center;gap:14px}}
.region-bar label{{font-size:12px;font-weight:600;color:#666}}
.region-bar select{{padding:7px 12px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px;min-width:260px;cursor:pointer;outline:none}}

/* ── KPIs ── */
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:14px;margin-bottom:22px}}
.kpi{{background:white;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #2563eb}}
.kpi.verde{{border-left-color:#16a34a}}.kpi.rojo{{border-left-color:#dc2626}}.kpi.amber{{border-left-color:#d97706}}.kpi.azul{{border-left-color:#2563eb}}
.kpi-label{{font-size:10px;color:#999;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.kpi-value{{font-size:22px;font-weight:700;color:#1a1a2e;line-height:1}}
.kpi-sub{{font-size:11px;color:#bbb;margin-top:5px}}

/* ── Cards ── */
.card{{background:white;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px}}
.card h3{{font-size:14px;font-weight:600;color:#333;margin-bottom:16px}}
.card canvas{{max-height:320px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}

/* ── Tablas ── */
.tabla-wrap{{overflow-x:auto;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
table.dt{{width:100%;border-collapse:collapse;font-size:12.5px}}
table.dt th{{background:#1a1a2e;color:white;padding:9px 14px;text-align:center;font-weight:500;font-size:11px;white-space:nowrap;cursor:pointer;user-select:none}}
table.dt th:first-child{{text-align:left;cursor:default;min-width:180px}}
table.dt th:hover:not(:first-child){{background:#2d3a55}}
table.dt th.asc::after{{content:' ▲';font-size:9px}}
table.dt th.desc::after{{content:' ▼';font-size:9px}}
table.dt td{{padding:8px 14px;border-bottom:1px solid #f0f0f0;text-align:right;white-space:nowrap}}
table.dt td:first-child{{text-align:left;font-weight:500;background:#fafafa}}
table.dt tr:hover td{{background:#f0f7ff}}
table.dt tr:hover td:first-child{{background:#e8f1ff}}
table.dt .total{{font-weight:700}}
table.dt td.total{{background:#eef2ff!important;color:#1d4ed8}}
table.dt tr.extra-row td{{background:#fef9ec!important;color:#92400e;font-style:italic}}
table.dt tr.extra-row td:first-child{{font-weight:600}}
table.dt tr.nacional-row td{{background:#f0fdf4!important;font-weight:700;color:#166534}}
/* Seguridad hover */
#mod-seguridad table.dt tr:hover td{{background:#f0fff4}}
#mod-seguridad table.dt tr:hover td:first-child{{background:#dcfce7}}

/* ── Misc ── */
.neg{{color:#dc2626;font-weight:600}}.pos{{color:#16a34a;font-weight:600}}
.nota{{font-size:11px;color:#888;margin-top:10px;font-style:italic}}
.bar-wrap{{display:flex;align-items:center;gap:8px}}
.bar{{height:8px;background:#16a34a;border-radius:4px;min-width:2px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}}
.badge-baja{{background:#dcfce7;color:#166534}}.badge-alta{{background:#fef2f2;color:#991b1b}}.badge-media{{background:#fef9c3;color:#713f12}}
</style>
</head>
<body>

<header>
  <h1>📊 Dashboard Regional · Chile</h1>
  <span id="hdr-sub">Selecciona un módulo</span>
</header>

<!-- ══ NAVEGACIÓN DE MÓDULOS ══ -->
<nav class="mod-nav">
  <div class="mod-btn active" onclick="setModulo('seguridad',this)">🛡 Seguridad Pública</div>
  <div class="mod-btn" onclick="setModulo('pib',this)">📈 PIB Regional</div>
  <div class="mod-btn" onclick="setModulo('censo',this)">🏘 Censo 2024</div>
  <div class="mod-btn" onclick="setModulo('empleo',this)">💼 Empleo</div>
  <div class="mod-btn" onclick="setModulo('casen',this)">🏠 CASEN 2024</div>
</nav>

<!-- ══════════════════════════════════════════════════════════════
     MÓDULO: SEGURIDAD
══════════════════════════════════════════════════════════════ -->
<div class="modulo active" id="mod-seguridad">
  <div class="tabs">
    <div class="tab-seg active" onclick="setTabSeg('resumen',this)">Resumen por región</div>
    <div class="tab-seg" onclick="setTabSeg('evolucion',this)">Evolución temporal</div>
    <div class="tab-seg" onclick="setTabSeg('operativo',this)">Actividad operativa</div>
    <div class="tab-seg" onclick="setTabSeg('dmcs',this)">🔴 DMCS</div>
  </div>
  <div class="content">

    <!-- Resumen -->
    <div class="section active" id="seg-resumen">
      <div class="filtros">
        <div class="fg"><label>Semana</label>
          <select id="res-semana" onchange="renderResumen()"></select></div>
        <div class="fg"><label>Región</label>
          <select id="res-region" onchange="renderResumen()">
            <option value="">Todas las regiones</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="kpi-resumen"></div>
      <div class="card">
        <h3 id="res-title">Casos año a la fecha y variación por región</h3>
        <div class="tabla-wrap"><table class="dt" id="tabla-resumen"></table></div>
      </div>
      <div class="grid2">
        <div class="card">
          <h3>Top delito más frecuente por región</h3>
          <canvas id="chart-delitos" style="max-height:320px"></canvas>
        </div>
        <div class="card">
          <h3>Tasa de registro por 100 mil hab.</h3>
          <canvas id="chart-tasa" style="max-height:320px"></canvas>
        </div>
      </div>
    </div>

    <!-- Evolución -->
    <div class="section" id="seg-evolucion">
      <div class="filtros">
        <div class="fg"><label>Región</label>
          <select id="evo-seg-region" onchange="renderEvolucionSeg()"></select></div>
        <div class="fg"><label>Indicador</label>
          <select id="evo-seg-ind" onchange="renderEvolucionSeg()">
            <option value="casos_anno_fecha">Casos año a la fecha</option>
            <option value="tasa_registro">Tasa por 100 mil hab.</option>
            <option value="casos_ultima_semana">Casos última semana</option>
            <option value="casos_28dias">Casos últimos 28 días</option>
            <option value="var_anno_fecha">Variación % año a la fecha</option>
          </select></div>
      </div>
      <div class="card">
        <h3 id="evo-seg-title">Evolución temporal</h3>
        <canvas id="chart-evo-seg" style="max-height:340px"></canvas>
      </div>
      <div class="card">
        <h3 id="evo-delitos-title">Top 5 delitos — año a la fecha</h3>
        <canvas id="chart-evo-delitos" style="max-height:280px"></canvas>
      </div>
    </div>

    <!-- Operativo -->
    <div class="section" id="seg-operativo">
      <div class="filtros">
        <div class="fg"><label>Semana</label>
          <select id="op-semana" onchange="renderOperativo()"></select></div>
      </div>
      <div class="kpi-grid" id="kpi-op"></div>
      <div class="grid2">
        <div class="card">
          <h3>Controles por región</h3>
          <canvas id="chart-controles" style="max-height:320px"></canvas>
        </div>
        <div class="card">
          <h3>Incautaciones y decomisos</h3>
          <canvas id="chart-incaut" style="max-height:320px"></canvas>
        </div>
      </div>
    </div>

    <!-- DMCS -->
    <div class="section" id="seg-dmcs">
      <div class="filtros">
        <div class="fg"><label>Semana</label>
          <select id="dmcs-semana" onchange="renderDMCS()"></select></div>
        <div class="fg"><label>Región</label>
          <select id="dmcs-region" onchange="renderDMCS()">
            <option value="">Nacional (todas)</option>
          </select></div>
        <div class="fg"><label>Delito DMCS</label>
          <select id="dmcs-delito" onchange="renderDMCS()">
            <option value="">Todos los DMCS</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="kpi-dmcs"></div>
      <div class="grid2">
        <div class="card" style="grid-column:1/2">
          <h3 id="dmcs-chart-bar-title">DMCS por tipo</h3>
          <canvas id="chart-dmcs-regiones" style="max-height:380px"></canvas>
        </div>
        <div class="card" style="grid-column:2/3">
          <h3 id="dmcs-chart-pie-title">Distribución DMCS</h3>
          <canvas id="chart-dmcs-pie" style="max-height:380px"></canvas>
        </div>
      </div>
      <div class="card">
        <h3 id="dmcs-tabla-title">Detalle DMCS por región</h3>
        <div class="tabla-wrap"><table class="dt" id="tabla-dmcs"></table></div>
        <p class="nota">Var. % calculada respecto al mismo período del año anterior. "Delito más grave" = DMCS con umbral más alto (z-score Carabineros).</p>
      </div>
      <div class="card">
        <div style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px">
          <h3 id="dmcs-evo-title" style="margin:0">Evolución semanal DMCS — casos última semana</h3>
          <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end">
            <div class="fg">
              <label>Métrica</label>
              <select id="dmcs-evo-metrica" onchange="renderDMCSEvo()" style="padding:6px 10px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:12px;min-width:160px">
                <option value="ultima_semana">Casos última semana</option>
                <option value="dias28">Casos últimos 28 días</option>
                <option value="anno_fecha">Casos año a la fecha</option>
              </select>
            </div>
            <div class="fg">
              <label>Comparar año anterior</label>
              <select id="dmcs-evo-comparar" onchange="renderDMCSEvo()" style="padding:6px 10px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:12px;min-width:130px">
                <option value="no">Solo año actual</option>
                <option value="si">Sí — superponer 2025</option>
              </select>
            </div>
          </div>
        </div>
        <canvas id="chart-dmcs-evo" style="max-height:340px"></canvas>
        <p class="nota" id="dmcs-evo-nota"></p>
      </div>
    </div>

  </div><!-- /content seg -->
</div><!-- /mod-seguridad -->

<!-- ══════════════════════════════════════════════════════════════
     MÓDULO: PIB
══════════════════════════════════════════════════════════════ -->
<div class="modulo" id="mod-pib">
  <div class="region-bar">
    <label>Región:</label>
    <select id="pib-region-sel" onchange="setRegionPib(this.value)">
      <option value="">-- Selecciona una región --</option>
    </select>
  </div>
  <div class="tabs">
    <div class="tab-pib active" onclick="setTabPib('evolucion',this)">Evolución</div>
    <div class="tab-pib" onclick="setTabPib('sectores',this)">Sectores productivos</div>
    <div class="tab-pib" onclick="setTabPib('resumen',this)">Resumen nacional</div>
  </div>
  <div class="content">

    <!-- Evolución PIB -->
    <div class="section active" id="pib-evolucion">
      <div class="filtros">
        <div class="fg"><label>Frecuencia</label>
          <select id="pib-evo-freq" onchange="onFreqChange('pib-evo')">
            <option value="anual">Anual</option>
            <option value="trimestral">Trimestral</option>
          </select></div>
        <div class="fg"><label>Indicador</label><select id="pib-evo-ind" onchange="renderEvolucionPib()"></select></div>
        <div class="fg"><label>Año desde</label><select id="pib-evo-desde" onchange="renderEvolucionPib()"></select></div>
        <div class="fg"><label>Año hasta</label><select id="pib-evo-hasta" onchange="renderEvolucionPib()"></select></div>
      </div>
      <div class="kpi-grid" id="pib-kpi-evo"></div>
      <div class="card">
        <h3 id="pib-evo-title">PIB</h3>
        <canvas id="pib-chart-evo" style="max-height:320px"></canvas>
      </div>
    </div>

    <!-- Sectores PIB -->
    <div class="section" id="pib-sectores">
      <div class="filtros">
        <div class="fg"><label>Frecuencia</label>
          <select id="pib-sec-freq" onchange="onFreqChange('pib-sec')">
            <option value="anual">Anual</option>
            <option value="trimestral">Trimestral</option>
          </select></div>
        <div class="fg"><label>Indicador</label><select id="pib-sec-ind" onchange="renderSectores()"></select></div>
        <div class="fg"><label>Año desde</label><select id="pib-sec-desde" onchange="renderSectores()"></select></div>
        <div class="fg"><label>Año hasta</label><select id="pib-sec-hasta" onchange="renderSectores()"></select></div>
        <div class="fg" style="justify-content:flex-end">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:12px;color:#555;font-weight:600;text-transform:uppercase;letter-spacing:.4px">
            <input type="checkbox" id="pib-sec-mostrar-var" onchange="renderSectores()" style="width:15px;height:15px;cursor:pointer">
            Mostrar var. %
          </label>
        </div>
      </div>
      <div class="card">
        <h3 id="pib-sec-title">Sectores productivos</h3>
        <div class="tabla-wrap"><table class="dt" id="tabla-sec"></table></div>
        <p class="nota" id="pib-sec-nota"></p>
      </div>
    </div>

    <!-- Resumen PIB -->
    <div class="section" id="pib-resumen">
      <div class="filtros">
        <div class="fg"><label>Frecuencia</label>
          <select id="pib-res-freq" onchange="onFreqChange('pib-res')">
            <option value="anual">Anual</option>
            <option value="trimestral">Trimestral</option>
          </select></div>
        <div class="fg"><label>Indicador</label><select id="pib-res-ind" onchange="renderResumenPib()"></select></div>
        <div class="fg"><label>Año desde</label><select id="pib-res-desde" onchange="renderResumenPib()"></select></div>
        <div class="fg"><label>Año hasta</label><select id="pib-res-hasta" onchange="renderResumenPib()"></select></div>
        <div class="fg" style="justify-content:flex-end">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:12px;color:#555;font-weight:600;text-transform:uppercase;letter-spacing:.4px">
            <input type="checkbox" id="pib-res-mostrar-var" onchange="renderResumenPib()" style="width:15px;height:15px;cursor:pointer">
            Mostrar var. %
          </label>
        </div>
      </div>
      <div class="card">
        <h3 id="pib-res-title">PIB por región</h3>
        <div class="tabla-wrap"><table class="dt" id="tabla-res"></table></div>
        <p class="nota" id="pib-res-nota"></p>
      </div>
    </div>

  </div><!-- /content pib -->
</div><!-- /mod-pib -->


<!-- ══════════════════════════════════════════════════════════════
     MÓDULO: CENSO 2024
══════════════════════════════════════════════════════════════ -->
<div class="modulo" id="mod-censo">
  <div class="tabs">
    <div class="tab-censo active" onclick="setTabCenso('demografia',this)">Demografía</div>
    <div class="tab-censo" onclick="setTabCenso('vivienda',this)">Vivienda</div>
    <div class="tab-censo" onclick="setTabCenso('educacion',this)">Educación</div>
    <div class="tab-censo" onclick="setTabCenso('conectividad',this)">Conectividad y Servicios</div>
  </div>
  <div class="content">

    <!-- ═══ DEMOGRAFÍA ═══ -->
    <div class="section active" id="censo-demografia">
      <div class="filtros">
        <div class="fg"><label>Región</label>
          <select id="censo-region" onchange="renderCenso()"></select></div>
        <div class="fg"><label>Área</label>
          <select id="censo-area" onchange="renderCenso()">
            <option value="total">Total regional</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="censo-kpi-demo"></div>
      <div class="grid2">
        <div class="card">
          <h3>Distribución etaria</h3>
          <canvas id="censo-chart-edad" style="max-height:300px"></canvas>
        </div>
        <div class="card">
          <h3>Composición población</h3>
          <canvas id="censo-chart-comp" style="max-height:300px"></canvas>
        </div>
      </div>
      <div class="card">
        <h3>Comparación regional — Indicadores demográficos</h3>
        <div class="tabla-wrap"><table class="dt" id="censo-tabla-demo"></table></div>
      </div>
    </div>

    <!-- ═══ VIVIENDA ═══ -->
    <div class="section" id="censo-vivienda">
      <div class="filtros">
        <div class="fg"><label>Región</label>
          <select id="censo-region-viv" onchange="renderCensoViv()"></select></div>
      </div>
      <div class="kpi-grid" id="censo-kpi-viv"></div>
      <div class="grid2">
        <div class="card">
          <h3>Tipo de vivienda</h3>
          <canvas id="censo-chart-tipo-viv" style="max-height:300px"></canvas>
        </div>
        <div class="card">
          <h3>Tenencia</h3>
          <canvas id="censo-chart-tenencia" style="max-height:300px"></canvas>
        </div>
      </div>
      <div class="card">
        <h3>Comparación regional — Déficit habitacional</h3>
        <div class="tabla-wrap"><table class="dt" id="censo-tabla-viv"></table></div>
      </div>
    </div>

    <!-- ═══ EDUCACIÓN ═══ -->
    <div class="section" id="censo-educacion">
      <div class="filtros">
        <div class="fg"><label>Región</label>
          <select id="censo-region-edu" onchange="renderCensoEdu()"></select></div>
      </div>
      <div class="kpi-grid" id="censo-kpi-edu"></div>
      <div class="grid2">
        <div class="card">
          <h3>Nivel educacional (CINE)</h3>
          <canvas id="censo-chart-cine" style="max-height:300px"></canvas>
        </div>
        <div class="card">
          <h3>Nivel educacional alcanzado</h3>
          <canvas id="censo-chart-asist" style="max-height:300px"></canvas>
        </div>
      </div>
      <div class="card">
        <h3>Comparación regional — Educación</h3>
        <div class="tabla-wrap"><table class="dt" id="censo-tabla-edu"></table></div>
      </div>
    </div>

    <!-- ═══ CONECTIVIDAD Y SERVICIOS ═══ -->
    <div class="section" id="censo-conectividad">
      <div class="filtros">
        <div class="fg"><label>Región</label>
          <select id="censo-region-con" onchange="renderCensoCon()"></select></div>
      </div>
      <div class="kpi-grid" id="censo-kpi-con"></div>
      <div class="grid2">
        <div class="card">
          <h3>Acceso a servicios básicos (% viviendas)</h3>
          <canvas id="censo-chart-serv" style="max-height:300px"></canvas>
        </div>
        <div class="card">
          <h3>Conectividad digital — comparación regional</h3>
          <div style="margin-bottom:12px">
            <div class="fg">
              <label>Variable</label>
              <select id="censo-digital-var" onchange="renderCensoCon()" style="min-width:200px;padding:6px 10px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px">
                <option value="n_internet">Acceso a internet (cualquier tipo)</option>
                <option value="n_serv_internet_fija">Internet fija</option>
                <option value="n_serv_internet_movil">Internet móvil</option>
                <option value="n_serv_internet_satelital">Internet satelital</option>
                <option value="n_serv_tel_movil">Teléfono móvil</option>
                <option value="n_serv_compu">Computador</option>
                <option value="n_serv_tablet">Tablet</option>
              </select>
            </div>
          </div>
          <canvas id="censo-chart-digital" style="max-height:260px"></canvas>
        </div>
      </div>
      <div class="grid2">
        <div class="card">
          <h3>Combustible cocina</h3>
          <canvas id="censo-chart-cocina" style="max-height:280px"></canvas>
        </div>
        <div class="card">
          <h3>Combustible calefacción</h3>
          <canvas id="censo-chart-calef" style="max-height:280px"></canvas>
        </div>
      </div>
      <div class="card">
        <h3>Comparación regional — Servicios básicos</h3>
        <div class="tabla-wrap"><table class="dt" id="censo-tabla-con"></table></div>
      </div>
    </div>

  </div>
</div>

<script>
// ══════════════════════════════════════════════════════════════
// DATOS
// ══════════════════════════════════════════════════════════════
const SEG  = {data_seg_json};
const DELITOS = {data_delitos_json};
const CENSO_DATA = {data_censo_json};
const PIB  = {data_pib_json};

let charts = {{}}, sortState = {{}};

// ══════════════════════════════════════════════════════════════
// NAV MÓDULOS
// ══════════════════════════════════════════════════════════════
const MOD_LABELS = {{'empleo':'💼 Empleo · BCE/INE',
  casen:'🏠 CASEN 2024 · MIDESO',
  seguridad: '🛡 Seguridad Pública · Ley S.T.O.P',
  pib: '📈 PIB Regional · Banco Central',
  censo: '🏘 Censo 2024 · INE Chile',
}};

function setModulo(id, btn) {{
  document.querySelectorAll('.mod-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.modulo').forEach(m => m.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('mod-'+id).classList.add('active');
  document.getElementById('hdr-sub').textContent = MOD_LABELS[id] || '';
  // Trigger render del módulo activo
  if(id === 'seguridad') renderResumen();
  if(id === 'pib') {{ renderEvolucionPib(); }}
  if(id === 'censo') {{ if(!document.getElementById('censo-region').value) return; renderCenso(); }}
  if(id === 'casen') {{ renderCasenPob(); }}
}}

// ══════════════════════════════════════════════════════════════
// SUB-TABS
// ══════════════════════════════════════════════════════════════
function setTabSeg(tab, btn) {{
  document.querySelectorAll('.tab-seg').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#mod-seguridad .section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('seg-'+tab).classList.add('active');
  if(tab==='resumen')   renderResumen();
  if(tab==='evolucion') renderEvolucionSeg();
  if(tab==='operativo') renderOperativo();
  if(tab==='dmcs')      renderDMCS();
}}

let pibTabActual = 'evolucion';
function setTabPib(tab, btn) {{
  pibTabActual = tab;
  document.querySelectorAll('.tab-pib').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#mod-pib .section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('pib-'+tab).classList.add('active');
  if(tab==='evolucion') renderEvolucionPib();
  if(tab==='sectores')  renderSectores();
  if(tab==='resumen')   renderResumenPib();
}}

// ══════════════════════════════════════════════════════════════
// UTILS COMPARTIDOS
// ══════════════════════════════════════════════════════════════
function destroyChart(id) {{ if(charts[id]){{charts[id].destroy();delete charts[id];}} }}

function makeBarSeg(id, labels, datasets, opts={{}}) {{
  destroyChart(id);
  const ctx = document.getElementById(id); if(!ctx) return;
  charts[id] = new Chart(ctx, {{
    type: opts.type||'bar',
    data: {{labels, datasets}},
    plugins: [ChartDataLabels],
    options: {{
      responsive:true, maintainAspectRatio:true, indexAxis: opts.horizontal?'y':'x',
      plugins:{{
        legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}},padding:10}}}},
        tooltip:{{mode:'index',intersect:false}},
        datalabels:{{
          display: ctx => ctx.dataset.data[ctx.dataIndex] !== null && ctx.dataset.data[ctx.dataIndex] !== 0,
          color:'#333',
          font:{{size:9,weight:'600'}},
          anchor: opts.horizontal?'end':'end',
          align: opts.horizontal?'end':'top',
          formatter: v => v===null?'': (typeof v==='number'&&v<100&&v%1!==0? v.toFixed(1)+'%': Math.round(v).toLocaleString('es-CL')),
          clamp:true,
        }}
      }},
      scales:{{
        x:{{ticks:{{font:{{size:10}},maxRotation:opts.horizontal?0:55}},grid:{{display:opts.horizontal}}}},
        y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}
      }}
    }}
  }});
}}

function makeBarPib(id, labels, datasets) {{
  destroyChart(id);
  const ctx = document.getElementById(id); if(!ctx) return;
  charts[id] = new Chart(ctx, {{
    type:'bar', data:{{labels, datasets}},
    plugins: [ChartDataLabels],
    options:{{
      responsive:true, maintainAspectRatio:true,
      plugins:{{
        legend:{{display:false}},
        tooltip:{{mode:'index',intersect:false}},
        datalabels:{{
          display: ctx => ctx.dataset.data[ctx.dataIndex] !== null && ctx.dataset.data[ctx.dataIndex] !== 0,
          color:'#333', font:{{size:9,weight:'600'}},
          anchor:'end', align:'top', clamp:true,
          formatter: v => v===null?'': (Math.abs(v)<100&&v%1!==0? v.toFixed(1)+'%': Math.round(v).toLocaleString('es-CL')),
        }}
      }},
      scales:{{
        x:{{ticks:{{font:{{size:10}},maxRotation:60}},grid:{{display:false}}}},
        y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}
      }}
    }}
  }});
}}

function pct(v)  {{ return v===null||v===undefined?'—':v.toFixed(1)+'%'; }}
function num(v)  {{ return v===null||v===undefined?'—':Math.round(v).toLocaleString('es-CL'); }}
function clsCambio(v) {{ return v===null?'':v<0?'neg':'pos'; }}
function fmtCambio(v) {{ return v===null?'—':(v>0?'+':'')+v.toFixed(1)+'%'; }}

function sortDT(tableId, col) {{
  const tbl = document.getElementById(tableId);
  if(!sortState[tableId]) sortState[tableId] = {{}};
  const dir = sortState[tableId].col===col && sortState[tableId].dir==='desc' ? 'asc' : 'desc';
  sortState[tableId] = {{col, dir}};
  tbl.querySelectorAll('th').forEach(th => th.classList.remove('asc','desc'));
  const ths = tbl.querySelectorAll('th');
  if(ths[col]) ths[col].classList.add(dir);
  const tbody = tbl.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const especiales = rows.filter(r => r.classList.contains('extra-row')||r.classList.contains('nacional-row'));
  const normales   = rows.filter(r => !r.classList.contains('extra-row')&&!r.classList.contains('nacional-row'));
  normales.sort((a,b) => {{
    const av = a.cells[col]?.textContent.trim().replace(/[%+\\s,.]/g,'');
    const bv = b.cells[col]?.textContent.trim().replace(/[%+\\s,.]/g,'');
    const an = parseFloat(av), bn = parseFloat(bv);
    const cmp = isNaN(an)||isNaN(bn) ? av.localeCompare(bv,'es') : an-bn;
    return dir==='asc'?cmp:-cmp;
  }});
  [...normales,...especiales].forEach(r => tbody.appendChild(r));
}}

// ══════════════════════════════════════════════════════════════
// SEGURIDAD — helpers
// ══════════════════════════════════════════════════════════════
function datosParaSemana(id_semana) {{
  return SEG.datos.filter(d => d.id_semana === id_semana);
}}
function datosParaRegionSeg(region) {{
  return SEG.datos.filter(d => d.nombre_region === region).sort((a,b) => a.id_semana-b.id_semana);
}}
function poblarSemana(selId, handler) {{
  const sel = document.getElementById(selId);
  SEG.semanas.forEach(s => {{
    const o = document.createElement('option');
    o.value = s.id_semana; o.textContent = s.nombre; sel.appendChild(o);
  }});
  sel.value = SEG.semanas[SEG.semanas.length-1].id_semana;
  sel.onchange = handler;
}}
function poblarRegionSeg(selId, handler) {{
  const sel = document.getElementById(selId);
  SEG.regiones.forEach(r => {{
    const o = document.createElement('option'); o.value=r; o.textContent=r; sel.appendChild(o);
  }});
  sel.onchange = handler;
}}

// ── Resumen seg ──────────────────────────────────────────────
function renderResumen() {{
  const id_sem    = parseInt(document.getElementById('res-semana').value);
  const regFiltro = document.getElementById('res-region')?.value || '';
  let filas       = datosParaSemana(id_sem);
  if(regFiltro) filas = filas.filter(r => r.nombre_region === regFiltro);
  const sem       = SEG.semanas.find(s => s.id_semana===id_sem);

  document.getElementById('res-title').textContent = `Casos año a la fecha — ${{sem?.nombre||''}}${{regFiltro?' · '+regFiltro:''}}`;

  const totalCasos  = filas.reduce((a,r)=>a+(r.casos_anno_fecha||0),0);
  const totalSemana = filas.reduce((a,r)=>a+(r.casos_ultima_semana||0),0);
  const varArr   = filas.filter(r=>r.var_anno_fecha!==null);
  const varProm  = varArr.length ? varArr.reduce((a,r)=>a+r.var_anno_fecha,0)/varArr.length : 0;
  const tasaArr  = filas.filter(r=>r.tasa_registro!==null);
  const tasaProm = tasaArr.length ? tasaArr.reduce((a,r)=>a+r.tasa_registro,0)/tasaArr.length : 0;

  document.getElementById('kpi-resumen').innerHTML = `
    <div class="kpi azul"><div class="kpi-label">Casos año a la fecha</div><div class="kpi-value">${{num(totalCasos)}}</div><div class="kpi-sub">${{regFiltro||'Total nacional'}}</div></div>
    <div class="kpi ${{varProm<0?'verde':'rojo'}}"><div class="kpi-label">Variación año a la fecha</div><div class="kpi-value">${{fmtCambio(varProm)}}</div><div class="kpi-sub">${{regFiltro?regFiltro:'Promedio regional'}}</div></div>
    <div class="kpi azul"><div class="kpi-label">Casos última semana</div><div class="kpi-value">${{num(totalSemana)}}</div><div class="kpi-sub">${{regFiltro||'Nacional'}}</div></div>
    <div class="kpi amber"><div class="kpi-label">Tasa por 100 mil hab.</div><div class="kpi-value">${{tasaProm.toFixed(1)}}</div><div class="kpi-sub">${{regFiltro?regFiltro:'Promedio regional'}}</div></div>
  `;

  const cols = ['Región','Casos año a la fecha','Var. año %','Casos sem. actual','Tasa/100mil','Principal delito'];
  let thead = '<thead><tr>' + cols.map((c,i)=>
    i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('tabla-resumen',${{i}})">${{c}}</th>`
  ).join('') + '</tr></thead>';

  let tbody = '<tbody>';
  filas.sort((a,b)=>(b.casos_anno_fecha||0)-(a.casos_anno_fecha||0)).forEach(r => {{
    const cc = clsCambio(r.var_anno_fecha);
    tbody += `<tr>
      <td>${{r.nombre_region}}</td>
      <td>${{num(r.casos_anno_fecha)}}</td>
      <td class="${{cc}}">${{fmtCambio(r.var_anno_fecha)}}</td>
      <td>${{num(r.casos_ultima_semana)}}</td>
      <td>${{r.tasa_registro?.toFixed(1)||'—'}}</td>
      <td style="text-align:left;font-size:11px">${{r.mayor_registro_1||'—'}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('tabla-resumen').innerHTML = thead + tbody;

  const sorted = [...filas].sort((a,b)=>(b.tasa_registro||0)-(a.tasa_registro||0));
  makeBarSeg('chart-tasa',
    sorted.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [{{label:'Tasa/100mil hab.',
      data: sorted.map(r=>r.tasa_registro),
      backgroundColor: sorted.map(r=>r.tasa_registro>500?'rgba(220,38,38,.8)':r.tasa_registro>400?'rgba(217,119,6,.8)':'rgba(22,163,74,.8)'),
      borderRadius:3}}],
    {{horizontal:true}});

  const delitoCount = {{}};
  filas.forEach(r=>{{if(r.mayor_registro_1) delitoCount[r.mayor_registro_1]=(delitoCount[r.mayor_registro_1]||0)+1;}});
  const delSorted = Object.entries(delitoCount).sort((a,b)=>b[1]-a[1]);
  makeBarSeg('chart-delitos',
    delSorted.map(d=>d[0].length>30?d[0].substring(0,30)+'...':d[0]),
    [{{label:'Nº regiones',data:delSorted.map(d=>d[1]),backgroundColor:'rgba(37,99,235,.75)',borderRadius:3}}],
    {{horizontal:true}});
}}

// ── Evolución seg ─────────────────────────────────────────────
function renderEvolucionSeg() {{
  const region = document.getElementById('evo-seg-region').value;
  const ind    = document.getElementById('evo-seg-ind').value;
  const filas  = datosParaRegionSeg(region);
  const labels = filas.map(r => r.semana);
  const vals   = filas.map(r => r[ind]);
  const indLabels = {{
    casos_anno_fecha:'Casos año a la fecha', tasa_registro:'Tasa por 100 mil hab.',
    casos_ultima_semana:'Casos última semana', casos_28dias:'Casos últimos 28 días',
    var_anno_fecha:'Variación % año a la fecha',
  }};
  document.getElementById('evo-seg-title').textContent = `${{region}} — ${{indLabels[ind]}}`;
  const esVar = ind==='var_anno_fecha';
  makeBarSeg('chart-evo-seg', labels,
    [{{label:indLabels[ind], data:vals,
      backgroundColor:esVar?vals.map(v=>v===null?'#ccc':v<0?'rgba(22,163,74,.8)':'rgba(220,38,38,.8)'):'rgba(22,163,74,.75)',
      borderRadius:3}}]);

  document.getElementById('evo-delitos-title').textContent = `${{region}} — top delitos por semana (% del total)`;
  const delitos = ['mayor_registro_1','mayor_registro_2','mayor_registro_3','mayor_registro_4','mayor_registro_5'];
  const pcts    = ['pct_1','pct_2','pct_3','pct_4','pct_5'];
  const coloresD = ['rgba(22,163,74,.8)','rgba(37,99,235,.8)','rgba(217,119,6,.8)','rgba(220,38,38,.8)','rgba(147,51,234,.8)'];
  const todosDelitos = [...new Set(filas.flatMap(r=>delitos.map(d=>r[d]).filter(Boolean)))];
  const datasets = todosDelitos.slice(0,5).map((del,i) => {{
    const data = filas.map(r => {{ const idx=delitos.findIndex(d=>r[d]===del); return idx>=0?r[pcts[idx]]:null; }});
    return {{label:del.length>35?del.substring(0,35)+'...':del, data, backgroundColor:coloresD[i], borderRadius:2}};
  }});
  makeBarSeg('chart-evo-delitos', labels, datasets);
}}

// ── Operativo ─────────────────────────────────────────────────
function renderOperativo() {{
  const id_sem = parseInt(document.getElementById('op-semana').value);
  const filas  = datosParaSemana(id_sem);
  const totCtrl   = filas.reduce((a,r)=>a+(r.controles||0),0);
  const totFisc   = filas.reduce((a,r)=>a+(r.fiscalizaciones||0),0);
  const totIncaut = filas.reduce((a,r)=>a+(r.incautaciones||0),0);
  const totDecom  = filas.filter(r=>r.decomisos_anno!==null).reduce((a,r)=>a+(r.decomisos_anno||0),0);
  document.getElementById('kpi-op').innerHTML = `
    <div class="kpi azul"><div class="kpi-label">Controles realizados</div><div class="kpi-value">${{num(totCtrl)}}</div><div class="kpi-sub">Identidad + vehicular</div></div>
    <div class="kpi azul"><div class="kpi-label">Fiscalizaciones</div><div class="kpi-value">${{num(totFisc)}}</div><div class="kpi-sub">Alcohol + bancaria</div></div>
    <div class="kpi rojo"><div class="kpi-label">Incautaciones armas</div><div class="kpi-value">${{num(totIncaut)}}</div><div class="kpi-sub">Fuego + blancas</div></div>
    <div class="kpi amber"><div class="kpi-label">Decomisos drogas</div><div class="kpi-value">${{num(Math.round(totDecom))}}</div><div class="kpi-sub">Año a la fecha</div></div>
  `;
  const sorted = [...filas].sort((a,b)=>(b.controles||0)-(a.controles||0));
  makeBarSeg('chart-controles',
    sorted.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [
      {{label:'Identidad', data:sorted.map(r=>r.controles_identidad), backgroundColor:'rgba(37,99,235,.75)',borderRadius:2}},
      {{label:'Vehicular', data:sorted.map(r=>r.controles_vehicular), backgroundColor:'rgba(22,163,74,.75)',borderRadius:2}},
    ], {{horizontal:true}});
  const sorted2 = [...filas].sort((a,b)=>(b.incautaciones||0)-(a.incautaciones||0));
  makeBarSeg('chart-incaut',
    sorted2.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [
      {{label:'Armas de fuego', data:sorted2.map(r=>r.incaut_fuego), backgroundColor:'rgba(220,38,38,.75)',borderRadius:2}},
      {{label:'Armas blancas', data:sorted2.map(r=>r.incaut_blancas), backgroundColor:'rgba(217,119,6,.75)',borderRadius:2}},
    ], {{horizontal:true}});
}}


// ══════════════════════════════════════════════════════════════
// DMCS — Delitos de Mayor Connotación Social
// ══════════════════════════════════════════════════════════════

// Nombres exactos como vienen en el JSON de LeyStop
const DMCS_LISTA = [
  'HOMICIDIOS Y FEMICIDIOS',
  'VIOLACIONES Y DELITOS SEXUALES',
  'LESIONES GRAVES',
  'LESIONES MENOS GRAVES',
  'LESIONES LEVES',
  'ROBOS CON VIOLENCIA E INTIMIDACIÓN',
  'ROBOS POR SORPRESA',
  'ROBOS EN LUGARES HABITADOS Y NO HABITADOS',
  'ROBOS DE VEHÍCULOS Y SUS ACCESORIOS',
  'OTROS ROBOS CON FUERZA EN LAS COSAS',
  'HURTOS',
];

const DMCS_COLORES = [
  'rgba(220,38,38,.8)','rgba(190,24,93,.8)','rgba(234,88,12,.8)',
  'rgba(202,138,4,.8)','rgba(101,163,13,.8)','rgba(5,150,105,.8)',
  'rgba(6,182,212,.8)','rgba(37,99,235,.8)','rgba(99,102,241,.8)',
  'rgba(147,51,234,.8)','rgba(236,72,153,.8)',
];

// Helpers para acceder a DELITOS
function delitosPorSemanaRegion(id_semana, nombre_region) {{
  return DELITOS.datos.filter(d => d.id_semana === id_semana &&
    (nombre_region === '' || d.nombre_region === nombre_region));
}}

function dmcsPorSemanaRegion(id_semana, nombre_region) {{
  return delitosPorSemanaRegion(id_semana, nombre_region).filter(d => d.es_dmcs === 1);
}}

function renderDMCS() {{
  if(!DELITOS.tiene_datos) {{
    document.getElementById('kpi-dmcs').innerHTML =
      '<div style="padding:20px;color:#999;font-size:13px">⚠ La tabla de delitos desagregados aún no existe. Corre <strong>actualizar_datos.py</strong> para poblarla.</div>';
    return;
  }}

  const id_sem    = parseInt(document.getElementById('dmcs-semana').value);
  const regFiltro = document.getElementById('dmcs-region').value;
  const delFiltro = document.getElementById('dmcs-delito').value;
  const sem       = SEG.semanas.find(s => s.id_semana === id_sem);

  // Datos de todos los delitos para la semana/región seleccionada
  const todosDelitos = delitosPorSemanaRegion(id_sem, regFiltro);
  const soloDmcs     = todosDelitos.filter(d => d.es_dmcs === 1);

  // Totales DMCS nacionales o de la región
  const totalDmcsAnno = soloDmcs.reduce((a,d) => a + (d.anno_fecha||0), 0);
  const totalDmcsAnt  = soloDmcs.reduce((a,d) => a + (d.anno_fecha_ant||0), 0);
  const varDmcs       = totalDmcsAnt > 0 ? ((totalDmcsAnno - totalDmcsAnt) / totalDmcsAnt * 100) : null;
  const totalDmcsSem  = soloDmcs.reduce((a,d) => a + (d.ultima_semana||0), 0);
  const totalDmcs28   = soloDmcs.reduce((a,d) => a + (d.dias28||0), 0);

  // Total de todos los delitos (para calcular % DMCS)
  const totalTodosAnno = todosDelitos.reduce((a,d) => a + (d.anno_fecha||0), 0);
  const pctDmcs = totalTodosAnno > 0 ? (totalDmcsAnno / totalTodosAnno * 100) : 0;

  // Regiones con datos de DMCS
  const regionesConDatos = [...new Set(soloDmcs.map(d => d.nombre_region))];

  document.getElementById('kpi-dmcs').innerHTML =
    `<div class="kpi rojo"><div class="kpi-label">DMCS año a la fecha</div><div class="kpi-value">${{num(totalDmcsAnno)}}</div><div class="kpi-sub">${{regFiltro||'Total nacional'}}</div></div>`+
    `<div class="kpi ${{varDmcs===null?'azul':varDmcs<0?'verde':'rojo'}}"><div class="kpi-label">Variación vs año anterior</div><div class="kpi-value">${{fmtCambio(varDmcs)}}</div><div class="kpi-sub">año a la fecha</div></div>`+
    `<div class="kpi amber"><div class="kpi-label">DMCS última semana</div><div class="kpi-value">${{num(totalDmcsSem)}}</div><div class="kpi-sub">${{sem?.nombre||''}}</div></div>`+
    `<div class="kpi azul"><div class="kpi-label">% del total de delitos</div><div class="kpi-value">${{pctDmcs.toFixed(1)}}%</div><div class="kpi-sub">son DMCS (año a la fecha)</div></div>`;

  // ── Títulos dinámicos ──
  const tituloBase = `${{sem?.nombre||''}}${{regFiltro?' · '+regFiltro:' · Nacional'}}`;
  document.getElementById('dmcs-chart-bar-title').textContent = `DMCS por tipo — ${{tituloBase}}`;
  document.getElementById('dmcs-chart-pie-title').textContent = `Distribución DMCS — ${{tituloBase}}`;
  document.getElementById('dmcs-tabla-title').textContent     = `Detalle DMCS por región — ${{tituloBase}}`;
  document.getElementById('dmcs-evo-title').textContent       = `Evolución semanal DMCS${{regFiltro?' · '+regFiltro:''}}`;

  // ── Gráfico barras: DMCS por tipo (año a la fecha) ──
  const dmcsFiltrados = delFiltro
    ? soloDmcs.filter(d => d.nombre_delito === delFiltro)
    : soloDmcs;

  // Agrupar por nombre_delito y sumar anno_fecha
  const sumaPorDelito = {{}};
  const sumaAntPorDelito = {{}};
  dmcsFiltrados.forEach(d => {{
    sumaPorDelito[d.nombre_delito]    = (sumaPorDelito[d.nombre_delito]||0)    + (d.anno_fecha||0);
    sumaAntPorDelito[d.nombre_delito] = (sumaAntPorDelito[d.nombre_delito]||0) + (d.anno_fecha_ant||0);
  }});

  const dmcsOrdenados = Object.entries(sumaPorDelito).sort((a,b) => b[1]-a[1]);
  const barLabels = dmcsOrdenados.map(([k]) => k.length>35 ? k.substring(0,35)+'…' : k);
  const barVals   = dmcsOrdenados.map(([,v]) => v);
  const barValsAnt= dmcsOrdenados.map(([k]) => sumaAntPorDelito[k]||0);

  destroyChart('chart-dmcs-regiones');
  const ctxBar = document.getElementById('chart-dmcs-regiones');
  if(ctxBar) {{
    charts['chart-dmcs-regiones'] = new Chart(ctxBar, {{
      type: 'bar',
      data: {{
        labels: barLabels,
        datasets: [
          {{label:'2026 (año a la fecha)', data:barVals,
            backgroundColor: dmcsOrdenados.map((_,i)=>DMCS_COLORES[i%DMCS_COLORES.length]),
            borderRadius:3}},
          {{label:'2025 (año a la fecha)', data:barValsAnt,
            backgroundColor: 'rgba(156,163,175,.5)', borderRadius:3}},
        ]
      }},
      plugins: [ChartDataLabels],
      options: {{
        responsive:true, maintainAspectRatio:true, indexAxis:'y',
        plugins:{{
          legend:{{display:true,position:'bottom',labels:{{font:{{size:11}},padding:10}}}},
          tooltip:{{mode:'index',intersect:false}},
          datalabels:{{
            display: ctx => ctx.datasetIndex===0 && ctx.dataset.data[ctx.dataIndex]>0,
            color:'#333', font:{{size:9,weight:'600'}},
            anchor:'end', align:'end', clamp:true,
            formatter: v => v>0 ? Math.round(v).toLocaleString('es-CL') : '',
          }}
        }},
        scales:{{
          x:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}},
          y:{{ticks:{{font:{{size:10}},maxRotation:0}}}}
        }}
      }}
    }});
  }}

  // ── Gráfico pie: distribución de DMCS ──
  destroyChart('chart-dmcs-pie');
  const ctxPie = document.getElementById('chart-dmcs-pie');
  if(ctxPie && dmcsOrdenados.length > 0) {{
    charts['chart-dmcs-pie'] = new Chart(ctxPie, {{
      type:'doughnut',
      data:{{
        labels: dmcsOrdenados.map(([k]) => k.length>30?k.substring(0,30)+'…':k),
        datasets:[{{
          data: dmcsOrdenados.map(([,v])=>v),
          backgroundColor: dmcsOrdenados.map((_,i)=>DMCS_COLORES[i%DMCS_COLORES.length]),
          borderWidth:2, borderColor:'#fff'
        }}]
      }},
      plugins:[ChartDataLabels],
      options:{{
        responsive:true, maintainAspectRatio:true,
        plugins:{{
          legend:{{position:'right',labels:{{font:{{size:10}},padding:8}}}},
          tooltip:{{callbacks:{{label:ctx=>`${{ctx.label}}: ${{Math.round(ctx.parsed).toLocaleString('es-CL')}}`}}}},
          datalabels:{{
            display: ctx => ctx.dataset.data[ctx.dataIndex] > 0,
            color:'#fff', font:{{size:9,weight:'700'}},
            formatter: (v,ctx) => {{
              const total = ctx.dataset.data.reduce((a,b)=>a+b,0);
              return total>0?(v/total*100).toFixed(1)+'%':'';
            }}
          }}
        }}
      }}
    }});
  }}

  // ── Tabla: DMCS por región ──
  // Agrupar por región y delito
  const porRegion = {{}};
  soloDmcs.forEach(d => {{
    if(!porRegion[d.nombre_region]) porRegion[d.nombre_region] = [];
    porRegion[d.nombre_region].push(d);
  }});

  const cols = ['Región','Total DMCS año','Var. %','DMCS última sem.','DMCS 28 días','Delito más grave'];
  let thead = '<thead><tr>'+cols.map((c,i)=>
    i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('tabla-dmcs',${{i}})">${{c}}</th>`
  ).join('')+'</tr></thead>';
  let tbody = '<tbody>';

  const regionesOrdenadas = Object.entries(porRegion)
    .sort((a,b) => b[1].reduce((s,d)=>s+(d.anno_fecha||0),0) - a[1].reduce((s,d)=>s+(d.anno_fecha||0),0));

  regionesOrdenadas.forEach(([reg, delitos]) => {{
    const totAnno  = delitos.reduce((s,d)=>s+(d.anno_fecha||0),0);
    const totAnt   = delitos.reduce((s,d)=>s+(d.anno_fecha_ant||0),0);
    const varR     = totAnt>0 ? ((totAnno-totAnt)/totAnt*100) : null;
    const totSem   = delitos.reduce((s,d)=>s+(d.ultima_semana||0),0);
    const tot28    = delitos.reduce((s,d)=>s+(d.dias28||0),0);
    // Delito con mayor umbral (más alarmante)
    const masGrave = [...delitos].sort((a,b)=>(b.umbral||0)-(a.umbral||0))[0];
    const cc = clsCambio(varR);
    const umbralCls = masGrave?.umbral > 1.5 ? 'neg' : masGrave?.umbral > 0.5 ? 'amber' : '';
    tbody += `<tr>
      <td>${{reg}}</td>
      <td>${{num(totAnno)}}</td>
      <td class="${{cc}}">${{fmtCambio(varR)}}</td>
      <td>${{num(totSem)}}</td>
      <td>${{num(tot28)}}</td>
      <td style="text-align:left;font-size:11px" class="${{umbralCls}}">${{masGrave?masGrave.nombre_delito:'—'}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('tabla-dmcs').innerHTML = thead+tbody;

  // ── Gráfico evolución — llamar función separada para poder re-renderizar ──
  renderDMCSEvo();
}}

// ── Función dedicada al gráfico de evolución (permite refrescar sin re-render completo) ──
function renderDMCSEvo() {{
  const delFiltro  = document.getElementById('dmcs-delito').value;
  const regFiltro  = document.getElementById('dmcs-region').value;
  const metrica    = document.getElementById('dmcs-evo-metrica')?.value || 'ultima_semana';
  const comparar   = document.getElementById('dmcs-evo-comparar')?.value || 'no';

  // Mapeo de campo: año actual vs campo año anterior en el mismo registro
  const campoActual = metrica;                   // ultima_semana | dias28 | anno_fecha
  const campoAnt    = metrica + '_ant';          // ultima_semana_ant | dias28_ant | anno_fecha_ant

  const metricaLabel = {{
    ultima_semana: 'Casos última semana',
    dias28:        'Casos últimos 28 días',
    anno_fecha:    'Casos año a la fecha',
  }}[metrica] || metrica;

  const semanasEvo = SEG.semanas;
  const evoLabels  = semanasEvo.map(s => s.semana);

  // Años disponibles en los datos para el título
  const annoActual = semanasEvo.length ? (semanasEvo[semanasEvo.length-1].anno || '') : '';
  const annoAnt    = annoActual ? annoActual - 1 : '';

  document.getElementById('dmcs-evo-title').textContent =
    `Evolución semanal DMCS — ${{metricaLabel}}${{regFiltro?' · '+regFiltro:''}}`;
  document.getElementById('dmcs-evo-nota').textContent =
    comparar === 'si'
      ? `Línea sólida = ${{annoActual}} · Línea punteada = ${{annoAnt}} (dato "año anterior" guardado en cada registro).`
      : '';

  const dmcsParaEvo = delFiltro ? [delFiltro] : DMCS_LISTA.slice(0, 6);

  const evoDatasets = [];

  dmcsParaEvo.forEach((nombreDmcs, i) => {{
    const color = DMCS_COLORES[DMCS_LISTA.indexOf(nombreDmcs) % DMCS_COLORES.length];
    const labelBase = nombreDmcs.length > 28 ? nombreDmcs.substring(0,28)+'…' : nombreDmcs;

    // ── Año actual ──
    const dataActual = semanasEvo.map(s => {{
      const filas = DELITOS.datos.filter(d =>
        d.id_semana === s.id_semana &&
        d.nombre_delito === nombreDmcs &&
        (regFiltro === '' || d.nombre_region === regFiltro)
      );
      return filas.reduce((a, d) => a + (d[campoActual] || 0), 0);
    }});

    evoDatasets.push({{
      label: comparar === 'si' ? `${{labelBase}} (${{annoActual}})` : labelBase,
      data: dataActual,
      borderColor: color,
      backgroundColor: color.replace('.8)', '.08)'),
      fill: dmcsParaEvo.length === 1,  // Área solo si es un único delito
      tension: .35,
      pointRadius: semanasEvo.length > 20 ? 2 : 4,
      pointHoverRadius: 6,
      borderWidth: 2.5,
      borderDash: [],
    }});

    // ── Año anterior (si está activado) ──
    if(comparar === 'si') {{
      const dataAnt = semanasEvo.map(s => {{
        const filas = DELITOS.datos.filter(d =>
          d.id_semana === s.id_semana &&
          d.nombre_delito === nombreDmcs &&
          (regFiltro === '' || d.nombre_region === regFiltro)
        );
        return filas.reduce((a, d) => a + (d[campoAnt] || 0), 0);
      }});

      evoDatasets.push({{
        label: `${{labelBase}} (${{annoAnt}})`,
        data: dataAnt,
        borderColor: color,
        backgroundColor: 'transparent',
        fill: false,
        tension: .35,
        pointRadius: semanasEvo.length > 20 ? 1 : 3,
        pointHoverRadius: 5,
        borderWidth: 1.5,
        borderDash: [6, 3],  // Línea punteada para año anterior
      }});
    }}
  }});

  destroyChart('chart-dmcs-evo');
  const ctxEvo = document.getElementById('chart-dmcs-evo');
  if(!ctxEvo) return;

  charts['chart-dmcs-evo'] = new Chart(ctxEvo, {{
    type: 'line',
    data: {{labels: evoLabels, datasets: evoDatasets}},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      interaction: {{mode: 'index', intersect: false}},
      plugins: {{
        legend: {{
          display: true,
          position: 'bottom',
          labels: {{
            font: {{size: 10}},
            padding: 10,
            usePointStyle: true,
            // Diferenciar visualmente sólido vs punteado en la leyenda
            generateLabels: chart => {{
              return chart.data.datasets.map((ds, i) => ({{
                text: ds.label,
                fillStyle: ds.borderColor,
                strokeStyle: ds.borderColor,
                lineWidth: ds.borderWidth,
                lineDash: ds.borderDash || [],
                hidden: !chart.isDatasetVisible(i),
                datasetIndex: i,
              }}));
            }}
          }}
        }},
        tooltip: {{
          mode: 'index',
          intersect: false,
          callbacks: {{
            label: ctx => ` ${{ctx.dataset.label}}: ${{Math.round(ctx.parsed.y).toLocaleString('es-CL')}}`,
          }}
        }},
        datalabels: {{display: false}},
      }},
      scales: {{
        x: {{
          ticks: {{font: {{size: 10}}, maxRotation: 55, autoSkip: true, maxTicksLimit: 20}},
          grid: {{display: false}},
        }},
        y: {{
          ticks: {{font: {{size: 10}}}},
          grid: {{color: '#f0f0f0'}},
          title: {{display: true, text: metricaLabel, font: {{size: 10}}}},
          beginAtZero: true,
        }}
      }}
    }}
  }});
}}

// ══════════════════════════════════════════════════════════════
// PIB — helpers
// ══════════════════════════════════════════════════════════════
// Todos los indicadores usan volumen encadenado (precios año anterior, series empalmadas)
const PIB_INDICADORES = {{
  anual: [
    {{v:'miles_enc', l:'Miles de millones de pesos encadenados (vol.)'}},
    {{v:'peso_enc',  l:'Peso % del PIB nacional (encadenados)'}},
  ],
  trimestral: [
    {{v:'var_pct',   l:'Variación % vs mismo trimestre año anterior'}},
    {{v:'miles_enc', l:'Miles de millones de pesos encadenados (vol.)'}},
    {{v:'peso_enc',  l:'Peso % del PIB nacional (encadenados)'}},
  ]
}};

const DISP = {{
  'PIB':'Producto interno bruto',
  'PIB Producción de bienes':'Producción de bienes',
  'PIB Minería':'  Minería',
  'PIB Industria manufacturera':'  Industria manufacturera',
  'PIB Resto de bienes':'  Resto de bienes',
  'PIB Comercio':'Comercio',
  'PIB Servicios':'Servicios',
  'PIB Agropecuario-silvícola':'Agropecuario-silvícola',
  'PIB Construcción':'Construcción',
  'PIB Servicios financieros y empresariales':'Servicios financieros',
  'PIB Servicios personales':'Servicios personales',
  'PIB Administración pública':'Administración pública',
  'PIB Restaurantes y hoteles':'Restaurantes y hoteles',
  'PIB Electricidad, gas y agua':'Electricidad, gas y agua',
  'PIB Pesca':'Pesca',
}};

let regionPibActual = '';

function skPib(t) {{
  if(String(t).includes('.')){{const[tr,yr]=t.split('.');return parseInt(yr)*10+({{'I':1,'II':2,'III':3,'IV':4}}[tr]||0);}}
  const n=parseInt(t); return isNaN(n)?99999:n*10;
}}
function filtrarPib(ps, desde, hasta) {{
  return ps.filter(t=>{{const yr=String(t).includes('.')?parseInt(t.split('.')[1]):parseInt(t);return yr>=parseInt(desde)&&yr<=parseInt(hasta);}});
}}
function getCorr(sector,region,t)  {{ try{{return PIB.datos_corr[sector][region][t]??null;}}catch{{return null;}} }}
function getTrim(sector,clave,region,t) {{ try{{return PIB.datos_trim[sector][clave][region][t]??null;}}catch{{return null;}} }}
// getValPib: siempre usa encadenados.
// - freq anual:      lee PIB.datos_enc_anual (volumen, series empalmadas)
// - freq trimestral: lee PIB.datos_trim (encadenados trimestrales)
// ind: 'miles_enc' → valor nominal encadenado | 'var_pct' → variación % | 'peso_enc' → % nac.
function getValPib(sector,ind,region,t) {{
  // Determinar si el período es trimestral (contiene '.') o anual
  const esTrim = String(t).includes('.');
  if(esTrim) {{
    return getTrim(sector, ind==='peso_enc'?'miles_enc':ind, region, t);
  }} else {{
    // Anual: siempre encadenados
    try {{ return PIB.datos_enc_anual[sector][region][t]??null; }} catch{{ return null; }}
  }}
}}
function getEncAnual(sector,region,t) {{
  try {{ return PIB.datos_enc_anual[sector][region][t]??null; }} catch{{ return null; }}
}}
function getPIBNacional(ind,t) {{
  const esTrim = String(t).includes('.');
  if(esTrim) {{
    const sub=PIB.subtotal_trim_enc[t]??null, ext=PIB.extra_trim_enc[t]??null;
    if(sub===null&&ext===null) return null;
    return (sub||0)+(ext||0);
  }} else {{
    // Anual: encadenados
    const sub=PIB.subtotal_enc_anual[t]??null, ext=PIB.extra_enc_anual[t]??null;
    if(sub===null&&ext===null) return null;
    return (sub||0)+(ext||0);
  }}
}}
function calcPeso(sector,ind,region,t) {{
  // % del sector sobre PIB REGIONAL — siempre en encadenados para coherencia
  const esTrim = String(t).includes('.');
  const v   = esTrim ? getTrim(sector,'miles_enc',region,t) : getEncAnual(sector,region,t);
  const tot = esTrim ? getTrim('PIB','miles_enc',region,t)  : getEncAnual('PIB',region,t);
  if(v===null||!tot||tot===0) return null;
  return (v/tot)*100;
}}
function calcPesoNacional(region,ind,t) {{
  const esTrim = String(t).includes('.');
  const v   = esTrim ? getTrim('PIB','miles_enc',region,t) : getEncAnual('PIB',region,t);
  const total = getPIBNacional(ind,t);
  if(v===null||!total) return null; return (v/total)*100;
}}
function fmtPib(v,ind) {{
  if(v===null||v===undefined) return '—';
  if(['var_pct','peso_enc'].includes(ind)) return v.toFixed(2)+'%';
  if(ind==='cagr') return (v>0?'+':'')+v.toFixed(2)+'%';
  return Math.round(v).toLocaleString('es-CL');
}}
function colorClsPib(v,ind) {{
  if(!['var_pct','peso_enc','cagr'].includes(ind)) return '';
  return v>0?'pos':v<0?'neg':'';
}}
function getPeriodosPib(freq) {{ return freq==='anual'?PIB.años_enc_anual:PIB.trimestres; }}
function getSectoresPib(freq) {{ return freq==='anual'?PIB.sectores_corr:PIB.sectores_trim; }}
function getAñosPib(freq) {{ return freq==='anual'?PIB.años_enc_anual:PIB.años_trim; }}

function setRegionPib(r) {{
  regionPibActual = r;
  if(pibTabActual==='evolucion') renderEvolucionPib();
  if(pibTabActual==='sectores')  renderSectores();
}}

function poblarIndicadoresPib(prefix, freq) {{
  const sel=document.getElementById(prefix+'-ind');
  const prev=sel.value; sel.innerHTML='';
  PIB_INDICADORES[freq].forEach(o=>{{const opt=document.createElement('option');opt.value=o.v;opt.textContent=o.l;sel.appendChild(opt);}});
  sel.value=PIB_INDICADORES[freq].some(o=>o.v===prev)?prev:PIB_INDICADORES[freq][0].v;
}}
function poblarAñosPib(prefix, lista, n=6) {{
  ['desde','hasta'].forEach((s,i)=>{{
    const sel=document.getElementById(prefix+'-'+s),prev=sel.value;sel.innerHTML='';
    lista.forEach(a=>{{const o=document.createElement('option');o.value=a;o.textContent=a;sel.appendChild(o);}});
    sel.value=i===0?(lista.includes(prev)?prev:lista[Math.max(0,lista.length-n)]):(lista.includes(prev)?prev:lista[lista.length-1]);
  }});
}}
function onFreqChange(prefix) {{
  const freq=document.getElementById(prefix+'-freq').value;
  poblarIndicadoresPib(prefix,freq);
  poblarAñosPib(prefix,getAñosPib(freq),prefix==='pib-evo'?8:6);
  if(prefix==='pib-evo') renderEvolucionPib();
  if(prefix==='pib-sec') renderSectores();
  if(prefix==='pib-res') renderResumenPib();
}}

// ── Evolución PIB ─────────────────────────────────────────────
function renderEvolucionPib() {{
  const freq  = document.getElementById('pib-evo-freq').value;
  const ind   = document.getElementById('pib-evo-ind').value;
  const desde = document.getElementById('pib-evo-desde').value;
  const hasta = document.getElementById('pib-evo-hasta').value;
  const ps    = filtrarPib(getPeriodosPib(freq),desde,hasta);
  const lbl   = PIB_INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  document.getElementById('pib-evo-title').textContent = 'PIB — '+lbl;

  if(!regionPibActual) {{
    document.getElementById('pib-kpi-evo').innerHTML='<p style="color:#aaa;font-size:13px;padding:8px">Selecciona una región</p>';
    return;
  }}

  const esPeso = ind === 'peso_enc';
  const vals   = esPeso ? ps.map(t=>calcPesoNacional(regionPibActual,ind,t)) : ps.map(t=>getValPib('PIB',ind,regionPibActual,t));
  const noNull = vals.filter(v=>v!==null);
  const ultimo = noNull[noNull.length-1];
  const lUlt   = ps.filter((_,i)=>vals[i]!==null).slice(-1)[0];
  const prev   = freq==='anual'?noNull[noNull.length-2]:noNull[noNull.length-5];
  const lPrev  = freq==='anual'?ps.filter((_,i)=>vals[i]!==null).slice(-2)[0]:ps.filter((_,i)=>vals[i]!==null).slice(-5)[0];
  const prom   = noNull.length?noNull.reduce((a,b)=>a+b,0)/noNull.length:null;
  const cagr   = calcCAGR('PIB', regionPibActual, desde, hasta, freq);

  let kh='';
  if(ultimo!==null) kh+=`<div class="kpi ${{ind==='var_pct'?(ultimo>=0?'verde':'rojo'):''}}"><div class="kpi-label">Último período</div><div class="kpi-value">${{fmtPib(ultimo,ind)}}</div><div class="kpi-sub">${{lUlt||''}}</div></div>`;
  if(prev!==null)   kh+=`<div class="kpi ${{ind==='var_pct'?(prev>=0?'verde':'rojo'):''}}"><div class="kpi-label">${{freq==='anual'?'Año anterior':'Mismo trim. año ant.'}}</div><div class="kpi-value">${{fmtPib(prev,ind)}}</div><div class="kpi-sub">${{lPrev||''}}</div></div>`;
  if(prom!==null&&!esPeso) kh+=`<div class="kpi"><div class="kpi-label">Promedio período</div><div class="kpi-value">${{fmtPib(prom,ind)}}</div><div class="kpi-sub">${{desde}}–${{hasta}}</div></div>`;
  if(cagr!==null) kh+=`<div class="kpi ${{cagr>=0?'verde':'rojo'}}"><div class="kpi-label">CAGR (vol. encadenado)</div><div class="kpi-value">${{fmtPib(cagr,'cagr')}}</div><div class="kpi-sub">${{desde}}–${{hasta}}</div></div>`;
  document.getElementById('pib-kpi-evo').innerHTML=kh;

  const bg=vals.map(v=>{{if(v===null)return'rgba(0,0,0,0)';if(['var_pct','peso_enc','peso_corr'].includes(ind))return v>=0?'rgba(22,163,74,.75)':'rgba(220,38,38,.75)';return'rgba(37,99,235,.75)';}});
  makeBarPib('pib-chart-evo',ps,[{{label:lbl,data:vals,backgroundColor:bg,borderRadius:3}}]);
}}

// ── Variación interanual encadenada ──────────────────────────
// Calcula var% real (encadenados) de un sector/región respecto al año anterior.
// Anual:      enc[año]  / enc[año-1]  - 1
// Trimestral: enc[Trim.Año] / enc[Trim.Año-1] - 1
function calcVarEnc(sector, region, t) {{
  const esTrim = String(t).includes('.');
  if(esTrim) {{
    const [trim, yr] = t.split('.');
    const tAnt = `${{trim}}.${{parseInt(yr)-1}}`;
    const v1 = getTrim(sector,'miles_enc',region,t);
    const v0 = getTrim(sector,'miles_enc',region,tAnt);
    if(v1===null||v0===null||v0===0) return null;
    return (v1/v0 - 1)*100;
  }} else {{
    const v1 = getEncAnual(sector,region,t);
    const v0 = getEncAnual(sector,region,String(parseInt(t)-1));
    if(v1===null||v0===null||v0===0) return null;
    return (v1/v0 - 1)*100;
  }}
}}
// Variación interanual para el total nacional (subtotal+extrarregional)
function calcVarNacional(t) {{
  const esTrim = String(t).includes('.');
  const v1 = getPIBNacional('miles_enc',t);
  let tAnt;
  if(esTrim) {{
    const [trim,yr] = t.split('.');
    tAnt = `${{trim}}.${{parseInt(yr)-1}}`;
  }} else {{
    tAnt = String(parseInt(t)-1);
  }}
  const v0 = getPIBNacional('miles_enc',tAnt);
  if(v1===null||v0===null||v0===0) return null;
  return (v1/v0 - 1)*100;
}}
// Variación para extrarregional
function calcVarExtra(t) {{
  const esTrim = String(t).includes('.');
  const v1 = esTrim ? (PIB.extra_trim_enc[t]??null) : (PIB.extra_enc_anual[t]??null);
  let tAnt;
  if(esTrim) {{ const [tr,yr]=t.split('.'); tAnt=`${{tr}}.${{parseInt(yr)-1}}`; }}
  else {{ tAnt = String(parseInt(t)-1); }}
  const v0 = esTrim ? (PIB.extra_trim_enc[tAnt]??null) : (PIB.extra_enc_anual[tAnt]??null);
  if(v1===null||v0===null||v0===0) return null;
  return (v1/v0 - 1)*100;
}}

// ── CAGR helper ───────────────────────────────────────────────
// Calcula CAGR usando siempre encadenados (miles_enc) sin importar el ind activo.
// Para freq anual: usa datos_enc_anual directamente.
// Para freq trimestral: suma los 4 trimestres del primer y último año del rango
//   para construir un valor anual comparable, luego aplica CAGR.
function calcCAGR(sector, region, desde, hasta, freq) {{
  if(freq === 'anual') {{
    const v0 = getEncAnual(sector, region, desde);
    const v1 = getEncAnual(sector, region, hasta);
    const n  = parseInt(hasta) - parseInt(desde);
    if(v0===null||v1===null||v0===0||n<=0) return null;
    return (Math.pow(v1/v0, 1/n) - 1) * 100;
  }} else {{
    // Trimestral: sumar los 4 trimestres del año inicial y final
    const sumaAnio = (yr) => {{
      const ts = ['I','II','III','IV'].map(t => `${{t}}.${{yr}}`);
      const vals = ts.map(t => getTrim(sector,'miles_enc',region,t)).filter(v=>v!==null);
      return vals.length === 4 ? vals.reduce((a,b)=>a+b,0) : null;
    }};
    const v0 = sumaAnio(desde);
    const v1 = sumaAnio(hasta);
    const n  = parseInt(hasta) - parseInt(desde);
    if(v0===null||v1===null||v0===0||n<=0) return null;
    return (Math.pow(v1/v0, 1/n) - 1) * 100;
  }}
}}

// ── Sectores PIB ──────────────────────────────────────────────
function renderSectores() {{
  const freq       = document.getElementById('pib-sec-freq').value;
  const ind        = document.getElementById('pib-sec-ind').value;
  const desde      = document.getElementById('pib-sec-desde').value;
  const hasta      = document.getElementById('pib-sec-hasta').value;
  const mostrarVar = document.getElementById('pib-sec-mostrar-var')?.checked || false;
  const ps         = filtrarPib(getPeriodosPib(freq),desde,hasta);
  const sects      = getSectoresPib(freq);
  const lbl        = PIB_INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  document.getElementById('pib-sec-title').textContent=(regionPibActual||'Región')+' — sectores — '+lbl;
  if(!regionPibActual){{document.getElementById('tabla-sec').innerHTML='<tr><td colspan="99" style="padding:20px;color:#aaa;text-align:center">Selecciona una región</td></tr>';return;}}

  const esPeso  = ind === 'peso_enc';
  const nAnios  = parseInt(hasta) - parseInt(desde);
  const lblCagr = nAnios > 0 ? `CAGR ${{desde}}–${{hasta}}` : 'CAGR';
  const clsVar  = v => v===null?'': v>0?'pos':'neg';
  const colCagr = mostrarVar ? ps.length*2+1 : ps.length+1;

  // Encabezado — simple o doble según toggle
  let thead = '<thead><tr><th>Sector</th>';
  if(mostrarVar) {{
    thead += ps.map(p => `<th colspan="2" style="text-align:center;border-left:1px solid #2d3a55">${{p}}</th>`).join('');
  }} else {{
    thead += ps.map((p,i) => `<th onclick="sortDT('tabla-sec',${{i+1}})">${{p}}</th>`).join('');
  }}
  thead += `<th onclick="sortDT('tabla-sec',${{colCagr}})" style="background:#0f3460;border-left:2px solid #38bdf8;min-width:80px">${{lblCagr}}</th></tr>`;
  if(mostrarVar) {{
    thead += '<tr>'
      + ps.map((_,i) =>
          `<th onclick="sortDT('tabla-sec',${{i*2+1}})" style="font-size:10px;font-weight:500;border-left:1px solid #2d3a55">Vol. enc.</th>`
        + `<th onclick="sortDT('tabla-sec',${{i*2+2}})" style="font-size:10px;font-weight:500;color:#38bdf8">${{freq==='anual'?'Var. %':'Var. %¹'}}</th>`
      ).join('')
      + '</tr>';
  }}
  thead += '</thead>';

  let tbody = '<tbody>';
  sects.forEach(sector => {{
    const esTotal    = sector === 'PIB';
    const nombreDisp = DISP[sector] || sector;
    const vals = ps.map(t => esPeso ? calcPeso(sector,ind,regionPibActual,t) : getValPib(sector,ind,regionPibActual,t));
    const vars = mostrarVar && !esPeso ? ps.map(t => calcVarEnc(sector,regionPibActual,t)) : [];
    const cagr = calcCAGR(sector, regionPibActual, desde, hasta, freq);

    tbody += `<tr><td class="${{esTotal?'total':''}}" style="font-weight:${{esTotal?700:500}}">${{nombreDisp}}</td>`;
    ps.forEach((_,i) => {{
      const v   = vals[i];
      const ccV = v!==null ? colorClsPib(v,ind) : '';
      tbody += `<td class="${{esTotal?'total':''}} ${{ccV}}">${{fmtPib(v,ind)}}</td>`;
      if(mostrarVar) {{
        const vr  = vars[i];
        const ccR = vr!=null ? clsVar(vr) : '';
        tbody += `<td class="${{esTotal?'total':''}} ${{ccR}}" style="font-size:11px">${{vr!=null?(vr>0?'+':'')+vr.toFixed(1)+'%':'—'}}</td>`;
      }}
    }});
    const ccCagr = cagr!==null ? colorClsPib(cagr,'cagr') : '';
    tbody += `<td class="${{esTotal?'total':''}} ${{ccCagr}}" style="border-left:2px solid #e0e7ff;font-weight:${{esTotal?700:600}}">${{fmtPib(cagr,'cagr')}}</td>`;
    tbody += '</tr>';
  }});
  tbody += '</tbody>';

  document.getElementById('tabla-sec').innerHTML = thead + tbody;
  const notaVar = (mostrarVar && freq==='trimestral') ? ' ¹Var. respecto al mismo trimestre del año anterior.' : '';
  document.getElementById('pib-sec-nota').textContent =
    'Volumen encadenado a precios del año anterior, series empalmadas.'
    + (nAnios>0 ? ` CAGR calculado sobre volumen encadenado (${{desde}}→${{hasta}}, ${{nAnios}} año${{nAnios!==1?'s':''}}).` : '')
    + notaVar;
}}

// ── Resumen PIB ───────────────────────────────────────────────
function renderResumenPib() {{
  const freq       = document.getElementById('pib-res-freq').value;
  const ind        = document.getElementById('pib-res-ind').value;
  const desde      = document.getElementById('pib-res-desde').value;
  const hasta      = document.getElementById('pib-res-hasta').value;
  const mostrarVar = document.getElementById('pib-res-mostrar-var')?.checked || false;
  const ps         = filtrarPib(getPeriodosPib(freq),desde,hasta);
  const lbl        = PIB_INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  const esPeso     = ind === 'peso_enc';
  document.getElementById('pib-res-title').textContent='PIB por región — '+lbl;

  const nAnios  = parseInt(hasta) - parseInt(desde);
  const lblCagr = nAnios > 0 ? `CAGR ${{desde}}–${{hasta}}` : 'CAGR';
  const clsVar  = v => v===null?'': v>0?'pos':'neg';
  const colCagr = mostrarVar ? ps.length*2+1 : ps.length+1;

  // Encabezado — simple o doble según toggle
  let thead = '<thead><tr><th>Región</th>';
  if(mostrarVar) {{
    thead += ps.map(p => `<th colspan="2" style="text-align:center;border-left:1px solid #2d3a55">${{p}}</th>`).join('');
  }} else {{
    thead += ps.map((p,i) => `<th onclick="sortDT('tabla-res',${{i+1}})">${{p}}</th>`).join('');
  }}
  thead += `<th onclick="sortDT('tabla-res',${{colCagr}})" style="background:#0f3460;border-left:2px solid #38bdf8;min-width:80px">${{lblCagr}}</th></tr>`;
  if(mostrarVar) {{
    thead += '<tr>'
      + ps.map((_,i) =>
          `<th onclick="sortDT('tabla-res',${{i*2+1}})" style="font-size:10px;font-weight:500;border-left:1px solid #2d3a55">Vol. enc.</th>`
        + `<th onclick="sortDT('tabla-res',${{i*2+2}})" style="font-size:10px;font-weight:500;color:#38bdf8">${{freq==='anual'?'Var. %':'Var. %¹'}}</th>`
      ).join('')
      + '</tr>';
  }}
  thead += '</thead>';

  // Helper celdas por período
  const celdas = (v, vr, esT) => {{
    const ccV = v!==null ? colorClsPib(v,ind) : '';
    let html = `<td class="${{esT?'total':''}} ${{ccV}}">${{fmtPib(v,ind)}}</td>`;
    if(mostrarVar) {{
      const ccR = vr!=null ? clsVar(vr) : '';
      html += `<td class="${{esT?'total':''}} ${{ccR}}" style="font-size:11px">${{vr!=null?(vr>0?'+':'')+vr.toFixed(1)+'%':'—'}}</td>`;
    }}
    return html;
  }};

  // Filas regiones
  let tbody = '<tbody>';
  PIB.regiones.forEach(reg => {{
    const vals = ps.map(t => esPeso ? calcPesoNacional(reg,ind,t) : getValPib('PIB',ind,reg,t));
    const vars = mostrarVar && !esPeso ? ps.map(t => calcVarEnc('PIB',reg,t)) : ps.map(()=>null);
    const cagr = calcCAGR('PIB', reg, desde, hasta, freq);
    const ccCagr = cagr!==null ? colorClsPib(cagr,'cagr') : '';
    tbody += `<tr><td>${{reg}}</td>`
      + ps.map((_,i) => celdas(vals[i], vars[i], false)).join('')
      + `<td class="${{ccCagr}}" style="border-left:2px solid #e0e7ff;font-weight:600">${{fmtPib(cagr,'cagr')}}</td></tr>`;
  }});

  // Extrarregional
  const extraVals = ps.map(t => {{
    if(esPeso) {{
      const vE = String(t).includes('.') ? PIB.extra_trim_enc[t] : PIB.extra_enc_anual[t];
      const tot = getPIBNacional(ind,t); return(vE&&tot)?(vE/tot*100):null;
    }}
    return String(t).includes('.') ? (PIB.extra_trim_enc[t]??null) : (PIB.extra_enc_anual[t]??null);
  }});
  const extraVars = mostrarVar && !esPeso ? ps.map(t => calcVarExtra(t)) : ps.map(()=>null);
  const cagrExtra = (() => {{
    if(freq==='anual') {{
      const v0=PIB.extra_enc_anual[desde]??null, v1=PIB.extra_enc_anual[hasta]??null;
      const n=parseInt(hasta)-parseInt(desde);
      return(v0&&v1&&v0>0&&n>0)?(Math.pow(v1/v0,1/n)-1)*100:null;
    }}
    const sumaE = yr => ['I','II','III','IV'].map(t=>`${{t}}.${{yr}}`).reduce((a,t)=>a+(PIB.extra_trim_enc[t]??0),0);
    const v0=sumaE(desde), v1=sumaE(hasta), n=parseInt(hasta)-parseInt(desde);
    return(v0&&v1&&v0>0&&n>0)?(Math.pow(v1/v0,1/n)-1)*100:null;
  }})();
  tbody += '<tr class="extra-row"><td>Extrarregional</td>';
  ps.forEach((_,i) => {{
    const v  = extraVals[i];
    const vr = extraVars[i];
    const ccV = v!==null  ? colorClsPib(v,ind) : '';
    const ccR = vr!==null ? clsVar(vr)         : '';
    tbody += `<td class="${{ccV}}" style="border-left:1px solid #e8e8e8">${{fmtPib(v,ind)}}</td>`;
    tbody += `<td class="${{ccR}}" style="font-size:11px">${{vr!==null?(vr>0?'+':'')+vr.toFixed(1)+'%':'—'}}</td>`;
  }});
  tbody += `<td style="border-left:2px solid #e0e7ff">${{fmtPib(cagrExtra,'cagr')}}</td></tr>`;

  // Total nacional
  const totalVals = ps.map(t => {{
    const nac = getPIBNacional(ind,t);
    if(esPeso) return nac?100:null;
    return nac;
  }});
  const totalVars = mostrarVar && !esPeso ? ps.map(t => calcVarNacional(t)) : ps.map(()=>null);
  const cagrNac = (() => {{
    if(freq==='anual') {{
      const v0=getPIBNacional(ind,desde), v1=getPIBNacional(ind,hasta), n=parseInt(hasta)-parseInt(desde);
      return(v0&&v1&&v0>0&&n>0)?(Math.pow(v1/v0,1/n)-1)*100:null;
    }}
    const sumaN = yr => ['I','II','III','IV'].map(t=>`${{t}}.${{yr}}`).reduce((a,t)=>{{const v=getPIBNacional(ind,t);return a+(v??0);}},0);
    const v0=sumaN(desde), v1=sumaN(hasta), n=parseInt(hasta)-parseInt(desde);
    return(v0&&v1&&v0>0&&n>0)?(Math.pow(v1/v0,1/n)-1)*100:null;
  }})();
  tbody += '<tr class="nacional-row"><td>Total nacional</td>';
  ps.forEach((_,i) => {{
    const v  = totalVals[i];
    const vr = totalVars[i];
    const ccR = vr!==null ? clsVar(vr) : '';
    tbody += `<td>${{fmtPib(v,ind)}}</td>`;
    tbody += `<td class="${{ccR}}" style="font-size:11px;font-weight:700">${{vr!==null?(vr>0?'+':'')+vr.toFixed(1)+'%':'—'}}</td>`;
  }});
  tbody += `<td style="border-left:2px solid #e0e7ff;font-weight:700">${{fmtPib(cagrNac,'cagr')}}</td></tr>`;

  tbody += '</tbody>';
  document.getElementById('tabla-res').innerHTML = thead + tbody;
  const notaPeso = esPeso ? '% calculado sobre el total nacional (subtotal regional + extrarregional). La suma de regiones + extrarregional = 100%.' : '';
  const notaVar  = (mostrarVar && freq==='trimestral') ? ' ¹Var. respecto al mismo trimestre del año anterior.' : '';
  document.getElementById('pib-res-nota').textContent =
    'Volumen encadenado a precios del año anterior, series empalmadas.'
    + (notaPeso?' '+notaPeso:'')
    + (nAnios>0?` CAGR calculado sobre volumen encadenado (${{añoDesde}}→${{añoHasta}}).`:'')
    + notaVar;
}}


// ══════════════════════════════════════════════════════════════
// CENSO 2024
// ══════════════════════════════════════════════════════════════
const CENSO = CENSO_DATA;

let censoTabActual = 'demografia';

function setTabCenso(tab, btn) {{
  censoTabActual = tab;
  document.querySelectorAll('.tab-censo').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#mod-censo .section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('censo-'+tab).classList.add('active');
  // Sincronizar región seleccionada entre pestañas
  const codActual = document.getElementById('censo-region').value ||
                    document.getElementById('censo-region-viv').value ||
                    document.getElementById('censo-region-edu').value ||
                    document.getElementById('censo-region-con').value;
  if(codActual) {{
    ['censo-region','censo-region-viv','censo-region-edu','censo-region-con'].forEach(id => {{
      document.getElementById(id).value = codActual;
    }});
  }}
  if(tab==='demografia')   renderCenso();
  if(tab==='vivienda')     renderCensoViv();
  if(tab==='educacion')    renderCensoEdu();
  if(tab==='conectividad') renderCensoCon();
}}

function getCensoReg(selId) {{
  return CENSO.datos[document.getElementById(selId).value];
}}

function pct(n, d) {{ return d > 0 ? (n/d*100) : 0; }}
function fmtN(v) {{ return v===null||v===undefined ? '—' : Math.round(v).toLocaleString('es-CL'); }}
function fmtP(v) {{ return v===null||v===undefined ? '—' : v.toFixed(1)+'%'; }}
function fmtD(v) {{ return v===null||v===undefined ? '—' : v.toFixed(1); }}

function kpiCenso(label, value, sub='', cls='') {{
  return `<div class="kpi ${{cls}}"><div class="kpi-label">${{label}}</div><div class="kpi-value">${{value}}</div><div class="kpi-sub">${{sub}}</div></div>`;
}}

function makePie(id, labels, data, colors) {{
  destroyChart(id);
  const ctx = document.getElementById(id); if(!ctx) return;
  charts[id] = new Chart(ctx, {{
    type: 'doughnut',
    data: {{labels, datasets:[{{data, backgroundColor:colors, borderWidth:2, borderColor:'#fff'}}]}},
    plugins: [ChartDataLabels],
    options: {{
      responsive:true, maintainAspectRatio:true,
      plugins:{{
        legend:{{position:'right',labels:{{font:{{size:11}},padding:12}}}},
        tooltip:{{callbacks:{{label:ctx=>` ${{ctx.label}}: ${{ctx.parsed.toFixed(1)}}%`}}}},
        datalabels:{{
          display: ctx => ctx.dataset.data[ctx.dataIndex] > 3,
          color:'#fff', font:{{size:10,weight:'700'}},
          formatter: v => v.toFixed(1)+'%',
        }}
      }}
    }}
  }});
}}

function makeHBar(id, labels, datasets) {{
  destroyChart(id);
  const ctx = document.getElementById(id); if(!ctx) return;
  charts[id] = new Chart(ctx, {{
    type:'bar',
    data:{{labels, datasets}},
    plugins: [ChartDataLabels],
    options:{{
      responsive:true, maintainAspectRatio:true, indexAxis:'y',
      plugins:{{
        legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}}}}}},
        tooltip:{{mode:'index',intersect:false}},
        datalabels:{{
          display: ctx => ctx.dataset.data[ctx.dataIndex] > 0,
          color:'#333', font:{{size:9,weight:'600'}},
          anchor:'end', align:'end', clamp:true,
          formatter: v => v===null?'': v.toFixed(1)+'%',
        }}
      }},
      scales:{{
        x:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}},max:100}},
        y:{{ticks:{{font:{{size:10}}}}}}
      }}
    }}
  }});
}}

// ── Poblar selects censo ─────────────────────────────────────
function poblarSelectsCenso() {{
  const selIds = ['censo-region','censo-region-viv','censo-region-edu','censo-region-con'];
  // Ordenar regiones por código numérico
  const ordenadas = Object.entries(CENSO.datos).sort((a,b) => parseInt(a[0])-parseInt(b[0]));
  selIds.forEach(id => {{
    const sel = document.getElementById(id);
    if(!sel) return;
    // Opción placeholder
    const ph = document.createElement('option');
    ph.value = ''; ph.textContent = '-- Selecciona una región --'; sel.appendChild(ph);
    ordenadas.forEach(([cod, r]) => {{
      const o = document.createElement('option');
      o.value = cod; o.textContent = r.nombre; sel.appendChild(o);
    }});
    sel.value = '13'; // Default Metropolitana
  }});
}}

// ── DEMOGRAFÍA ───────────────────────────────────────────────
function renderCenso() {{
  const r = getCensoReg('censo-region');
  if(!r) return;
  // Sincronizar todos los selects del censo
  const cod = document.getElementById('censo-region').value;
  ['censo-region-viv','censo-region-edu','censo-region-con'].forEach(id => {{ document.getElementById(id).value = cod; }});
  const pop = r.n_per, hog = r.n_hog;

  // KPIs
  document.getElementById('censo-kpi-demo').innerHTML =
    kpiCenso('Población total', fmtN(pop), r.nombre) +
    kpiCenso('Hogares', fmtN(hog), `${{fmtD(r.prom_per_hog)}} pers/hogar`) +
    kpiCenso('Edad promedio', fmtD(r.prom_edad), 'años') +
    kpiCenso('Inmigrantes', fmtP(pct(r.n_inmigrantes,pop)), fmtN(r.n_inmigrantes)+' personas', pct(r.n_inmigrantes,pop)>10?'amber':'') +
    kpiCenso('Pueblos originarios', fmtP(pct(r.n_pueblos_orig,pop)), fmtN(r.n_pueblos_orig)+' personas') +
    kpiCenso('Discapacidad', fmtP(pct(r.n_discapacidad,pop)), fmtN(r.n_discapacidad)+' personas');

  // Gráfico etario
  const edades = ['0–5','6–13','14–17','18–24','25–44','45–59','60+'];
  const vals_e = [r.n_edad_0_5,r.n_edad_6_13,r.n_edad_14_17,r.n_edad_18_24,r.n_edad_25_44,r.n_edad_45_59,r.n_edad_60_mas];
  const pcts_e = vals_e.map(v => pct(v,pop));
  makeBarSeg('censo-chart-edad', edades, [{{
    label:'% población', data:pcts_e,
    backgroundColor:['#7c3aed','#8b5cf6','#a78bfa','#c4b5fd','#6d28d9','#4c1d95','#3b0764'],
    borderRadius:4
  }}]);

  // Gráfico composición (pie) — solo Hombres/Mujeres
  makePie('censo-chart-comp',
    ['Hombres','Mujeres'],
    [pct(r.n_hombres,pop), pct(r.n_mujeres,pop)],
    ['#3b82f6','#ec4899']
  );

  // Tabla comparativa
  const cols = ['Región','Población','% Mujeres','Prom. edad','% Inmigrantes','% Pueblos orig.','% Discapacidad'];
  let thead = '<thead><tr>'+cols.map((c,i)=>i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('censo-tabla-demo',${{i}})">${{c}}</th>`).join('')+'</tr></thead>';
  let tbody = '<tbody>';
  Object.values(CENSO.datos).sort((a,b)=>b.n_per-a.n_per).forEach(reg => {{
    const p=reg.n_per;
    const isAct = reg.cod === r.cod;
    tbody += `<tr style="${{isAct?'background:#f5f3ff;font-weight:600':''}}">
      <td>${{reg.nombre}}</td>
      <td>${{fmtN(p)}}</td>
      <td>${{fmtP(pct(reg.n_mujeres,p))}}</td>
      <td>${{fmtD(reg.prom_edad)}}</td>
      <td>${{fmtP(pct(reg.n_inmigrantes,p))}}</td>
      <td>${{fmtP(pct(reg.n_pueblos_orig,p))}}</td>
      <td>${{fmtP(pct(reg.n_discapacidad,p))}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('censo-tabla-demo').innerHTML = thead+tbody;
}}

// ── VIVIENDA ─────────────────────────────────────────────────
function renderCensoViv() {{
  const r = getCensoReg('censo-region-viv');
  if(!r) return;
  const cod = document.getElementById('censo-region-viv').value;
  ['censo-region','censo-region-edu','censo-region-con'].forEach(id => {{ document.getElementById(id).value = cod; }});
  const vp = r.n_vp_ocupada, hog = r.n_hog;

  document.getElementById('censo-kpi-viv').innerHTML =
    kpiCenso('Viviendas ocupadas', fmtN(vp), '') +
    kpiCenso('Hogares', fmtN(hog), `${{fmtD(r.prom_per_hog)}} pers/hogar`) +
    kpiCenso('Jefatura mujer', fmtP(pct(r.n_jefatura_mujer,hog)), fmtN(r.n_jefatura_mujer)+' hogares', pct(r.n_jefatura_mujer,hog)>45?'verde':'') +
    kpiCenso('Hacinamiento', fmtP(pct(r.n_viv_hacinadas,vp)), fmtN(r.n_viv_hacinadas)+' viviendas', pct(r.n_viv_hacinadas,vp)>8?'rojo':'amber') +
    kpiCenso('Irrecuperables', fmtP(pct(r.n_viv_irrecuperables,vp)), fmtN(r.n_viv_irrecuperables)+' viviendas', pct(r.n_viv_irrecuperables,vp)>2?'rojo':'') +
    kpiCenso('Déficit cuantitativo', fmtP(pct(r.n_deficit_cuantitativo,vp)), fmtN(r.n_deficit_cuantitativo)+' viviendas', pct(r.n_deficit_cuantitativo,vp)>8?'rojo':'amber');

  // Tipo vivienda (incluye vivienda tradicional indígena = ruka, palafito, etc.)
  makePie('censo-chart-tipo-viv',
    ['Casa','Departamento','Mediagua','Pieza','Vivienda trad.','Móvil','Otro'],
    [pct(r.n_tipo_viv_casa,vp),pct(r.n_tipo_viv_depto,vp),pct(r.n_tipo_viv_mediagua,vp),
     pct(r.n_tipo_viv_pieza,vp),pct(r.n_tipo_viv_indigena,vp),pct(r.n_tipo_viv_movil,vp),pct(r.n_tipo_viv_otro,vp)],
    ['#2563eb','#7c3aed','#dc2626','#f59e0b','#10b981','#6366f1','#94a3b8']
  );

  // Tenencia
  makePie('censo-chart-tenencia',
    ['Propia pagada','Propia pagándose','Arrendada c/contrato','Arrendada s/contrato','Cedida','Otro'],
    [pct(r.n_tenencia_propia_pagada,hog),pct(r.n_tenencia_propia_pagandose,hog),
     pct(r.n_tenencia_arrendada_contrato,hog),pct(r.n_tenencia_arrendada_sin_contrato,hog),
     pct(r.n_tenencia_cedida_trabajo+r.n_tenencia_cedida_familiar,hog),pct(r.n_tenencia_otro,hog)],
    ['#16a34a','#4ade80','#f59e0b','#dc2626','#6366f1','#94a3b8']
  );

  // Tabla comparativa déficit
  const cols = ['Región','Viv. ocupadas','% Hacinadas','% Irrecuperables','% Déficit cuant.','% Allegados','% Jef. mujer'];
  let thead = '<thead><tr>'+cols.map((c,i)=>i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('censo-tabla-viv',${{i}})">${{c}}</th>`).join('')+'</tr></thead>';
  let tbody = '<tbody>';
  Object.values(CENSO.datos).sort((a,b)=>pct(b.n_deficit_cuantitativo,b.n_vp_ocupada)-pct(a.n_deficit_cuantitativo,a.n_vp_ocupada)).forEach(reg => {{
    const v=reg.n_vp_ocupada, h=reg.n_hog;
    const isAct = reg.cod === r.cod;
    tbody += `<tr style="${{isAct?'background:#f5f3ff;font-weight:600':''}}">
      <td>${{reg.nombre}}</td>
      <td>${{fmtN(v)}}</td>
      <td class="${{pct(reg.n_viv_hacinadas,v)>8?'neg':''}}">${{fmtP(pct(reg.n_viv_hacinadas,v))}}</td>
      <td class="${{pct(reg.n_viv_irrecuperables,v)>2?'neg':''}}">${{fmtP(pct(reg.n_viv_irrecuperables,v))}}</td>
      <td class="${{pct(reg.n_deficit_cuantitativo,v)>8?'neg':''}}">${{fmtP(pct(reg.n_deficit_cuantitativo,v))}}</td>
      <td>${{fmtP(pct(reg.n_hog_allegados,h))}}</td>
      <td>${{fmtP(pct(reg.n_jefatura_mujer,h))}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('censo-tabla-viv').innerHTML = thead+tbody;
}}

// ── EDUCACIÓN ────────────────────────────────────────────────
function renderCensoEdu() {{
  const r = getCensoReg('censo-region-edu');
  if(!r) return;
  const cod = document.getElementById('censo-region-edu').value;
  ['censo-region','censo-region-viv','censo-region-con'].forEach(id => {{ document.getElementById(id).value = cod; }});
  const pop = r.n_per;
  const tot_asist = r.n_asistencia_parv+r.n_asistencia_basica+r.n_asistencia_media+r.n_asistencia_superior;
  const tot_cine  = r.n_cine_nunca_curso_primera_infancia+r.n_cine_primaria+r.n_cine_secundaria+r.n_cine_terciaria_maestria_doctorado+r.n_cine_especial_diferencial;

  document.getElementById('censo-kpi-edu').innerHTML =
    kpiCenso('Prom. escolaridad', fmtD(r.prom_escolaridad18)+' años', 'Población 18+') +
    kpiCenso('Analfabetismo', fmtP(pct(r.n_analfabet,pop)), fmtN(r.n_analfabet)+' personas', pct(r.n_analfabet,pop)>3?'rojo':'verde') +
    kpiCenso('Asistencia superior', fmtP(pct(r.n_asistencia_superior,tot_asist)), 'Del total en sistema') +
    kpiCenso('Ed. terciaria (CINE)', fmtP(pct(r.n_cine_terciaria_maestria_doctorado,tot_cine)), 'Maestría/Doctorado incl.');

  // CINE
  makeHBar('censo-chart-cine',
    ['Sin escolaridad','Primaria','Secundaria','Terciaria/Posgrado','Ed. especial'],
    [{{label:'% población', borderRadius:3,
      data:[
        pct(r.n_cine_nunca_curso_primera_infancia,tot_cine),
        pct(r.n_cine_primaria,tot_cine),
        pct(r.n_cine_secundaria,tot_cine),
        pct(r.n_cine_terciaria_maestria_doctorado,tot_cine),
        pct(r.n_cine_especial_diferencial,tot_cine),
      ],
      backgroundColor:['#dc2626','#f59e0b','#3b82f6','#7c3aed','#94a3b8'],
    }}]
  );

  // Gráfico analfabetismo y escolaridad por tramos CINE — más interpretable
  const vAnalf = pct(r.n_analfabet, pop);
  const vSinEsc = pct(r.n_cine_nunca_curso_primera_infancia, tot_cine);
  const vPrim = pct(r.n_cine_primaria, tot_cine);
  const vSec = pct(r.n_cine_secundaria, tot_cine);
  const vTer = pct(r.n_cine_terciaria_maestria_doctorado, tot_cine);
  makeHBar('censo-chart-asist',
    ['Sin escolaridad','Primaria completa','Secundaria completa','Terciaria / Posgrado','Analfabetismo (ref.)'],
    [{{label:'% población', borderRadius:3,
      data:[vSinEsc, vPrim, vSec, vTer, vAnalf],
      backgroundColor:['#dc2626','#f59e0b','#3b82f6','#7c3aed','#94a3b8'],
    }}]
  );

  // Tabla
  const cols = ['Región','Prom. escolaridad','% Analfabetismo','% Parvularia','% Básica','% Media','% Superior'];
  let thead = '<thead><tr>'+cols.map((c,i)=>i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('censo-tabla-edu',${{i}})">${{c}}</th>`).join('')+'</tr></thead>';
  let tbody = '<tbody>';
  Object.values(CENSO.datos).sort((a,b)=>b.prom_escolaridad18-a.prom_escolaridad18).forEach(reg => {{
    const p=reg.n_per;
    const ta=reg.n_asistencia_parv+reg.n_asistencia_basica+reg.n_asistencia_media+reg.n_asistencia_superior;
    const isAct = reg.cod === r.cod;
    tbody += `<tr style="${{isAct?'background:#f5f3ff;font-weight:600':''}}">
      <td>${{reg.nombre}}</td>
      <td>${{fmtD(reg.prom_escolaridad18)}}</td>
      <td class="${{pct(reg.n_analfabet,p)>3?'neg':'pos'}}">${{fmtP(pct(reg.n_analfabet,p))}}</td>
      <td>${{fmtP(pct(reg.n_asistencia_parv,ta))}}</td>
      <td>${{fmtP(pct(reg.n_asistencia_basica,ta))}}</td>
      <td>${{fmtP(pct(reg.n_asistencia_media,ta))}}</td>
      <td>${{fmtP(pct(reg.n_asistencia_superior,ta))}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('censo-tabla-edu').innerHTML = thead+tbody;
}}

// ── CONECTIVIDAD Y SERVICIOS ─────────────────────────────────
function renderCensoCon() {{
  const r = getCensoReg('censo-region-con');
  if(!r) return;
  const cod = document.getElementById('censo-region-con').value;
  ['censo-region','censo-region-viv','censo-region-edu'].forEach(id => {{ document.getElementById(id).value = cod; }});
  const vp = r.n_vp_ocupada, hog = r.n_hog;

  document.getElementById('censo-kpi-con').innerHTML =
    kpiCenso('Acceso a internet', fmtP(pct(r.n_internet,hog)), fmtN(r.n_internet)+' hogares', pct(r.n_internet,hog)<70?'rojo':pct(r.n_internet,hog)<85?'amber':'verde') +
    kpiCenso('Teléfono móvil', fmtP(pct(r.n_serv_tel_movil,hog)), fmtN(r.n_serv_tel_movil)+' hogares') +
    kpiCenso('Agua red pública', fmtP(pct(r.n_fuente_agua_publica,vp)), fmtN(r.n_fuente_agua_publica)+' viviendas', pct(r.n_fuente_agua_publica,vp)<80?'rojo':'verde') +
    kpiCenso('Alcantarillado', fmtP(pct(r.n_serv_hig_alc_dentro,vp)), 'Dentro de la vivienda', pct(r.n_serv_hig_alc_dentro,vp)<70?'rojo':'verde') +
    kpiCenso('Electricidad red', fmtP(pct(r.n_fuente_elect_publica,vp)), fmtN(r.n_fuente_elect_publica)+' viviendas') +
    kpiCenso('Retiro basura', fmtP(pct(r.n_basura_servicios,vp)), 'Servicio municipal/empresa', pct(r.n_basura_servicios,vp)<80?'amber':'');

  // Servicios básicos
  makeHBar('censo-chart-serv',
    ['Agua red pública','Alcantarillado dentro','Electricidad red','Retiro de basura'],
    [{{label:'% viviendas', borderRadius:3,
      data:[
        pct(r.n_fuente_agua_publica,vp),
        pct(r.n_serv_hig_alc_dentro,vp),
        pct(r.n_fuente_elect_publica,vp),
        pct(r.n_basura_servicios,vp),
      ],
      backgroundColor:['#2563eb','#16a34a','#f59e0b','#6366f1'],
    }}]
  );

  // Conectividad digital — comparación regional con variable seleccionada
  const digitalVar = document.getElementById('censo-digital-var')?.value || 'n_internet';
  const digitalLabels = {{
    n_internet:'Internet (cualquier)', n_serv_internet_fija:'Internet fija',
    n_serv_internet_movil:'Internet móvil', n_serv_internet_satelital:'Internet satelital',
    n_serv_tel_movil:'Teléfono móvil', n_serv_compu:'Computador', n_serv_tablet:'Tablet',
  }};
  const regsSorted = Object.values(CENSO.datos).sort((a,b) => pct(b[digitalVar],b.n_hog) - pct(a[digitalVar],a.n_hog));
  makeBarSeg('censo-chart-digital',
    regsSorted.map(reg => reg.nombre.replace('Metropolitana','RM').replace('Arica y Parinacota','Arica')),
    [
      {{label:'Con acceso', data:regsSorted.map(reg=>pct(reg[digitalVar],reg.n_hog)),
        backgroundColor:'rgba(37,99,235,.75)', borderRadius:3}},
      {{label:'Sin acceso', data:regsSorted.map(reg=>100-pct(reg[digitalVar],reg.n_hog)),
        backgroundColor:'rgba(220,38,38,.35)', borderRadius:3}},
    ],
    {{horizontal:false}}
  );

  // Combustible cocina
  makeHBar('censo-chart-cocina',
    ['Gas','Leña','Electricidad','No utiliza'],
    [{{label:'% viviendas', borderRadius:3,
      data:[pct(r.n_comb_cocina_gas,vp),pct(r.n_comb_cocina_lena,vp),
            pct(r.n_comb_cocina_electricidad,vp),pct(r.n_comb_cocina_no_utiliza,vp)],
      backgroundColor:['#f59e0b','#92400e','#2563eb','#94a3b8'],
    }}]
  );

  // Combustible calefacción
  makeHBar('censo-chart-calef',
    ['Gas','Leña','Electricidad','No utiliza'],
    [{{label:'% viviendas', borderRadius:3,
      data:[pct(r.n_comb_calefaccion_gas,vp),pct(r.n_comb_calefaccion_lena,vp),
            pct(r.n_comb_calefaccion_electricidad,vp),pct(r.n_comb_calefaccion_no_utiliza,vp)],
      backgroundColor:['#f59e0b','#92400e','#2563eb','#94a3b8'],
    }}]
  );

  // Tabla comparativa
  const cols = ['Región','% Internet','% Agua pública','% Alcantarillado','% Electricidad','% Retiro basura','% Sin saneamiento'];
  let thead = '<thead><tr>'+cols.map((c,i)=>i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('censo-tabla-con',${{i}})">${{c}}</th>`).join('')+'</tr></thead>';
  let tbody = '<tbody>';
  Object.values(CENSO.datos).sort((a,b)=>pct(b.n_internet,b.n_hog)-pct(a.n_internet,a.n_hog)).forEach(reg => {{
    const v=reg.n_vp_ocupada, h=reg.n_hog;
    const isAct = reg.cod === r.cod;
    tbody += `<tr style="${{isAct?'background:#f5f3ff;font-weight:600':''}}">
      <td>${{reg.nombre}}</td>
      <td class="${{pct(reg.n_internet,h)<70?'neg':''}}">${{fmtP(pct(reg.n_internet,h))}}</td>
      <td class="${{pct(reg.n_fuente_agua_publica,v)<80?'neg':''}}">${{fmtP(pct(reg.n_fuente_agua_publica,v))}}</td>
      <td class="${{pct(reg.n_serv_hig_alc_dentro,v)<70?'neg':''}}">${{fmtP(pct(reg.n_serv_hig_alc_dentro,v))}}</td>
      <td>${{fmtP(pct(reg.n_fuente_elect_publica,v))}}</td>
      <td>${{fmtP(pct(reg.n_basura_servicios,v))}}</td>
      <td class="${{pct(reg.n_serv_hig_no_tiene,v)>1?'neg':''}}">${{fmtP(pct(reg.n_serv_hig_no_tiene,v))}}</td>
    </tr>`;
  }});
  tbody += '</tbody>';
  document.getElementById('censo-tabla-con').innerHTML = thead+tbody;
}}


// ══════════════════════════════════════════════════════════════
// MÓDULO EMPLEO
// ══════════════════════════════════════════════════════════════
const EMP = {data_emp_json};

function setTabEmp(tab, el) {{
  document.querySelectorAll('.tab-emp').forEach(t=>t.classList.remove('active'));
  if(el) el.classList.add('active');
  document.querySelectorAll('#mod-empleo .section').forEach(s=>s.classList.remove('active'));
  document.getElementById('emp-'+tab).classList.add('active');
  if(tab==='resumen') renderEmpResumen();
  if(tab==='evolucion') renderEmpEvolucion();
  if(tab==='ranking') renderEmpRanking();
}}

function empGetVal(reg, periodo, ind) {{
  const d=EMP.datos[reg]; if(!d) return null;
  const i=d.periodos.indexOf(periodo);
  return i>=0?d[ind][i]:null;
}}

function fmtEmpPer(p){{return p?p.replace('-','/'):'';}}
function fmtEmpNum(v,dec=1){{return v===null||v===undefined?'—':v.toFixed(dec).replace('.',',');}}
function fmtEmpMiles(v){{return v===null||v===undefined?'—':Math.round(v).toLocaleString('es-CL');}}

function renderEmpResumen() {{
  const per = document.getElementById('emp-res-periodo').value;
  const ind = document.getElementById('emp-res-ind').value;
  const indL = {{tasa:'Tasa de desocupación (%)',ocupados:'Ocupados (miles)',ft:'Fuerza de trabajo* (miles)'}};
  document.getElementById('emp-res-chart-title').textContent = indL[ind]+' — '+fmtEmpPer(per);

  const vals   = EMP.regiones.map(r=>empGetVal(r,per,ind));
  const tasas  = EMP.regiones.map(r=>empGetVal(r,per,'tasa'));
  const ocups  = EMP.regiones.map(r=>empGetVal(r,per,'ocupados'));
  const fts    = EMP.regiones.map(r=>empGetVal(r,per,'ft'));
  const noNull = vals.filter(v=>v!==null);
  const prom   = noNull.length?noNull.reduce((a,b)=>a+b,0)/noNull.length:null;
  const maxV   = noNull.length?Math.max(...noNull):null;
  const minV   = noNull.length?Math.min(...noNull):null;
  const rMax   = EMP.regiones[vals.indexOf(maxV)];
  const rMin   = EMP.regiones[vals.indexOf(minV)];
  const totOc  = ocups.filter(v=>v!==null).reduce((a,b)=>a+b,0);

  document.getElementById('emp-kpi-resumen').innerHTML = `
    <div class="kpi azul"><div class="kpi-label">Promedio nacional</div><div class="kpi-value">${{ind==='tasa'?fmtEmpNum(prom):fmtEmpMiles(prom)}}</div><div class="kpi-sub">${{fmtEmpPer(per)}}</div></div>
    <div class="kpi rojo"><div class="kpi-label">Mayor ${{ind==='tasa'?'desocupación':'valor'}}</div><div class="kpi-value">${{ind==='tasa'?fmtEmpNum(maxV):fmtEmpMiles(maxV)}}</div><div class="kpi-sub">${{rMax||''}}</div></div>
    <div class="kpi verde"><div class="kpi-label">Menor ${{ind==='tasa'?'desocupación':'valor'}}</div><div class="kpi-value">${{ind==='tasa'?fmtEmpNum(minV):fmtEmpMiles(minV)}}</div><div class="kpi-sub">${{rMin||''}}</div></div>
    <div class="kpi amber"><div class="kpi-label">Total ocupados</div><div class="kpi-value">${{fmtEmpMiles(totOc)}}</div><div class="kpi-sub">Miles de personas</div></div>`;

  const sorted = EMP.regiones.map((r,i)=>{{return{{r,v:vals[i]}}}}).filter(x=>x.v!==null).sort((a,b)=>b.v-a.v);
  const bg = sorted.map(x=>ind==='tasa'?(x.v>8?'rgba(220,38,38,.8)':x.v>6?'rgba(217,119,6,.8)':'rgba(22,163,74,.8)'):'rgba(37,99,235,.75)');
  makeBarH('emp-chart-resumen',sorted.map(x=>x.r.replace('Metropolitana de Santiago','RM')),[{{label:indL[ind],data:sorted.map(x=>x.v),backgroundColor:bg,borderRadius:3}}]);

  let thead=`<thead><tr><th>Región</th><th onclick="sortDT('emp-tabla-resumen',1)">Tasa desocup. %</th><th onclick="sortDT('emp-tabla-resumen',2)">Ocupados (miles)</th><th onclick="sortDT('emp-tabla-resumen',3)">Fuerza de trabajo*</th></tr></thead>`;
  let tbody='<tbody>';
  EMP.regiones.forEach((r,i)=>{{
    const t=tasas[i],o=ocups[i],f=fts[i];
    const cls=t===null?'':t>8?'neg':t<5?'pos':'';
    tbody+=`<tr><td>${{r}}</td><td class="${{cls}}">${{fmtEmpNum(t)}}%</td><td>${{fmtEmpMiles(o)}}</td><td>${{fmtEmpMiles(f)}}</td></tr>`;
  }});
  document.getElementById('emp-tabla-resumen').innerHTML=thead+tbody+'</tbody>';
}}

function renderEmpEvolucion() {{
  const reg   = document.getElementById('emp-evo-region').value;
  const desde = document.getElementById('emp-evo-desde').value;
  const hasta = document.getElementById('emp-evo-hasta').value;
  const d = EMP.datos[reg]; if(!d) return;
  const ps = d.periodos.filter(p=>p>=desde+'-01'&&p<=hasta+'-12');
  const ii = ps.map(p=>d.periodos.indexOf(p));
  const tasas=ii.map(i=>d.tasa[i]), ocup=ii.map(i=>d.ocupados[i]), ft=ii.map(i=>d.ft[i]);
  const lbls=ps.map(p=>p.replace('-','/'));
  const noNull=tasas.filter(v=>v!==null);
  const ult=noNull[noNull.length-1], prom=noNull.length?noNull.reduce((a,b)=>a+b,0)/noNull.length:null;
  const maxT=noNull.length?Math.max(...noNull):null, minT=noNull.length?Math.min(...noNull):null;

  document.getElementById('emp-kpi-evo').innerHTML=`
    <div class="kpi ${{ult>8?'rojo':ult>6?'amber':'verde'}}"><div class="kpi-label">Tasa actual</div><div class="kpi-value">${{fmtEmpNum(ult)}}%</div><div class="kpi-sub">${{fmtEmpPer(ps[ps.length-1])}}</div></div>
    <div class="kpi"><div class="kpi-label">Promedio período</div><div class="kpi-value">${{fmtEmpNum(prom)}}%</div><div class="kpi-sub">${{desde}}–${{hasta}}</div></div>
    <div class="kpi rojo"><div class="kpi-label">Máx. desocupación</div><div class="kpi-value">${{fmtEmpNum(maxT)}}%</div></div>
    <div class="kpi verde"><div class="kpi-label">Mín. desocupación</div><div class="kpi-value">${{fmtEmpNum(minT)}}%</div></div>`;

  document.getElementById('emp-evo-title-tasa').textContent=reg+' — Tasa de desocupación (%)';
  document.getElementById('emp-evo-title-ocup').textContent=reg+' — Ocupados (miles)';
  document.getElementById('emp-evo-title-ft').textContent=reg+' — Fuerza de trabajo* (miles)';
  makeLine2('emp-chart-evo-tasa',lbls,[{{label:'Tasa de desocupación (%)',data:tasas,borderColor:'rgba(37,99,235,.9)',backgroundColor:'rgba(37,99,235,.08)',tension:.3,fill:true,pointRadius:5,pointHoverRadius:7,pointBackgroundColor:tasas.map(v=>v===null?'#ccc':v>8?'#dc2626':v>6?'#d97706':'#16a34a'),pointBorderColor:'white',pointBorderWidth:2}}]);
  makeLine2('emp-chart-evo-ocup',lbls,[{{label:'Ocupados',data:ocup,borderColor:'rgba(37,99,235,.8)',backgroundColor:'rgba(37,99,235,.1)',tension:.3,fill:true,pointRadius:0}}]);
  makeLine2('emp-chart-evo-ft',lbls,[{{label:'Fuerza de trabajo',data:ft,borderColor:'rgba(217,119,6,.8)',backgroundColor:'rgba(217,119,6,.1)',tension:.3,fill:true,pointRadius:0}}]);
}}

function renderEmpRanking() {{
  const per=document.getElementById('emp-rank-periodo').value;
  const pairs=EMP.regiones.map(r=>{{return{{r,t:empGetVal(r,per,'tasa'),o:empGetVal(r,per,'ocupados'),f:empGetVal(r,per,'ft')}}}}).filter(x=>x.t!==null).sort((a,b)=>b.t-a.t);
  document.getElementById('emp-rank-title').textContent='Ranking completo — '+fmtEmpPer(per);
  const top5=pairs.slice(0,5), bot5=[...pairs].reverse().slice(0,5);
  makeBarH('emp-chart-rank-alta',top5.map(x=>x.r.replace('Metropolitana de Santiago','RM')),[{{label:'Tasa %',data:top5.map(x=>x.t),backgroundColor:'rgba(220,38,38,.8)',borderRadius:3}}]);
  makeBarH('emp-chart-rank-baja',bot5.map(x=>x.r.replace('Metropolitana de Santiago','RM')),[{{label:'Tasa %',data:bot5.map(x=>x.t),backgroundColor:'rgba(22,163,74,.8)',borderRadius:3}}]);
  let thead=`<thead><tr><th>#</th><th>Región</th><th onclick="sortDT('emp-tabla-ranking',2)">Tasa %</th><th onclick="sortDT('emp-tabla-ranking',3)">Ocupados</th><th onclick="sortDT('emp-tabla-ranking',4)">Fuerza trabajo*</th></tr></thead>`;
  let tbody='<tbody>';
  pairs.forEach((x,i)=>{{
    const cls=x.t>8?'neg':x.t<5?'pos':'';
    tbody+=`<tr><td>${{i+1}}</td><td style="text-align:left;font-weight:500">${{x.r}}</td><td class="${{cls}}">${{fmtEmpNum(x.t)}}%</td><td>${{fmtEmpMiles(x.o)}}</td><td>${{fmtEmpMiles(x.f)}}</td></tr>`;
  }});
  document.getElementById('emp-tabla-ranking').innerHTML=thead+tbody+'</tbody>';
}}

function makeBarH(id,labels,datasets,horizontal=true) {{
  if(charts[id]){{charts[id].destroy();delete charts[id];}}
  const ctx=document.getElementById(id); if(!ctx) return;
  charts[id]=new Chart(ctx,{{type:'bar',data:{{labels,datasets}},options:{{
    responsive:true,maintainAspectRatio:true,indexAxis:horizontal?'y':'x',
    plugins:{{legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}}}}}},tooltip:{{mode:'index',intersect:false}}}},
    scales:{{x:{{ticks:{{font:{{size:10}},maxRotation:horizontal?0:55}},grid:{{display:horizontal}}}},y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}}}
  }}}});
}}
function makeLine2(id,labels,datasets,tipo='line') {{
  if(charts[id]){{charts[id].destroy();delete charts[id];}}
  const ctx=document.getElementById(id); if(!ctx) return;
  charts[id]=new Chart(ctx,{{type:tipo,data:{{labels,datasets}},options:{{
    responsive:true,maintainAspectRatio:true,
    plugins:{{legend:{{display:false}},tooltip:{{mode:'index',intersect:false}}}},
    scales:{{x:{{ticks:{{font:{{size:10}},maxRotation:55,autoSkip:true,maxTicksLimit:24}},grid:{{display:false}}}},y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}}}
  }}}});
}}

// ══════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════
window.onload = function() {{
  // Seguridad — semanas
  poblarSemana('res-semana', renderResumen);
  poblarSemana('op-semana', renderOperativo);
  poblarSemana('dmcs-semana', renderDMCS);
  poblarRegionSeg('evo-seg-region', renderEvolucionSeg);

  // Filtros región en Resumen y DMCS
  ['res-region', 'dmcs-region'].forEach(selId => {{
    const sel = document.getElementById(selId);
    if(!sel) return;
    SEG.regiones.forEach(r => {{
      const o = document.createElement('option');
      o.value = r; o.textContent = r; sel.appendChild(o);
    }});
  }});

  // Filtro delito en DMCS — usar nombres reales de la DB si están disponibles
  const selDelito = document.getElementById('dmcs-delito');
  const listaDelitos = DELITOS.tiene_datos && DELITOS.nombres_delitos.length
    ? DELITOS.nombres_delitos.filter(d => DMCS_LISTA.includes(d))
    : DMCS_LISTA;
  listaDelitos.forEach(d => {{
    const o = document.createElement('option');
    o.value = d; o.textContent = d; selDelito.appendChild(o);
  }});

  renderResumen();

  // PIB — selects de región
  const selReg = document.getElementById('pib-region-sel');
  PIB.regiones.forEach(r=>{{const o=document.createElement('option');o.value=r;o.textContent=r;selReg.appendChild(o);}});

  // PIB — indicadores y años
  ['pib-evo','pib-sec','pib-res'].forEach(p=>{{
    poblarIndicadoresPib(p,'anual');
    poblarAñosPib(p,PIB.años_corr,p==='pib-evo'?8:6);
  }});

  document.getElementById('hdr-sub').textContent = MOD_LABELS['seguridad'];

  // Empleo — períodos
  ['emp-res-periodo','emp-rank-periodo'].forEach(id=>{{
    const sel=document.getElementById(id);
    [...EMP.periodos].reverse().forEach(p=>{{
      const o=document.createElement('option');
      o.value=p; o.textContent=fmtEmpPer(p); sel.appendChild(o);
    }});
  }});
  // Empleo — regiones
  const empSelR=document.getElementById('emp-evo-region');
  EMP.regiones.forEach(r=>{{const o=document.createElement('option');o.value=r;o.textContent=r;empSelR.appendChild(o);}});
  // Empleo — años
  const empAños=EMP.años;
  ['emp-evo-desde','emp-evo-hasta'].forEach((id,i)=>{{
    const sel=document.getElementById(id);
    empAños.forEach(a=>{{const o=document.createElement('option');o.value=a;o.textContent=a;sel.appendChild(o);}});
    sel.value=i===0?empAños[Math.max(0,empAños.length-10)]:empAños[empAños.length-1];
  }});

  // Censo — poblar selects
  poblarSelectsCenso();

  // CASEN 2024
  initCasen();
}};
</script>


<!-- ══════════════════════════════════════════════════════════════
     MÓDULO: EMPLEO
══════════════════════════════════════════════════════════════ -->
<div class="modulo" id="mod-empleo">
  <div class="tabs">
    <div class="tab-emp active" onclick="setTabEmp('resumen',this)">Resumen comparativo</div>
    <div class="tab-emp" onclick="setTabEmp('evolucion',this)">Evolución por región</div>
    <div class="tab-emp" onclick="setTabEmp('ranking',this)">Ranking regional</div>
  </div>
  <div class="content">

    <!-- Resumen -->
    <div class="section active" id="emp-resumen">
      <div class="filtros">
        <div class="fg"><label>Período</label><select id="emp-res-periodo" onchange="renderEmpResumen()"></select></div>
        <div class="fg"><label>Indicador</label>
          <select id="emp-res-ind" onchange="renderEmpResumen()">
            <option value="tasa">Tasa de desocupación (%)</option>
            <option value="ocupados">Ocupados (miles de personas)</option>
            <option value="ft">Fuerza de trabajo* (miles)</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="emp-kpi-resumen"></div>
      <div class="card"><h3 id="emp-res-chart-title">Tasa de desocupación por región</h3>
        <canvas id="emp-chart-resumen" style="max-height:320px"></canvas></div>
      <div class="card"><h3>Comparativa regional</h3>
        <div class="tabla-wrap"><table class="dt" id="emp-tabla-resumen"></table></div>
        <p class="nota">* Fuerza de trabajo = Ocupados / (1 - Tasa/100)</p>
      </div>
    </div>

    <!-- Evolución -->
    <div class="section" id="emp-evolucion">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="emp-evo-region" onchange="renderEmpEvolucion()"></select></div>
        <div class="fg"><label>Año desde</label><select id="emp-evo-desde" onchange="renderEmpEvolucion()"></select></div>
        <div class="fg"><label>Año hasta</label><select id="emp-evo-hasta" onchange="renderEmpEvolucion()"></select></div>
      </div>
      <div class="kpi-grid" id="emp-kpi-evo"></div>
      <div class="card"><h3 id="emp-evo-title-tasa">Tasa de desocupación (%)</h3>
        <canvas id="emp-chart-evo-tasa" style="max-height:260px"></canvas></div>
      <div class="grid2">
        <div class="card"><h3 id="emp-evo-title-ocup">Ocupados (miles)</h3>
          <canvas id="emp-chart-evo-ocup" style="max-height:220px"></canvas></div>
        <div class="card"><h3 id="emp-evo-title-ft">Fuerza de trabajo* (miles)</h3>
          <canvas id="emp-chart-evo-ft" style="max-height:220px"></canvas></div>
      </div>
    </div>

    <!-- Ranking -->
    <div class="section" id="emp-ranking">
      <div class="filtros">
        <div class="fg"><label>Período</label><select id="emp-rank-periodo" onchange="renderEmpRanking()"></select></div>
      </div>
      <div class="grid2">
        <div class="card"><h3>Mayor desocupación</h3>
          <canvas id="emp-chart-rank-alta" style="max-height:320px"></canvas></div>
        <div class="card"><h3>Menor desocupación</h3>
          <canvas id="emp-chart-rank-baja" style="max-height:320px"></canvas></div>
      </div>
      <div class="card"><h3 id="emp-rank-title">Ranking completo</h3>
        <div class="tabla-wrap"><table class="dt" id="emp-tabla-ranking"></table></div>
      </div>
    </div>

  </div>
</div><!-- /mod-empleo -->


<!-- ══════════════════════════════════════════════════════════════
     MÓDULO: CASEN 2024
══════════════════════════════════════════════════════════════ -->
<div class="modulo" id="mod-casen">
  <div class="tabs">
    <div class="tab-casen active" onclick="setTabCasen('pobreza',this)">Pobreza por ingresos</div>
    <div class="tab-casen" onclick="setTabCasen('severa',this)">Pobreza severa</div>
    <div class="tab-casen" onclick="setTabCasen('multi',this)">Pobreza multidimensional</div>
    <div class="tab-casen" onclick="setTabCasen('ingreso',this)">Ingresos</div>
    <div class="tab-casen" onclick="setTabCasen('salud',this)">Salud</div>
  </div>
  <div class="content">

    <!-- ═══ POBREZA POR INGRESOS ═══ -->
    <div class="section active" id="casen-pobreza">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="cp-r" onchange="syncCS('cp-r');renderCasenPob()"></select></div>
      </div>
      <div class="kpi-grid" id="cp-kpi"></div>
      <div class="grid2">
        <div class="card"><h3>Evolución pobreza (% personas)</h3><canvas id="cp-evo" style="max-height:280px"></canvas></div>
        <div class="card"><h3>Índices FGT: Brecha y Severidad</h3><canvas id="cp-fgt" style="max-height:280px"></canvas></div>
      </div>
      <div class="card">
        <h3>Comparación regional 2024</h3>
        <div class="tabla-wrap"><table class="dt" id="cp-tabla"></table></div>
        <p class="nota">FGT1 = brecha promedio; FGT2 = severidad (pondera más a los más pobres). Fuente: CASEN 2024, MIDESO.</p>
      </div>
    </div>

    <!-- ═══ POBREZA SEVERA ═══ -->
    <div class="section" id="casen-severa">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="csv-r" onchange="syncCS('csv-r');renderCasenSevera()"></select></div>
      </div>
      <div class="kpi-grid" id="csv-kpi"></div>
      <div class="grid2">
        <div class="card"><h3>Distribución 2024 (% personas)</h3><canvas id="csv-pie" style="max-height:300px"></canvas></div>
        <div class="card"><h3>Comparación 2022 vs 2024 por región</h3><canvas id="csv-comp" style="max-height:300px"></canvas></div>
      </div>
      <div class="card">
        <h3>Ranking regional — Pobreza Severa 2024</h3>
        <div class="tabla-wrap"><table class="dt" id="csv-tabla"></table></div>
        <p class="nota">Pobreza severa: personas en situación simultánea de pobreza por ingresos y pobreza multidimensional.</p>
      </div>
    </div>

    <!-- ═══ POBREZA MULTIDIMENSIONAL ═══ -->
    <div class="section" id="casen-multi">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="cm-r" onchange="syncCS('cm-r');renderCasenMulti()"></select></div>
      </div>
      <div class="kpi-grid" id="cm-kpi"></div>
      <div class="grid2">
        <div class="card"><h3>Carencias por indicador 2024 (% hogares)</h3><canvas id="cm-car" style="max-height:360px"></canvas></div>
        <div class="card"><h3>Contribución por dimensión 2024 (%)</h3><canvas id="cm-dim" style="max-height:300px"></canvas></div>
      </div>
      <div class="card">
        <h3>Comparación regional — Incidencia multidimensional 2024</h3>
        <div class="tabla-wrap"><table class="dt" id="cm-tabla"></table></div>
        <p class="nota">Met. 2024 incluye nuevos indicadores vs met. 2015 (aprendizaje, alimentos, cuidados, trato igualitario, seguridad, conectividad).</p>
      </div>
    </div>

    <!-- ═══ INGRESOS ═══ -->
    <div class="section" id="casen-ingreso">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="ci-r" onchange="syncCS('ci-r');renderCasenIngreso()"></select></div>
        <div class="fg"><label>Tipo de ingreso</label>
          <select id="ci-tipo" onchange="renderCasenIngreso()">
            <option value="Ingreso monetario">Ingreso monetario (total)</option>
            <option value="Ingreso autónomo">Ingreso autónomo</option>
            <option value="Ingreso del trabajo">Ingreso del trabajo</option>
            <option value="Subsidios monetarios">Subsidios monetarios</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="ci-kpi"></div>
      <div class="grid2">
        <div class="card"><h3 id="ci-title">Evolución ingreso promedio hogares</h3><canvas id="ci-evo" style="max-height:260px"></canvas></div>
        <div class="card"><h3>Pobreza relativa — % personas bajo 50% de la mediana</h3><canvas id="ci-prel" style="max-height:260px"></canvas></div>
      </div>
      <div class="card"><h3>Composición ingreso monetario 2024 — todas las regiones</h3><canvas id="ci-comp" style="max-height:260px"></canvas></div>
      <div class="card">
        <h3>Comparación regional — Ingresos 2024</h3>
        <div class="tabla-wrap"><table class="dt" id="ci-tabla"></table></div>
        <p class="nota">Cifras en $ de noviembre de cada año. Ingresos corregidos por no respuesta. Fuente: CASEN 2024.</p>
      </div>
    </div>

    <!-- ═══ SALUD ═══ -->
    <div class="section" id="casen-salud">
      <div class="filtros">
        <div class="fg"><label>Región</label><select id="cs-r" onchange="syncCS('cs-r');renderCasenSalud()"></select></div>
        <div class="fg"><label>Tipo de prestación</label>
          <select id="cs-prest-tipo" onchange="renderCasenPrest()">
            <option value="Consulta médica general">Consulta médica general</option>
            <option value="Consulta de urgencia">Consulta de urgencia</option>
            <option value="Atención de salud mental">Atención de salud mental</option>
            <option value="Consulta de especialidad">Consulta de especialidad</option>
            <option value="Atención dental">Atención dental</option>
            <option value="Exámenes de laboratorio">Exámenes de laboratorio</option>
            <option value="Controles médicos">Controles médicos</option>
            <option value="Hospitalizaciones/cirugías">Hospitalizaciones/cirugías</option>
          </select></div>
      </div>
      <div class="kpi-grid" id="cs-kpi"></div>
      <div class="grid2">
        <div class="card"><h3>Sistema previsional 2024</h3><canvas id="cs-prev" style="max-height:280px"></canvas></div>
        <div class="card"><h3>Evolución FONASA vs Isapre (%)</h3><canvas id="cs-fon" style="max-height:280px"></canvas></div>
      </div>
      <div class="grid2">
        <div class="card"><h3>Problemas para obtener atención médica (% Tuvo)</h3><canvas id="cs-prob" style="max-height:260px"></canvas></div>
        <div class="card"><h3>Cobertura AUGE-GES (%)</h3><canvas id="cs-ges" style="max-height:260px"></canvas></div>
      </div>
      <div class="card"><h3 id="cs-prest-title">Prestaciones recibidas — comparación regional 2024</h3><canvas id="cs-prest" style="max-height:260px"></canvas></div>
      <div class="card">
        <h3>Comparación regional — Salud 2024</h3>
        <div class="tabla-wrap"><table class="dt" id="cs-tabla"></table></div>
      </div>
    </div>

  </div>
</div><!-- /mod-casen -->

<script>
// ══════════════════════════════════════════════════════════════
// CASEN 2024
// ══════════════════════════════════════════════════════════════
const CASEN = {data_casen_json};

function casenReg(id){{return CASEN.datos[document.getElementById(id).value];}}
function fp(v,d=1){{return v==null?'—':v.toFixed(d)+'%';}}
function fm(v){{return v==null?'—':'$'+Math.round(v/1000).toLocaleString('es-CL')+' mil';}}
function fdiff(v){{return v==null?'—':(v>0?'+':'')+v.toFixed(1)+' p.p.';}}
function clsDiff(v){{return v==null?'':v<0?'pos':'neg';}}

function syncCS(id){{
  const v=document.getElementById(id).value;
  ['cp-r','csv-r','cm-r','ci-r','cs-r'].forEach(x=>{{const e=document.getElementById(x);if(e)e.value=v;}});
}}

function poblarSelectsCasen(){{
  ['cp-r','csv-r','cm-r','ci-r','cs-r'].forEach(id=>{{
    const sel=document.getElementById(id);if(!sel)return;
    CASEN.regiones.forEach(r=>{{const o=document.createElement('option');o.value=r;o.textContent=r;sel.appendChild(o);}});
    sel.value='Metropolitana de Santiago';
  }});
}}

function setTabCasen(tab,btn){{
  document.querySelectorAll('.tab-casen').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('#mod-casen .section').forEach(s=>s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('casen-'+tab).classList.add('active');
  if(tab==='pobreza')  renderCasenPob();
  if(tab==='severa')   renderCasenSevera();
  if(tab==='multi')    renderCasenMulti();
  if(tab==='ingreso')  renderCasenIngreso();
  if(tab==='salud')    renderCasenSalud();
}}

function mkLineC(id,labels,datasets){{
  destroyChart(id);const ctx=document.getElementById(id);if(!ctx)return;
  charts[id]=new Chart(ctx,{{type:'line',data:{{labels,datasets}},options:{{
    responsive:true,maintainAspectRatio:true,
    plugins:{{legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}}}}}},tooltip:{{mode:'index',intersect:false}}}},
    scales:{{x:{{ticks:{{font:{{size:10}},maxRotation:55}},grid:{{display:false}}}},y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}}}
  }}}});
}}
function mkBarC(id,labels,datasets,horiz=false){{
  destroyChart(id);const ctx=document.getElementById(id);if(!ctx)return;
  charts[id]=new Chart(ctx,{{type:'bar',data:{{labels,datasets}},plugins:[ChartDataLabels],options:{{
    responsive:true,maintainAspectRatio:true,indexAxis:horiz?'y':'x',
    plugins:{{
      legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}},padding:10}}}},
      tooltip:{{mode:'index',intersect:false}},
      datalabels:{{display:c=>{{const v=c.dataset.data[c.dataIndex];return v!=null&&Math.abs(v)>0.3;}},
        color:'#fff',font:{{size:8,weight:'700'}},anchor:'center',align:'center',
        formatter:v=>v==null?'':v.toFixed(1)+'%',clamp:true}}
    }},
    scales:{{
      x:{{ticks:{{font:{{size:9}},maxRotation:horiz?0:55}},grid:{{display:horiz}}}},
      y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}
    }}
  }}}});
}}
function mkBarHC(id,labels,datasets){{
  destroyChart(id);const ctx=document.getElementById(id);if(!ctx)return;
  charts[id]=new Chart(ctx,{{type:'bar',data:{{labels,datasets}},plugins:[ChartDataLabels],options:{{
    responsive:true,maintainAspectRatio:true,indexAxis:'y',
    plugins:{{legend:{{display:false}},tooltip:{{mode:'index',intersect:false}},
      datalabels:{{display:c=>{{const v=c.dataset.data[c.dataIndex];return v!=null&&v>0.5;}},
        color:'#333',font:{{size:8,weight:'600'}},anchor:'end',align:'end',clamp:true,formatter:v=>v==null?'':v.toFixed(1)+'%'}}}},
    scales:{{x:{{ticks:{{font:{{size:9}}}},grid:{{color:'#f0f0f0'}},max:100}},y:{{ticks:{{font:{{size:9}}}}}}}}
  }}}});
}}
function mkPieC(id,labels,data,colors){{
  destroyChart(id);const ctx=document.getElementById(id);if(!ctx)return;
  charts[id]=new Chart(ctx,{{type:'doughnut',data:{{labels,datasets:[{{data,backgroundColor:colors,borderWidth:2,borderColor:'#fff'}}]}},
    plugins:[ChartDataLabels],options:{{responsive:true,maintainAspectRatio:true,
      plugins:{{legend:{{position:'right',labels:{{font:{{size:11}},padding:10}}}},
        tooltip:{{callbacks:{{label:c=>' '+c.label+': '+c.parsed.toFixed(1)+'%'}}}},
        datalabels:{{display:c=>c.dataset.data[c.dataIndex]>2,color:'#fff',font:{{size:9,weight:'700'}},formatter:v=>v.toFixed(1)+'%'}}
    }}}}}});
}}
function cTHead(tId,cols){{
  return '<thead><tr>'+cols.map((c,i)=>i===0?`<th>${{c}}</th>`:`<th onclick="sortDT('${{tId}}',${{i}})">${{c}}</th>`).join('')+'</tr></thead>';
}}
function cTRow(vals,isAct,cls=[]){{
  return `<tr style="${{isAct?'background:#fff7ed;font-weight:600':''}}">`+vals.map((v,i)=>`<td class="${{cls[i]||''}}">${{v}}</td>`).join('')+'</tr>';
}}

// ── POBREZA POR INGRESOS ──────────────────────────────────────
function renderCasenPob(){{
  const r=casenReg('cp-r');if(!r)return;
  const pi=r.pobreza_ingresos, fgt=r.fgt, AÑOS=CASEN.años_pob;
  const ext=pi['Pobreza extrema']||{{}}, nxt=pi['Pobreza no extrema']||{{}}, tot=pi['Pobreza total']||{{}};
  const v24=tot['2024'], v22=tot['2022'], vx24=ext['2024']||0;
  const d=v24!=null&&v22!=null?+(v24-v22).toFixed(2):null;
  const fgt1=fgt['FGT1_Brecha']?.['2024'], fgt2=fgt['FGT2_Severidad']?.['2024'];
  const cls=v=>v>15?'rojo':v>10?'amber':'verde';
  document.getElementById('cp-kpi').innerHTML=
    `<div class="kpi ${{cls(v24)}}"><div class="kpi-label">Pobreza total 2024</div><div class="kpi-value">${{fp(v24)}}</div><div class="kpi-sub">% personas</div></div>`+
    `<div class="kpi ${{vx24>5?'rojo':'verde'}}"><div class="kpi-label">Pobreza extrema 2024</div><div class="kpi-value">${{fp(vx24)}}</div><div class="kpi-sub">% personas</div></div>`+
    `<div class="kpi ${{d==null?'':d<0?'verde':'rojo'}}"><div class="kpi-label">Variación 2022→2024</div><div class="kpi-value">${{fdiff(d)}}</div><div class="kpi-sub">puntos porcentuales</div></div>`+
    `<div class="kpi amber"><div class="kpi-label">Brecha FGT1 2024</div><div class="kpi-value">${{fp(fgt1,2)}}</div><div class="kpi-sub">índice</div></div>`+
    `<div class="kpi rojo"><div class="kpi-label">Severidad FGT2 2024</div><div class="kpi-value">${{fp(fgt2,2)}}</div><div class="kpi-sub">índice</div></div>`+
    `<div class="kpi azul"><div class="kpi-label">No pobreza 2024</div><div class="kpi-value">${{fp(pi['No pobreza']?.['2024'])}}</div><div class="kpi-sub">% personas</div></div>`;
  mkLineC('cp-evo',AÑOS,[
    {{label:'Pobreza extrema',data:AÑOS.map(a=>ext[a]||null),borderColor:'rgba(220,38,38,.9)',backgroundColor:'rgba(220,38,38,.08)',tension:.3,fill:true,pointRadius:3}},
    {{label:'Pobreza no extrema',data:AÑOS.map(a=>nxt[a]||null),borderColor:'rgba(217,119,6,.9)',backgroundColor:'rgba(217,119,6,.08)',tension:.3,fill:true,pointRadius:3}}
  ]);
  mkLineC('cp-fgt',AÑOS,[
    {{label:'FGT1: Brecha',data:AÑOS.map(a=>fgt['FGT1_Brecha']?.[a]||null),borderColor:'rgba(217,119,6,.9)',backgroundColor:'transparent',tension:.3,pointRadius:3}},
    {{label:'FGT2: Severidad',data:AÑOS.map(a=>fgt['FGT2_Severidad']?.[a]||null),borderColor:'rgba(220,38,38,.9)',backgroundColor:'transparent',tension:.3,pointRadius:3}}
  ]);
  const isAct=document.getElementById('cp-r').value;
  const rows=CASEN.regiones.map(rn=>{{
    const d2=CASEN.datos[rn]; const p=d2.pobreza_ingresos, f=d2.fgt;
    const t24=p['Pobreza total']?.['2024']||null, t22=p['Pobreza total']?.['2022']||null;
    const dv=t24!=null&&t22!=null?+(t24-t22).toFixed(2):null;
    return {{r:rn,tot:t24,ext:p['Pobreza extrema']?.['2024']||null,var:dv,b:f['FGT1_Brecha']?.['2024']||null,sv:f['FGT2_Severidad']?.['2024']||null}};
  }}).sort((a,b)=>(b.tot||0)-(a.tot||0));
  document.getElementById('cp-tabla').innerHTML=
    cTHead('cp-tabla',['Región','Pobreza total 2024','Pobreza extrema 2024','Var. 2022→2024','FGT1 Brecha','FGT2 Severidad'])+
    '<tbody>'+rows.map(x=>cTRow([x.r,fp(x.tot),fp(x.ext),fdiff(x.var),fp(x.b,2),fp(x.sv,2)],x.r===isAct,
      ['',x.tot>15?'neg':x.tot<10?'pos':'',x.ext>5?'neg':'',clsDiff(x.var),'',''])).join('')+'</tbody>';
}}

// ── POBREZA SEVERA ────────────────────────────────────────────
function renderCasenSevera(){{
  const r=casenReg('csv-r');if(!r)return;
  const ps=r.pobreza_severa;
  const s24=ps['Pobreza Severa']?.['2024']||null, s22=ps['Pobreza Severa']?.['2022']||null;
  const d=s24!=null&&s22!=null?+(s24-s22).toFixed(2):null;
  document.getElementById('csv-kpi').innerHTML=
    `<div class="kpi ${{s24>8?'rojo':s24>5?'amber':'verde'}}"><div class="kpi-label">Pobreza Severa 2024</div><div class="kpi-value">${{fp(s24)}}</div><div class="kpi-sub">% personas</div></div>`+
    `<div class="kpi"><div class="kpi-label">Pobreza Severa 2022</div><div class="kpi-value">${{fp(s22)}}</div><div class="kpi-sub">% personas</div></div>`+
    `<div class="kpi ${{d==null?'':d<0?'verde':'rojo'}}"><div class="kpi-label">Variación 2022→2024</div><div class="kpi-value">${{fdiff(d)}}</div><div class="kpi-sub">puntos porcentuales</div></div>`+
    `<div class="kpi azul"><div class="kpi-label">Solo pob. ingresos 2024</div><div class="kpi-value">${{fp(ps['Sólo pobreza por ingresos']?.['2024'])}}</div><div class="kpi-sub">% personas</div></div>`;
  mkPieC('csv-pie',['Pob. Severa','Solo ingresos','Solo multidim.','No pobreza'],
    ['Pobreza Severa','Sólo pobreza por ingresos','Sólo pobreza multidimensional','No pobreza'].map(c=>ps[c]?.['2024']||0),
    ['#dc2626','#f59e0b','#3b82f6','#16a34a']);
  const lbls=CASEN.regiones.map(rn=>rn.replace('Metropolitana de Santiago','RM').replace('Arica y Parinacota','Arica'));
  mkBarC('csv-comp',lbls,[
    {{label:'2022',data:CASEN.regiones.map(rn=>CASEN.datos[rn].pobreza_severa['Pobreza Severa']?.['2022']||null),backgroundColor:'rgba(220,38,38,.3)',borderRadius:2}},
    {{label:'2024',data:CASEN.regiones.map(rn=>CASEN.datos[rn].pobreza_severa['Pobreza Severa']?.['2024']||null),backgroundColor:'rgba(220,38,38,.85)',borderRadius:2}}
  ]);
  const isAct=document.getElementById('csv-r').value;
  const rows=CASEN.regiones.map(rn=>{{
    const d2=CASEN.datos[rn].pobreza_severa;
    return {{r:rn,s24:d2['Pobreza Severa']?.['2024']||null,s22:d2['Pobreza Severa']?.['2022']||null,
            ing:d2['Sólo pobreza por ingresos']?.['2024']||null,mu:d2['Sólo pobreza multidimensional']?.['2024']||null}};
  }}).sort((a,b)=>(b.s24||0)-(a.s24||0));
  document.getElementById('csv-tabla').innerHTML=
    cTHead('csv-tabla',['Región','Pob. Severa 2024','Pob. Severa 2022','Solo Ingresos','Solo Multidim.'])+
    '<tbody>'+rows.map(x=>cTRow([x.r,fp(x.s24),fp(x.s22),fp(x.ing),fp(x.mu)],x.r===isAct,
      ['',(x.s24>8?'neg':x.s24<5?'pos':''),'','',''])).join('')+'</tbody>';
}}

// ── POBREZA MULTIDIMENSIONAL ──────────────────────────────────
function renderCasenMulti(){{
  const r=casenReg('cm-r');if(!r)return;
  const mi=r.multi_incidencia, car=r.carencias, con=r.contribucion_dims;
  const h24=mi.met2024_2024_hog, h22=mi.met2024_2022_hog, p24=mi.met2024_2024_per;
  const d=h24!=null&&h22!=null?+(h24-h22).toFixed(2):null;
  document.getElementById('cm-kpi').innerHTML=
    `<div class="kpi ${{h24>20?'rojo':h24>12?'amber':'verde'}}"><div class="kpi-label">Incidencia hogares 2024</div><div class="kpi-value">${{fp(h24)}}</div><div class="kpi-sub">Met. 2024</div></div>`+
    `<div class="kpi ${{p24>20?'rojo':p24>15?'amber':'verde'}}"><div class="kpi-label">Incidencia personas 2024</div><div class="kpi-value">${{fp(p24)}}</div><div class="kpi-sub">Met. 2024</div></div>`+
    `<div class="kpi ${{d==null?'':d<0?'verde':'rojo'}}"><div class="kpi-label">Var. hogares 2022→2024</div><div class="kpi-value">${{fdiff(d)}}</div><div class="kpi-sub">puntos porcentuales</div></div>`+
    `<div class="kpi azul"><div class="kpi-label">Met. 2015 comparación</div><div class="kpi-value">${{fp(mi.met2015_2024_hog)}}</div><div class="kpi-sub">% hogares 2024</div></div>`;
  const inds=CASEN.indicadores_multi;
  const indS=inds.map(i=>i.replace('Aprendizaje escolar en el establecimiento','Aprendizaje escolar').replace('Apoyo en cuidado de personas con dependencia funcional','Apoyo en cuidado'));
  const pal=['#7c3aed','#8b5cf6','#a78bfa','#6d28d9','#dc2626','#ef4444','#f87171','#fca5a5',
             '#2563eb','#3b82f6','#60a5fa','#93c5fd','#16a34a','#22c55e','#4ade80','#86efac',
             '#d97706','#f59e0b','#fbbf24','#fde68a'];
  mkBarHC('cm-car',indS,[{{label:'% hogares carentes',data:inds.map(i=>car[i]||null),backgroundColor:pal,borderRadius:3}}]);
  const dims=CASEN.dimensiones_multi;
  mkPieC('cm-dim',dims,dims.map(d2=>con[d2]||null),['#7c3aed','#dc2626','#2563eb','#16a34a','#f59e0b']);
  const isAct=document.getElementById('cm-r').value;
  const rows=CASEN.regiones.map(rn=>{{
    const m=CASEN.datos[rn].multi_incidencia;
    return {{r:rn,h24:m.met2024_2024_hog,h22:m.met2024_2022_hog,p24:m.met2024_2024_per,m15:m.met2015_2024_hog}};
  }}).sort((a,b)=>(b.h24||0)-(a.h24||0));
  document.getElementById('cm-tabla').innerHTML=
    cTHead('cm-tabla',['Región','Hogares 2024 (met.2024)','Hogares 2022 (met.2024)','Personas 2024','Hogares 2024 (met.2015)'])+
    '<tbody>'+rows.map(x=>cTRow([x.r,fp(x.h24),fp(x.h22),fp(x.p24),fp(x.m15)],x.r===isAct,
      ['',(x.h24>20?'neg':x.h24<12?'pos':''),'','',''])).join('')+'</tbody>';
}}

// ── INGRESOS ──────────────────────────────────────────────────
function renderCasenIngreso(){{
  const r=casenReg('ci-r');if(!r)return;
  const tipo=document.getElementById('ci-tipo').value;
  const ing=r.ingresos[tipo]||{{}}, AÑOS=CASEN.años_ing;
  const v24=ing['2024'], v22=ing['2022'];
  const varN=v24!=null&&v22!=null?+((v24/v22-1)*100).toFixed(1):null;
  const rm24=CASEN.datos['Metropolitana de Santiago'].ingresos[tipo]?.['2024']||null;
  const brecha=v24!=null&&rm24!=null?+((v24/rm24-1)*100).toFixed(1):null;
  const pr24=r.pob_relativa['Ingreso monetario']?.['2024']||null;
  const aut24=r.composicion_ing['Ingreso autónomo']?.['2024']||null;
  const sub24=r.composicion_ing['Subsidios monetarios']?.['2024']||null;
  document.getElementById('ci-kpi').innerHTML=
    `<div class="kpi azul"><div class="kpi-label">${{tipo}} 2024</div><div class="kpi-value">${{v24?'$'+Math.round(v24/1000).toLocaleString('es-CL')+' mil':'—'}}</div><div class="kpi-sub">promedio hogar</div></div>`+
    `<div class="kpi ${{varN==null?'':varN>0?'verde':'rojo'}}"><div class="kpi-label">Var. nominal 2022→2024</div><div class="kpi-value">${{varN==null?'—':(varN>0?'+':'')+varN+'%'}}</div><div class="kpi-sub">pesos nominales</div></div>`+
    `<div class="kpi ${{brecha==null?'azul':brecha>=0?'verde':'rojo'}}"><div class="kpi-label">Relación vs RM 2024</div><div class="kpi-value">${{brecha==null?'—':(brecha>0?'+':'')+brecha+'%'}}</div><div class="kpi-sub"></div></div>`+
    `<div class="kpi ${{pr24>25?'rojo':pr24>18?'amber':'verde'}}"><div class="kpi-label">Pobreza relativa 2024</div><div class="kpi-value">${{fp(pr24)}}</div><div class="kpi-sub">< 50% mediana ing.mon.</div></div>`+
    `<div class="kpi amber"><div class="kpi-label">Ingreso autónomo 2024</div><div class="kpi-value">${{fp(aut24)}}</div><div class="kpi-sub">% del ing. monetario</div></div>`+
    `<div class="kpi rojo"><div class="kpi-label">Subsidios monetarios 2024</div><div class="kpi-value">${{fp(sub24)}}</div><div class="kpi-sub">% del ing. monetario</div></div>`;
  document.getElementById('ci-title').textContent=tipo+' — evolución 2006–2024 ($ nominales)';
  mkLineC('ci-evo',AÑOS,[{{label:tipo,data:AÑOS.map(a=>ing[a]||null),borderColor:'rgba(37,99,235,.9)',backgroundColor:'rgba(37,99,235,.08)',tension:.3,fill:true,pointRadius:4}}]);
  mkLineC('ci-prel',CASEN.años_ing,[{{label:'% < 50% mediana',data:CASEN.años_ing.map(a=>r.pob_relativa['Ingreso monetario']?.[a]||null),borderColor:'rgba(220,38,38,.9)',backgroundColor:'rgba(220,38,38,.08)',tension:.3,fill:true,pointRadius:3}}]);
  const lbls=CASEN.regiones.map(rn=>rn.replace('Metropolitana de Santiago','RM').replace('Arica y Parinacota','Arica'));
  mkBarC('ci-comp',lbls,[
    {{label:'Ingreso autónomo %',data:CASEN.regiones.map(rn=>CASEN.datos[rn].composicion_ing['Ingreso autónomo']?.['2024']||null),backgroundColor:'rgba(37,99,235,.75)',borderRadius:2}},
    {{label:'Subsidios %',data:CASEN.regiones.map(rn=>CASEN.datos[rn].composicion_ing['Subsidios monetarios']?.['2024']||null),backgroundColor:'rgba(220,38,38,.7)',borderRadius:2}}
  ]);
  const isAct=document.getElementById('ci-r').value;
  const fM=v=>v?'$'+Math.round(v/1000).toLocaleString('es-CL')+' mil':'—';
  const rows=CASEN.regiones.map(rn=>{{
    const d2=CASEN.datos[rn];
    return {{r:rn,mon:d2.ingresos['Ingreso monetario']?.['2024']||null,trab:d2.ingresos['Ingreso del trabajo']?.['2024']||null,
            pr:d2.pob_relativa['Ingreso monetario']?.['2024']||null,aut:d2.composicion_ing['Ingreso autónomo']?.['2024']||null}};
  }}).sort((a,b)=>(b.mon||0)-(a.mon||0));
  document.getElementById('ci-tabla').innerHTML=
    cTHead('ci-tabla',['Región','Ing. monetario 2024','Ing. del trabajo 2024','Pob. relativa 2024','% Autónomo 2024'])+
    '<tbody>'+rows.map(x=>cTRow([x.r,fM(x.mon),fM(x.trab),fp(x.pr),fp(x.aut)],x.r===isAct,['','','',x.pr>25?'neg':x.pr<18?'pos':'',''])).join('')+'</tbody>';
}}

// ── SALUD ─────────────────────────────────────────────────────
function renderCasenPrest(){{
  const tipoSel=document.getElementById('cs-prest-tipo').value;
  document.getElementById('cs-prest-title').textContent=tipoSel+' — comparación regional 2024';
  const lbls=CASEN.regiones.map(rn=>rn.replace('Metropolitana de Santiago','RM').replace('Arica y Parinacota','Arica'));
  mkBarC('cs-prest',lbls,[{{label:'% personas que recibió',data:CASEN.regiones.map(rn=>CASEN.datos[rn].prestaciones[tipoSel]?.['2024']||null),backgroundColor:'rgba(37,99,235,.75)',borderRadius:3}}]);
}}
function renderCasenSalud(){{
  const r=casenReg('cs-r');if(!r)return;
  const prev=r.previsional, at=r.atencion_medica, prob=r.prob_atencion, ges=r.auge_ges;
  const fon24=prev['Sistema Público FONASA']?.['2024']||null;
  const isa24=prev['Isapre']?.['2024']||null;
  const aten24=at['Sí']?.['2024']||null;
  const prob24=prob['Tuvo']?.['2024']||null;
  const ges24=ges['Si']?.['2024']||null;
  document.getElementById('cs-kpi').innerHTML=
    `<div class="kpi azul"><div class="kpi-label">FONASA 2024</div><div class="kpi-value">${{fp(fon24)}}</div><div class="kpi-sub">% afiliados</div></div>`+
    `<div class="kpi"><div class="kpi-label">Isapre 2024</div><div class="kpi-value">${{fp(isa24)}}</div><div class="kpi-sub">% afiliados</div></div>`+
    `<div class="kpi verde"><div class="kpi-label">Recibió atención médica</div><div class="kpi-value">${{fp(aten24)}}</div><div class="kpi-sub">ante problema de salud 2024</div></div>`+
    `<div class="kpi ${{prob24>40?'rojo':prob24>30?'amber':'verde'}}"><div class="kpi-label">Tuvo problema p/ atenderse</div><div class="kpi-value">${{fp(prob24)}}</div><div class="kpi-sub">2024</div></div>`+
    `<div class="kpi ${{ges24<70?'rojo':ges24<80?'amber':'verde'}}"><div class="kpi-label">Cubierto AUGE-GES 2024</div><div class="kpi-value">${{fp(ges24)}}</div><div class="kpi-sub">de quienes estuvieron en tto.</div></div>`;
  const catsPrev=['Sistema Público FONASA','Isapre','FF.AA. y del Orden','Ninguno (particular)'];
  mkPieC('cs-prev',catsPrev,catsPrev.map(c=>prev[c]?.['2024']||0),['#2563eb','#f59e0b','#6366f1','#94a3b8']);
  const AÑOS_S=CASEN.años_sal;
  mkLineC('cs-fon',AÑOS_S,[
    {{label:'FONASA',data:AÑOS_S.map(a=>prev['Sistema Público FONASA']?.[a]||null),borderColor:'rgba(37,99,235,.9)',backgroundColor:'transparent',tension:.3,pointRadius:3}},
    {{label:'Isapre',data:AÑOS_S.map(a=>prev['Isapre']?.[a]||null),borderColor:'rgba(217,119,6,.9)',backgroundColor:'transparent',tension:.3,pointRadius:3}}
  ]);
  const AÑOS_P=CASEN.años_prob;
  mkLineC('cs-prob',AÑOS_P,[{{label:'% Tuvo problemas p/ atenderse',data:AÑOS_P.map(a=>prob['Tuvo']?.[a]||null),borderColor:'rgba(220,38,38,.9)',backgroundColor:'rgba(220,38,38,.08)',tension:.3,fill:true,pointRadius:4}}]);
  const AÑOS_G=CASEN.años_ges;
  mkLineC('cs-ges',AÑOS_G,[
    {{label:'Sí cubierto',data:AÑOS_G.map(a=>ges['Si']?.[a]||null),borderColor:'rgba(22,163,74,.9)',backgroundColor:'rgba(22,163,74,.08)',tension:.3,fill:true,pointRadius:3}},
    {{label:'No cubierto',data:AÑOS_G.map(a=>ges['No']?.[a]||null),borderColor:'rgba(220,38,38,.9)',backgroundColor:'transparent',tension:.3,pointRadius:3}}
  ]);
  renderCasenPrest();
  const isAct=document.getElementById('cs-r').value;
  const rows=CASEN.regiones.map(rn=>{{
    const d2=CASEN.datos[rn];
    return {{r:rn,fon:d2.previsional['Sistema Público FONASA']?.['2024']||null,
            isa:d2.previsional['Isapre']?.['2024']||null,
            aten:d2.atencion_medica['Sí']?.['2024']||null,
            prob:d2.prob_atencion['Tuvo']?.['2024']||null,
            ges:d2.auge_ges['Si']?.['2024']||null}};
  }}).sort((a,b)=>(b.fon||0)-(a.fon||0));
  document.getElementById('cs-tabla').innerHTML=
    cTHead('cs-tabla',['Región','FONASA 2024','Isapre 2024','Recibió atención','Tuvo problemas','Cubierto AUGE-GES'])+
    '<tbody>'+rows.map(x=>cTRow([x.r,fp(x.fon),fp(x.isa),fp(x.aten),fp(x.prob),fp(x.ges)],x.r===isAct,
      ['','','',x.aten<85?'neg':'pos',x.prob>40?'neg':x.prob<25?'pos':'',x.ges<70?'neg':x.ges>80?'pos':''])).join('')+'</tbody>';
}}

function initCasen(){{
  poblarSelectsCasen();
  document.getElementById('ci-tipo').onchange=renderCasenIngreso;
  document.getElementById('cs-prest-tipo').onchange=renderCasenPrest;
}}
</script>

</body>
</html>"""


html = html.replace('{data_seg_json}', data_seg_json)           .replace('{data_delitos_json}', data_delitos_json)           .replace('{data_pib_json}', data_pib_json)           .replace('{data_censo_json}', data_censo_json)           .replace('{data_emp_json}', data_emp_json)           .replace('{data_casen_json}', data_casen_json)

with open('dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('=== dashboard.html generado ===')
print(f'Seguridad  → semanas: {len(semanas_clean)}, regiones: {len(regiones_seg)}')
print(f'PIB        → trimestres: {trimestres[0]} → {trimestres[-1]}')
print(f'Empleo     → periodos: {periodos_emp[0]} → {periodos_emp[-1]}, regiones: {len(regiones_emp)}')
