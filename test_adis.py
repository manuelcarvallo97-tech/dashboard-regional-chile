import hashlib, json, time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

ENV_PATH = Path(__file__).parent / "env.local"
p = ENV_PATH.read_text(encoding="utf-8")
rut = [l.split('=',1)[1].strip() for l in p.splitlines() if l.startswith('USER=')][0]
pwd = [l.split('=',1)[1].strip() for l in p.splitlines() if l.startswith('PASS=')][0]
run_num = int(rut[:-1])
pwd_md5 = hashlib.md5(pwd.encode()).hexdigest()

opts = Options()
opts.add_argument("--start-maximized")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

def xhr_get(driver, url, token):
    return driver.execute_script("""
        var xhr = new XMLHttpRequest();
        xhr.open('GET', arguments[0], false);
        xhr.setRequestHeader('Authorization', 'Bearer ' + arguments[1]);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.withCredentials = true;
        xhr.send();
        return {status: xhr.status, body: xhr.responseText.substring(0,400)};
    """, url, token)

def xhr_post(driver, url, token, body):
    return driver.execute_script("""
        var xhr = new XMLHttpRequest();
        xhr.open('POST', arguments[0], false);
        xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
        xhr.setRequestHeader('Authorization', 'Bearer ' + arguments[1]);
        xhr.withCredentials = true;
        xhr.send(JSON.stringify(arguments[2]));
        return {status: xhr.status, body: xhr.responseText.substring(0,600)};
    """, url, token, body)

try:
    driver.get("https://adis.gob.cl")
    time.sleep(3)

    # Login
    r = driver.execute_script("""
        var xhr = new XMLHttpRequest();
        xhr.open('POST', 'https://api.adis.gob.cl/authorization/login?blockui=true&system=false', false);
        xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
        xhr.withCredentials = true;
        xhr.send(JSON.stringify(arguments[0]));
        return {status: xhr.status, body: xhr.responseText};
    """, {"run": run_num, "password": pwd_md5})

    data = json.loads(r['body'])
    token = data.get('token', '')
    print(f"Login: exitoLogin={data.get('exitoLogin')}, token={'OK' if token else 'NO'}")

    if not token:
        print("Sin token, abortando"); driver.quit(); exit()

    # Test periodos
    r2 = xhr_get(driver, "https://api.adis.gob.cl/base/1/periodo?blockui=true&system=false", token)
    print(f"\nPeriodos [{r2['status']}]: {r2['body'][:200]}")

    # Test frecuentes indicador 1
    body = {
        "periodosRsh": [202602],
        "agregadoTerritorialFiltro": {
            "desagregadoTerritorialType": 4,
            "idRegion": None, "idComuna": None,
            "idComunaList": [], "idUvList": [], "idAhList": []
        },
        "indicadores": [1],
        "aperturaResultadoOption": {"aperturaType": 0, "aperturaResultadoId": None}
    }
    r3 = xhr_post(driver,
        "https://api.adis.gob.cl/estadisticasSocioeconomicas/frecuentes?blockui=true&system=false",
        token, body)
    print(f"\nFrecuentes ind=1 [{r3['status']}]: {r3['body'][:400]}")

    time.sleep(8)
finally:
    driver.quit()
