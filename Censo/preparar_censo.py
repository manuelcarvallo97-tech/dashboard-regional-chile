"""
preparar_censo.py — Agrega microdatos del Censo 2024 por región
===============================================================
INPUT : Base_zona_localidad_CPV24.csv  (en el mismo directorio)
OUTPUT: censo_regiones.json            (para el dashboard)

Uso:
    python preparar_censo.py
    → censo_regiones.json (~50 KB)

Luego sube censo_regiones.json y se integra al dashboard.
"""

import pandas as pd
import json, math, sys
from pathlib import Path

CSV_PATH = Path("Base_zona_localidad_CPV24.csv")  # nombre exacto dentro del ZIP
OUT_PATH = Path("censo_regiones.json")

if not CSV_PATH.exists():
    sys.exit(f"❌ No se encuentra {CSV_PATH}. Coloca el CSV en el mismo directorio.")

print("📂 Leyendo CSV...")
df = pd.read_csv(CSV_PATH, sep=';', encoding='utf-8-sig', decimal=',', low_memory=False)
print(f"   {len(df):,} localidades, {len(df.columns)} columnas")

# ── Columnas numéricas: forzar a numérico (algunas vienen como str por mixed types)
skip = ['CONTENEDOR_COMUNAL','COD_REGION','REGION','PROVINCIA','CUT','COMUNA',
        'AREA_C','DISTRITO','COD_DISTRITO','COD_LOCALIDAD','COD_ZONA','LOCALIDAD',
        'ID_ENTIDAD','ID_LOCALIDAD','ID_DISTRITO','ID_ZONA']
num_cols = [c for c in df.columns if c not in skip]
for c in num_cols:
    df[c] = pd.to_numeric(df[c], errors='coerce')

# ── Nombre limpio de región
region_nombres = (df[['COD_REGION','REGION']]
                  .drop_duplicates()
                  .sort_values('COD_REGION')
                  .set_index('COD_REGION')['REGION']
                  .str.title()
                  .to_dict())

# Normalizar nombres largos
NOMBRES = {
    1:  'Tarapacá',
    2:  'Antofagasta',
    3:  'Atacama',
    4:  'Coquimbo',
    5:  'Valparaíso',
    6:  "O'Higgins",
    7:  'Maule',
    8:  'Biobío',
    9:  'La Araucanía',
    10: 'Los Lagos',
    11: 'Aysén',
    12: 'Magallanes',
    13: 'Metropolitana',
    14: 'Los Ríos',
    15: 'Arica y Parinacota',
    16: 'Ñuble',
}

# ── Columnas de SUMA (conteos absolutos)
SUMAS = [
    # Demografía
    'n_per','n_hombres','n_mujeres',
    'n_edad_0_5','n_edad_6_13','n_edad_14_17','n_edad_18_24',
    'n_edad_25_44','n_edad_45_59','n_edad_60_mas',
    'n_inmigrantes','n_pueblos_orig','n_afrodescendencia',
    # Discapacidad
    'n_discapacidad',
    'n_dificultad_ver','n_dificultad_oir','n_dificultad_mover',
    'n_dificultad_cogni','n_dificultad_cuidado','n_dificultad_comunic',
    # Educación
    'n_analfabet',
    'n_asistencia_parv','n_asistencia_basica','n_asistencia_media','n_asistencia_superior',
    'n_cine_nunca_curso_primera_infancia','n_cine_primaria','n_cine_secundaria',
    'n_cine_terciaria_maestria_doctorado','n_cine_especial_diferencial',
    # Trabajo
    'n_ocupado','n_desocupado','n_fuera_fuerza_trabajo',
    'n_cise_rec_independientes','n_cise_rec_dependientes','n_cise_rec_trabajador_no_remunerado',
    # Vivienda / hogares
    'n_hog','n_vp','n_vp_ocupada','n_vp_desocupada',
    'n_hog_unipersonales','n_hog_60','n_hog_menores','n_jefatura_mujer',
    'n_tipo_viv_casa','n_tipo_viv_depto','n_tipo_viv_mediagua',
    'n_tipo_viv_indigena','n_tipo_viv_pieza','n_tipo_viv_movil','n_tipo_viv_otro',
    'n_tenencia_propia_pagada','n_tenencia_propia_pagandose',
    'n_tenencia_arrendada_contrato','n_tenencia_arrendada_sin_contrato',
    'n_tenencia_cedida_trabajo','n_tenencia_cedida_familiar','n_tenencia_otro',
    'n_viv_hacinadas','n_viv_irrecuperables','n_deficit_cuantitativo',
    'n_hog_allegados','n_nucleos_hacinados_allegados',
    # Servicios básicos
    'n_fuente_agua_publica','n_fuente_agua_pozo','n_fuente_agua_camion','n_fuente_agua_rio',
    'n_distrib_agua_llave','n_distrib_agua_llave_fuera','n_distrib_agua_acarreo',
    'n_serv_hig_alc_dentro','n_serv_hig_alc_fuera','n_serv_hig_fosa',
    'n_serv_hig_pozo','n_serv_hig_no_tiene',
    'n_fuente_elect_publica','n_fuente_elect_no_tiene',
    'n_basura_servicios','n_basura_entierra','n_basura_eriazo','n_basura_rio',
    # Conectividad
    'n_internet','n_serv_tel_movil','n_serv_compu','n_serv_tablet',
    'n_serv_internet_fija','n_serv_internet_movil','n_serv_internet_satelital',
    # Combustible cocina/calefacción
    'n_comb_cocina_gas','n_comb_cocina_lena','n_comb_cocina_electricidad','n_comb_cocina_no_utiliza',
    'n_comb_calefaccion_gas','n_comb_calefaccion_lena',
    'n_comb_calefaccion_electricidad','n_comb_calefaccion_no_utiliza',
    # Transporte
    'n_transporte_auto','n_transporte_publico','n_transporte_camina',
    'n_transporte_bicicleta','n_transporte_motocicleta',
]
SUMAS = [c for c in SUMAS if c in df.columns]

