"""
Genera dashboard_seguridad.html con datos de LeyStop
Pestañas: Resumen regional | Evolución temporal | Ranking delitos
"""
import sqlite3, json
DB_PATH = "bcn_indicadores.db"

def q(sql):
    conn = sqlite3.connect(DB_PATH)
    import pandas as pd
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

# ── Datos LeyStop ─────────────────────────────────────────────────────────────
# Semanas disponibles
semanas = q("""
    SELECT DISTINCT r.id_semana, s.nombre, s.semana, s.fecha_desde_iso, s.fecha_hasta_iso,
           s.anno
    FROM registros_leystop r
    JOIN leystop_semanas s ON r.id_semana = s.id
    ORDER BY r.id_semana
""")

# Datos por región y semana
datos = q("""
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
           r.allanamientos_anno, r.vehiculos_recuperados_anno,
           r.decomisos_anno
    FROM registros_leystop r
    ORDER BY r.id_semana, r.id_region
""")

regiones = sorted(datos['nombre_region'].unique().tolist())
semanas_list = semanas.to_dict('records')
datos_list = datos.to_dict('records')

# Convertir NaN a None para JSON
import math
def clean(v):
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    return v

datos_clean = [{k: clean(v) for k,v in row.items()} for row in datos_list]
semanas_clean = [{k: clean(v) for k,v in row.items()} for row in semanas_list]

