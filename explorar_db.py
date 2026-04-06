import sqlite3
conn = sqlite3.connect("bcn_indicadores.db")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tablas:", cur.fetchall())

cur.execute("""SELECT DISTINCT indicador_limpio, unidad_limpia, nombre_region
    FROM registros_bce
    WHERE indicador_limpio LIKE '%ocup%'
    OR indicador_limpio LIKE '%fuerza%'
    OR indicador_limpio LIKE '%desocup%'
    OR indicador_limpio LIKE '%trabajo%'
    LIMIT 40""")
print("\nIndicadores trabajo:")
for r in cur.fetchall():
    print(r)

cur.execute("""SELECT indicador_limpio, unidad_limpia, COUNT(*) as n,
    MIN(periodo) as desde, MAX(periodo) as hasta
    FROM registros_bce
    WHERE indicador_limpio LIKE '%ocup%'
    OR indicador_limpio LIKE '%fuerza%'
    OR indicador_limpio LIKE '%desocup%'
    GROUP BY indicador_limpio, unidad_limpia""")
print("\nResumen:")
for r in cur.fetchall():
    print(r)

conn.close()
