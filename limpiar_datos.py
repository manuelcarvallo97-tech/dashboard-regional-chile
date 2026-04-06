"""
Limpieza de datos BCN y BCE
============================
Limpia y normaliza las tablas registros_bcn y registros_bce en bcn_indicadores.db

Cambios BCN:
- Elimina numeración del inicio de subtabla (ej: "1.1 Distribución..." → "Distribución...")
- Corrige separador decimal en columna valor (punto como decimal)

Cambios BCE:
- Extrae nombre_region del título
- Extrae indicador limpio del título
- Extrae unidad del título (entre paréntesis al final)
- Corrige valor numérico según unidad (porcentaje → decimal, otros → miles)
- Elimina referencia 2018 y otros textos innecesarios
"""

import sqlite3
import pandas as pd
import re

DB_PATH = "bcn_indicadores.db"

# ── Mapeo de nombres de región para estandarizar ──────────────────────────────
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
    # Numeración romana (series antiguas BCE)
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

REGIONES_LISTA = list(REGION_MAP.keys())


def normalizar_region(texto):
    """Busca el nombre de región dentro de un texto y lo devuelve estandarizado."""
    t = texto.lower()
    # Ordenar por longitud descendente para que coincida primero el más específico
    for patron in sorted(REGIONES_LISTA, key=len, reverse=True):
        if patron in t:
            return REGION_MAP[patron]
    return None


def limpiar_titulo_bce(titulo):
    """
    Extrae: indicador, region, unidad de un título BCE.
    Maneja los 3 patrones encontrados:
      1. Indicador, Región, descripción, referencia 2018 (Unidad)
      2. Indicador, Región descripción, referencia 2018 (Unidad)
      3. Indicador+Región juntos, descripción, referencia 2018 (Unidad)
    """
    if not titulo or pd.isna(titulo):
        return None, None, None

    t = str(titulo).strip()

    # Detectar si es serie de precios corrientes ANTES de modificar t
    es_corriente = bool(re.search(r'precios corrientes', t, re.IGNORECASE))
    base_año = None
    match_base = re.search(r'base\s+(\d{4})', t, re.IGNORECASE)
    if match_base:
        base_año = match_base.group(1)

    # Extraer unidad entre paréntesis al final
    unidad = None
    match_unidad = re.search(r'\(([^)]+)\)\s*$', t)
    if match_unidad:
        unidad = match_unidad.group(1).strip()
        t = t[:match_unidad.start()].strip().rstrip(',').strip()

    # Si es corriente, ajustar la unidad para distinguirla
    if es_corriente:
        if unidad and 'millones' in unidad.lower():
            unidad = f"miles de millones de pesos corrientes (base {base_año})" if base_año else "miles de millones de pesos corrientes"
        else:
            unidad = f"miles de millones de pesos corrientes (base {base_año})" if base_año else "miles de millones de pesos corrientes"

    # Eliminar referencias innecesarias
    t = re.sub(r',?\s*referencia\s+\d{4}', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*base\s+\d{4}', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*BCCh?$', '', t, flags=re.IGNORECASE)
    t = re.sub(r',?\s*serie\s+\w+$', '', t, flags=re.IGNORECASE)
    t = t.strip().rstrip(',').strip()

    # Extraer región
    region = normalizar_region(t)

    # Limpiar indicador: quitar la región del texto y limpiar residuos
    indicador = t
    if region:
        # Intentar eliminar la mención de región del título
        for patron in sorted(REGIONES_LISTA, key=len, reverse=True):
            if REGION_MAP.get(patron) == region:
                # Eliminar con variantes de "Región de/del/..."
                for prefijo in ["región de ", "región del ", "región ", "region de ", "region del ", "region "]:
                    indicador = re.sub(
                        re.escape(prefijo + patron), '', indicador,
                        flags=re.IGNORECASE
                    )
                indicador = re.sub(
                    re.escape(patron), '', indicador,
                    flags=re.IGNORECASE
                )

    # Limpiar residuos del indicador
    indicador = re.sub(r',\s*,', ',', indicador)
    indicador = indicador.strip().strip(',').strip()
    # Eliminar partes después de la última coma si son muy cortas o vagas
    partes = [p.strip() for p in indicador.split(',') if p.strip()]
    # Filtrar partes que solo son descripciones técnicas repetitivas
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

    indicador = ', '.join(partes_limpias) if partes_limpias else partes[0] if partes else t
    indicador = indicador.strip().strip(',').strip()

    return indicador, region, unidad


