"""
ADIS API Interceptor v2
========================
- Lee credenciales de env.local correctamente
- Navega a login, estadísticas y hace consultas reales
- Intercepta llamadas a la API y prueba endpoints directamente
"""

import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ── Leer credenciales ─────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).parent / "env.local"
ADIS_USER, ADIS_PASS = "", ""
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("USER="):
            ADIS_USER = line.split("=", 1)[1].strip()
        elif line.startswith("PASS="):
            ADIS_PASS = line.split("=", 1)[1].strip()

print(f"Credenciales: {'✓ usuario=' + ADIS_USER if ADIS_USER else '✗ no encontradas'}")

# ── Driver ────────────────────────────────────────────────────────────────────
def crear_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_cdp_cmd("Network.enable", {})
    return driver

def capturar(driver):
    out = {}
    try: logs = driver.get_log("performance")
    except: return out
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
            m = msg.get("method","")
            if m == "Network.requestWillBeSent":
                p = msg["params"]
                url = p["request"]["url"]
                rid = p["requestId"]
                if any(url.endswith(e) for e in [".js",".css",".png",".jpg",".svg",".ico",".gif",".woff",".woff2"]):
                    continue
                if "fonts.google" in url or "fonts.gstatic" in url:
                    continue
                out[rid] = {
                    "url": url,
                    "method": p["request"]["method"],
                    "post_data": p["request"].get("postData",""),
                    "headers": {k:v for k,v in p["request"].get("headers",{}).items()
                                if k.lower() in ["authorization","x-auth-token","cookie","content-type"]},
                    "status": None, "content_type": "", "response_body": None,
                }
            elif m == "Network.responseReceived":
                rid = msg["params"]["requestId"]
                if rid in out:
                    r = msg["params"]["response"]
                    out[rid]["status"] = r.get("status")
                    out[rid]["content_type"] = r.get("mimeType","")
        except: continue
    return out

def get_body(driver, rid):
    try:
        res = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
        b = res.get("body","")
        if b:
            try: return json.loads(b)
            except: return b[:3000]
    except: return None

def fetch_directo(driver, url):
    try:
        return driver.execute_script(f"""
            const r = await fetch('{url}', {{credentials:'include', headers:{{'Accept':'application/json'}}}});
            const t = await r.text();
            return {{status: r.status, body: t.substring(0,2000)}};
        """)
    except: return None

