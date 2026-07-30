"""
generar_dashboard_v2.py
=======================
Genera dashboard.html dinámico: los datos de Seguridad, PIB y Empleo
se cargan desde Supabase en tiempo real. Censo y CASEN se cargan desde
los JSON estáticos del repo (no están en Supabase).

Uso:
    python generar_dashboard_v2.py
    → dashboard.html

No requiere SQLite ni pandas. Solo necesita el archivo fuente
generar_dashboard.py en el mismo directorio para extraer el JS/HTML
base y reemplazar los bloques de datos embebidos.
"""

from pathlib import Path
import re

SRC = Path("generar_dashboard.py")
OUT = Path("dashboard.html")

SUPABASE_URL = "https://hufgtspktblxxkwocsof.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Zmd0c3BrdGJseHhrd29jc29mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNjM5MjksImV4cCI6MjA5MDYzOTkyOX0.81qaWauO4e92TYB6LfxSk6pZ46f8sZ29alZ876Baw1I"

# ── Leer el generar_dashboard.py original como texto ─────────────────────────
src_text = SRC.read_text(encoding="utf-8")

# ── Extraer el bloque HTML del f-string ──────────────────────────────────────
# El HTML empieza en `html = f"""<!DOCTYPE html>` y termina en `</html>"""`
m = re.search(r'html = f"""(.*?)"""', src_text, re.DOTALL)
if not m:
    raise RuntimeError("No se encontró el bloque html = f\"\"\"...\"\"\" en generar_dashboard.py")

html_raw = m.group(1)

# ── Des-escapar las llaves dobles del f-string ({{ → {, }} → }) ──────────────
# En un f-string, {{ y }} son literales { y }. Las que son reemplazos van sin doblar.
# Necesitamos conservar los placeholders {data_*_json} como texto plano.
# Estrategia: primero proteger los placeholders, luego des-escapar, luego restaurar.
PLACEHOLDERS = [
    "{data_seg_json}",
    "{data_delitos_json}",
    "{data_censo_json}",
    "{data_pib_json}",
    "{data_emp_json}",
    "{data_casen_json}",
]
TOKENS = {p: f"__PLACEHOLDER_{i}__" for i, p in enumerate(PLACEHOLDERS)}

for ph, tok in TOKENS.items():
    html_raw = html_raw.replace(ph, tok)

# Des-escapar llaves dobles
html_raw = html_raw.replace("{{", "{").replace("}}", "}")

# Restaurar placeholders (ahora como tokens, los reemplazaremos por JS real)
for ph, tok in TOKENS.items():
    html_raw = html_raw.replace(tok, ph)

