"""
preparar_casen.py  — v2 completo
Extrae todas las hojas seleccionadas de los 5 xlsx CASEN 2024
y genera casen_regiones.json

Fuentes:
  Pobreza_Casen_2024.xlsx          hojas: 6 (personas), 15 (FGT personas)
  Pobreza_Multidimensional_*       hojas: 4, 25, 29, 33
  Pobreza_Severa_Casen_2024.xlsx   hojas: 3
  Ingreso_Casen_2024.xlsx          hojas: 3, 9, 21
  Salud_Casen_2024.xlsx            hojas: 3, 24, 36, 47, 69
"""
import pandas as pd, json, math
from pathlib import Path

BASE = Path(r"C:\Users\manuel.carvallo\OneDrive - interior.gob.cl\Documentos\Scrap\Casen")
OUT  = Path("casen_regiones.json")

REGIONES_CANON = [
    "Arica y Parinacota","Tarapacá","Antofagasta","Atacama","Coquimbo",
    "Valparaíso","O'Higgins","Maule","Ñuble","Biobío",
    "La Araucanía","Los Ríos","Los Lagos","Aysén","Magallanes",
    "Metropolitana de Santiago"
]

# Alias que aparecen en los archivos → nombre canónico
REG_ALIAS = {
    "Región Metropolitana":      "Metropolitana de Santiago",
    "Metropolitana":             "Metropolitana de Santiago",
    "O´Higgins":                 "O'Higgins",
    "O`Higgins":                 "O'Higgins",
    "Bío Bío":                   "Biobío",
    "Bio Bio":                   "Biobío",
    "Biobío":                    "Biobío",
    "Araucanía":                 "La Araucanía",
    "La Araucanía":              "La Araucanía",
    "Aysén":                     "Aysén",
}

def cn(v):
    """Convierte a float limpio o None."""
    if v is None: return None
    try:
        f = float(str(v).replace(",","."))
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    except: return None

def canon(s):
    """Normaliza nombre de región."""
    if not s: return None
    s = str(s).strip()
    if s in ("nan","NaN","-","","Total país","Total País"): return None
    for alias, can in REG_ALIAS.items():
        if alias == s or alias in s: return can
    for r in REGIONES_CANON:
        if r == s or r in s or s in r: return r
    return None

# ──────────────────────────────────────────────────────────────
# Helpers de parseo
# ──────────────────────────────────────────────────────────────
def parse_cat_region(df, region_col, cat_col, col_años, skip_cats=None):
    """
    Tabla donde region_col tiene la región (con carry-forward) y
    cat_col la categoría en cada fila.
    Devuelve {region: {categoria: {año: valor}}}.
    """
    skip_cats = set(skip_cats or [])
    out = {}; cur_reg = None
    for _, row in df.iterrows():
        r = canon(row[region_col])
        if r: cur_reg = r
        c = str(row[cat_col]).strip() if pd.notna(row[cat_col]) else None
        if not cur_reg or not c or c in skip_cats | {"nan","NaN","Estimación","Desagregación","Total","Total país"}: continue
        out.setdefault(cur_reg, {}).setdefault(c, {})
        for col, año in col_años:
            v = cn(row[col])
            if v is not None: out[cur_reg][c][año] = v
    return out

def parse_ind_region(df, ind_col, region_col, col_años, ind_rename=None):
    """
    Tabla donde ind_col tiene el indicador (carry-forward) y
    region_col la región en cada fila.
    Devuelve {region: {indicador: {año: valor}}}.
    """
    ind_rename = ind_rename or {}
    out = {}; cur_ind = None
    for _, row in df.iterrows():
        raw_ind = str(row[ind_col]).strip() if pd.notna(row[ind_col]) else None
        if raw_ind and raw_ind not in ("nan","NaN","Estimación","Desagregación"):
            cur_ind = ind_rename.get(raw_ind, raw_ind)
        r = canon(row[region_col])
        if not r or not cur_ind: continue
        out.setdefault(r, {}).setdefault(cur_ind, {})
        for col, año in col_años:
            v = cn(row[col])
            if v is not None: out[r][cur_ind][año] = v
    return out

# ══════════════════════════════════════════════════════════════
# POBREZA POR INGRESOS
# ══════════════════════════════════════════════════════════════
AÑOS_POB = [(2,"2009"),(3,"2011"),(4,"2013"),(5,"2015"),(6,"2017"),(7,"2020"),(8,"2022"),(9,"2024")]