data_json = json.dumps({
    'semanas': semanas_clean,
    'datos': datos_clean,
    'regiones': regiones,
}, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Seguridad Regional · Chile</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e}}
header{{background:#1a1a2e;color:white;padding:16px 32px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
header h1{{font-size:17px;font-weight:600}}
.tabs{{background:white;border-bottom:2px solid #e8e8e8;padding:0 32px;display:flex;gap:4px}}
.tab{{padding:13px 22px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;color:#666;transition:all .2s;white-space:nowrap}}
.tab:hover{{color:#16a34a}}.tab.active{{color:#16a34a;border-bottom-color:#16a34a;font-weight:600}}
.content{{padding:24px 32px;max-width:1500px;margin:0 auto}}
.section{{display:none}}.section.active{{display:block}}
.filtros{{background:white;border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.fg{{display:flex;flex-direction:column;gap:5px}}
.fg label{{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.4px}}
.fg select{{padding:7px 12px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px;background:white;cursor:pointer;outline:none;min-width:180px}}
.fg select:focus{{border-color:#16a34a}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin-bottom:22px}}
.kpi{{background:white;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #16a34a}}
.kpi.rojo{{border-left-color:#dc2626}}.kpi.verde{{border-left-color:#16a34a}}.kpi.amber{{border-left-color:#d97706}}.kpi.azul{{border-left-color:#2563eb}}
.kpi-label{{font-size:10px;color:#999;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.kpi-value{{font-size:22px;font-weight:700;color:#1a1a2e;line-height:1}}
.kpi-sub{{font-size:11px;color:#bbb;margin-top:5px}}
.card{{background:white;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px}}
.card h3{{font-size:14px;font-weight:600;color:#333;margin-bottom:16px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.tabla-wrap{{overflow-x:auto;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
table.dt{{width:100%;border-collapse:collapse;font-size:12.5px}}
table.dt th{{background:#1a1a2e;color:white;padding:9px 14px;text-align:center;font-weight:500;font-size:11px;white-space:nowrap;cursor:pointer;user-select:none}}
table.dt th:first-child{{text-align:left;cursor:default}}
table.dt th:hover:not(:first-child){{background:#2d3a55}}
table.dt th.asc::after{{content:' ▲';font-size:9px}}
table.dt th.desc::after{{content:' ▼';font-size:9px}}
table.dt td{{padding:8px 14px;border-bottom:1px solid #f0f0f0;text-align:right;white-space:nowrap}}
table.dt td:first-child{{text-align:left;font-weight:500;background:#fafafa}}
table.dt tr:hover td{{background:#f0fff4}}
table.dt tr:hover td:first-child{{background:#dcfce7}}
.neg{{color:#dc2626;font-weight:600}}.pos{{color:#16a34a;font-weight:600}}
.bar-wrap{{display:flex;align-items:center;gap:8px}}
.bar{{height:8px;background:#16a34a;border-radius:4px;min-width:2px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}}
.badge-baja{{background:#dcfce7;color:#166534}}.badge-alta{{background:#fef2f2;color:#991b1b}}.badge-media{{background:#fef9c3;color:#713f12}}
</style>
</head>
<body>
<header>
  <h1>🛡 Seguridad Pública · Ley S.T.O.P · Chile</h1>
  <span id="hdr-info" style="font-size:12px;opacity:.7">Fuente: Carabineros de Chile · LeyStop</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="setTab('resumen',event)">Resumen por región</div>
  <div class="tab" onclick="setTab('evolucion',event)">Evolución temporal</div>
  <div class="tab" onclick="setTab('operativo',event)">Actividad operativa</div>
</div>

<div class="content">

<!-- ═══ RESUMEN ═══ -->
<div class="section active" id="sec-resumen">
  <div class="filtros">
    <div class="fg"><label>Semana</label>
      <select id="res-semana" onchange="renderResumen()"></select></div>
  </div>
  <div class="kpi-grid" id="kpi-resumen"></div>
  <div class="card">
    <h3 id="res-title">Casos año a la fecha y variación por región</h3>
    <div class="tabla-wrap">
      <table class="dt" id="tabla-resumen"></table>
    </div>
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

<!-- ═══ EVOLUCIÓN ═══ -->
<div class="section" id="sec-evolucion">
  <div class="filtros">
    <div class="fg"><label>Región</label>
      <select id="evo-region" onchange="renderEvolucion()"></select></div>
    <div class="fg"><label>Indicador</label>
      <select id="evo-ind" onchange="renderEvolucion()">
        <option value="casos_anno_fecha">Casos año a la fecha</option>
        <option value="tasa_registro">Tasa por 100 mil hab.</option>
        <option value="casos_ultima_semana">Casos última semana</option>
        <option value="casos_28dias">Casos últimos 28 días</option>
        <option value="var_anno_fecha">Variación % año a la fecha</option>
      </select></div>
  </div>
  <div class="card">
    <h3 id="evo-title">Evolución temporal</h3>
    <canvas id="chart-evo" style="max-height:340px"></canvas>
  </div>
  <div class="card">
    <h3 id="evo-delitos-title">Top 5 delitos — año a la fecha</h3>
    <canvas id="chart-evo-delitos" style="max-height:280px"></canvas>
  </div>
</div>

<!-- ═══ OPERATIVO ═══ -->
<div class="section" id="sec-operativo">
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

</div>

<script>
const DATA = {data_json};
let charts = {{}};
let sortState = {{}};

function destroyChart(id) {{ if(charts[id]){{charts[id].destroy();delete charts[id];}} }}

function makeBar(id, labels, datasets, opts={{}}) {{
  destroyChart(id);
  const ctx = document.getElementById(id); if(!ctx) return;
  charts[id] = new Chart(ctx, {{
    type: opts.type||'bar',
    data: {{labels, datasets}},
    options: {{
      responsive:true, maintainAspectRatio:true, indexAxis: opts.horizontal?'y':'x',
      plugins:{{
        legend:{{display:datasets.length>1,position:'bottom',labels:{{font:{{size:11}},padding:10}}}},
        tooltip:{{mode:'index',intersect:false}}
      }},
      scales:{{
        x:{{ticks:{{font:{{size:10}},maxRotation: opts.horizontal?0:55}},grid:{{display:opts.horizontal}}}},
        y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}
      }}
    }}
  }});
}}

function pct(v) {{ return v===null||v===undefined?'—':v.toFixed(1)+'%'; }}
function num(v) {{ return v===null||v===undefined?'—':Math.round(v).toLocaleString('es-CL'); }}
function clsCambio(v) {{ return v===null?'':v<0?'neg':'pos'; }}
function fmtCambio(v) {{ return v===null?'—':(v>0?'+':'')+v.toFixed(1)+'%'; }}

function datosParaSemana(id_semana) {{
  return DATA.datos.filter(d => d.id_semana === id_semana);
}}

function datosParaRegion(region) {{
  return DATA.datos.filter(d => d.nombre_region === region).sort((a,b)=>a.id_semana-b.id_semana);
}}

// ── Poblar selects ──────────────────────────────────────────────────────────
function poblarSemana(selId, handler) {{
  const sel = document.getElementById(selId);
  DATA.semanas.forEach(s => {{
    const o = document.createElement('option');
    o.value = s.id_semana; o.textContent = s.nombre; sel.appendChild(o);
  }});
  sel.value = DATA.semanas[DATA.semanas.length-1].id_semana;
  sel.onchange = handler;
}}

function poblarRegion(selId, handler) {{
  const sel = document.getElementById(selId);
  DATA.regiones.forEach(r => {{
    const o = document.createElement('option'); o.value=r; o.textContent=r; sel.appendChild(o);
  }});
  sel.onchange = handler;
}}

// ── RESUMEN ──────────────────────────────────────────────────────────────────
function renderResumen() {{
  const id_sem = parseInt(document.getElementById('res-semana').value);
  const filas = datosParaSemana(id_sem);
  const sem = DATA.semanas.find(s => s.id_semana===id_sem);

  document.getElementById('res-title').textContent =
    `Casos año a la fecha — ${{sem?.nombre||''}}`;

  // KPIs nacionales (suma)
  const totalCasos = filas.reduce((a,r)=>a+(r.casos_anno_fecha||0),0);
  const totalSemana = filas.reduce((a,r)=>a+(r.casos_ultima_semana||0),0);
  const varProm = filas.filter(r=>r.var_anno_fecha!==null).reduce((a,r,_,arr)=>a+r.var_anno_fecha/arr.length,0);
  const tasaProm = filas.filter(r=>r.tasa_registro!==null).reduce((a,r,_,arr)=>a+r.tasa_registro/arr.length,0);

  document.getElementById('kpi-resumen').innerHTML = `
    <div class="kpi azul"><div class="kpi-label">Casos año a la fecha</div><div class="kpi-value">${{num(totalCasos)}}</div><div class="kpi-sub">Total nacional</div></div>
    <div class="kpi ${{varProm<0?'verde':'rojo'}}"><div class="kpi-label">Variación año a la fecha</div><div class="kpi-value">${{fmtCambio(varProm)}}</div><div class="kpi-sub">Promedio regional</div></div>
    <div class="kpi azul"><div class="kpi-label">Casos última semana</div><div class="kpi-value">${{num(totalSemana)}}</div><div class="kpi-sub">Nacional</div></div>
    <div class="kpi amber"><div class="kpi-label">Tasa por 100 mil hab.</div><div class="kpi-value">${{tasaProm.toFixed(1)}}</div><div class="kpi-sub">Promedio regional</div></div>
  `;

  // Tabla
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

  // Gráfico tasa
  const sorted = [...filas].sort((a,b)=>(b.tasa_registro||0)-(a.tasa_registro||0));
  makeBar('chart-tasa',
    sorted.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [{{label:'Tasa/100mil hab.',
      data: sorted.map(r=>r.tasa_registro),
      backgroundColor: sorted.map(r=>r.tasa_registro>500?'rgba(220,38,38,.8)':r.tasa_registro>400?'rgba(217,119,6,.8)':'rgba(22,163,74,.8)'),
      borderRadius:3}}],
    {{horizontal:true}});

  // Gráfico delitos más frecuentes
  const delitoCount = {{}};
  filas.forEach(r=>{{if(r.mayor_registro_1){{delitoCount[r.mayor_registro_1]=(delitoCount[r.mayor_registro_1]||0)+1;}}}});
  const delSorted = Object.entries(delitoCount).sort((a,b)=>b[1]-a[1]);
  makeBar('chart-delitos',
    delSorted.map(d=>d[0].length>30?d[0].substring(0,30)+'...':d[0]),
    [{{label:'Nº regiones',data:delSorted.map(d=>d[1]),
      backgroundColor:'rgba(37,99,235,.75)',borderRadius:3}}],
    {{horizontal:true}});
}}

// ── EVOLUCIÓN ────────────────────────────────────────────────────────────────
function renderEvolucion() {{
  const region = document.getElementById('evo-region').value;
  const ind = document.getElementById('evo-ind').value;
  const filas = datosParaRegion(region);

  const labels = filas.map(r => r.semana);
  const vals = filas.map(r => r[ind]);

  const indLabels = {{
    casos_anno_fecha: 'Casos año a la fecha',
    tasa_registro: 'Tasa por 100 mil hab.',
    casos_ultima_semana: 'Casos última semana',
    casos_28dias: 'Casos últimos 28 días',
    var_anno_fecha: 'Variación % año a la fecha',
  }};

  document.getElementById('evo-title').textContent = `${{region}} — ${{indLabels[ind]}}`;

  const esVar = ind === 'var_anno_fecha';
  const colores = esVar
    ? vals.map(v=>v===null?'#ccc':v<0?'rgba(22,163,74,.8)':'rgba(220,38,38,.8)')
    : 'rgba(22,163,74,.75)';

  makeBar('chart-evo', labels,
    [{{label: indLabels[ind], data: vals,
      backgroundColor: colores,
      borderRadius: 3,
      type: esVar ? 'bar' : 'bar'}}]);

  // Top 5 delitos evolución
  document.getElementById('evo-delitos-title').textContent = `${{region}} — top delitos por semana (% del total)`;
  const delitos = ['mayor_registro_1','mayor_registro_2','mayor_registro_3','mayor_registro_4','mayor_registro_5'];
  const pcts    = ['pct_1','pct_2','pct_3','pct_4','pct_5'];
  const coloresD = ['rgba(22,163,74,.8)','rgba(37,99,235,.8)','rgba(217,119,6,.8)','rgba(220,38,38,.8)','rgba(147,51,234,.8)'];

  // Recopilar todos los delitos únicos
  const todosDelitos = [...new Set(filas.flatMap(r=>delitos.map(d=>r[d]).filter(Boolean)))];

  const datasets = todosDelitos.slice(0,5).map((del,i) => {{
    const data = filas.map(r => {{
      const idx = delitos.findIndex(d=>r[d]===del);
      return idx>=0 ? r[pcts[idx]] : null;
    }});
    return {{
      label: del.length>35?del.substring(0,35)+'...':del,
      data, backgroundColor: coloresD[i], borderRadius:2,
    }};
  }});

  makeBar('chart-evo-delitos', labels, datasets);
}}

// ── OPERATIVO ────────────────────────────────────────────────────────────────
function renderOperativo() {{
  const id_sem = parseInt(document.getElementById('op-semana').value);
  const filas = datosParaSemana(id_sem);

  const totCtrl = filas.reduce((a,r)=>a+(r.controles||0),0);
  const totFisc = filas.reduce((a,r)=>a+(r.fiscalizaciones||0),0);
  const totIncaut = filas.reduce((a,r)=>a+(r.incautaciones||0),0);
  const totDecom = filas.filter(r=>r.decomisos_anno!==null).reduce((a,r)=>a+(r.decomisos_anno||0),0);

  document.getElementById('kpi-op').innerHTML = `
    <div class="kpi azul"><div class="kpi-label">Controles realizados</div><div class="kpi-value">${{num(totCtrl)}}</div><div class="kpi-sub">Identidad + vehicular</div></div>
    <div class="kpi azul"><div class="kpi-label">Fiscalizaciones</div><div class="kpi-value">${{num(totFisc)}}</div><div class="kpi-sub">Alcohol + bancaria</div></div>
    <div class="kpi rojo"><div class="kpi-label">Incautaciones armas</div><div class="kpi-value">${{num(totIncaut)}}</div><div class="kpi-sub">Fuego + blancas</div></div>
    <div class="kpi amber"><div class="kpi-label">Decomisos drogas</div><div class="kpi-value">${{num(Math.round(totDecom))}}</div><div class="kpi-sub">Año a la fecha</div></div>
  `;

  const sorted = [...filas].sort((a,b)=>(b.controles||0)-(a.controles||0));
  makeBar('chart-controles',
    sorted.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [
      {{label:'Identidad', data:sorted.map(r=>r.controles_identidad), backgroundColor:'rgba(37,99,235,.75)',borderRadius:2}},
      {{label:'Vehicular', data:sorted.map(r=>r.controles_vehicular), backgroundColor:'rgba(22,163,74,.75)',borderRadius:2}},
    ], {{horizontal:true}});

  const sorted2 = [...filas].sort((a,b)=>(b.incautaciones||0)-(a.incautaciones||0));
  makeBar('chart-incaut',
    sorted2.map(r=>r.nombre_region.replace('Metropolitana de Santiago','RM')),
    [
      {{label:'Armas de fuego', data:sorted2.map(r=>r.incaut_fuego), backgroundColor:'rgba(220,38,38,.75)',borderRadius:2}},
      {{label:'Armas blancas', data:sorted2.map(r=>r.incaut_blancas), backgroundColor:'rgba(217,119,6,.75)',borderRadius:2}},
    ], {{horizontal:true}});
}}

// ── Sort tabla ───────────────────────────────────────────────────────────────
function sortDT(tableId, col) {{
  const tbl = document.getElementById(tableId);
  if (!sortState[tableId]) sortState[tableId] = {{}};
  const dir = sortState[tableId].col===col && sortState[tableId].dir==='desc' ? 'asc' : 'desc';
  sortState[tableId] = {{col, dir}};
  tbl.querySelectorAll('th').forEach(th=>th.classList.remove('asc','desc'));
  const ths = tbl.querySelectorAll('th');
  if(ths[col]) ths[col].classList.add(dir);
  const tbody = tbl.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a,b)=>{{
    const av=a.cells[col]?.textContent.trim().replace(/[%+\s,.]/g,'');
    const bv=b.cells[col]?.textContent.trim().replace(/[%+\s,.]/g,'');
    const an=parseFloat(av), bn=parseFloat(bv);
    const cmp=isNaN(an)||isNaN(bn)?av.localeCompare(bv,'es'):an-bn;
    return dir==='asc'?cmp:-cmp;
  }});
  rows.forEach(r=>tbody.appendChild(r));
}}

// ── Nav ───────────────────────────────────────────────────────────────────────
function setTab(tab, ev) {{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  if(ev) ev.target.classList.add('active');
  document.getElementById('sec-'+tab).classList.add('active');
  if(tab==='resumen') renderResumen();
  if(tab==='evolucion') renderEvolucion();
  if(tab==='operativo') renderOperativo();
}}

// ── Init ─────────────────────────────────────────────────────────────────────
window.onload = function() {{
  poblarSemana('res-semana', renderResumen);
  poblarSemana('op-semana', renderOperativo);
  poblarRegion('evo-region', renderEvolucion);
  renderResumen();
}};
</script>
</body>
</html>"""

with open("dashboard_seguridad.html","w",encoding="utf-8") as f:
    f.write(html)
print("=== dashboard_seguridad.html generado ===")
print(f"Semanas: {len(semanas_clean)}, Regiones: {len(regiones)}, Registros: {len(datos_clean)}")
