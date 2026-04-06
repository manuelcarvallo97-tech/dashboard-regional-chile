"""
Generador módulo PIB — Dashboard Regional Chile v4
===================================================
- Tabla Resumen: % calculado sobre PIB nacional (subtotal regional + extrarregional)
- Fila Extrarregional incluida en tabla resumen
- Frecuencia Anual/Trimestral con indicadores correspondientes
- Tablas ordenables por columna
"""

import sqlite3
import pandas as pd
import json

DB_PATH = "bcn_indicadores.db"

def q(sql):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

def periodo_a_label(p, freq='anual'):
    try:
        partes = p.split('-')
        mes, año = int(partes[1]), partes[2]
        if freq == 'anual':
            return año
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

SECTORES_TRIM = ["PIB","PIB Producción de bienes","PIB Minería",
    "PIB Industria manufacturera","PIB Resto de bienes","PIB Comercio","PIB Servicios"]

SECTORES_CORR = ["PIB","PIB Agropecuario-silvícola","PIB Minería",
    "PIB Industria manufacturera","PIB Construcción","PIB Comercio",
    "PIB Servicios financieros y empresariales","PIB Servicios personales",
    "PIB Administración pública","PIB Restaurantes y hoteles",
    "PIB Electricidad, gas y agua","PIB Pesca"]

UNIDAD_CORR = "miles de millones de pesos corrientes (base 2018)"
UNIDAD_ENC  = "miles de millones de pesos encadenados"

regiones = q("SELECT DISTINCT nombre_region FROM registros_bcn ORDER BY nombre_region")['nombre_region'].tolist()

def leer_por_region(indicador_limpio, unidad_limpia, freq):
    df = q(f"""SELECT nombre_region, periodo, valor_corregido as valor
        FROM registros_bce
        WHERE indicador_limpio='{indicador_limpio}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NOT NULL AND valor_corregido IS NOT NULL
        ORDER BY nombre_region, periodo""")
    if df.empty: return {}
    df['label'] = df['periodo'].apply(lambda p: periodo_a_label(p, freq))
    pr = {}
    for reg in df['nombre_region'].unique():
        pr[reg] = df[df['nombre_region']==reg][['label','valor']].set_index('label')['valor'].to_dict()
    return pr

def leer_nacional(indicador_limpio, unidad_limpia, freq):
    """Lee series nacionales (nombre_region IS NULL)"""
    df = q(f"""SELECT periodo, valor_corregido as valor
        FROM registros_bce
        WHERE indicador_limpio='{indicador_limpio}' AND unidad_limpia='{unidad_limpia}'
        AND nombre_region IS NULL AND valor_corregido IS NOT NULL
        ORDER BY periodo""")
    if df.empty: return {}
    df['label'] = df['periodo'].apply(lambda p: periodo_a_label(p, freq))
    return df[['label','valor']].set_index('label')['valor'].to_dict()

# ── Trimestrales ──────────────────────────────────────────────────────────────
datos_trim = {}
for sector in SECTORES_TRIM:
    datos_trim[sector] = {}
    for clave, unidad in [('var_pct','Porcentaje'),('miles_enc', UNIDAD_ENC)]:
        pr = leer_por_region(sector, unidad, 'trimestral')
        if pr: datos_trim[sector][clave] = pr

# Extrarregional trimestral (para % nacional)
extra_trim_enc = leer_nacional('Extrarregional', UNIDAD_ENC, 'trimestral')
# PIB subtotal regionalizado trimestral
subtotal_trim_enc = leer_nacional('PIB subtotal regionalizado', UNIDAD_ENC, 'trimestral')

# ── Anuales corrientes ────────────────────────────────────────────────────────
datos_corr = {}
for sector in SECTORES_CORR:
    pr = leer_por_region(sector, UNIDAD_CORR, 'anual')
    if pr: datos_corr[sector] = pr

# Extrarregional anual corriente (para % nacional)
extra_corr = leer_nacional('Extrarregional', UNIDAD_CORR, 'anual')
# PIB subtotal regionalizado anual corriente
subtotal_corr = leer_nacional('PIB subtotal regionalizado', UNIDAD_CORR, 'anual')