# ── Bloque JS de carga dinámica (reemplaza los datos embebidos) ───────────────
LOADER_JS = f"""
// ══════════════════════════════════════════════════════════════
// CONFIGURACIÓN SUPABASE
// ══════════════════════════════════════════════════════════════
const SUPA_URL  = "{SUPABASE_URL}";
const SUPA_KEY  = "{SUPABASE_ANON_KEY}";

// Variables globales de datos — se rellenan al cargar
let SEG        = null;
let DELITOS    = null;
let CENSO_DATA = null;
let PIB        = null;
let EMP        = null;
let CASEN      = null;

// ── Helpers Supabase ────────────────────────────────────────────
async function supaFetch(table, params = "") {{
  const url = `${{SUPA_URL}}/rest/v1/${{table}}?${{params}}`;
  const res = await fetch(url, {{
    headers: {{
      "apikey": SUPA_KEY,
      "Authorization": "Bearer " + SUPA_KEY,
      "Accept": "application/json",
    }}
  }});
  if (!res.ok) throw new Error(`Supabase error ${{res.status}} en ${{table}}`);
  return res.json();
}}

async function supaFetchAll(table, params = "", pageSize = 1000) {{
  let all = [], offset = 0;
  while (true) {{
    const chunk = await supaFetch(table, `${{params}}&limit=${{pageSize}}&offset=${{offset}}`);
    all = all.concat(chunk);
    if (chunk.length < pageSize) break;
    offset += pageSize;
  }}
  return all;
}}

// ── Loader de datos ─────────────────────────────────────────────
function showLoader(msg) {{
  document.getElementById("app-loader").style.display = "flex";
  document.getElementById("loader-msg").textContent = msg;
}}
function hideLoader() {{
  document.getElementById("app-loader").style.display = "none";
}}

async function cargarDatos() {{
  showLoader("Cargando datos de seguridad...");

  // ── SEGURIDAD ──────────────────────────────────────────────────
  const [rawSeg, rawSemanas] = await Promise.all([
    supaFetchAll("registros_leystop", "select=*&order=id_semana,id_region"),
    supaFetchAll("leystop_semanas",   "select=*&order=id"),
  ]);

  // Limpiar nulls
  const clean = v => (v === undefined ? null : v);
  const cleanRow = row => Object.fromEntries(Object.entries(row).map(([k,v]) => [k, clean(v)]));

  const datosSegClean = rawSeg.map(cleanRow);
  const semanasClean  = rawSemanas.map(cleanRow);

  // Reconstruir semanas en el formato que espera el JS
  // (id_semana viene de registros_leystop, semanas tiene id)
  const semanasFormato = semanasClean.map(s => ({{
    id_semana: s.id,
    nombre: s.nombre,
    semana: s.semana,
    fecha_desde_iso: s.fecha_desde_iso,
    fecha_hasta_iso: s.fecha_hasta_iso,
    anno: s.anno,
  }}));

  const regionesSeg = [...new Set(datosSegClean.map(d => d.nombre_region))].filter(Boolean).sort();

  SEG = {{
    semanas: semanasFormato,
    datos:   datosSegClean,
    regiones: regionesSeg,
  }};

  DELITOS = {{ datos: [], nombres_delitos: [], tiene_datos: false }};

  showLoader("Cargando PIB regional...");

  // ── PIB ────────────────────────────────────────────────────────
  const rawPib = await supaFetchAll(
    "registros_bce",
    "select=nombre_region,periodo,valor_corregido,indicador_limpio,unidad_limpia,series_id&order=nombre_region,periodo"
  );

  // Reconstruir la estructura que espera el JS del dashboard
  const UNIDAD_ENC  = "miles de millones de pesos encadenados";
  const SECTORES_TRIM = ["PIB","PIB Producción de bienes","PIB Minería",
    "PIB Industria manufacturera","PIB Resto de bienes","PIB Comercio","PIB Servicios"];
  const SECTORES_ENC_ANUAL = ["PIB","PIB Agropecuario-silvícola","PIB Minería",
    "PIB Industria manufacturera","PIB Construcción","PIB Comercio",
    "PIB Servicios financieros y empresariales","PIB Servicios personales",
    "PIB Administración pública","PIB Restaurantes y hoteles",
    "PIB Electricidad, gas y agua","PIB Pesca"];

  function periodoALabel(p, freq) {{
    try {{
      const partes = p.split("T")[0].split("-");
      // formato ISO: YYYY-MM-DD
      const año = partes[0], mes = parseInt(partes[1]);
      if (freq === "anual") return año;
      const trim = {{1:"I",4:"II",7:"III",10:"IV"}}[mes] || "?";
      return `${{trim}}.${{año}}`;
    }} catch(e) {{ return p; }}
  }}

  function extraerAño(p) {{ return p ? p.split("-")[0] : null; }}
  function extraerMes(p) {{ return p ? parseInt(p.split("-")[1]) : null; }}

  function leerPorRegion(indicador, unidad, freq) {{
    const sufijo = freq === "anual" ? ".A" : ".T";
    const rows = rawPib.filter(r =>
      r.indicador_limpio === indicador &&
      r.unidad_limpia    === unidad &&
      r.nombre_region    !== null &&
      r.valor_corregido  !== null &&
      r.series_id?.endsWith(sufijo.slice(1))
    );
    const pr = {{}};
    for (const r of rows) {{
      const label = periodoALabel(r.periodo, freq);
      if (!pr[r.nombre_region]) pr[r.nombre_region] = {{}};
      // preferir base 2018
      const es2018 = r.series_id?.includes("2018") ? 1 : 0;
      if (!pr[r.nombre_region][label] || es2018)
        pr[r.nombre_region][label] = r.valor_corregido;
    }}
    return pr;
  }}

  function leerNacional(indicador, unidad, freq) {{
    const sufijo = freq === "anual" ? ".A" : ".T";
    const rows = rawPib.filter(r =>
      r.indicador_limpio === indicador &&
      r.unidad_limpia    === unidad &&
      r.nombre_region    === null &&
      r.valor_corregido  !== null &&
      r.series_id?.endsWith(sufijo.slice(1))
    );
    const res = {{}};
    for (const r of rows) {{
      const label = periodoALabel(r.periodo, freq);
      if (!res[label]) res[label] = r.valor_corregido;
    }}
    return res;
  }}

  function completarConTrimestres(indicador, unidad) {{
    const rows = rawPib.filter(r =>
      r.indicador_limpio === indicador &&
      r.unidad_limpia    === unidad &&
      r.nombre_region    !== null &&
      r.valor_corregido  !== null &&
      r.series_id?.endsWith("T")
    );
    const byRegAño = {{}};
    for (const r of rows) {{
      const mes = extraerMes(r.periodo);
      if (![1,4,7,10].includes(mes)) continue;
      const año = extraerAño(r.periodo);
      const key = `${{r.nombre_region}}|${{año}}`;
      if (!byRegAño[key]) byRegAño[key] = {{ reg: r.nombre_region, año, vals: [] }};
      byRegAño[key].vals.push(r.valor_corregido);
    }}
    const res = {{}};
    for (const {{ reg, año, vals }} of Object.values(byRegAño)) {{
      if (vals.length === 4) {{
        if (!res[reg]) res[reg] = {{}};
        res[reg][año] = Math.round(vals.reduce((a,b)=>a+b,0) * 10000) / 10000;
      }}
    }}
    return res;
  }}

  function sumTrimestresNacional(indicador, unidad) {{
    const rows = rawPib.filter(r =>
      r.indicador_limpio === indicador &&
      r.unidad_limpia    === unidad &&
      r.nombre_region    === null &&
      r.valor_corregido  !== null &&
      r.series_id?.endsWith("T")
    );
    const byAño = {{}};
    for (const r of rows) {{
      const mes = extraerMes(r.periodo);
      if (![1,4,7,10].includes(mes)) continue;
      const año = extraerAño(r.periodo);
      if (!byAño[año]) byAño[año] = [];
      byAño[año].push(r.valor_corregido);
    }}
    const res = {{}};
    for (const [año, vals] of Object.entries(byAño)) {{
      if (vals.length === 4) res[año] = Math.round(vals.reduce((a,b)=>a+b,0)*10000)/10000;
    }}
    return res;
  }}

  // Regiones PIB encadenado
  const regionesPib = [...new Set(
    rawPib.filter(r => r.nombre_region && r.unidad_limpia === UNIDAD_ENC && r.indicador_limpio === "PIB" && r.series_id?.includes("2018"))
          .map(r => r.nombre_region)
  )].sort();

  // Trimestral
  const datosTrim = {{}};
  for (const sector of SECTORES_TRIM) {{
    datosTrim[sector] = {{}};
    const pr = leerPorRegion(sector, "Porcentaje", "trimestral");
    if (Object.keys(pr).length) datosTrim[sector].var_pct = pr;
    const pe = leerPorRegion(sector, UNIDAD_ENC, "trimestral");
    if (Object.keys(pe).length) datosTrim[sector].miles_enc = pe;
  }}

  const extraTrimEnc    = leerNacional("Extrarregional", UNIDAD_ENC, "trimestral");
  const subtotalTrimEnc = leerNacional("PIB subtotal regionalizado", UNIDAD_ENC, "trimestral");

  // Anual encadenado
  const datosEncAnual = {{}};
  for (const sector of SECTORES_ENC_ANUAL) {{
    const pr = leerPorRegion(sector, UNIDAD_ENC, "anual");
    if (Object.keys(pr).length) datosEncAnual[sector] = pr;
    // Completar con trimestres donde falte
    const comp = completarConTrimestres(sector, UNIDAD_ENC);
    for (const [reg, años] of Object.entries(comp)) {{
      if (!datosEncAnual[sector]) datosEncAnual[sector] = {{}};
      if (!datosEncAnual[sector][reg]) datosEncAnual[sector][reg] = años;
    }}
  }}

  const extraEncAnual    = sumTrimestresNacional("Extrarregional", UNIDAD_ENC);
  const subtotalEncAnual = sumTrimestresNacional("PIB subtotal regionalizado", UNIDAD_ENC);

  // Labels de tiempo
  function sk(t) {{
    if (t.includes(".")) {{
      const [tr, yr] = t.split(".");
      return parseInt(yr)*10 + ({{I:1,II:2,III:3,IV:4}}[tr]||0);
    }}
    return parseInt(t)*10 || 99999;
  }}

  const periodosVarRaw = rawPib
    .filter(r => r.indicador_limpio==="PIB" && r.unidad_limpia==="Porcentaje" && r.nombre_region)
    .map(r => r.periodo);
  const trimestres = [...new Set(periodosVarRaw.map(p => periodoALabel(p,"trimestral")))].sort((a,b)=>sk(a)-sk(b));
  const añosTrim   = [...new Set(trimestres.map(t=>t.split(".")[1]))].sort();
  const añosEncAnual = [...new Set(
    Object.values(datosEncAnual).flatMap(rd => Object.values(rd).flatMap(rv => Object.keys(rv)))
  )].sort();

  PIB = {{
    regiones: regionesPib,
    años_trim: añosTrim,
    años_enc_anual: añosEncAnual,
    años_corr: añosEncAnual,
    trimestres,
    sectores_trim: SECTORES_TRIM,
    sectores_enc_anual: SECTORES_ENC_ANUAL,
    sectores_corr: SECTORES_ENC_ANUAL,
    datos_trim: datosTrim,
    datos_enc_anual: datosEncAnual,
    datos_corr: datosEncAnual,
    extra_trim_enc: extraTrimEnc,
    extra_enc_anual: extraEncAnual,
    extra_corr: extraEncAnual,
    subtotal_trim_enc: subtotalTrimEnc,
    subtotal_enc_anual: subtotalEncAnual,
    subtotal_corr: subtotalEncAnual,
  }};

  showLoader("Cargando datos de empleo...");

  // ── EMPLEO ─────────────────────────────────────────────────────
  const rawEmp = await supaFetchAll(
    "registros_bce_empleo",
    "select=nombre_region,periodo,indicador,valor&order=nombre_region,periodo"
  );

  const regionesEmp = [...new Set(rawEmp.map(r => r.nombre_region))].filter(Boolean).sort();
  const periodosEmp = [...new Set(rawEmp.map(r => r.periodo))].sort();
  const añosEmp     = [...new Set(periodosEmp.map(p => p.slice(0,4)))].sort();

  const datosEmp = {{}};
  for (const reg of regionesEmp) {{
    const tasaRows = rawEmp.filter(r => r.nombre_region===reg && r.indicador==="Tasa de desocupación").sort((a,b)=>a.periodo.localeCompare(b.periodo));
    const ocupRows = rawEmp.filter(r => r.nombre_region===reg && r.indicador==="Ocupados").sort((a,b)=>a.periodo.localeCompare(b.periodo));
    // Merge por periodo
    const periMap = {{}};
    for (const r of tasaRows) {{ if (!periMap[r.periodo]) periMap[r.periodo] = {{}}; periMap[r.periodo].tasa = r.valor; }}
    for (const r of ocupRows) {{ if (!periMap[r.periodo]) periMap[r.periodo] = {{}}; periMap[r.periodo].ocu  = r.valor; }}
    const perisMerge = Object.keys(periMap).sort();
    datosEmp[reg] = {{
      periodos: perisMerge,
      tasa:     perisMerge.map(p => periMap[p].tasa ?? null),
      ocupados: perisMerge.map(p => periMap[p].ocu  ?? null),
      ft:       perisMerge.map(p => {{
        const t = periMap[p].tasa, o = periMap[p].ocu;
        return (t != null && o != null && t < 100) ? Math.round(o/(1-t/100)*10)/10 : null;
      }}),
    }};
  }}

  EMP = {{ regiones: regionesEmp, periodos: periodosEmp, años: añosEmp, datos: datosEmp }};

  showLoader("Cargando Censo y CASEN...");

  // ── CENSO + CASEN (JSON estáticos del repo) ────────────────────
  const [censoJson, casenJson] = await Promise.all([
    fetch("censo_regiones.json").then(r => r.json()),
    fetch("casen_regiones.json").then(r => r.json()),
  ]);
  CENSO_DATA = censoJson;
  CASEN      = casenJson;

  hideLoader();
}}
"""