# Hoja 6 — personas por región
df_p6 = pd.read_excel(BASE/"Pobreza_Casen_2024.xlsx", sheet_name="6", header=None)
pobreza_ing_pers = {}; cur_reg = None
for _, row in df_p6.iterrows():
    r = canon(row[0])
    if r: cur_reg = r
    c = str(row[1]).strip() if pd.notna(row[1]) else None
    if not cur_reg or not c or c in {"nan","NaN","Estimación","Desagregación"}: continue
    label = "Pobreza total" if c == "Pobreza1" else c
    pobreza_ing_pers.setdefault(cur_reg, {}).setdefault(label, {})
    for col, año in AÑOS_POB:
        v = cn(row[col])
        if v is not None: pobreza_ing_pers[cur_reg][label][año] = v

# Hoja 15 — FGT personas (ind en col0 carry-forward, región en col1)
df_fgt = pd.read_excel(BASE/"Pobreza_Casen_2024.xlsx", sheet_name="15", header=None)
fgt_pers = parse_ind_region(df_fgt, ind_col=0, region_col=1, col_años=AÑOS_POB,
    ind_rename={
        "FGT(0): Incidencia":    "FGT0_Incidencia",
        "FGT(1): Brecha promedio":"FGT1_Brecha",
        "FGT(2): Severidad":     "FGT2_Severidad",
    })

# ══════════════════════════════════════════════════════════════
# POBREZA SEVERA
# ══════════════════════════════════════════════════════════════
AÑOS_SEV = [(2,"2022"),(3,"2024")]
df_sv3 = pd.read_excel(BASE/"Pobreza_Severa_Casen_2024.xlsx", sheet_name="3", header=None)
pob_severa = parse_cat_region(df_sv3, region_col=0, cat_col=1, col_años=AÑOS_SEV,
    skip_cats={"Total"})

# ══════════════════════════════════════════════════════════════
# POBREZA MULTIDIMENSIONAL
# ══════════════════════════════════════════════════════════════
df_mh  = pd.read_excel(BASE/"Pobreza_Multidimensional_Casen_2024.xlsx", sheet_name="4",  header=None)
df_mp  = pd.read_excel(BASE/"Pobreza_Multidimensional_Casen_2024.xlsx", sheet_name="33", header=None)

multi_incidencia = {}
for df, suffix in [(df_mh,"_hog"),(df_mp,"_per")]:
    for _, row in df.iterrows():
        r = canon(row[0])
        if r:
            multi_incidencia.setdefault(r, {})
            multi_incidencia[r][f"met2024_2022{suffix}"] = cn(row[1])
            multi_incidencia[r][f"met2024_2024{suffix}"] = cn(row[2])
            multi_incidencia[r][f"met2015_2022{suffix}"] = cn(row[10])
            multi_incidencia[r][f"met2015_2024{suffix}"] = cn(row[11])

df_car = pd.read_excel(BASE/"Pobreza_Multidimensional_Casen_2024.xlsx", sheet_name="25", header=None)
indicadores_multi = [str(v).strip() for v in df_car.iloc[7][1:21]
                     if pd.notna(v) and str(v).strip() not in ("nan","NaN")]
carencias = {}
for _, row in df_car.iloc[8:].iterrows():
    r = canon(row[0])
    if r:
        carencias[r] = {ind: cn(row[i+1]) for i,ind in enumerate(indicadores_multi)
                        if cn(row[i+1]) is not None}

df_cont = pd.read_excel(BASE/"Pobreza_Multidimensional_Casen_2024.xlsx", sheet_name="29", header=None)
dims_multi = [str(v).strip() for v in df_cont.iloc[5][1:6] if pd.notna(v)]
contribucion = {}
for _, row in df_cont.iloc[6:].iterrows():
    r = canon(row[0])
    if r:
        contribucion[r] = {d: cn(row[i+1]) for i,d in enumerate(dims_multi)
                           if cn(row[i+1]) is not None}

# ══════════════════════════════════════════════════════════════
# INGRESOS
# ══════════════════════════════════════════════════════════════
AÑOS_ING = [(2,"2006"),(3,"2009"),(4,"2011"),(5,"2013"),(6,"2015"),(7,"2017"),(8,"2020"),(9,"2022"),(10,"2024")]
TIPOS_ING = {
    "Ingreso del trabajo1": "Ingreso del trabajo",
    "Ingreso autónomo2":    "Ingreso autónomo",
    "Subsidios monetarios3":"Subsidios monetarios",
    "Ingreso monetario4":   "Ingreso monetario",
}

