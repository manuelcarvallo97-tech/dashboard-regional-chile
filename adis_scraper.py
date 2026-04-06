"""
ADIS RSH Scraper v4 - Selenium + XMLHttpRequest síncrono
"""
import sqlite3, json, time, argparse, logging, hashlib
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH  = "bcn_indicadores.db"
ENV_PATH = Path(__file__).parent / "env.local"

def leer_credenciales():
    user, pwd = "", ""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("USER="): user = line.split("=",1)[1].strip()
            elif line.startswith("PASS="): pwd  = line.split("=",1)[1].strip()
    return user, pwd

def crear_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def xhr_post(driver, url, payload):
    """POST síncrono via XMLHttpRequest desde el browser"""
    script = """
        var xhr = new XMLHttpRequest();
        xhr.open('POST', arguments[0], false);
        xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
        xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
        xhr.withCredentials = true;
        xhr.send(JSON.stringify(arguments[1]));
        return {status: xhr.status, body: xhr.responseText};
    """
    try:
        result = driver.execute_script(script, url, payload)
        if result and result["status"] == 200:
            return json.loads(result["body"])
        elif result:
            log.debug(f"XHR {result['status']}: {result['body'][:100]}")
        return {}
    except Exception as e:
        log.error(f"XHR error: {e}")
        return {}

def xhr_get(driver, url):
    """GET síncrono via XMLHttpRequest"""
    script = """
        var xhr = new XMLHttpRequest();
        xhr.open('GET', arguments[0], false);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.withCredentials = true;
        xhr.send();
        return {status: xhr.status, body: xhr.responseText};
    """
    try:
        result = driver.execute_script(script, url)
        if result and result["status"] == 200:
            return json.loads(result["body"])
        return {}
    except Exception as e:
        log.error(f"XHR GET error: {e}")
        return {}

def parsear(response: dict, id_indicador: int, periodo: int) -> list:
    registros = []
    if not response: return registros
    titulo = response.get("title", "")
    tablas = response.get("tablas", [{}])
    if not tablas: return registros
    tabla_0 = tablas[0].get("0", {})
    if not tabla_0: return registros
    data = tabla_0.get("data", [])
    col_headers = tabla_0.get("columnHeaders", [])
    nombres_col = [h.get("headerText","") for h in col_headers]
    for fila in data:
        if not fila: continue
        region = fila[0].get("formattedValue","")
        if region in ("Total",""): continue
        if len(fila) > 1:
            celda = fila[1]
            valor_str = celda.get("formattedValue","")
            try:
                valor_num = float(valor_str.replace(".","").replace(",","."))
            except:
                valor_num = None
            nombre_ind = nombres_col[1] if len(nombres_col) > 1 else titulo
            registros.append({
                "periodo": periodo, "nombre_region": region,
                "id_indicador": id_indicador, "nombre_indicador": nombre_ind,
                "valor": valor_num, "valor_texto": valor_str,
                "titulo_consulta": titulo, "cell_type": celda.get("cellType",0),
            })
    return registros