# ── Bloque de datos embebidos a reemplazar en el HTML ────────────────────────
OLD_DATA_BLOCK = """const SEG  = {data_seg_json};
const DELITOS = {data_delitos_json};
const CENSO_DATA = {data_censo_json};
const PIB  = {data_pib_json};"""

# El LOADER_JS reemplaza ese bloque
html_v2 = html_raw.replace(OLD_DATA_BLOCK, LOADER_JS.strip())

# ── EMP y CASEN embebidos (líneas sueltas más abajo) ─────────────────────────
html_v2 = html_v2.replace(
    "const EMP = {data_emp_json};",
    "// EMP cargado dinámicamente — ver cargarDatos()"
)
html_v2 = html_v2.replace(
    "const CASEN = {data_casen_json};",
    "// CASEN cargado dinámicamente — ver cargarDatos()"
)

# ── Reemplazar window.onload por init async ──────────────────────────────────
OLD_ONLOAD = "window.onload = function() {"
NEW_ONLOAD = """window.onload = async function() {
  try {
    await cargarDatos();
  } catch(err) {
    hideLoader();
    document.getElementById("app-loader").style.display = "flex";
    document.getElementById("loader-msg").textContent = "Error cargando datos: " + err.message;
    document.getElementById("loader-msg").style.color = "#dc2626";
    console.error(err);
    return;
  }
  // ── A partir de aquí, SEG/PIB/EMP/CASEN/CENSO_DATA están listos ──"""

