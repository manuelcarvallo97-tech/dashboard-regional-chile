"""
parche_pdf_dashboard.py — v5 (definitivo, no toca generar_dashboard.py)
========================================================================
ESTRATEGIA NUEVA: no modifica generar_dashboard.py en absoluto.
En cambio:
  1. Genera pdf_minuta.js  (el JS del modal y generador PDF)
  2. Modifica dashboard.html DESPUES de que generar_dashboard.py lo crea,
     inyectando el <script src>, el CSS y el modal HTML.

FLUJO DE USO:
  1. python generar_dashboard.py       <- genera dashboard.html normal
  2. python parche_pdf_dashboard.py    <- agrega el boton PDF al HTML

O automaticamente: modifica el .bat para que llame ambos scripts seguidos.

No hay f-string, no hay conflicto de llaves, no hay SyntaxError.
"""

from pathlib import Path
import re

HTML_PATH = Path("dashboard.html")

if not HTML_PATH.exists():
    print("ERROR: dashboard.html no encontrado.")
    print("Primero corre: python generar_dashboard.py")
    exit(1)

# ══════════════════════════════════════════════════════════════
# 1. Generar pdf_minuta.js como archivo separado
# ══════════════════════════════════════════════════════════════
JS_PATH = Path("pdf_minuta.js")