def main():
    print("\n=== ADIS Interceptor v2 ===")
    driver = crear_driver()
    todos = {}

    try:
        # ── Login ──────────────────────────────────────────────────────────────
        print("\n[1] Login...")
        driver.get("https://adis.gob.cl/#/login")
        time.sleep(5)
        todos.update(capturar(driver))

        if ADIS_USER and ADIS_PASS:
            for sel in ["input[type='email']","input[type='text']",
                        "input[formcontrolname='username']","input[formcontrolname='email']"]:
                f = driver.find_elements(By.CSS_SELECTOR, sel)
                if f and f[0].is_displayed():
                    f[0].clear(); f[0].send_keys(ADIS_USER)
                    print(f"  → usuario ({sel})")
                    break

            for sel in ["input[type='password']","input[formcontrolname='password']"]:
                f = driver.find_elements(By.CSS_SELECTOR, sel)
                if f and f[0].is_displayed():
                    f[0].clear(); f[0].send_keys(ADIS_PASS)
                    print(f"  → contraseña ({sel})")
                    break

            submitted = False
            for sel in ["button[type='submit']","button.login-btn","input[type='submit']"]:
                b = driver.find_elements(By.CSS_SELECTOR, sel)
                if b and b[0].is_displayed():
                    b[0].click(); submitted = True
                    print(f"  → submit ({sel})"); break

            if not submitted:
                for txt in ["Ingresar","Entrar","Login","Iniciar"]:
                    b = driver.find_elements(By.XPATH, f"//button[contains(text(),'{txt}')]")
                    if b: b[0].click(); submitted=True; print(f"  → '{txt}'"); break

            time.sleep(6)
            todos.update(capturar(driver))
        else:
            print("  Sin credenciales — ingresa manualmente si quieres (20s)...")
            time.sleep(20)
            todos.update(capturar(driver))

        # ── Estadísticas frecuentes ────────────────────────────────────────────
        print("\n[2] Estadísticas frecuentes...")
        driver.get("https://adis.gob.cl/#/estadisticas-socioeconomicas/frecuentes")
        time.sleep(7)
        todos.update(capturar(driver))

        # Interactuar
        driver.execute_script("window.scrollTo(0, 500)")
        time.sleep(2)
        for sel in ["mat-checkbox","p-checkbox","input[type='checkbox']",".indicador-item",".frecuente"]:
            items = driver.find_elements(By.CSS_SELECTOR, sel)
            if items:
                print(f"  → {len(items)} items con '{sel}'")
                for item in items[:3]:
                    try: driver.execute_script("arguments[0].click();", item); time.sleep(0.3)
                    except: pass
                break

        for txt in ["Ver resultados","Consultar","Ver","Aplicar"]:
            b = driver.find_elements(By.XPATH, f"//*[contains(text(),'{txt}')]")
            for btn in b:
                try:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"  → '{txt}'"); time.sleep(5); break
                except: pass

        todos.update(capturar(driver))

        # ── Pruebas directas de API ────────────────────────────────────────────
        print("\n[3] Probando endpoints directamente...")
        pruebas = [
            "https://api.adis.gob.cl/app?blockui=true&system=true",
            "https://api.adis.gob.cl/api/estadisticas/frecuentes",
            "https://api.adis.gob.cl/api/indicadores/frecuentes",
            "https://api.adis.gob.cl/api/regiones",
            "https://api.adis.gob.cl/api/indicadores",
            "https://api.adis.gob.cl/estadisticas",
            "https://api.adis.gob.cl/frecuentes",
            "https://api.adis.gob.cl/v1/estadisticas/frecuentes",
            "https://api.adis.gob.cl/api/v1/estadisticas",
            "https://api.adis.gob.cl/auth/login",
        ]
        directos = {}
        for url in pruebas:
            r = fetch_directo(driver, url)
            if r:
                directos[url] = r
                print(f"  [{r.get('status','-')}] {url}")
                if r.get("status") == 200 and r.get("body"):
                    print(f"    → {r['body'][:300]}")

        with open("adis_direct.json","w",encoding="utf-8") as f:
            json.dump(directos, f, ensure_ascii=False, indent=2)

        # ── Bodies ────────────────────────────────────────────────────────────
        print("\n[4] Obteniendo bodies JSON...")
        for rid, ep in todos.items():
            if "json" in ep.get("content_type","") or "api.adis" in ep.get("url",""):
                ep["response_body"] = get_body(driver, rid)

        # ── Guardar ───────────────────────────────────────────────────────────
        lista = list(todos.values())
        with open("adis_endpoints.json","w",encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)

        with open("adis_report.txt","w",encoding="utf-8") as f:
            f.write("=== ADIS Report ===\n\n")
            f.write(f"Total requests: {len(lista)}\n\n")
            f.write("── URLs únicas ──\n")
            for url in sorted(set(e["url"] for e in lista)):
                f.write(f"  {url}\n")
            f.write("\n── Detalle ──\n\n")
            for ep in lista:
                f.write(f"[{ep.get('status','-')}] {ep['method']} {ep['url']}\n")
                if ep.get("headers"): f.write(f"  Headers auth: {ep['headers']}\n")
                if ep.get("post_data"): f.write(f"  Body: {str(ep['post_data'])[:400]}\n")
                if ep.get("response_body"):
                    f.write(f"  Respuesta: {json.dumps(ep['response_body'],ensure_ascii=False)[:1000]}\n")
                f.write("\n")
            f.write("\n── Pruebas directas ──\n\n")
            for url, r in directos.items():
                f.write(f"[{r.get('status')}] {url}\n")
                if r.get("body"): f.write(f"  {r['body'][:500]}\n\n")

        print("\n=== Listo ===")
        print(f"Requests capturadas: {len(lista)}")
        print("\nURLs de API:")
        for url in sorted(set(e["url"] for e in lista)):
            if "api.adis" in url or (
                "adis.gob" in url and not any(url.endswith(x) for x in
                [".js",".css",".png",".jpg",".svg",".gif",".ico",".woff"])):
                print(f"  {url}")

        print("\nCerrando en 15s...")
        time.sleep(15)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
