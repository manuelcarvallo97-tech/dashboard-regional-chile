"""
Busca IDs correctos de series de empleo regional en BCE
"""
import requests, json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# Leer .env
creds = {}
for fname in [".env", "env.local"]:
    p = Path(__file__).parent / fname
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()

user = creds.get("BDE_USER","")
pwd  = creds.get("BDE_PASS","")
log.info(f"BDE_USER: {user}")

BASE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

# Test
r = requests.get(BASE_URL, params={
    "user": user, "pass": pwd, "function": "GetSeries",
    "timeseries": "F022.TPM.TIN.D001.NO.Z.D",
    "firstdate": "2024-01-01", "lastdate": "2024-01-05"
}, timeout=30)
data = r.json()
log.info(f"Test API: Codigo={data.get('Codigo')}, {data.get('Descripcion')}")

if data.get("Codigo") != 0:
    log.error("Credenciales inválidas"); exit()

log.info("✓ Credenciales OK — buscando series de empleo regional...")

resultados = []
for freq in ["MONTHLY", "QUARTERLY"]:
    r2 = requests.get(BASE_URL, params={
        "user": user, "pass": pwd,
        "function": "SearchSeries", "frequency": freq
    }, timeout=60)
    series = r2.json().get("SeriesInfos", [])
    log.info(f"  Series {freq}: {len(series)}")
    for s in series:
        titulo = s.get("spanishTitle","").lower()
        if any(k in titulo for k in ["desocupaci","fuerza de trabajo","ocupados","empleo"]):
            if any(k in titulo for k in ["región","region","regional","arica","tarapacá","antofagasta","atacama","coquimbo","valparaíso","metropolitana","higgins","maule","biobío","araucan","lagos","aysén","magallanes","ñuble","ríos"]):
                resultados.append({"freq":freq, "id":s["seriesId"], "titulo":s["spanishTitle"], "ultima":s.get("lastObservation","")})

log.info(f"\nSeries regionales de empleo: {len(resultados)}")
for r in resultados:
    print(f"  [{r['freq']}] {r['id']}")
    print(f"    {r['titulo']} (hasta {r['ultima']})")

with open("bce_empleo_catalogo.json","w",encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)
log.info("\nGuardado en bce_empleo_catalogo.json")
