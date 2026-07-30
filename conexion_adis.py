import argparse
import hashlib
import json
import logging
import os
import re
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning

urllib3 = None
try:
    import urllib3 as _urllib3
    urllib3 = _urllib3
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DEFAULT_ADIS_URL = "https://adis.gob.cl"
ENV_VARS = {
    "ADIS_URL": "URL base de ADIS (default https://adis.gob.cl)",
    "ADIS_RUN": "RUN institucional para login ADIS",
    "ADIS_PASS": "Clave institucional para login ADIS",
    "ADIS_RECAPTCHA_TOKEN": "Token reCAPTCHA para login público ADIS",
}


def read_env_file():
    env = {}
    for fname in [".env", "env.local"]:
        path = Path(__file__).parent / fname
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def load_config(args):
    env = read_env_file()
    return {
        "base_url": args.base_url or env.get("ADIS_URL") or DEFAULT_ADIS_URL,
        "run": args.run or env.get("ADIS_RUN"),
        "password": args.password or env.get("ADIS_PASS"),
        "recaptcha_token": args.recaptcha_token or env.get("ADIS_RECAPTCHA_TOKEN"),
        "verify_ssl": args.secure,
        "timeout": args.timeout,
    }


class ADISClient:
    def __init__(self, base_url=None, verify_ssl=False, timeout=30):
        self.base_url = (base_url or DEFAULT_ADIS_URL).rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ADIS-Client/1.0",
        })
        self.token = None

    def _url(self, path):
        return f"{self.base_url}{path}"

    def set_token(self, token):
        self.token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    def _request(self, method, path, json_data=None, params=None, allow_text=False):
        url = self._url(path)
        log.debug("ADIS %s %s", method.upper(), url)
        try:
            response = self.session.request(
                method,
                url,
                json=json_data,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except Exception as exc:
            raise RuntimeError(f"Error conectando a ADIS: {exc}") from exc

        if not response.ok:
            raise RuntimeError(
                f"ADIS HTTP {response.status_code} {response.reason} en {url}: {response.text[:400]}"
            )

        if allow_text:
            return response.text

        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"ADIS devolvió respuesta no JSON en {url}: {exc}") from exc

    @staticmethod
    def _normalize_run(run_value):
        if run_value is None:
            return None
        run_numeric = re.sub(r"\D", "", str(run_value))
        return run_numeric

    @staticmethod
    def _md5_hash(value):
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    def login(self, run, password):
        if not run or not password:
            raise ValueError("RUN y contraseña son obligatorios para login institucional.")
        run_number = self._normalize_run(run)
        payload = {"run": int(run_number) if run_number.isdigit() else run_number, "password": self._md5_hash(password)}
        result = self._request("post", "/authorization/login", json_data=payload)
        if isinstance(result, dict) and result.get("exitoLogin") and result.get("token"):
            self.set_token(result["token"])
            return result
        raise RuntimeError(f"Login ADIS fallido: {result}")

    def login_publico(self, recaptcha_token):
        if not recaptcha_token:
            raise ValueError("Token reCAPTCHA es requerido para login público.")
        payload = {"token": recaptcha_token}
        result = self._request("post", "/authorization/login/public", json_data=payload)
        if isinstance(result, dict) and result.get("exitoLogin") and result.get("token"):
            self.set_token(result["token"])
            return result
        raise RuntimeError(f"Login público ADIS fallido: {result}")

    def refresh_token(self):
        result = self._request("post", "/authorization/token/adis/refresh", json_data=None, allow_text=False)
        if isinstance(result, dict) and result.get("token"):
            self.set_token(result["token"])
            return result
        return result

    def get_filters_persona(self):
        return self._request("get", "/getFiltrosEstadiscasSocioeconomicasPersona")

    def get_filters_hogar(self):
        return self._request("get", "/getFiltrosEstadiscasSocioeconomicasHogar")

    def query_frecuentes(self, payload):
        return self._request("post", "/estadisticasSocioeconomicas/frecuentes", json_data=payload)

    def query_personalizadas(self, payload):
        return self._request("post", "/estadisticasSocioeconomicas/personalizadas", json_data=payload)

    def query_personalizadas_beneficios(self, payload):
        return self._request("post", "/estadisticasSocioeconomicas/personalizadas/beneficios", json_data=payload)

    def get_nomina_frecuentes(self, payload):
        return self._request("post", "/estadisticasSocioeconomicas/nomina/frecuentes", json_data=payload)

    def get_nomina_persona(self, payload):
        return self._request("post", "/estadisticasSocioeconomicas/nomina/personalizadas/persona", json_data=payload)

    def ping(self):
        return self._request("get", "/", allow_text=True)


