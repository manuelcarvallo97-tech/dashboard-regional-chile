import sqlite3, requests, json, math
import urllib3; urllib3.disable_warnings()

DB   = 'bcn_indicadores.db'
SUPA = [l.split('=',1)[1].strip() for l in open('.env').read().splitlines() if l.startswith('WORKOS_SUPABASE_URL')][0]
KEY  = [l.split('=',1)[1].strip() for l in open('.env').read().splitlines() if l.startswith('WORKOS_SUPABASE_SERVICE_KEY')][0]

conn = sqlite3.connect(DB)
cur  = conn.execute("""
    SELECT id_semana, anno, semana, fecha_desde_iso, fecha_hasta_iso,
           id_region, nombre_region, nombre_delito, es_dmcs,
           ultima_semana_ant, ultima_semana,
           dias28_ant, dias28,
           anno_fecha_ant, anno_fecha, umbral
    FROM registros_leystop_delitos
    ORDER BY id_semana, id_region
""")
cols = [d[0] for d in cur.description]
rows = [
    {k: (None if isinstance(v, float) and math.isnan(v) else v)
     for k, v in dict(zip(cols, r)).items()}
    for r in cur.fetchall()
]
conn.close()
print(f"Total filas a subir: {len(rows)}")

ok = 0
BATCH = 200
for i in range(0, len(rows), BATCH):
    batch = rows[i:i+BATCH]
    r = requests.post(
        f"{SUPA}/rest/v1/registros_leystop_delitos",
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "id_semana,id_region,nombre_delito"},
        data=json.dumps(batch, default=str),
        verify=False,
        timeout=60
    )
    if r.status_code in (200, 201):
        ok += len(batch)
        print(f"  Batch {i//BATCH+1}/{(len(rows)-1)//BATCH+1}: OK ({ok}/{len(rows)})")
    else:
        print(f"  Batch {i//BATCH+1}: ERROR {r.status_code} — {r.text[:150]}")
        break

print(f"\nListo: {ok} filas subidas a Supabase.")
