"""
Descarga PIB regional BCE — series FLU base 2018 (niveles en miles de millones)
Uso: python bajar_pib.py
"""
import sqlite3, requests, time
try:
    import urllib3; urllib3.disable_warnings()
except: pass

DB = "bcn_indicadores.db"
FIRSTDATE = "2025-01-01"
USER = None
PASS = None

# Leer credenciales desde .env si existe
try:
    for line in open(".env"):
        line = line.strip()
        if line.startswith("BDE_USER"): USER = line.split("=",1)[1].strip()
        if line.startswith("BDE_PASS"): PASS = line.split("=",1)[1].strip()
except: pass

if not USER or not PASS:
    print("ERROR: no se encontraron BDE_USER / BDE_PASS en .env")
    exit(1)

conn = sqlite3.connect(DB)

# Series de NIVELES anuales (FLU) — las que usa el dashboard para el PIB en pesos
series = conn.execute(
    "SELECT DISTINCT series_id FROM registros_bce "
    "WHERE series_id LIKE 'F035.PIB.FLU.R.CLP.2018%' "
    "ORDER BY series_id"
).fetchall()

print(f"{len(series)} series a bajar desde {FIRSTDATE}")
n_total = 0

for i, (sid,) in enumerate(series, 1):
    try:
        r = requests.get(
            "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx",
            params={"user": USER, "pass": PASS, "function": "GetSeries",
                    "timeseries": sid, "firstdate": FIRSTDATE},
            timeout=30, verify=False
        )
        obs = r.json().get("Series", {}).get("Obs") or []
        n = 0
        for o in obs:
            if o.get("statusCode") == "OK" and o.get("value") not in ("", "NaN", None):
                conn.execute(
                    "INSERT OR REPLACE INTO registros_bce (series_id, periodo, valor_corregido) "
                    "VALUES (?,?,?)",
                    (sid, o["indexDateString"], float(o["value"].replace(",",".")))
                )
                n += 1
        if n > 0:
            print(f"  [{i}/{len(series)}] {sid}: {n} nuevos períodos")
        n_total += n
    except Exception as e:
        print(f"  [{i}/{len(series)}] ERROR {sid}: {e}")
    if i % 50 == 0:
        conn.commit()
        print(f"  ... {i}/{len(series)} procesadas, {n_total} registros hasta ahora")
    time.sleep(0.3)

conn.commit()
conn.close()
print(f"\nListo. Total: {n_total} registros nuevos en registros_bce")