# Hoja 3 — ingreso promedio por tipo y región ($)
df_i3 = pd.read_excel(BASE/"Ingreso_Casen_2024.xlsx", sheet_name="3", header=None)
ingresos = {}; cur_tipo = None
for _, row in df_i3.iterrows():
    t0 = str(row[0]).strip() if pd.notna(row[0]) else None
    t1 = str(row[1]).strip() if pd.notna(row[1]) else None
    if t0 and t0 in TIPOS_ING: cur_tipo = TIPOS_ING[t0]
    r = canon(t0) or canon(t1)
    if r and cur_tipo:
        ingresos.setdefault(r, {}).setdefault(cur_tipo, {})
        for col, año in AÑOS_ING:
            v = cn(row[col])
            if v is not None: ingresos[r][cur_tipo][año] = v

# Hoja 9 — composición % del ingreso monetario
df_i9 = pd.read_excel(BASE/"Ingreso_Casen_2024.xlsx", sheet_name="9", header=None)
TIPOS_COMP = {"Ingreso autónomo1":"Ingreso autónomo", "Ingreso autónomo":"Ingreso autónomo",
              "Subsidios monetarios2":"Subsidios monetarios", "Subsidios monetarios":"Subsidios monetarios"}
composicion_ing = {}; cur_reg = None
for _, row in df_i9.iterrows():
    r = canon(row[0])
    if r: cur_reg = r
    c_raw = str(row[1]).strip() if pd.notna(row[1]) else None
    if not cur_reg or not c_raw or c_raw in ("nan","NaN","Estimación","Desagregación","Ingreso monetario3","Ingreso monetario"): continue
    # Limpiar sufijos numéricos
    c_clean = TIPOS_COMP.get(c_raw, c_raw.rstrip("0123456789").strip())
    if c_clean in ("nan","NaN",""): continue
    composicion_ing.setdefault(cur_reg, {}).setdefault(c_clean, {})
    for col, año in AÑOS_ING:
        v = cn(row[col])
        if v is not None: composicion_ing[cur_reg][c_clean][año] = v

# Hoja 21 — pobreza relativa (< 50% mediana)
df_i21 = pd.read_excel(BASE/"Ingreso_Casen_2024.xlsx", sheet_name="21", header=None)
TIPOS_REL = {
    "Ingreso del trabajo1":"Ingreso del trabajo",
    "Ingreso autónomo2":   "Ingreso autónomo",
    "Ingreso monetario3":  "Ingreso monetario",
    "Ingreso total4":      "Ingreso total",
}
pob_relativa = {}; cur_tipo = None
for _, row in df_i21.iterrows():
    t0 = str(row[0]).strip() if pd.notna(row[0]) else None
    t1 = str(row[1]).strip() if pd.notna(row[1]) else None
    if t0 and t0 in TIPOS_REL: cur_tipo = TIPOS_REL[t0]
    r = canon(t0) or canon(t1)
    if r and cur_tipo:
        pob_relativa.setdefault(r, {}).setdefault(cur_tipo, {})
        for col, año in AÑOS_ING:
            v = cn(row[col])
            if v is not None: pob_relativa[r][cur_tipo][año] = v

# ══════════════════════════════════════════════════════════════
# SALUD
# ══════════════════════════════════════════════════════════════
AÑOS_SAL  = [(2,"2006"),(3,"2009"),(4,"2011"),(5,"2013"),(6,"2015"),(7,"2017"),(8,"2020"),(9,"2022"),(10,"2024")]
AÑOS_ATEN = [(2,"2011"),(3,"2013"),(4,"2015"),(5,"2017"),(6,"2020"),(7,"2022"),(8,"2024")]
AÑOS_DEP  = [(2,"2022"),(3,"2024")]

# Hoja 3 — previsional
CATS_PREV = {"Sistema Público FONASA","Isapre","FF.AA. y del Orden","Ninguno (particular)"}
df_s3 = pd.read_excel(BASE/"Salud_Casen_2024.xlsx", sheet_name="3", header=None)
previsional = {}; cur_reg = None
for _, row in df_s3.iterrows():
    r = canon(row[0])
    if r: cur_reg = r
    c = str(row[1]).strip() if pd.notna(row[1]) else None
    if not cur_reg or c not in CATS_PREV: continue
    previsional.setdefault(cur_reg, {}).setdefault(c, {})
    for col, año in AÑOS_SAL:
        v = cn(row[col])
        if v is not None: previsional[cur_reg][c][año] = v

