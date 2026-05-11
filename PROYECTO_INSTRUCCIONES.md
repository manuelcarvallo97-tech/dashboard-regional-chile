# Contexto del Proyecto — Dashboard Regional Chile

## Quién soy
Manuel Carvallo, asesor División de Coordinación Interministerial, Ministerio del Interior y Seguridad Pública de Chile.

## Qué es este proyecto
Sistema de monitoreo de indicadores regionales para las 16 regiones de Chile. Incluye scraping, procesamiento de datos y un dashboard HTML interactivo publicado en GitHub Pages.

**URL del dashboard:**
https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html

**Repositorio GitHub:**
https://github.com/manuelcarvallo97-tech/dashboard-regional-chile

---

## Stack técnico
- **Lenguaje:** Python 3.14
- **Base de datos:** SQLite (`bcn_indicadores.db`) — vive en local, nunca se sube a GitHub
- **Dashboard:** HTML autónomo con Chart.js, sin servidor
- **Publicación:** GitHub Pages (auto-deploy al hacer push)
- **Credenciales:** archivo `.env` local (nunca en GitHub)
  - `BDE_USER` / `BDE_PASS` — API Banco Central
  - `USER` / `PASS` — ADIS RSH (pendiente de uso)

---

## Fuentes de datos y estado actual

### 1. BCE — Banco Central de Chile ✅
- **Script:** `bce_api.py` — descarga PIB regional trimestral y anual
- **Script:** `bce_empleo.py` — descarga empleo regional mensual
- **API:** `https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx`
- **Tablas SQLite:** `registros_bce`, `bce_catalogo`, `registros_bce_empleo`
- **Datos disponibles:**
  - PIB trimestral: I.2010 → III.2025 (encadenados y corrientes base 2018)
  - Empleo mensual: 2010-03 → 2026-02 (tasa desocupación + ocupados, 16 regiones)
  - Fuerza de trabajo: calculada como Ocupados/(1-Tasa/100)
- **Series empleo:** `F049.DES.TAS.INE9.{11-26}.M` y `F049.OCU.PMT.INE9.{11-26}.M`

### 2. BCN SIIT ✅
- **Script:** `bcn_scraper.py`
- **Tabla:** `registros_bcn` — 7.770 registros, 16 regiones, 10 secciones
- **Datos:** demografía, educación, salud, vivienda, seguridad, indicadores varios

### 3. LeyStop Carabineros ✅ (parcial)
- **Script:** `leystop_scraper.py`
- **Script inteligente:** `actualizar_datos.py`
- **API:** `GET /api/estadistica/{id_semana}/REGION/{id_region}` (1-16, RM=13)
- **Tablas:** `registros_leystop`, `leystop_semanas`
- **Datos:** semanas 160-172 (semanas 1-13 de 2026), 16 regiones
- **Pendiente:** semanas 173+ (bloqueo WAF por exceso de requests — esperar y usar `actualizar_datos.py` que descarga solo lo nuevo)
- **Nota WAF:** usar cable de red (WiFi del Ministerio bloquea), pausas de 1.5s entre requests

### 4. ADIS RSH 🔄 Pendiente
- **URL:** `https://adis.gob.cl`
- **Endpoint conocido:** `POST /estadisticasSocioeconomicas/frecuentes?blockui=true&system=false`
- **Login:** `POST /authorization/login` con `{run: INT_sin_DV, password: MD5(pwd)}`
- **Problema actual:** `desagregadoTerritorialType` correcto para "Nacional por Regiones" aún no confirmado (probamos 1-5, todos dan 500)
- **Token:** JWT Bearer, guardado en sessionStorage como `ngx-webstorage|session`
- **Períodos:** `GET /base/1/periodo` → lista con `{nombrePeriodo, valorPeriodo}`
- **Tabla destino:** `registros_adis`, `adis_catalogo`

### 5. Censo 2024 INE ✅
- **Script:** `Censo/preparar_censo.py`
- **Archivo:** `censo_regiones.json`
- **Datos:** demografía, vivienda, educación, conectividad por región

---

## Dashboard — módulos actuales

El dashboard es un HTML autónomo generado por `generar_dashboard.py`.

### Módulos (nav superior):
1. **🛡 Seguridad Pública** (LeyStop)
   - Resumen por región: casos año a la fecha, variación %, tasa por 100mil, principal delito
   - Evolución temporal: por región e indicador
   - Actividad operativa: controles, fiscalizaciones, incautaciones

2. **📈 PIB Regional** (BCE)
   - Frecuencia Anual/Trimestral
   - Indicadores: corrientes base 2018, encadenados, variación %, peso %
   - Tabla Resumen: % calculado sobre PIB nacional real (subtotal + extrarregional)
   - Tablas ordenables por columna

3. **💼 Empleo** (BCE/INE)
   - Resumen comparativo: semáforo rojo >8%, ámbar >6%, verde <6%
   - Evolución por región: línea con puntos coloreados por umbral
   - Ranking regional

4. **🏘 Censo 2024** (INE)
   - Demografía, Vivienda, Educación, Conectividad y Servicios

### Pendiente de agregar:
- **Población Vulnerable** (ADIS RSH) — cuando se resuelva el `desagregadoTerritorialType`
- Semanas LeyStop 173+ cuando se levante bloqueo WAF

---

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `generar_dashboard.py` | Genera `dashboard.html` desde SQLite |
| `actualizar_datos.py` | Script inteligente: descarga solo lo nuevo de BCE + LeyStop |
| `actualizar_datos.bat` | Ejecuta `actualizar_datos.py` y hace push a GitHub |
| `actualizar_dashboard.bat` | Solo regenera HTML y hace push (sin tocar datos) |
| `bce_api.py` | Descarga PIB desde API BCE |
| `bce_empleo.py` | Descarga empleo regional desde API BCE |
| `bcn_scraper.py` | Scraping BCN SIIT |
| `limpiar_datos.py` | Limpieza y normalización datos BCE |
| `leystop_scraper.py` | Scraping LeyStop (con parámetro `--desde`) |
| `adis_scraper.py` | Scraper ADIS v4 (Selenium + XHR síncrono) — pendiente |
| `censo_regiones.json` | Datos Censo 2024 procesados |

---

## Estructura SQLite (`bcn_indicadores.db`)

```sql
registros_bcn          -- BCN SIIT, 7770 filas
registros_bce          -- BCE PIB trimestral/anual
registros_bce_empleo   -- BCE Empleo mensual regional
bce_catalogo           -- Catálogo series BCE
registros_leystop      -- LeyStop semanal por región
leystop_semanas        -- Catálogo semanas LeyStop
registros_adis         -- ADIS RSH (vacío, pendiente)
adis_catalogo          -- Catálogo indicadores ADIS
```

---

## Flujo de actualización

```
1. python actualizar_datos.py
   ├── BCE Empleo: descarga desde último período en DB +1 mes
   ├── LeyStop: descarga desde último id_semana en DB +1
   └── Si hay datos nuevos → python generar_dashboard.py

2. git add -f dashboard.html
3. git commit --allow-empty -m "Actualizacion"
4. git push origin main
→ GitHub Pages publica en ~2 minutos
```

Todo esto está automatizado en `actualizar_datos.bat` (doble clic).

---

## Notas importantes
- La red WiFi del Ministerio bloquea GitHub y LeyStop — usar cable de red
- SSL del Ministerio requiere `verify=False` en requests a LeyStop
- Git requiere `http.sslVerify false` para conectar a GitHub
- La DB nunca se sube a GitHub (está en `.gitignore`)
- Las credenciales están en `.env` local (nunca en GitHub)