JS_CONTENT = r"""// pdf_minuta.js — Generador Minuta PDF formato DCI
// Ministerio del Interior y Seguridad Publica
// Generado por parche_pdf_dashboard.py

const GEO_REG = {
  'Tarapaca':{km2:42226,comunas:7,prov:2,capital:'Iquique'},
  'Antofagasta':{km2:126049,comunas:9,prov:3,capital:'Antofagasta'},
  'Atacama':{km2:75176,comunas:9,prov:3,capital:'Copiapo'},
  'Coquimbo':{km2:40580,comunas:15,prov:3,capital:'La Serena'},
  'Valparaiso':{km2:16396,comunas:38,prov:8,capital:'Valparaiso'},
  "O'Higgins":{km2:16387,comunas:33,prov:3,capital:'Rancagua'},
  'Maule':{km2:30296,comunas:30,prov:4,capital:'Talca'},
  'Biobio':{km2:24021,comunas:33,prov:3,capital:'Concepcion'},
  'La Araucania':{km2:31842,comunas:32,prov:2,capital:'Temuco'},
  'Los Lagos':{km2:48584,comunas:30,prov:4,capital:'Puerto Montt'},
  'Aysen':{km2:108494,comunas:10,prov:4,capital:'Coyhaique'},
  'Magallanes':{km2:132034,comunas:11,prov:4,capital:'Punta Arenas'},
  'Metropolitana de Santiago':{km2:15403,comunas:52,prov:6,capital:'Santiago'},
  'Los Rios':{km2:18430,comunas:12,prov:2,capital:'Valdivia'},
  'Arica y Parinacota':{km2:16873,comunas:4,prov:2,capital:'Arica'},
  'Nuble':{km2:13179,comunas:21,prov:3,capital:'Chillan'},
};
const TOTAL_KM2 = 756102;

function _normReg(r){
  if(!r) return '';
  return r.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\u00f1/g,'n').replace(/\u00d1/g,'N');
}
function _getGeo(region){
  const norm=_normReg(region);
  return GEO_REG[norm]||GEO_REG[Object.keys(GEO_REG).find(k=>_normReg(k)===norm)]||{};
}
function _getCodCenso(region){
  const COD={
    'Tarapaca':'1','Antofagasta':'2','Atacama':'3','Coquimbo':'4',
    'Valparaiso':'5',"O'Higgins":'6','Maule':'7','Biobio':'8',
    'La Araucania':'9','Los Lagos':'10','Aysen':'11','Magallanes':'12',
    'Metropolitana de Santiago':'13','Los Rios':'14',
    'Arica y Parinacota':'15','Nuble':'16',
  };
  const norm=_normReg(region);
  return COD[norm]||COD[Object.keys(COD).find(k=>_normReg(k)===norm)]||null;
}

// Formato
const _N  = v => v==null ? '\u2014' : Math.round(v).toLocaleString('es-CL');
const _P  = (v,d=1) => v==null ? '\u2014' : v.toFixed(d)+'%';
const _M  = v => v==null ? '\u2014' : '$'+Math.round(v/1000).toLocaleString('es-CL')+' mil';
const _D  = (v,d=1) => v==null ? '\u2014' : v.toFixed(d);
const _CV = v => v==null ? '\u2014' : (v>0?'+':'')+v.toFixed(1)+'%';

// Colores [r,g,b]
const _C={
  dark:[15,23,42], navy:[26,26,46], green:[22,163,74], red:[220,38,38],
  amber:[217,119,6], gray:[100,116,139], lgray:[241,245,249],
  white:[255,255,255], accent:[56,189,248]
};

// ── Primitivos PDF ────────────────────────────────────────────
function _portada(doc,region,secc,pW,pH){
  doc.setFillColor(..._C.navy); doc.rect(0,0,pW,pH,'F');
  doc.setFillColor(..._C.dark); doc.rect(0,pH*0.52,pW,pH*0.48,'F');
  doc.setFillColor(..._C.accent); doc.rect(0,pH*0.52,5,pH*0.48,'F');
  doc.setTextColor(..._C.accent); doc.setFontSize(7.5); doc.setFont('helvetica','bold');
  doc.text('MINISTERIO DEL INTERIOR Y SEGURIDAD PUBLICA',18,pH*0.26);
  doc.setFontSize(7); doc.setFont('helvetica','normal'); doc.setTextColor(150,200,230);
  doc.text('Division de Coordinacion Interministerial  |  Unidad de Regiones',18,pH*0.26+7);
  doc.setTextColor(..._C.white); doc.setFont('helvetica','bold');
  doc.setFontSize(10); doc.text('MINUTA',18,pH*0.36);
  doc.setFontSize(26); doc.text('Data Region',18,pH*0.43);
  doc.setFontSize(18); doc.setTextColor(..._C.accent);
  doc.text(region.replace('Metropolitana de Santiago','Metropolitana'),18,pH*0.43+13);
  const fecha=new Date().toLocaleDateString('es-CL',{month:'long',year:'numeric'});
  doc.setFontSize(8); doc.setFont('helvetica','normal'); doc.setTextColor(150,200,230);
  doc.text(fecha.charAt(0).toUpperCase()+fecha.slice(1),18,pH*0.43+23);
  doc.setTextColor(130,170,210); doc.setFontSize(7.5); doc.setFont('helvetica','bold');
  doc.text('SECCIONES INCLUIDAS',18,pH*0.57);
  doc.setFont('helvetica','normal'); doc.setTextColor(..._C.white);
  secc.forEach((s,i)=>doc.text('  '+s,18,pH*0.57+6*(i+1)));
  doc.setFontSize(6.5); doc.setTextColor(90,130,170);
  doc.text('Fuentes: INE Censo 2024 \u00b7 CASEN 2024 \u00b7 Banco Central \u00b7 Carabineros (LeyStop) \u00b7 BCE/INE Empleo',18,pH-14);
  doc.text('Documento generado automaticamente. Uso interno. Datos sujetos a actualizacion.',18,pH-9);
  doc.setTextColor(0,0,0);
}
function _hdrPag(doc,region,pW){
  doc.setFillColor(..._C.dark); doc.rect(0,0,pW,14,'F');
  doc.setFillColor(..._C.accent); doc.rect(0,0,3,14,'F');
  doc.setTextColor(..._C.white); doc.setFontSize(8); doc.setFont('helvetica','bold');
  doc.text('Data Region '+region.replace('Metropolitana de Santiago','Metropolitana'),8,9);
  const f=new Date().toLocaleDateString('es-CL',{day:'2-digit',month:'short',year:'numeric'});
  doc.setFontSize(7); doc.setFont('helvetica','normal'); doc.setTextColor(..._C.accent);
  doc.text(f,pW-14,9,{align:'right'});
  doc.setTextColor(0,0,0); return 20;
}
function _hdrSec(doc,num,titulo,y,pW){
  doc.setFillColor(..._C.navy); doc.rect(0,y,pW,9,'F');
  doc.setFillColor(..._C.accent); doc.rect(0,y,1.5,9,'F');
  doc.setTextColor(..._C.accent); doc.setFontSize(7.5); doc.setFont('helvetica','bold');
  doc.text(num+'.',5,y+6.2);
  doc.setTextColor(..._C.white); doc.setFontSize(8.5);
  doc.text(titulo.toUpperCase(),14,y+6.2);
  doc.setTextColor(0,0,0); return y+13;
}
function _item(doc,num,texto,y,pW){
  doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(..._C.navy);
  doc.text(String(num)+'.',14,y);
  doc.setFont('helvetica','normal'); doc.setFontSize(8); doc.setTextColor(30,41,59);
  const lines=doc.splitTextToSize(texto,pW-34);
  doc.text(lines,22,y);
  doc.setTextColor(0,0,0); return y+Math.max(lines.length*5,6.5);
}
function _sub(doc,letra,texto,y,pW){
  doc.setFont('helvetica','normal'); doc.setFontSize(7.8); doc.setTextColor(71,85,105);
  const lines=doc.splitTextToSize('    '+letra+'. '+texto,pW-40);
  doc.text(lines,26,y);
  doc.setTextColor(0,0,0); return y+Math.max(lines.length*4.8,5.5);
}
function _tabla(doc,head,rows,y,pW,opts){
  opts=opts||{};
  doc.autoTable({
    startY:y, head:[head], body:rows, margin:{left:14,right:14},
    styles:{fontSize:7.5,cellPadding:2.5,lineColor:[220,225,235],lineWidth:0.25},
    headStyles:{fillColor:_C.navy,textColor:_C.white,fontStyle:'bold',fontSize:7.5},
    alternateRowStyles:{fillColor:[248,250,252]},
    columnStyles:opts.columnStyles||{},
  });
  return doc.lastAutoTable.finalY+6;
}
function _pies(doc,region,pW,pH){
  const n=doc.internal.getNumberOfPages();
  for(let i=1;i<=n;i++){
    doc.setPage(i);
    doc.setFillColor(..._C.lgray); doc.rect(0,pH-9,pW,9,'F');
    doc.setFontSize(6.5); doc.setFont('helvetica','normal'); doc.setTextColor(..._C.gray);
    doc.text('Unidad de Regiones \u00b7 DCI \u00b7 Ministerio del Interior \u2014 '+region,14,pH-3.5);
    doc.text('Pag. '+i+' / '+n,pW-14,pH-3.5,{align:'right'});
  }
  doc.setTextColor(0,0,0);
}
function _chk(doc,region,y,pW,pH,n){
  if(y+(n||35)>pH-12){doc.addPage();y=_hdrPag(doc,region,pW);}
  return y;
}

// ── Helpers datos ─────────────────────────────────────────────
function _censo(region){
  const cod=_getCodCenso(region);
  return cod&&CENSO_DATA&&CENSO_DATA.datos?CENSO_DATA.datos[cod]:null;
}
function _casen(region){
  return CASEN&&CASEN.datos?CASEN.datos[region]||null:null;
}
function _pibUlt(region){
  const anos=(PIB&&(PIB.años_corr||PIB.anos_corr))||[];
  const ult=anos[anos.length-1];
  const val=PIB&&PIB.datos_corr&&PIB.datos_corr['PIB']&&PIB.datos_corr['PIB'][region]?
    PIB.datos_corr['PIB'][region][ult]:null;
  return {ano:ult,val:val||null};
}
function _sectores(region){
  const anos=(PIB&&(PIB.años_corr||PIB.anos_corr))||[];
  const ult=anos[anos.length-1]; if(!ult) return [];
  const sects=((PIB&&PIB.sectores_corr)||[]).filter(s=>s!=='PIB');
  const tot=(PIB&&PIB.datos_corr&&PIB.datos_corr['PIB']&&PIB.datos_corr['PIB'][region]?
    PIB.datos_corr['PIB'][region][ult]:null)||1;
  return sects.map(s=>{
    const v=PIB&&PIB.datos_corr&&PIB.datos_corr[s]&&PIB.datos_corr[s][region]?
      PIB.datos_corr[s][region][ult]:null;
    return {s:s.replace('PIB ',''),p:v!=null?v/tot*100:null};
  }).filter(x=>x.p!=null).sort((a,b)=>b.p-a.p);
}
function _empUlt(region){
  const d=EMP&&EMP.datos?EMP.datos[region]:null;
  if(!d||!d.periodos.length) return null;
  const i=d.periodos.length-1;
  return {per:d.periodos[i],tasa:d.tasa[i],ocup:d.ocupados[i],ft:d.ft[i]};
}

// ── Secciones ─────────────────────────────────────────────────
function _secGeo(doc,region,y,pW,pH){
  const g=_getGeo(region);
  const pct=g.km2?(g.km2/TOTAL_KM2*100).toFixed(1):'\u2014';
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'I','Geografico',y,pW);
  y=_item(doc,'1','Superficie total de '+_N(g.km2)+' km\u00b2, equivalente al '+pct+'% del territorio nacional.',y,pW);y+=1;
  y=_item(doc,'2','Capital regional: '+(g.capital||'\u2014')+'.',y,pW);y+=1;
  y=_item(doc,'3','La Region esta dividida en '+(g.comunas||'\u2014')+' comunas, distribuidas en '+(g.prov||'\u2014')+' provincias.',y,pW);y+=4;
  return y;
}
function _secDemo(doc,region,y,pW,pH){
  const r=_censo(region); if(!r) return y;
  const pop=r.n_per||1, TNAC=19960889;
  const m15=(r.n_edad_0_5||0)+(r.n_edad_6_13||0)+(r.n_edad_14_17||0);
  const d64=(r.n_edad_18_24||0)+(r.n_edad_25_44||0)+(r.n_edad_45_59||0);
  const m60=r.n_edad_60_mas||0;
  const razSex=r.n_mujeres?(r.n_hombres/r.n_mujeres*100).toFixed(1):'\u2014';
  const indEnv=m15?(m60/m15*100).toFixed(0):'\u2014';
  y=_chk(doc,region,y,pW,pH,55);
  y=_hdrSec(doc,'II','Demografico',y,pW);
  y=_item(doc,'1','En la Region habitan '+_N(pop)+' personas, equivalente al '+(pop/TNAC*100).toFixed(1)+'% del total nacional (Censo 2024).',y,pW);y+=1;
  y=_item(doc,'2','De ese total, '+_N(r.n_mujeres)+' son mujeres y '+_N(r.n_hombres)+' hombres, con una razon de '+razSex+' hombres por cada 100 mujeres (Censo 2024).',y,pW);y+=1;
  y=_item(doc,'3','El promedio de edad es de '+_D(r.prom_edad)+' anos (Censo 2024).',y,pW);y+=1;
  y=_chk(doc,region,y,pW,pH,32);
  y=_item(doc,'4','Distribucion segun rango etario:',y,pW);
  y=_sub(doc,'a',_P(m15/pop*100)+' es menor de 15 anos.',y,pW);
  y=_sub(doc,'b',_P(d64/pop*100)+' entre 15 y 64 anos.',y,pW);
  y=_sub(doc,'c',_P(m60/pop*100)+' de 60 anos o mas.',y,pW);y+=1;
  y=_item(doc,'5','El indice de envejecimiento es de '+indEnv+' adultos mayores (60+) por cada 100 menores de 15 anos (Censo 2024).',y,pW);y+=1;
  y=_item(doc,'6','Un '+_P(r.n_inmigrantes/pop*100)+' de la poblacion es inmigrante ('+_N(r.n_inmigrantes)+' personas) (Censo 2024).',y,pW);y+=1;
  y=_item(doc,'7','El '+_P(r.n_pueblos_orig/pop*100)+' pertenece o se considera de un pueblo originario (Censo 2024).',y,pW);y+=4;
  return y;
}
function _secVuln(doc,region,y,pW,pH){
  const r=_censo(region), ca=_casen(region);
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'III','Poblacion Vulnerable',y,pW);
  let n=1;
  if(r){
    const pop=r.n_per||1;
    y=_item(doc,n++,'Un '+_P(r.n_discapacidad/pop*100)+' de la poblacion presenta algun tipo de discapacidad ('+_N(r.n_discapacidad)+' hab.) (Censo 2024).',y,pW);y+=1;
  }
  if(ca){
    const ps=(ca.pobreza_severa&&ca.pobreza_severa['Pobreza Severa']&&ca.pobreza_severa['Pobreza Severa']['2024'])||null;
    const pt=ca.pobreza_ingresos&&ca.pobreza_ingresos['Pobreza total']?ca.pobreza_ingresos['Pobreza total']['2024']:null;
    const pe=ca.pobreza_ingresos&&ca.pobreza_ingresos['Pobreza extrema']?ca.pobreza_ingresos['Pobreza extrema']['2024']:null;
    const pm=ca.multi_incidencia&&ca.multi_incidencia['Pobreza multidimensional']?ca.multi_incidencia['Pobreza multidimensional']['2024']:null;
    if(ps!=null){y=_item(doc,n++,'La pobreza severa alcanza el '+_P(ps)+' en la Region vs 6,1% a nivel nacional (CASEN 2024).',y,pW);y+=1;}
    if(pt!=null){y=_item(doc,n++,'El '+_P(pt)+' se encuentra en pobreza por ingresos (nacional: 17,3%); el '+_P(pe)+' en pobreza extrema (nacional: 6,1%) (CASEN 2024).',y,pW);y+=1;}
    if(pm!=null){y=_item(doc,n++,'El '+_P(pm)+' esta en situacion de pobreza multidimensional (nacional: 17,7%) (CASEN 2024).',y,pW);y+=1;}
  } else {
    y=_item(doc,n++,'Datos CASEN 2024 no disponibles en el dashboard para esta region.',y,pW);
  }
  return y+4;
}
function _secEcon(doc,region,y,pW,pH){
  const p=_pibUlt(region), ca=_casen(region), emp=_empUlt(region);
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'IV','Economia',y,pW); let n=1;
  if(p.val!=null){
    y=_item(doc,n++,'El PIB de la Region alcanzo '+(p.val/1000).toFixed(2)+' billones de pesos en '+p.ano+' (Banco Central de Chile).',y,pW);y+=1;
    const sects=_sectores(region);
    if(sects.length){
      y=_item(doc,n++,'Sus principales sectores productivos son:',y,pW);
      sects.slice(0,5).forEach((s,i)=>{y=_sub(doc,String.fromCharCode(97+i),s.s+': '+_P(s.p)+'.',y,pW);});
      y+=1;
    }
  }
  if(emp){y=_item(doc,n++,'La tasa de desocupacion regional es de '+_D(emp.tasa)+'% ('+emp.per.replace('-','/')+', BCE/INE).',y,pW);y+=1;}
  if(ca){
    const ing=ca.ingresos&&ca.ingresos['Ingreso monetario']?ca.ingresos['Ingreso monetario']['2024']:null;
    const sub=ca.composicion_ing&&ca.composicion_ing['Subsidios monetarios']?ca.composicion_ing['Subsidios monetarios']['2024']:null;
    if(ing!=null){y=_item(doc,n++,'El ingreso monetario promedio del hogar es de '+_M(ing)+(sub!=null?', del cual el '+_P(sub)+' corresponde a subsidios monetarios':'')+' (CASEN 2024).',y,pW);y+=1;}
  }
  return y+4;
}
function _secEdu(doc,region,y,pW,pH){
  const r=_censo(region); if(!r) return y;
  const pop=r.n_per||1;
  const tC=(r.n_cine_nunca_curso_primera_infancia||0)+(r.n_cine_primaria||0)+
    (r.n_cine_secundaria||0)+(r.n_cine_terciaria_maestria_doctorado||0)+
    (r.n_cine_especial_diferencial||0)||1;
  y=_chk(doc,region,y,pW,pH,38);
  y=_hdrSec(doc,'V','Educacion',y,pW);
  y=_item(doc,'1','La Region presenta '+_D(r.prom_escolaridad18)+' anos de escolaridad promedio (pob. 18+) (Censo 2024).',y,pW);y+=1;
  y=_item(doc,'2','Distribucion por nivel educacional (CINE):',y,pW);
  y=_sub(doc,'a','Sin escolaridad: '+_P((r.n_cine_nunca_curso_primera_infancia||0)/tC*100)+'.',y,pW);
  y=_sub(doc,'b','Educacion primaria: '+_P((r.n_cine_primaria||0)/tC*100)+'.',y,pW);
  y=_sub(doc,'c','Educacion secundaria: '+_P((r.n_cine_secundaria||0)/tC*100)+'.',y,pW);
  y=_sub(doc,'d','Educacion terciaria/posgrado: '+_P((r.n_cine_terciaria_maestria_doctorado||0)/tC*100)+'.',y,pW);y+=1;
  y=_item(doc,'3','La tasa de analfabetismo es de '+_P((r.n_analfabet||0)/pop*100)+' (Censo 2024).',y,pW);y+=4;
  return y;
}
function _secSalud(doc,region,y,pW,pH){
  const ca=_casen(region);
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'VI','Salud',y,pW);
  if(!ca){y=_item(doc,'1','Datos CASEN 2024 no disponibles.',y,pW);return y+4;}
  const prev=ca.previsional||{}, at=ca.atencion_medica||{};
  const prob=ca.prob_atencion||{}, ges=ca.auge_ges||{};
  const fon=(prev['Sistema P\u00FAblico FONASA']||prev['Sistema Publico FONASA']||{})['2024'];
  const isa=(prev['Isapre']||{})['2024'];
  const ate=(at['S\u00ED']||at['Si']||{})['2024'];
  const prb=(prob['Tuvo']||{})['2024'];
  const gg=(ges['Si']||{})['2024'];
  let n=1;
  if(fon!=null){y=_item(doc,n++,'El '+_P(fon)+' de la poblacion esta afiliada a FONASA y el '+_P(isa)+' a Isapre (CASEN 2024).',y,pW);y+=1;}
  if(ate!=null){y=_item(doc,n++,'El '+_P(ate)+' recibio atencion medica ante problemas de salud en el ultimo ano (CASEN 2024).',y,pW);y+=1;}
  if(prb!=null){y=_item(doc,n++,'El '+_P(prb)+' tuvo problemas para acceder a atencion medica (CASEN 2024).',y,pW);y+=1;}
  if(gg!=null){y=_item(doc,n++,'El '+_P(gg)+' de las personas en tratamiento fue cubierta por AUGE-GES (CASEN 2024).',y,pW);y+=1;}
  return y+4;
}
function _secViv(doc,region,y,pW,pH){
  const r=_censo(region); if(!r) return y;
  const vp=r.n_vp_ocupada||1, hog=r.n_hog||1;
  y=_chk(doc,region,y,pW,pH,45);
  y=_hdrSec(doc,'VII','Vivienda',y,pW);
  y=_item(doc,'1','Los habitantes se distribuyen en '+_N(vp)+' viviendas ocupadas (Censo 2024):',y,pW);
  y=_sub(doc,'a','El '+_P((r.n_tipo_viv_casa||0)/vp*100)+' son casas y el '+_P((r.n_tipo_viv_depto||0)/vp*100)+' departamentos.',y,pW);
  y=_sub(doc,'b','El '+_P((r.n_jefatura_mujer||0)/hog*100)+' de los hogares tiene jefatura mujer.',y,pW);y+=1;
  y=_item(doc,'2','Indicadores de deficit habitacional:',y,pW);
  y=_sub(doc,'a','Hacinamiento: '+_P((r.n_viv_hacinadas||0)/vp*100)+' de las viviendas.',y,pW);
  y=_sub(doc,'b','Viviendas irrecuperables: '+_P((r.n_viv_irrecuperables||0)/vp*100)+'.',y,pW);
  y=_sub(doc,'c','Deficit cuantitativo: '+_P((r.n_deficit_cuantitativo||0)/vp*100)+'.',y,pW);y+=1;
  const ppa=(r.n_tenencia_propia_pagada||0)/hog*100;
  const par=((r.n_tenencia_arrendada_contrato||0)+(r.n_tenencia_arrendada_sin_contrato||0))/hog*100;
  y=_item(doc,'3','El '+_P(ppa)+' habita en vivienda propia pagada y el '+_P(par)+' en arrendada (Censo 2024).',y,pW);y+=4;
  return y;
}
function _secSeg(doc,region,y,pW,pH){
  const ds=(SEG&&SEG.datos?SEG.datos.filter(d=>d.nombre_region===region):[])||[];
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'VIII','Seguridad Publica',y,pW);
  if(!ds.length){y=_item(doc,'1','Sin datos de seguridad disponibles.',y,pW);return y+4;}
  const mxS=Math.max(...ds.map(d=>d.id_semana));
  const ul=ds.find(d=>d.id_semana===mxS);
  const sm=SEG.semanas.find(s=>s.id_semana===mxS);
  let n=1;
  y=_item(doc,n++,'Datos LeyStop Carabineros \u2014 '+(sm&&sm.nombre||'')+' ('+(sm&&sm.fecha_desde_iso||'')+' al '+(sm&&sm.fecha_hasta_iso||'')+').',y,pW);y+=1;
  y=_item(doc,n++,'Casos ano a la fecha: '+_N(ul.casos_anno_fecha)+'. Variacion anual: '+_CV(ul.var_anno_fecha)+'.',y,pW);y+=1;
  y=_item(doc,n++,'Tasa de registro: '+_D(ul.tasa_registro)+' por cada 100.000 habitantes.',y,pW);y+=1;
  if(ul.delito_1){
    y=_item(doc,n++,'Top delitos mas frecuentes:',y,pW);
    [1,2,3,4,5].filter(i=>ul['delito_'+i]).forEach((i,idx)=>{
      y=_sub(doc,String.fromCharCode(97+idx),ul['delito_'+i]+': '+_P(ul['pct_delito_'+i])+' del total.',y,pW);
    });y+=1;
  }
  y=_item(doc,n++,'Actividad operativa: controles '+_N(ul.controles)+', fiscalizaciones '+_N(ul.fiscalizaciones)+', incautaciones de armas '+_N(ul.incautaciones)+'.',y,pW);y+=4;
  return y;
}
function _secEmp(doc,region,y,pW,pH){
  const e=_empUlt(region);
  y=_chk(doc,region,y,pW,pH,30);
  y=_hdrSec(doc,'IX','Mercado Laboral',y,pW);
  if(!e){y=_item(doc,'1','Sin datos de empleo disponibles.',y,pW);return y+4;}
  const sem=e.per&&e.per.replace('-','/');
  const sfx=e.tasa>8?' (ALTA, sobre 8%)':e.tasa>6?' (MEDIA, entre 6% y 8%)':' (BAJA, bajo 6%)';
  let n=1;
  y=_item(doc,n++,'Datos BCE / INE ('+sem+').',y,pW);y+=1;
  y=_item(doc,n++,'La tasa de desocupacion regional es de '+_D(e.tasa)+'%'+sfx+'.',y,pW);y+=1;
  y=_item(doc,n++,'Ocupados: '+_N(e.ocup)+' miles de personas. Fuerza de trabajo estimada: '+_N(e.ft)+' miles.',y,pW);y+=2;
  const d=EMP&&EMP.datos?EMP.datos[region]:null;
  if(d&&d.periodos&&d.periodos.length){
    const anos=[...new Set(d.periodos.map(p=>p.slice(0,4)))].sort().slice(-6);
    const filas=anos.map(a=>{
      const ix=d.periodos.reduce((acc,p,i)=>p.startsWith(a)?[...acc,i]:acc,[]);
      const ts=ix.map(i=>d.tasa[i]).filter(v=>v!=null);
      const os=ix.map(i=>d.ocupados[i]).filter(v=>v!=null);
      return [a, ts.length?_D(ts.reduce((a,b)=>a+b)/ts.length)+'%':'\u2014',
              os.length?_N(os.reduce((a,b)=>a+b)/os.length):'\u2014'];
    });
    y=_tabla(doc,['Ano','Tasa desocup. promedio','Ocupados promedio (miles)'],filas,y,pW,
      {columnStyles:{0:{cellWidth:25},1:{halign:'right'},2:{halign:'right'}}});
  }
  return y;
}

// ── Modal ─────────────────────────────────────────────────────
function abrirModalPdf(){
  const sel=document.getElementById('pdf-reg');
  if(sel.options.length<=1){
    const regs=[...new Set([
      ...((SEG&&SEG.regiones)||[]),
      ...((EMP&&EMP.regiones)||[]),
      ...((PIB&&PIB.regiones)||[]),
    ])].sort();
    regs.forEach(r=>{const o=document.createElement('option');o.value=r;o.textContent=r;sel.appendChild(o);});
    const rm=regs.find(r=>r.includes('Metropolitana'));
    if(rm) sel.value=rm;
  }
  ['demo','vuln','econ','edu','sal','viv','seg','emp'].forEach(id=>{
    const chk=document.getElementById('pc-'+id);
    const wrap=document.getElementById('pw-'+id);
    if(chk&&wrap) chk.onchange=()=>wrap.classList.toggle('on',chk.checked);
  });
  document.getElementById('pdf-overlay').classList.add('open');
  document.getElementById('pdf-prog').style.display='none';
  const btn=document.getElementById('pdf-gbtn');
  btn.disabled=false; btn.textContent='Generar Minuta PDF';
}
function cerrarPdf(){document.getElementById('pdf-overlay').classList.remove('open');}
function pdfProg(pct,lbl){
  document.getElementById('pdf-prog').style.display='block';
  document.getElementById('pdf-pfill').style.width=pct+'%';
  document.getElementById('pdf-plbl').textContent=lbl;
}

async function generarMinuta(){
  const region=document.getElementById('pdf-reg').value;
  if(!region){alert('Selecciona una region primero.');return;}
  const inc={
    demo:document.getElementById('pc-demo').checked,
    vuln:document.getElementById('pc-vuln').checked,
    econ:document.getElementById('pc-econ').checked,
    edu:document.getElementById('pc-edu').checked,
    sal:document.getElementById('pc-sal').checked,
    viv:document.getElementById('pc-viv').checked,
    seg:document.getElementById('pc-seg').checked,
    emp:document.getElementById('pc-emp').checked,
  };
  if(!Object.values(inc).some(Boolean)){alert('Selecciona al menos una seccion.');return;}
  const btn=document.getElementById('pdf-gbtn');
  btn.disabled=true; btn.textContent='Generando...';
  try{
    const{jsPDF}=window.jspdf;
    const doc=new jsPDF({orientation:'portrait',unit:'mm',format:'a4'});
    const pW=doc.internal.pageSize.getWidth(), pH=doc.internal.pageSize.getHeight();
    const secc=[
      'I. Geografico',
      inc.demo&&'II. Demografico', inc.vuln&&'III. Poblacion Vulnerable',
      inc.econ&&'IV. Economia',    inc.edu&&'V. Educacion',
      inc.sal&&'VI. Salud',        inc.viv&&'VII. Vivienda',
      inc.seg&&'VIII. Seguridad Publica', inc.emp&&'IX. Mercado Laboral',
    ].filter(Boolean);
    pdfProg(5,'Generando portada...'); _portada(doc,region,secc,pW,pH);
    doc.addPage(); let y=_hdrPag(doc,region,pW);
    const tot=Object.values(inc).filter(Boolean).length+1; let paso=1;
    pdfProg(10,'Seccion geografica...'); await new Promise(r=>setTimeout(r,20));
    y=_secGeo(doc,region,y,pW,pH);
    if(inc.demo){pdfProg(10+paso++/tot*75,'Demografico...');await new Promise(r=>setTimeout(r,20));y=_secDemo(doc,region,y,pW,pH);}
    if(inc.vuln){pdfProg(10+paso++/tot*75,'Pob. Vulnerable...');await new Promise(r=>setTimeout(r,20));y=_secVuln(doc,region,y,pW,pH);}
    if(inc.econ){pdfProg(10+paso++/tot*75,'Economia...');await new Promise(r=>setTimeout(r,20));y=_secEcon(doc,region,y,pW,pH);}
    if(inc.edu){pdfProg(10+paso++/tot*75,'Educacion...');await new Promise(r=>setTimeout(r,20));y=_secEdu(doc,region,y,pW,pH);}
    if(inc.sal){pdfProg(10+paso++/tot*75,'Salud...');await new Promise(r=>setTimeout(r,20));y=_secSalud(doc,region,y,pW,pH);}
    if(inc.viv){pdfProg(10+paso++/tot*75,'Vivienda...');await new Promise(r=>setTimeout(r,20));y=_secViv(doc,region,y,pW,pH);}
    if(inc.seg){pdfProg(10+paso++/tot*75,'Seguridad...');await new Promise(r=>setTimeout(r,20));y=_secSeg(doc,region,y,pW,pH);}
    if(inc.emp){pdfProg(10+paso++/tot*75,'Mercado laboral...');await new Promise(r=>setTimeout(r,20));y=_secEmp(doc,region,y,pW,pH);}
    pdfProg(92,'Numerando paginas...'); await new Promise(r=>setTimeout(r,20));
    _pies(doc,region,pW,pH);
    pdfProg(97,'Descargando...'); await new Promise(r=>setTimeout(r,20));
    const nom='Minuta_Data_Region_'
      +region.normalize('NFD').replace(/[\u0300-\u036f]/g,'')
        .replace('Metropolitana de Santiago','RM')
        .replace(/[^a-zA-Z0-9\s]/g,'').replace(/\s+/g,'_')
      +'_'+new Date().toISOString().slice(0,7)+'.pdf';
    doc.save(nom);
    pdfProg(100,'Minuta descargada'); btn.textContent='Descargada';
    setTimeout(()=>{
      cerrarPdf(); btn.disabled=false; btn.textContent='Generar Minuta PDF';
      document.getElementById('pdf-prog').style.display='none';
    },1800);
  }catch(err){
    console.error(err);
    document.getElementById('pdf-plbl').textContent='Error: '+err.message;
    btn.disabled=false; btn.textContent='Generar Minuta PDF';
  }
}
"""