# Períodos
periodos_trim_raw = sorted(
    q(f"SELECT DISTINCT periodo FROM registros_bce WHERE indicador_limpio='PIB' AND unidad_limpia='Porcentaje' AND nombre_region IS NOT NULL")['periodo'].tolist())
trimestres = sorted(set(periodo_a_label(p,'trimestral') for p in periodos_trim_raw), key=sk)
años_trim  = sorted(set(t.split('.')[1] for t in trimestres))
años_corr  = sorted(set(yr for rd in datos_corr.values() for rv in rd.values() for yr in rv.keys()))

data_js = {
    'regiones': regiones,
    'años_trim': años_trim,
    'años_corr': años_corr,
    'trimestres': trimestres,
    'sectores_trim': SECTORES_TRIM,
    'sectores_corr': SECTORES_CORR,
    'datos_trim': datos_trim,
    'datos_corr': datos_corr,
    'extra_trim_enc': extra_trim_enc,
    'extra_corr': extra_corr,
    'subtotal_trim_enc': subtotal_trim_enc,
    'subtotal_corr': subtotal_corr,
}
data_json = json.dumps(data_js, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>PIB Regional Chile</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e}}
header{{background:#1a1a2e;color:white;padding:16px 32px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
header h1{{font-size:17px;font-weight:600}}
header span{{font-size:12px;opacity:.7}}
.tabs{{background:white;border-bottom:2px solid #e8e8e8;padding:0 32px;display:flex;gap:4px}}
.tab{{padding:13px 22px;font-size:13px;font-weight:500;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;white-space:nowrap;color:#666;transition:all .2s}}
.tab:hover{{color:#2563eb}}.tab.active{{color:#2563eb;border-bottom-color:#2563eb;font-weight:600}}
.content{{padding:24px 32px;max-width:1500px;margin:0 auto}}
.section{{display:none}}.section.active{{display:block}}
.filtros{{background:white;border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.fg{{display:flex;flex-direction:column;gap:5px}}
.fg label{{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.4px}}
.fg select{{padding:7px 12px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px;background:white;cursor:pointer;outline:none;min-width:150px}}
.fg select:focus{{border-color:#2563eb}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin-bottom:22px}}
.kpi{{background:white;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #2563eb}}
.kpi.verde{{border-left-color:#16a34a}}.kpi.rojo{{border-left-color:#dc2626}}.kpi.amber{{border-left-color:#d97706}}
.kpi-label{{font-size:10px;color:#999;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.kpi-value{{font-size:24px;font-weight:700;color:#1a1a2e;line-height:1}}
.kpi-sub{{font-size:11px;color:#bbb;margin-top:5px}}
.card{{background:white;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px}}
.card h3{{font-size:14px;font-weight:600;color:#333;margin-bottom:16px}}
.card canvas{{max-height:320px}}
.tabla-wrap{{overflow-x:auto;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
table.dt{{width:100%;border-collapse:collapse;font-size:12.5px}}
table.dt th{{background:#1a1a2e;color:white;padding:9px 14px;text-align:center;font-weight:500;font-size:11px;white-space:nowrap;cursor:pointer;user-select:none}}
table.dt th:first-child{{text-align:left;min-width:200px;cursor:default}}
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
table.dt tr.nacional-row td:first-child{{font-weight:700}}
.neg{{color:#dc2626}}.pos{{color:#16a34a}}
.region-bar{{background:white;border-bottom:1px solid #e0e0e0;padding:10px 32px;display:flex;align-items:center;gap:14px}}
.region-bar label{{font-size:12px;font-weight:600;color:#666}}
.region-bar select{{padding:7px 12px;border:1.5px solid #d0d0d0;border-radius:8px;font-size:13px;min-width:260px;cursor:pointer;outline:none}}
.nota{{font-size:11px;color:#888;margin-top:10px;font-style:italic}}
</style>
</head>
<body>

<header>
  <h1>PIB Regional · Chile</h1>
  <span id="hdr-region">Selecciona una región</span>
</header>

<div class="region-bar">
  <label>Región:</label>
  <select id="region-sel" onchange="setRegion(this.value)"><option value="">-- Selecciona una región --</option></select>
</div>

<div class="tabs">
  <div class="tab active" onclick="setTab('evolucion',event)">Evolución</div>
  <div class="tab" onclick="setTab('sectores',event)">Sectores productivos</div>
  <div class="tab" onclick="setTab('resumen',event)">Resumen nacional</div>
</div>

<div class="content">

<!-- ═══ EVOLUCIÓN ═══ -->
<div class="section active" id="sec-evolucion">
  <div class="filtros">
    <div class="fg"><label>Frecuencia</label>
      <select id="evo-freq" onchange="onFreqChange('evo')">
        <option value="anual">Anual</option>
        <option value="trimestral">Trimestral</option>
      </select></div>
    <div class="fg"><label>Indicador</label><select id="evo-ind" onchange="renderEvolucion()"></select></div>
    <div class="fg"><label>Año desde</label><select id="evo-desde" onchange="renderEvolucion()"></select></div>
    <div class="fg"><label>Año hasta</label><select id="evo-hasta" onchange="renderEvolucion()"></select></div>
  </div>
  <div class="kpi-grid" id="kpi-evo"></div>
  <div class="card">
    <h3 id="evo-title">PIB</h3>
    <canvas id="chart-evo" style="max-height:320px"></canvas>
  </div>
</div>

<!-- ═══ SECTORES ═══ -->
<div class="section" id="sec-sectores">
  <div class="filtros">
    <div class="fg"><label>Frecuencia</label>
      <select id="sec-freq" onchange="onFreqChange('sec')">
        <option value="anual">Anual</option>
        <option value="trimestral">Trimestral</option>
      </select></div>
    <div class="fg"><label>Indicador</label><select id="sec-ind" onchange="renderSectores()"></select></div>
    <div class="fg"><label>Año desde</label><select id="sec-desde" onchange="renderSectores()"></select></div>
    <div class="fg"><label>Año hasta</label><select id="sec-hasta" onchange="renderSectores()"></select></div>
  </div>
  <div class="card">
    <h3 id="sec-title">Sectores productivos</h3>
    <div class="tabla-wrap"><table class="dt" id="tabla-sec"></table></div>
  </div>
</div>

<!-- ═══ RESUMEN ═══ -->
<div class="section" id="sec-resumen">
  <div class="filtros">
    <div class="fg"><label>Frecuencia</label>
      <select id="res-freq" onchange="onFreqChange('res')">
        <option value="anual">Anual</option>
        <option value="trimestral">Trimestral</option>
      </select></div>
    <div class="fg"><label>Indicador</label><select id="res-ind" onchange="renderResumen()"></select></div>
    <div class="fg"><label>Año desde</label><select id="res-desde" onchange="renderResumen()"></select></div>
    <div class="fg"><label>Año hasta</label><select id="res-hasta" onchange="renderResumen()"></select></div>
  </div>
  <div class="card">
    <h3 id="res-title">PIB por región</h3>
    <div class="tabla-wrap"><table class="dt" id="tabla-res"></table></div>
    <p class="nota" id="res-nota"></p>
  </div>
</div>

</div>

<script>
const DATA = {data_json};

const INDICADORES = {{
  anual: [
    {{v:'corrientes', l:'Miles de millones de pesos corrientes'}},
    {{v:'peso_corr',  l:'Peso % del PIB nacional (pesos corrientes)'}},
  ],
  trimestral: [
    {{v:'var_pct',    l:'Variación % vs mismo trimestre año anterior'}},
    {{v:'miles_enc',  l:'Miles de millones de pesos encadenados'}},
    {{v:'peso_enc',   l:'Peso % del PIB nacional (pesos encadenados)'}},
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

let regionActual='', tabActual='evolucion', charts={{}}, sortState={{}};

// ── Utils ─────────────────────────────────────────────────────────────────────
function sk(t) {{
  if(String(t).includes('.')){{const[tr,yr]=t.split('.');return parseInt(yr)*10+({{'I':1,'II':2,'III':3,'IV':4}}[tr]||0);}}
  const n=parseInt(t);return isNaN(n)?99999:n*10;
}}
function filtrar(ps, desde, hasta) {{
  return ps.filter(t=>{{const yr=String(t).includes('.')?parseInt(t.split('.')[1]):parseInt(t);return yr>=parseInt(desde)&&yr<=parseInt(hasta);}});
}}

// ── Acceso datos ──────────────────────────────────────────────────────────────
function getCorr(sector, region, t)  {{ try{{return DATA.datos_corr[sector][region][t]??null;}}catch{{return null;}} }}
function getTrim(sector, clave, region, t) {{ try{{return DATA.datos_trim[sector][clave][region][t]??null;}}catch{{return null;}} }}

function getVal(sector, ind, region, t) {{
  if(ind==='corrientes'||ind==='peso_corr') return getCorr(sector, region, t);
  return getTrim(sector, ind==='peso_enc'?'miles_enc':ind, region, t);
}}

// PIB nacional = subtotal regional + extrarregional
function getPIBNacional(ind, t) {{
  if(ind==='peso_corr'||ind==='corrientes') {{
    const sub = DATA.subtotal_corr[t] ?? null;
    const ext = DATA.extra_corr[t] ?? null;
    if(sub===null&&ext===null) return null;
    return (sub||0)+(ext||0);
  }} else {{
    const sub = DATA.subtotal_trim_enc[t] ?? null;
    const ext = DATA.extra_trim_enc[t] ?? null;
    if(sub===null&&ext===null) return null;
    return (sub||0)+(ext||0);
  }}
}}

function calcPeso(sector, ind, region, t) {{
  const v = getVal(sector, ind, region, t);
  const total = getPIBNacional(ind, t);
  if(v===null||!total) return null;
  return (v/total)*100;
}}

function calcPesoNacional(region, ind, t) {{
  // Peso de la región sobre el PIB nacional total
  const v = (ind==='peso_corr'||ind==='corrientes') ? getCorr('PIB',region,t) : getTrim('PIB',ind==='peso_enc'?'miles_enc':ind,region,t);
  const total = getPIBNacional(ind, t);
  if(v===null||!total) return null;
  return (v/total)*100;
}}

// ── Formato ───────────────────────────────────────────────────────────────────
function fmt(v, ind) {{
  if(v===null||v===undefined) return '—';
  if(['var_pct','peso_enc','peso_corr'].includes(ind)) return v.toFixed(2)+'%';
  return Math.round(v).toLocaleString('es-CL');
}}
function colorCls(v, ind) {{
  if(!['var_pct','peso_enc','peso_corr'].includes(ind)) return '';
  return v>0?'pos':v<0?'neg':'';
}}

// ── Chart ─────────────────────────────────────────────────────────────────────
function destroyChart(id){{if(charts[id]){{charts[id].destroy();delete charts[id];}}}}
function makeBar(id, labels, datasets) {{
  destroyChart(id);
  const ctx=document.getElementById(id);if(!ctx)return;
  charts[id]=new Chart(ctx,{{
    type:'bar',data:{{labels,datasets}},
    options:{{responsive:true,maintainAspectRatio:true,
      plugins:{{legend:{{display:false}},tooltip:{{mode:'index',intersect:false}}}},
      scales:{{x:{{ticks:{{font:{{size:10}},maxRotation:60}},grid:{{display:false}}}},y:{{ticks:{{font:{{size:10}}}},grid:{{color:'#f0f0f0'}}}}}}
    }}
  }});
}}

// ── Selects ───────────────────────────────────────────────────────────────────
function poblarIndicadores(prefix, freq) {{
  const sel=document.getElementById(prefix+'-ind');
  const prev=sel.value; sel.innerHTML='';
  INDICADORES[freq].forEach(o=>{{const opt=document.createElement('option');opt.value=o.v;opt.textContent=o.l;sel.appendChild(opt);}});
  sel.value=INDICADORES[freq].some(o=>o.v===prev)?prev:INDICADORES[freq][0].v;
}}
function poblarAños(prefix, lista, n=6) {{
  ['desde','hasta'].forEach((s,i)=>{{
    const sel=document.getElementById(prefix+'-'+s),prev=sel.value;sel.innerHTML='';
    lista.forEach(a=>{{const o=document.createElement('option');o.value=a;o.textContent=a;sel.appendChild(o);}});
    sel.value=i===0?(lista.includes(prev)?prev:lista[Math.max(0,lista.length-n)]):(lista.includes(prev)?prev:lista[lista.length-1]);
  }});
}}
function getAños(freq){{return freq==='anual'?DATA.años_corr:DATA.años_trim;}}
function getPeriodos(freq){{return freq==='anual'?DATA.años_corr:DATA.trimestres;}}
function getSectores(freq){{return freq==='anual'?DATA.sectores_corr:DATA.sectores_trim;}}

function onFreqChange(prefix) {{
  const freq=document.getElementById(prefix+'-freq').value;
  poblarIndicadores(prefix, freq);
  poblarAños(prefix, getAños(freq), prefix==='evo'?8:6);
  if(prefix==='evo') renderEvolucion();
  if(prefix==='sec') renderSectores();
  if(prefix==='res') renderResumen();
}}

// ── Nav ───────────────────────────────────────────────────────────────────────
function setRegion(r){{regionActual=r;document.getElementById('hdr-region').textContent=r||'Selecciona una región';renderTab(tabActual);}}
function setTab(tab,ev){{
  tabActual=tab;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  if(ev)ev.target.classList.add('active');
  document.getElementById('sec-'+tab).classList.add('active');
  renderTab(tab);
}}
function renderTab(t){{if(t==='evolucion')renderEvolucion();if(t==='sectores')renderSectores();if(t==='resumen')renderResumen();}}

// ══════════════════════════════
// PESTAÑA 1: EVOLUCIÓN
// ══════════════════════════════
function renderEvolucion() {{
  const freq=document.getElementById('evo-freq').value;
  const ind=document.getElementById('evo-ind').value;
  const desde=document.getElementById('evo-desde').value;
  const hasta=document.getElementById('evo-hasta').value;
  const ps=filtrar(getPeriodos(freq),desde,hasta);
  const lbl=INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  document.getElementById('evo-title').textContent='PIB — '+lbl;

  if(!regionActual){{document.getElementById('kpi-evo').innerHTML='<p style="color:#aaa;font-size:13px">Selecciona una región</p>';return;}}

  const esPeso=ind.startsWith('peso_');
  const vals=esPeso?ps.map(t=>calcPesoNacional(regionActual,ind,t)):ps.map(t=>getVal('PIB',ind,regionActual,t));

  const noNull=vals.filter(v=>v!==null);
  const ultimo=noNull[noNull.length-1];
  const lUlt=ps.filter((_,i)=>vals[i]!==null).slice(-1)[0];
  const prev=freq==='anual'?noNull[noNull.length-2]:noNull[noNull.length-5];
  const lPrev=freq==='anual'?ps.filter((_,i)=>vals[i]!==null).slice(-2)[0]:ps.filter((_,i)=>vals[i]!==null).slice(-5)[0];
  const prom=noNull.length?noNull.reduce((a,b)=>a+b,0)/noNull.length:null;

  let kh='';
  if(ultimo!==null)kh+=kpiCard('Último período',fmt(ultimo,ind),lUlt||'',(ind==='var_pct'?(ultimo>=0?'verde':'rojo'):''));
  if(prev!==null)kh+=kpiCard(freq==='anual'?'Año anterior':'Mismo trim. año ant.',fmt(prev,ind),lPrev||'',(ind==='var_pct'?(prev>=0?'verde':'rojo'):''));
  if(prom!==null)kh+=kpiCard('Promedio período',fmt(prom,ind),desde+'–'+hasta);
  document.getElementById('kpi-evo').innerHTML=kh;

  const bg=vals.map(v=>{{if(v===null)return'rgba(0,0,0,0)';if(['var_pct','peso_enc','peso_corr'].includes(ind))return v>=0?'rgba(22,163,74,.75)':'rgba(220,38,38,.75)';return'rgba(37,99,235,.75)';}});
  makeBar('chart-evo',ps,[{{label:lbl,data:vals,backgroundColor:bg,borderRadius:3}}]);
}}

// ══════════════════════════════
// PESTAÑA 2: SECTORES
// ══════════════════════════════
function renderSectores() {{
  const freq=document.getElementById('sec-freq').value;
  const ind=document.getElementById('sec-ind').value;
  const desde=document.getElementById('sec-desde').value;
  const hasta=document.getElementById('sec-hasta').value;
  const ps=filtrar(getPeriodos(freq),desde,hasta);
  const sects=getSectores(freq);
  const lbl=INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  document.getElementById('sec-title').textContent=(regionActual||'Región')+' — sectores — '+lbl;

  if(!regionActual){{document.getElementById('tabla-sec').innerHTML='<tr><td colspan="99" style="padding:20px;color:#aaa;text-align:center">Selecciona una región</td></tr>';return;}}

  const esPeso=ind.startsWith('peso_');
  let thead=buildThead('tabla-sec',['Sector',...ps]);
  let tbody='<tbody>';
  sects.forEach(sector=>{{
    const esTotal=sector==='PIB';
    const vals=ps.map(t=>esPeso?calcPeso(sector,ind,regionActual,t):getVal(sector,ind,regionActual,t));
    tbody+=`<tr><td class="${{esTotal?'total':''}}">${{DISP[sector]||sector}}</td>`;
    vals.forEach(v=>{{const cc=v!==null?colorCls(v,ind):'';tbody+=`<td class="${{esTotal?'total':''}} ${{cc}}">${{fmt(v,ind)}}</td>`;}});
    tbody+='</tr>';
  }});
  tbody+='</tbody>';
  document.getElementById('tabla-sec').innerHTML=thead+tbody;
  attachSort('tabla-sec');
}}

// ══════════════════════════════
// PESTAÑA 3: RESUMEN NACIONAL
// ══════════════════════════════
function renderResumen() {{
  const freq=document.getElementById('res-freq').value;
  const ind=document.getElementById('res-ind').value;
  const desde=document.getElementById('res-desde').value;
  const hasta=document.getElementById('res-hasta').value;
  const ps=filtrar(getPeriodos(freq),desde,hasta);
  const lbl=INDICADORES[freq].find(o=>o.v===ind)?.l||ind;
  const esPeso=ind.startsWith('peso_');

  document.getElementById('res-title').textContent='PIB por región — '+lbl;

  // Para % el denominador es PIB nacional (subtotal+extrarregional)
  let thead=buildThead('tabla-res',['Región',...ps]);
  let tbody='<tbody>';

  // Filas de regiones
  DATA.regiones.forEach(reg=>{{
    const vals=ps.map(t=>esPeso?calcPesoNacional(reg,ind,t):getVal('PIB',ind,reg,t));
    tbody+=`<tr><td>${{reg}}</td>`;
    vals.forEach(v=>{{const cc=v!==null?colorCls(v,ind):'';tbody+=`<td class="${{cc}}">${{fmt(v,ind)}}</td>`;}});
    tbody+='</tr>';
  }});

  // Fila Extrarregional
  const extraVals=ps.map(t=>{{
    if(esPeso){{
      const vExtra=ind==='peso_corr'?DATA.extra_corr[t]:DATA.extra_trim_enc[t];
      const total=getPIBNacional(ind,t);
      return(vExtra&&total)?(vExtra/total*100):null;
    }}
    return ind==='corrientes'?DATA.extra_corr[t]:DATA.extra_trim_enc[t]??null;
  }});
  tbody+='<tr class="extra-row"><td>Extrarregional</td>';
  extraVals.forEach(v=>{{const cc=v!==null?colorCls(v,ind):'';tbody+=`<td class="${{cc}}">${{fmt(v,ind)}}</td>`;}});
  tbody+='</tr>';

  // Fila Total nacional
  const totalVals=ps.map(t=>{{
    const nac=getPIBNacional(ind,t);
    if(esPeso) return nac?100:null;
    return nac;
  }});
  tbody+='<tr class="nacional-row"><td>Total nacional</td>';
  totalVals.forEach(v=>tbody+=`<td>${{fmt(v,ind)}}</td>`);
  tbody+='</tr>';

  tbody+='</tbody>';
  document.getElementById('tabla-res').innerHTML=thead+tbody;

  // Nota
  const nota=esPeso?'% calculado sobre el total nacional (subtotal regional + extrarregional). La suma de regiones + extrarregional = 100%.':'';
  document.getElementById('res-nota').textContent=nota;

  attachSort('tabla-res');
}}

// ── Sort ──────────────────────────────────────────────────────────────────────
function buildThead(tableId, cols) {{
  sortState[tableId]={{col:null,dir:null}};
  let tr='<thead><tr>';
  cols.forEach((c,i)=>{{
    if(i===0) tr+=`<th style="cursor:default">${{c}}</th>`;
    else tr+=`<th onclick="sortTable('${{tableId}}',${{i}})" data-col="${{i}}">${{c}}</th>`;
  }});
  return tr+'</tr></thead>';
}}

function sortTable(tableId, col) {{
  const tbl=document.getElementById(tableId);
  const state=sortState[tableId];
  const dir=(state.col===col&&state.dir==='desc')?'asc':'desc';
  state.col=col;state.dir=dir;
  tbl.querySelectorAll('th').forEach(th=>{{th.classList.remove('asc','desc');if(parseInt(th.getAttribute('data-col'))===col)th.classList.add(dir);}});
  const tbody=tbl.querySelector('tbody');
  const rows=Array.from(tbody.querySelectorAll('tr'));
  // Separar filas especiales (extrarregional, total) para que queden siempre al fondo
  const especiales=rows.filter(r=>r.classList.contains('extra-row')||r.classList.contains('nacional-row'));
  const normales=rows.filter(r=>!r.classList.contains('extra-row')&&!r.classList.contains('nacional-row'));
  normales.sort((a,b)=>{{
    const av=a.cells[col]?.textContent.trim().replace(/[%\s,]/g,'').replace('.','');
    const bv=b.cells[col]?.textContent.trim().replace(/[%\s,]/g,'').replace('.','');
    const an=parseFloat(av),bn=parseFloat(bv);
    const cmp=isNaN(an)||isNaN(bn)?av.localeCompare(bv,'es'):an-bn;
    return dir==='asc'?cmp:-cmp;
  }});
  [...normales,...especiales].forEach(r=>tbody.appendChild(r));
}}

function attachSort(tableId) {{}}

function kpiCard(label,value,sub='',cls=''){{
  return `<div class="kpi ${{cls}}"><div class="kpi-label">${{label}}</div><div class="kpi-value">${{value}}</div><div class="kpi-sub">${{sub}}</div></div>`;
}}

// ── Init ──────────────────────────────────────────────────────────────────────
window.onload=function(){{
  const sel=document.getElementById('region-sel');
  DATA.regiones.forEach(r=>{{const o=document.createElement('option');o.value=r;o.textContent=r;sel.appendChild(o);}});
  ['evo','sec','res'].forEach(p=>{{
    poblarIndicadores(p,'anual');
    poblarAños(p,DATA.años_corr,p==='evo'?8:6);
  }});
}};
</script>
</body>
</html>"""

html = html.replace('{data_json}', data_json)
with open("dashboard_pib.html","w",encoding="utf-8") as f:
    f.write(html)

print("=== dashboard_pib.html generado ===")
print(f"Trimestres: {trimestres[0]} → {trimestres[-1]}")
print(f"Años corrientes: {años_corr[0]} → {años_corr[-1]}")
print(f"Extrarregional anual (base 2018): {len(extra_corr)} obs → {list(extra_corr.items())[:3]}")
print(f"Extrarregional trimestral enc: {len(extra_trim_enc)} obs")
print(f"Subtotal anual: {len(subtotal_corr)} obs")