def corregir_valor_bce(valor, unidad):
    """
    Corrige el valor numérico según la unidad:
    - Porcentaje: el punto es decimal (ej: 2.5 → 2.5%)
    - Otros (miles de millones, etc.): el punto es separador de miles
    """
    if pd.isna(valor):
        return valor

    if unidad and 'porcentaje' in str(unidad).lower():
        # Ya viene como decimal, no hay que tocar
        return valor
    else:
        # El punto en el valor original era separador de miles
        # pandas ya lo leyó como float, pero si venía "1.234" lo interpretó como 1.234
        # cuando debería ser 1234. Detectamos esto: si tiene exactamente 3 decimales
        # probablemente era separador de miles
        val_str = str(valor)
        if '.' in val_str:
            decimales = val_str.split('.')[1]
            if len(decimales) == 3:
                # Era separador de miles: multiplicar por 1000
                return valor * 1000
        return valor


# ── Limpieza BCN ──────────────────────────────────────────────────────────────

def limpiar_bcn(conn):
    print("\n=== Limpiando registros_bcn ===")
    df = pd.read_sql("SELECT * FROM registros_bcn", conn)
    print(f"  Filas originales: {len(df)}")

    # 1. Limpiar subtabla: eliminar numeración del inicio (ej: "1.1 Texto" → "Texto")
    df['subtabla'] = df['subtabla'].str.replace(
        r'^\d+(\.\d+)*\s+', '', regex=True
    ).str.strip()

    # 2. El valor ya debería estar bien (Python lo parseó con punto decimal)
    #    Solo verificamos que no haya valores absurdos
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce')

    # 3. Guardar de vuelta
    df.to_sql('registros_bcn', conn, if_exists='replace', index=False)
    print(f"  Subtablas limpias: ejemplo → '{df['subtabla'].iloc[10]}'")
    print(f"  Valores nulos: {df['valor'].isna().sum()}")
    print("  BCN limpio ✓")


# ── Limpieza BCE ──────────────────────────────────────────────────────────────

def limpiar_bce(conn):
    print("\n=== Limpiando registros_bce ===")
    df = pd.read_sql("SELECT * FROM registros_bce", conn)
    print(f"  Filas originales: {len(df)}")

    # Aplicar extracción de campos
    resultados = df['titulo'].apply(limpiar_titulo_bce)
    df['indicador_limpio'] = [r[0] for r in resultados]
    df['nombre_region']    = [r[1] for r in resultados]
    df['unidad_limpia']    = [r[2] for r in resultados]

    # Corregir valores numéricos
    df['valor_corregido'] = df.apply(
        lambda row: corregir_valor_bce(row['valor'], row['unidad_limpia']),
        axis=1
    )

    # Reporte de extracción
    sin_region = df['nombre_region'].isna().sum()
    print(f"  Registros sin región identificada: {sin_region} ({sin_region/len(df)*100:.1f}%)")
    print(f"  Regiones encontradas: {df['nombre_region'].nunique()}")
    print(f"  Indicadores únicos: {df['indicador_limpio'].nunique()}")

    # Mostrar muestra de resultados
    print("\n  Muestra de extracción:")
    muestra = df[['titulo', 'nombre_region', 'indicador_limpio', 'unidad_limpia']].head(5)
    for _, row in muestra.iterrows():
        print(f"    Título:     {row['titulo'][:70]}...")
        print(f"    → Región:   {row['nombre_region']}")
        print(f"    → Indicador:{row['indicador_limpio']}")
        print(f"    → Unidad:   {row['unidad_limpia']}")
        print()

    # Guardar tabla limpia
    df.to_sql('registros_bce', conn, if_exists='replace', index=False)
    print("  BCE limpio ✓")

    # Exportar CSV actualizado
    df_export = df[[
        'nombre_region', 'indicador_limpio', 'unidad_limpia',
        'periodo', 'valor_corregido', 'titulo', 'series_id'
    ]].rename(columns={
        'indicador_limpio': 'indicador',
        'unidad_limpia': 'unidad',
        'valor_corregido': 'valor'
    })
    df_export.to_csv('bce_datos_limpio.csv', index=False, encoding='utf-8-sig')
    print("  Exportado: bce_datos_limpio.csv")


# ── Exportar BCN limpio ───────────────────────────────────────────────────────

def exportar_bcn_limpio(conn):
    df = pd.read_sql("""
        SELECT nombre_region, anno, seccion, subtabla,
               indicador, nivel, valor, valor_texto, fuente
        FROM registros_bcn
        WHERE valor IS NOT NULL
        ORDER BY anno, nombre_region, seccion
    """, conn)
    df.to_csv('bcn_datos_limpio.csv', index=False, encoding='utf-8-sig')
    print("\n  Exportado: bcn_datos_limpio.csv")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    limpiar_bcn(conn)
    limpiar_bce(conn)
    exportar_bcn_limpio(conn)

    conn.close()
    print("\n=== Limpieza completa ===")
    print("Archivos generados:")
    print("  bcn_datos_limpio.csv")
    print("  bce_datos_limpio.csv")