JS_PATH.write_text(JS_CONTENT, encoding="utf-8")
print(f"Generado: {JS_PATH} ({JS_PATH.stat().st_size//1024} KB)")

# ══════════════════════════════════════════════════════════════
# 2. Modificar dashboard.html
# ══════════════════════════════════════════════════════════════
html = HTML_PATH.read_text(encoding="utf-8")

# Verificar que no fue parchado antes
if "pdf-overlay" in html:
    print("dashboard.html ya tiene el modal PDF. Regenera con generar_dashboard.py primero.")
    exit(0)

# 2a. Agregar jsPDF + script externo antes de </head>
SCRIPTS = (
    '<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/jspdf-autotable@3.8.2/dist/jspdf.plugin.autotable.min.js"></script>\n'
    '<script src="pdf_minuta.js"></script>\n'
)
html = html.replace('</head>', SCRIPTS + '</head>', 1)
print("Scripts jsPDF + pdf_minuta.js agregados al <head>")

# 2b. CSS del modal — insertar antes de </head>
PDF_CSS = """<style>
.btn-pdf{display:inline-flex;align-items:center;gap:7px;padding:7px 16px;
  border-radius:8px;font-size:12px;font-weight:700;
  background:linear-gradient(135deg,#38bdf8,#0ea5e9);
  color:#0f172a;border:none;cursor:pointer;
  box-shadow:0 2px 8px rgba(56,189,248,.35);transition:all .2s;white-space:nowrap;}
.btn-pdf:hover{transform:translateY(-1px);}
.btn-pdf svg{width:14px;height:14px;}
.pdf-overlay{display:none;position:fixed;inset:0;z-index:9000;
  background:rgba(10,15,30,.75);backdrop-filter:blur(5px);
  align-items:center;justify-content:center;}
.pdf-overlay.open{display:flex;}
.pdf-modal{background:#fff;border-radius:18px;width:500px;max-width:95vw;
  box-shadow:0 28px 70px rgba(0,0,0,.35);overflow:hidden;
  animation:pdfIn .22s cubic-bezier(.34,1.3,.64,1);}
@keyframes pdfIn{from{opacity:0;transform:scale(.92) translateY(14px)}to{opacity:1;transform:none}}
.pdf-mhdr{background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;
  padding:22px 26px 18px;display:flex;align-items:flex-start;justify-content:space-between;}
.pdf-mhdr h2{font-size:15px;font-weight:700;margin-bottom:3px;}
.pdf-mhdr p{font-size:11px;opacity:.5;}
.pdf-close{background:none;border:none;color:white;opacity:.45;font-size:22px;
  cursor:pointer;line-height:1;padding:2px 6px;border-radius:4px;transition:.15s;}
.pdf-close:hover{opacity:1;background:rgba(255,255,255,.12);}
.pdf-body{padding:24px 26px;}
.pdf-label{display:block;font-size:10px;font-weight:800;color:#94a3b8;
  text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px;}
.pdf-region-sel{width:100%;padding:9px 13px;border:1.5px solid #e2e8f0;
  border-radius:9px;font-size:13px;background:white;cursor:pointer;outline:none;margin-bottom:20px;}
.pdf-region-sel:focus{border-color:#0ea5e9;}
.pdf-mods{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:22px;}
.pdf-mod{display:flex;align-items:center;gap:10px;padding:10px 13px;
  border-radius:10px;border:1.5px solid #e2e8f0;cursor:pointer;transition:all .15s;user-select:none;}
.pdf-mod:hover{border-color:#0ea5e9;background:#f0f9ff;}
.pdf-mod.on{border-color:#0ea5e9;background:#e0f2fe;}
.pdf-mod input{accent-color:#0ea5e9;width:15px;height:15px;cursor:pointer;}
.pdf-mod .ico{font-size:17px;line-height:1;}
.pdf-mod .mn{font-size:12px;font-weight:700;color:#1e293b;}
.pdf-mod .ms{font-size:10px;color:#94a3b8;}
.pdf-prog{display:none;margin-bottom:16px;}
.pdf-prog-bar{height:6px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin-top:6px;}
.pdf-prog-fill{height:100%;background:linear-gradient(90deg,#38bdf8,#0ea5e9);
  border-radius:99px;width:0%;transition:width .35s ease;}
.pdf-prog-lbl{font-size:11px;color:#64748b;margin-top:5px;}
.pdf-btn{width:100%;padding:13px;border-radius:11px;border:none;cursor:pointer;
  font-size:13px;font-weight:800;background:linear-gradient(135deg,#1a1a2e,#0f3460);
  color:white;transition:all .2s;box-shadow:0 2px 10px rgba(0,0,0,.22);}
.pdf-btn:hover{transform:translateY(-1px);}
.pdf-btn:disabled{opacity:.45;cursor:not-allowed;transform:none;}
</style>
"""
html = html.replace('</head>', PDF_CSS + '</head>', 1)
print("CSS del modal insertado")