# ── Columnas de PROMEDIO PONDERADO (promedios × n_per o n_hog)
# Se recalculan como suma(prom * n) / suma(n) por región
PROMS_PER = ['prom_edad']          # ponderado por n_per
PROMS_ESC = ['prom_escolaridad18'] # ponderado por n_per (aprox)
PROMS_HOG = ['prom_per_hog']       # ponderado por n_hog

print("📊 Agregando por región...")
g = df.groupby('COD_REGION')

resultado = {}
for cod, grp in g:
    r = {'nombre': NOMBRES.get(cod, region_nombres.get(cod, str(cod))), 'cod': int(cod)}

    # Sumas
    for c in SUMAS:
        r[c] = int(grp[c].sum()) if c in grp else 0

    # Promedios ponderados
    def prom_pond(col, peso):
        mask = grp[col].notna() & grp[peso].notna() & (grp[peso] > 0)
        num = (grp.loc[mask, col] * grp.loc[mask, peso]).sum()
        den = grp.loc[mask, peso].sum()
        return round(float(num / den), 1) if den > 0 else None

    r['prom_edad']          = prom_pond('prom_edad', 'n_per')
    r['prom_escolaridad18'] = prom_pond('prom_escolaridad18', 'n_per')
    r['prom_per_hog']       = prom_pond('prom_per_hog', 'n_hog')

    # Indicadores derivados (calculados, no embebidos como % para no fijar denominadores)
    resultado[cod] = r

# ── Ordenar regiones
regiones_ordenadas = [NOMBRES[k] for k in sorted(NOMBRES.keys())]

# ── Serializar (limpiar NaN/inf)
def clean(v):
    if v is None: return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
    return v

datos_limpios = {}
for cod, r in resultado.items():
    datos_limpios[str(cod)] = {k: clean(v) for k, v in r.items()}

out = {
    'regiones': regiones_ordenadas,
    'datos': datos_limpios,
    'fuente': 'Censo de Población y Vivienda 2024 — INE Chile',
    'nivel': 'región',   # cambiar a 'comuna' cuando se amplíe
}

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

size_kb = OUT_PATH.stat().st_size / 1024
print(f"\n✅ Generado: {OUT_PATH}  ({size_kb:.1f} KB)")
print(f"   Regiones: {len(datos_limpios)}")
print(f"   Variables por región: {len(next(iter(datos_limpios.values())))}")
print(f"\n→ Sube censo_regiones.json para integrarlo al dashboard.")

# Vista previa RM
rm = datos_limpios.get('13', {})
print(f"\nEjemplo Metropolitana:")
print(f"  Población: {rm.get('n_per'):,}")
print(f"  Hogares:   {rm.get('n_hog'):,}")
print(f"  Inmigrantes: {rm.get('n_inmigrantes'):,}")
print(f"  Prom. edad: {rm.get('prom_edad')}")
print(f"  Prom. escolaridad: {rm.get('prom_escolaridad18')}")
print(f"  Internet: {rm.get('n_internet'):,}")
print(f"  Déficit cuantitativo: {rm.get('n_deficit_cuantitativo'):,}")