def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS registros_adis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo INTEGER, nombre_region TEXT, id_indicador INTEGER,
        nombre_indicador TEXT, valor REAL, valor_texto TEXT,
        titulo_consulta TEXT, cell_type INTEGER,
        fuente TEXT DEFAULT 'ADIS RSH',
        fecha_descarga TEXT DEFAULT (date('now')),
        UNIQUE(periodo, nombre_region, id_indicador))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS adis_catalogo (
        id_indicador INTEGER PRIMARY KEY, nombre TEXT, titulo TEXT,
        fecha_descarga TEXT DEFAULT (date('now')))""")
    conn.commit()

def guardar(conn, registros):
    n = 0
    for r in registros:
        try:
            conn.execute("""INSERT OR REPLACE INTO registros_adis
                (periodo, nombre_region, id_indicador, nombre_indicador,
                 valor, valor_texto, titulo_consulta, cell_type)
                VALUES (?,?,?,?,?,?,?,?)""",
                (r["periodo"], r["nombre_region"], r["id_indicador"],
                 r["nombre_indicador"], r["valor"], r["valor_texto"],
                 r["titulo_consulta"], r["cell_type"]))
            n += 1
        except Exception as e:
            log.warning(f"Insert: {e}")
    conn.commit()
    return n

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--todos", action="store_true")
    parser.add_argument("--periodo", type=int)
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    rut, pwd = leer_credenciales()
    if not rut:
        log.error("Sin credenciales"); return

    log.info("=== ADIS RSH Scraper v4 ===")
    driver = crear_driver()

    try:
        # Navegar a ADIS y hacer login via XHR
        driver.get("https://adis.gob.cl")
        time.sleep(3)

        run_num = int(rut[:-1])
        pwd_md5 = hashlib.md5(pwd.encode()).hexdigest()

        log.info("Haciendo login...")
        login_result = xhr_post(driver,
            "https://api.adis.gob.cl/authorization/login?blockui=true&system=false",
            {"run": run_num, "password": pwd_md5})

        if login_result.get("exitoLogin"):
            token = login_result["token"]
            # Guardar token en sessionStorage como lo hace Angular
            driver.execute_script(f"""
                const payload = JSON.parse(atob('{token}'.split('.')[1]));
                const session = {{token: '{token}', iat: payload.iat, exp: payload.exp, jti: payload.jti, data: JSON.parse(payload.sub)}};
                sessionStorage.setItem('ngx-webstorage|session', JSON.stringify(session));
            """)
            log.info("Login exitoso, sesión guardada")
        else:
            log.warning("Login automático falló — ingresa manualmente en Chrome (30s)...")
            time.sleep(30)

        # Navegar a estadísticas para activar la sesión Angular
        driver.get("https://adis.gob.cl/#/estadisticas-socioeconomicas/frecuentes")
        time.sleep(5)

        # Obtener períodos
        periodos_data = xhr_get(driver, "https://api.adis.gob.cl/base/1/periodo?blockui=true&system=false")
        if isinstance(periodos_data, list) and periodos_data:
            if isinstance(periodos_data[0], dict):
                periodos = [d["valorPeriodo"] for d in periodos_data if d.get("valorPeriodo")]
            else:
                periodos = periodos_data
            log.info(f"Períodos: {len(periodos)} disponibles ({periodos[0]}→{periodos[-1]})")
        else:
            periodos = [202602]
            log.warning("Sin períodos, usando 202602")

        if args.periodo:   periodos = [args.periodo]
        elif not args.todos: periodos = [periodos[0]]
        log.info(f"Descargando: {periodos}")

        conn = sqlite3.connect(args.db)
        init_db(conn)
        total = 0

        for periodo in periodos:
            log.info(f"\n── Período {periodo} ──")
            for ind_id in range(1, 21):
                payload = {
                    "periodosRsh": [periodo],
                    "agregadoTerritorialFiltro": {
                        "desagregadoTerritorialType": 4,
                        "idRegion": None, "idComuna": None,
                        "idComunaList": [], "idUvList": [], "idAhList": []
                    },
                    "indicadores": [ind_id],
                    "aperturaResultadoOption": {"aperturaType": 0, "aperturaResultadoId": None}
                }
                data = xhr_post(driver,
                    "https://api.adis.gob.cl/estadisticasSocioeconomicas/frecuentes?blockui=true&system=false",
                    payload)
                if data.get("tablas"):
                    registros = parsear(data, ind_id, periodo)
                    if registros:
                        n = guardar(conn, registros)
                        total += n
                        titulo = data.get("title","")
                        log.info(f"  [{ind_id}] {titulo[:65]} → {n} regiones")
                        conn.execute("INSERT OR REPLACE INTO adis_catalogo (id_indicador, nombre, titulo) VALUES (?,?,?)",
                                    (ind_id, registros[0]["nombre_indicador"], titulo))
                        conn.commit()
                time.sleep(0.2)

        conn.close()
        log.info(f"\n=== Listo: {total} registros ===")

        conn2 = sqlite3.connect(args.db)
        n = conn2.execute("SELECT COUNT(*) FROM registros_adis").fetchone()[0]
        log.info(f"Total en DB: {n} filas")
        print("\nIndicadores descargados:")
        for row in conn2.execute("SELECT id_indicador, titulo FROM adis_catalogo ORDER BY id_indicador"):
            print(f"  [{row[0]}] {row[1]}")
        conn2.close()

        log.info("Cerrando en 10s...")
        time.sleep(10)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