def dump_json(value, indent=2):
    output = json.dumps(value, ensure_ascii=False, indent=indent)
    try:
        print(output)
    except UnicodeEncodeError:
        print(output.encode("utf-8", errors="replace").decode("utf-8"))


def parse_payload_file(path):
    if not path:
        return None
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"No se pudo parsear JSON en {path}: {exc}") from exc


def build_query_payload(periodos_rsh=None,
                        desagregado_type=None,
                        id_region=None,
                        id_comuna=None,
                        id_comuna_list=None,
                        id_uv_list=None,
                        id_ah_list=None,
                        indicadores=None,
                        apertura_option=None):
    """Construye un body compatible con los endpoints de estadísticas.

    Los nombres de campo buscan replicar la forma que envía el cliente web:
    - `periodosRsh`: lista de periodos
    - `agregadoTerritorialFiltro`: objeto con `desagregadoTerritorialType` y ids
    - `indicadores`: lista de indicadores (estructura dependiente del catálogo)
    - `aperturaResultadoOption`: opción de apertura si aplica
    """
    payload = {
        "periodosRsh": periodos_rsh or [],
        "agregadoTerritorialFiltro": {
            "desagregadoTerritorialType": desagregado_type,
            "idRegion": int(id_region) if id_region is not None and str(id_region).isdigit() else id_region,
            "idComuna": int(id_comuna) if id_comuna is not None and str(id_comuna).isdigit() else id_comuna,
            "idComunaList": [int(x) for x in id_comuna_list] if id_comuna_list else [],
            "idUvList": [int(x) for x in id_uv_list] if id_uv_list else [],
            "idAhList": [int(x) for x in id_ah_list] if id_ah_list else [],
        },
        "indicadores": indicadores or [],
    }
    if apertura_option is not None:
        payload["aperturaResultadoOption"] = apertura_option
    return payload