# 2c. Boton en el header — buscar el </header> y agregar el boton antes
BTN_HTML = """  <button class="btn-pdf" onclick="abrirModalPdf()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M12 3v12m0 0l-4-4m4 4l4-4M3 17v2a2 2 0 002 2h14a2 2 0 002-2v-2"/>
    </svg>
    Minuta Regional PDF
  </button>
</header>"""
html = html.replace('</header>', BTN_HTML, 1)
print("Boton agregado al header")

# 2d. Modal HTML antes de </body>
MODAL_HTML = """
<div class="pdf-overlay" id="pdf-overlay" onclick="if(event.target===this)cerrarPdf()">
  <div class="pdf-modal">
    <div class="pdf-mhdr">
      <div><h2>&#x1F4C4; Generar Minuta Regional</h2><p>Formato DCI &mdash; Ministerio del Interior</p></div>
      <button class="pdf-close" onclick="cerrarPdf()">&#x2715;</button>
    </div>
    <div class="pdf-body">
      <label class="pdf-label">Regi&oacute;n</label>
      <select class="pdf-region-sel" id="pdf-reg"></select>
      <label class="pdf-label">Secciones a incluir</label>
      <div class="pdf-mods">
        <label class="pdf-mod on" id="pw-demo"><input type="checkbox" id="pc-demo" checked>
          <span class="ico">&#x1F465;</span><span><div class="mn">Demograf&iacute;a</div><div class="ms">Censo 2024</div></span></label>
        <label class="pdf-mod on" id="pw-vuln"><input type="checkbox" id="pc-vuln" checked>
          <span class="ico">&#x1F91D;</span><span><div class="mn">Pob. Vulnerable</div><div class="ms">CASEN 2024</div></span></label>
        <label class="pdf-mod on" id="pw-econ"><input type="checkbox" id="pc-econ" checked>
          <span class="ico">&#x1F4C8;</span><span><div class="mn">Econom&iacute;a</div><div class="ms">PIB BCE + CASEN</div></span></label>
        <label class="pdf-mod on" id="pw-edu"><input type="checkbox" id="pc-edu" checked>
          <span class="ico">&#x1F393;</span><span><div class="mn">Educaci&oacute;n</div><div class="ms">Censo 2024</div></span></label>
        <label class="pdf-mod on" id="pw-sal"><input type="checkbox" id="pc-sal" checked>
          <span class="ico">&#x1F3E5;</span><span><div class="mn">Salud</div><div class="ms">CASEN 2024</div></span></label>
        <label class="pdf-mod on" id="pw-viv"><input type="checkbox" id="pc-viv" checked>
          <span class="ico">&#x1F3E0;</span><span><div class="mn">Vivienda</div><div class="ms">Censo 2024</div></span></label>
        <label class="pdf-mod on" id="pw-seg"><input type="checkbox" id="pc-seg" checked>
          <span class="ico">&#x1F6E1;</span><span><div class="mn">Seguridad P&uacute;blica</div><div class="ms">LeyStop</div></span></label>
        <label class="pdf-mod on" id="pw-emp"><input type="checkbox" id="pc-emp" checked>
          <span class="ico">&#x1F4BC;</span><span><div class="mn">Mercado Laboral</div><div class="ms">BCE / INE</div></span></label>
      </div>
      <div class="pdf-prog" id="pdf-prog">
        <div class="pdf-prog-bar"><div class="pdf-prog-fill" id="pdf-pfill"></div></div>
        <div class="pdf-prog-lbl" id="pdf-plbl">Preparando...</div>
      </div>
      <button class="pdf-btn" id="pdf-gbtn" onclick="generarMinuta()">Generar Minuta PDF</button>
    </div>
  </div>
</div>
"""
html = html.replace('</body>', MODAL_HTML + '\n</body>', 1)
print("Modal HTML insertado")

HTML_PATH.write_text(html, encoding="utf-8")
print(f"\n{'='*55}")
print(f"dashboard.html actualizado con el boton PDF")
print(f"pdf_minuta.js generado en la misma carpeta")
print(f"{'='*55}\n")
print("IMPORTANTE: pdf_minuta.js debe estar en la misma")
print("carpeta que dashboard.html para que funcione.")
print()
print("Para GitHub Pages: sube AMBOS archivos:")
print("  git add -f dashboard.html pdf_minuta.js")
print("  git commit -m 'Agrega boton minuta PDF'")
print("  git push origin main")
print()
print("Flujo de actualizacion futuro:")
print("  1. python generar_dashboard.py")
print("  2. python parche_pdf_dashboard.py")
print("  3. git add -f dashboard.html pdf_minuta.js && git push")