# Hoja 24 — tasa atención médica (Sí/No)
df_s24 = pd.read_excel(BASE/"Salud_Casen_2024.xlsx", sheet_name="24", header=None)
atencion_med = parse_cat_region(df_s24, region_col=0, cat_col=1, col_años=AÑOS_ATEN,
    skip_cats={"Ns/Nr","Total","nan"})

# Hoja 36 — problemas para obtener atención (Tuvo / No tuvo)
AÑOS_PROB = [(2,"2015"),(3,"2017"),(4,"2022"),(5,"2024")]
df_s36 = pd.read_excel(BASE/"Salud_Casen_2024.xlsx", sheet_name="36", header=None)
prob_atencion = parse_cat_region(df_s36, region_col=0, cat_col=1, col_años=AÑOS_PROB,
    skip_cats={"Ns/Nr","Total","nan"})

# Hoja 47 — prestaciones recibidas por tipo (% Sí)
# Cada bloque de 10 cols es un tipo de prestación
df_s47 = pd.read_excel(BASE/"Salud_Casen_2024.xlsx", sheet_name="47", header=None)
PRESTACIONES = {}
BLOQUES_PREST = [
    (0,  "Consulta médica general",     [(2,"2009"),(3,"2011"),(4,"2013"),(5,"2015"),(6,"2017"),(7,"2022"),(8,"2024")]),
    (10, "Consulta de urgencia",         [(12,"2009"),(13,"2011"),(14,"2013"),(15,"2015"),(16,"2017"),(17,"2022"),(18,"2024")]),
    (20, "Atención de salud mental",     [(22,"2009"),(23,"2011"),(24,"2013"),(25,"2015"),(26,"2017"),(27,"2022"),(28,"2024")]),
    (30, "Consulta de especialidad",     [(32,"2009"),(33,"2011"),(34,"2013"),(35,"2015"),(36,"2017"),(37,"2022"),(38,"2024")]),
    (40, "Atención dental",              [(42,"2009"),(43,"2011"),(44,"2013"),(45,"2015"),(46,"2017"),(47,"2022"),(48,"2024")]),
    (50, "Exámenes de laboratorio",      [(51,"2009"),(52,"2011"),(53,"2013"),(54,"2015"),(55,"2017"),(56,"2022")]),
    (68, "Controles médicos",            [(69,"2009"),(70,"2011"),(71,"2013"),(72,"2015"),(73,"2017"),(74,"2022"),(75,"2024")]),
    (77, "Hospitalizaciones/cirugías",   [(78,"2009"),(79,"2011"),(80,"2013"),(81,"2015"),(82,"2017"),(83,"2022"),(84,"2024")]),
]
for c_start, nombre, col_años in BLOQUES_PREST:
    cur_reg = None
    for _, row in df_s47.iterrows():
        # col region puede estar en c_start o c_start+0 (depende del bloque)
        r_val = row[c_start] if c_start < 60 else row[c_start]
        r = canon(r_val)
        if r: cur_reg = r
        cat = str(row[c_start+1]).strip() if pd.notna(row[c_start+1]) else None
        if not cur_reg or cat != "Sí": continue
        PRESTACIONES.setdefault(cur_reg, {}).setdefault(nombre, {})
        for col, año in col_años:
            v = cn(row[col])
            if v is not None: PRESTACIONES[cur_reg][nombre][año] = v

# Hoja 69 — AUGE-GES
AÑOS_GES = [(2,"2009"),(3,"2011"),(4,"2013"),(5,"2015"),(6,"2017"),(7,"2020"),(8,"2022"),(9,"2024")]
df_s69 = pd.read_excel(BASE/"Salud_Casen_2024.xlsx", sheet_name="69", header=None)
auge_ges = parse_cat_region(df_s69, region_col=0, cat_col=1, col_años=AÑOS_GES,
    skip_cats={"No sabe/No recuerda","Total","nan"})