html_v2 = html_v2.replace(OLD_ONLOAD, NEW_ONLOAD, 1)

# ── Agregar overlay de carga al <body> ───────────────────────────────────────
LOADER_HTML = """<div id="app-loader" style="position:fixed;inset:0;background:rgba(26,26,46,.92);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px">
  <div style="width:48px;height:48px;border:4px solid rgba(255,255,255,.2);border-top-color:#38bdf8;border-radius:50%;animation:spin 0.8s linear infinite"></div>
  <p id="loader-msg" style="color:white;font-size:14px;font-weight:500;font-family:system-ui">Iniciando dashboard...</p>
  <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
</div>
"""

html_v2 = html_v2.replace("<body>", "<body>\n" + LOADER_HTML, 1)

# ── Agregar DOCTYPE si no está ────────────────────────────────────────────────
if not html_v2.strip().startswith("<!DOCTYPE"):
    html_v2 = "<!DOCTYPE html>\n" + html_v2

# ── Escribir resultado ────────────────────────────────────────────────────────
OUT.write_text(html_v2, encoding="utf-8")
print(f"✅ {OUT} generado ({OUT.stat().st_size // 1024} KB)")
print("   - Datos de Seguridad: fetch desde Supabase (registros_leystop + leystop_semanas)")
print("   - PIB: fetch desde Supabase (registros_bce)")
print("   - Empleo: fetch desde Supabase (registros_bce_empleo)")
print("   - Censo y CASEN: fetch desde JSON estáticos del repo")