def main():
    parser = argparse.ArgumentParser(description="Conexión ADIS RSH — login y consultas básicas")
    parser.add_argument("--base-url", help="Base URL de ADIS (default: https://adis.gob.cl)")
    parser.add_argument("--run", help="RUN institucional para login ADIS")
    parser.add_argument("--password", help="Clave institucional para login ADIS")
    parser.add_argument("--recaptcha-token", help="Token reCAPTCHA para login público ADIS")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout en segundos")
    parser.add_argument("--secure", action="store_true", help="Habilitar verificación SSL (por defecto está desactivada)")
    parser.add_argument("--ping", action="store_true", help="Probar conectividad al sitio ADIS")
    parser.add_argument("--login", action="store_true", help="Hacer login institucional con RUN/clave")
    parser.add_argument("--login-publico", action="store_true", help="Hacer login público usando token recaptcha")
    parser.add_argument("--refresh-token", action="store_true", help="Refrescar el token ADIS activo")
    parser.add_argument("--get-filtros-persona", action="store_true", help="Descargar filtros de persona")
    parser.add_argument("--get-filtros-hogar", action="store_true", help="Descargar filtros de hogar")
    parser.add_argument("--frecuentes", action="store_true", help="Consultar estadísticas frecuentes")
    parser.add_argument("--personalizadas", action="store_true", help="Consultar estadísticas personalizadas")
    parser.add_argument("--personalizadas-beneficios", action="store_true", help="Consultar estadísticas personalizadas de beneficios")
    parser.add_argument("--nomina-frecuentes", action="store_true", help="Descargar nómina frecuentes")
    parser.add_argument("--nomina-persona", action="store_true", help="Descargar nómina personalizadas por persona")
    parser.add_argument("--payload-file", help="JSON con el body a enviar para consultas POST")
    parser.add_argument("--build-payload", action="store_true", help="Construir y mostrar un payload de ejemplo desde argumentos")
    parser.add_argument("--periodos", help="Periodos RSH separados por comas, p.e. 202301,202302")
    parser.add_argument("--desagregado-type", help="Tipo de desagregado territorial (string/enum)")
    parser.add_argument("--region-id", help="ID de región")
    parser.add_argument("--comuna-id", help="ID de comuna")
    parser.add_argument("--comuna-list", help="Lista de IDs de comuna separados por comas")
    parser.add_argument("--uv-list", help="Lista de IDs UV separados por comas")
    parser.add_argument("--ah-list", help="Lista de IDs AH separados por comas")
    parser.add_argument("--indicadores-file", help="Archivo JSON con lista de indicadores para incluir en el payload")
    parser.add_argument("--dump-env", action="store_true", help="Mostrar variables ADIS leídas del .env")
    args = parser.parse_args()

    config = load_config(args)
    if args.dump_env:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    client = ADISClient(base_url=config["base_url"], verify_ssl=config["verify_ssl"], timeout=config["timeout"])

    if args.ping:
        result = client.ping()
        log.info("Ping ADIS exitoso")
        dump_json(result)
        return

    if args.login:
        result = client.login(config["run"], config["password"])
        log.info("Login ADIS exitoso")
        dump_json(result)

    elif args.login_publico:
        result = client.login_publico(config["recaptcha_token"])
        log.info("Login público ADIS exitoso")
        dump_json(result)

    if args.refresh_token:
        result = client.refresh_token()
        log.info("Token ADIS refrescado")
        dump_json(result)

    if args.get_filtros_persona:
        result = client.get_filters_persona()
        log.info("Filtros persona descargados")
        dump_json(result)

    if args.get_filtros_hogar:
        result = client.get_filters_hogar()
        log.info("Filtros hogar descargados")
        dump_json(result)

    payload = parse_payload_file(args.payload_file) if args.payload_file else None
    # soportes para construir payload desde argumentos
    if args.build_payload:
        periodos = [p for p in (args.periodos or "").split(",") if p]
        comuna_list = [x for x in (args.comuna_list or "").split(",") if x]
        uv_list = [x for x in (args.uv_list or "").split(",") if x]
        ah_list = [x for x in (args.ah_list or "").split(",") if x]
        indicadores = None
        if args.indicadores_file:
            indicadores = parse_payload_file(args.indicadores_file)
        built = build_query_payload(
            periodos_rsh=periodos,
            desagregado_type=args.desagregado_type,
            id_region=args.region_id,
            id_comuna=args.comuna_id,
            id_comuna_list=comuna_list,
            id_uv_list=uv_list,
            id_ah_list=ah_list,
            indicadores=indicadores,
        )
        dump_json(built)
        return
    if args.frecuentes:
        if payload is None:
            raise ValueError("--frecuentes requiere --payload-file con el body JSON.")
        result = client.query_frecuentes(payload)
        log.info("Consulta frecuentes completada")
        dump_json(result)

    if args.personalizadas:
        if payload is None:
            raise ValueError("--personalizadas requiere --payload-file con el body JSON.")
        result = client.query_personalizadas(payload)
        log.info("Consulta personalizadas completada")
        dump_json(result)

    if args.personalizadas_beneficios:
        if payload is None:
            raise ValueError("--personalizadas-beneficios requiere --payload-file con el body JSON.")
        result = client.query_personalizadas_beneficios(payload)
        log.info("Consulta personalizadas beneficios completada")
        dump_json(result)

    if args.nomina_frecuentes:
        if payload is None:
            raise ValueError("--nomina-frecuentes requiere --payload-file con el body JSON.")
        result = client.get_nomina_frecuentes(payload)
        log.info("Nómina frecuentes descargada")
        dump_json(result)

    if args.nomina_persona:
        if payload is None:
            raise ValueError("--nomina-persona requiere --payload-file con el body JSON.")
        result = client.get_nomina_persona(payload)
        log.info("Nómina persona descargada")
        dump_json(result)

    if not any([
        args.ping,
        args.login,
        args.login_publico,
        args.refresh_token,
        args.get_filtros_persona,
        args.get_filtros_hogar,
        args.frecuentes,
        args.personalizadas,
        args.personalizadas_beneficios,
        args.nomina_frecuentes,
        args.nomina_persona,
        args.dump_env,
    ]):
        parser.print_help()


if __name__ == "__main__":
    main()