# ══════════════════════════════════════════════════════════════
# CONSOLIDAR
# ══════════════════════════════════════════════════════════════
casen = {
    "años_pob":       [a for _,a in AÑOS_POB],
    "años_sev":       [a for _,a in AÑOS_SEV],
    "años_ing":       [a for _,a in AÑOS_ING],
    "años_sal":       [a for _,a in AÑOS_SAL],
    "años_aten":      [a for _,a in AÑOS_ATEN],
    "años_prob":      [a for _,a in AÑOS_PROB],
    "años_ges":       [a for _,a in AÑOS_GES],
    "indicadores_multi": indicadores_multi,
    "dimensiones_multi": dims_multi,
    "prestaciones_tipos": [b[1] for b in BLOQUES_PREST],
    "regiones": REGIONES_CANON,
    "datos": {}
}

for reg in REGIONES_CANON:
    casen["datos"][reg] = {
        "pobreza_ingresos":  pobreza_ing_pers.get(reg, {}),
        "fgt":               fgt_pers.get(reg, {}),
        "pobreza_severa":    pob_severa.get(reg, {}),
        "multi_incidencia":  multi_incidencia.get(reg, {}),
        "carencias":         carencias.get(reg, {}),
        "contribucion_dims": contribucion.get(reg, {}),
        "ingresos":          ingresos.get(reg, {}),
        "composicion_ing":   composicion_ing.get(reg, {}),
        "pob_relativa":      pob_relativa.get(reg, {}),
        "previsional":       previsional.get(reg, {}),
        "atencion_medica":   atencion_med.get(reg, {}),
        "prob_atencion":     prob_atencion.get(reg, {}),
        "prestaciones":      PRESTACIONES.get(reg, {}),
        "auge_ges":          auge_ges.get(reg, {}),
    }

# ══════════════════════════════════════════════════════════════
# VERIFICACIÓN
# ══════════════════════════════════════════════════════════════
print("=== VERIFICACIÓN COBERTURA ===")
bloques_check = [
    ("pobreza_ingresos","Pobreza total","2024"),
    ("fgt","FGT1_Brecha","2024"),
    ("pobreza_severa","Pobreza Severa","2024"),
    ("multi_incidencia","met2024_2024_hog",None),
    ("carencias","Informalidad",None),
    ("ingresos","Ingreso monetario","2024"),
    ("composicion_ing","Ingreso autónomo","2024"),
    ("pob_relativa","Ingreso monetario","2024"),
    ("previsional","Sistema Público FONASA","2024"),
    ("atencion_medica","Sí","2024"),
    ("prob_atencion","Tuvo","2024"),
    ("prestaciones","Consulta médica general","2024"),
    ("auge_ges","Si","2024"),
]
for bloque, key, año in bloques_check:
    faltantes = []
    for reg in REGIONES_CANON:
        d = casen["datos"][reg].get(bloque,{})
        if año:
            v = d.get(key,{}).get(año)
        else:
            v = d.get(key)
        if v is None: faltantes.append(reg)
    status = "✓" if not faltantes else f"⚠ faltan: {faltantes}"
    print(f"  {bloque}/{key}: {status}")

print("\n=== MUESTRA RM ===")
rm = casen["datos"]["Metropolitana de Santiago"]
print(f"  Pobreza total 2024:     {rm['pobreza_ingresos'].get('Pobreza total',{}).get('2024')}")
print(f"  FGT1 Brecha 2024:       {rm['fgt'].get('FGT1_Brecha',{}).get('2024')}")
print(f"  FGT2 Severidad 2024:    {rm['fgt'].get('FGT2_Severidad',{}).get('2024')}")
print(f"  Pob. relativa ing.mon:  {rm['pob_relativa'].get('Ingreso monetario',{}).get('2024')}")
print(f"  Composición autónomo:   {rm['composicion_ing'].get('Ingreso autónomo',{}).get('2024')}")
print(f"  FONASA 2024:            {rm['previsional'].get('Sistema Público FONASA',{}).get('2024')}")
print(f"  Prob.atención 2024:     {rm['prob_atencion'].get('Tuvo',{}).get('2024')}")
print(f"  Consulta médica 2024:   {rm['prestaciones'].get('Consulta médica general',{}).get('2024')}")
print(f"  AUGE-GES Sí 2024:       {rm['auge_ges'].get('Si',{}).get('2024')}")

with open(OUT,"w",encoding="utf-8") as f:
    json.dump(casen,f,ensure_ascii=False,indent=2)
sz = OUT.stat().st_size
print(f"\n✓ casen_regiones.json → {sz//1024} KB  ({sz} bytes)")
