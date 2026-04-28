# Dashboard Regional Chile 🇨🇱

Dashboard interactivo de indicadores regionales para las 16 regiones de Chile, desarrollado para la **División de Coordinación Interministerial del Ministerio del Interior y Seguridad Pública**.

## 🌐 Dashboard en producción

**[👉 https://dashboard-regional-chile.vercel.app](https://dashboard-regional-chile.vercel.app)**

> Publicado en Vercel. Se actualiza automáticamente con cada push a `main`.

---

## 📊 Módulos disponibles

| Módulo | Fuente | Frecuencia | Cobertura |
|--------|--------|------------|-----------|
| 🛡 Seguridad Pública | Carabineros · LeyStop | Semanal | 2026 |
| 📈 PIB Regional | Banco Central de Chile | Trimestral / Anual | 2010–2025 |
| 💼 Empleo | Banco Central de Chile / INE | Mensual | 2010–2026 |
| 🏘 Censo 2024 | INE Chile | Puntual | 2024 |
| 📋 CASEN | Ministerio de Desarrollo Social | Puntual | Última encuesta |

---

## 🗄 Base de datos — Supabase

Todos los datos históricos viven en **Supabase (PostgreSQL)**. El dashboard actualmente lee datos embebidos en el HTML (generado por `generar_dashboard.py`). La migración a lectura dinámica desde Supabase está en curso (Fase 2).

**Proyecto Supabase:** `spkfoavwjadyxjlcgkhq.supabase.co`
**API pública (solo lectura):** `https://spkfoavwjadyxjlcgkhq.supabase.co/rest/v1/`
**Anon key:** `sb_publishable_4oxMXd2rXRYtt4wMS_5Diw_gq1GDjCG`

### Tablas disponibles para lectura pública

| Tabla | Descripción | Filas aprox. |
|-------|-------------|-------------|
| `regiones` | Catálogo 16 regiones (cod + nombre) | 16 |
| `registros_bce` | PIB regional trimestral/anual BCE | 40.348 |
| `registros_bce_empleo` | Empleo mensual por región BCE | 6.144 |
| `bce_catalogo` | Catálogo de series BCE | 3.655 |
| `registros_leystop` | Seguridad semanal por región (LeyStop) | 256+ |
| `leystop_semanas` | Catálogo de semanas LeyStop | 175+ |
| `registros_leystop_delitos` | Delitos desagregados por semana/región | 672+ |
| `registros_bcn` | Indicadores BCN SIIT (demografía, salud, etc.) | 7.770 |
| `casen_regiones` | Datos CASEN por región | 16 |
| `adis_catalogo` | Catálogo ADIS RSH (pendiente) | — |
| `registros_adis` | Datos ADIS RSH (pendiente) | — |

### Ejemplo de consulta (fetch desde JS)

```javascript
const SUPABASE_URL = 'https://spkfoavwjadyxjlcgkhq.supabase.co'
const ANON_KEY    = 'sb_publishable_4oxMXd2rXRYtt4wMS_5Diw_gq1GDjCG'

// Últimos datos de seguridad por región
const res = await fetch(
  `${SUPABASE_URL}/rest/v1/registros_leystop?order=id_semana.desc&limit=16`,
  { headers: { apikey: ANON_KEY, Authorization: `Bearer ${ANON_KEY}` } }
)
const data = await res.json()
```

### Schema de tablas relevantes

**`registros_leystop`** — Seguridad semanal
```
id_semana       integer   — ID semana LeyStop (ej: 175)
id_region       numeric   — 1=Tarapacá ... 13=RM ... 16=Ñuble
nombre_region   text
fecha_desde_iso text      — 'YYYY-MM-DD'
fecha_hasta_iso text      — 'YYYY-MM-DD'
anno            integer
tasa_registro   numeric   — tasa por 100.000 hab
casos_anno_fecha numeric  — casos acumulados año a la fecha
var_anno_fecha  numeric   — variación % vs año anterior
mayor_registro_1..5 text  — top 5 tipos de delito
pct_1..5        numeric   — porcentaje de cada delito
```

**`registros_bce_empleo`** — Empleo mensual
```
serie_id        text      — código serie BCE
nombre_region   text
indicador       text      — 'Tasa de desocupación' | 'Ocupados'
unidad          text
periodo         text      — 'YYYY-MM'
valor           numeric
```

**`registros_bce`** — PIB regional
```
series_id       text
nombre_region   text
indicador_limpio text
unidad_limpia   text      — 'miles de millones de pesos corrientes (base 2018)'
periodo         text      — 'DD-MM-YYYY'
valor_corregido numeric
```

### Mapeo region_id → nombre

```
1=Tarapacá        2=Antofagasta      3=Atacama
4=Coquimbo        5=Valparaíso       6=O'Higgins
7=Maule           8=Biobío           9=La Araucanía
10=Los Lagos      11=Aysén           12=Magallanes
13=Metropolitana  14=Los Ríos        15=Arica y Parinacota
16=Ñuble
```

> El campo `id_region` en `registros_leystop` coincide con este mapeo.

---

## 🗂 Estructura del repositorio

```
📁 raíz
├── dashboard.html          ← Dashboard principal (servido por Vercel)
├── vercel.json             ← Configuración Vercel
├── requirements.txt        ← Dependencias Python
├── README.md               ← Este archivo
│
├── generar_dashboard.py    ← Genera dashboard.html desde Supabase/SQLite
├── actualizar_datos.py     ← Descarga BCE Empleo + LeyStop (solo lo nuevo)
├── actualizar_datos.bat    ← Ejecuta actualizar_datos.py y hace push
├── actualizar_dashboard.bat← Solo regenera HTML y hace push
│
├── bce_api.py              ← Descarga PIB desde API BCE
├── bce_empleo.py           ← Descarga empleo regional desde API BCE
├── bcn_scraper.py          ← Scraping BCN SIIT
├── leystop_scraper.py      ← Scraping LeyStop (con --desde)
├── limpiar_datos.py        ← Limpieza y normalización datos BCE
├── migrate_to_supabase.py  ← Migración histórica SQLite → Supabase
│
└── censo_regiones.json     ← Datos Censo 2024 procesados
```

---

## 🚀 Cómo actualizar los datos

### Actualización normal (recomendado)

Con cable de red (WiFi del Ministerio bloquea GitHub y LeyStop):

```bash
python actualizar_datos.py
```

O doble clic en `actualizar_datos.bat`. El script:
1. Descarga BCE Empleo desde el último período en Supabase +1 mes
2. Descarga LeyStop desde el último id_semana en Supabase +1
3. Si hay datos nuevos → regenera `dashboard.html` y hace push a GitHub
4. Vercel publica automáticamente en ~1 minuto

### Solo regenerar el HTML (sin descargar datos)

```bash
python generar_dashboard.py
git add -f dashboard.html
git commit -m "Actualización dashboard"
git push origin main
```

---

## ⚙️ Instalación local

### Requisitos
- Python 3.10+ (probado en 3.12; **evitar 3.14** por incompatibilidades de paquetes)
- Git con `http.sslVerify false` (red Ministerio)

### Dependencias

```bash
pip install pandas requests python-dotenv tqdm --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

### Variables de entorno (archivo `.env`)

Crear `.env` en la carpeta del proyecto:

```
BDE_USER=tu@email.cl              # Usuario API Banco Central
BDE_PASS=tucontraseña             # Contraseña API Banco Central
SUPABASE_URL=https://spkfoavwjadyxjlcgkhq.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>   # Solo para scripts de escritura
```

> ⚠️ **Nunca subas `.env` ni `bcn_indicadores.db` a GitHub** — están en `.gitignore`

---

## 🔗 Fuentes de datos

| Fuente | URL | Acceso |
|--------|-----|--------|
| Banco Central de Chile | [si3.bcentral.cl](https://si3.bcentral.cl) | Requiere registro gratuito |
| BCN SIIT | [siit.bcn.cl](https://siit.bcn.cl) | Público |
| LeyStop Carabineros | [leystop.carabineros.cl](https://leystop.carabineros.cl) | Público (requiere cable de red) |
| ADIS RSH | [adis.gob.cl](https://adis.gob.cl) | Requiere cuenta institucional |
| Censo 2024 INE | [ine.gob.cl](https://ine.gob.cl) | Público |

---

## 📝 Notas técnicas

- **Red Ministerio:** el WiFi bloquea GitHub y LeyStop — usar cable de red. SSL requiere `verify=False` en requests a LeyStop y `http.sslVerify false` en Git.
- **LeyStop WAF:** pausas de 1.5s entre requests para evitar bloqueos. Si hay bloqueo, esperar y usar `actualizar_datos.py` que descarga solo lo nuevo.
- **Supabase RLS:** lectura pública habilitada con anon key. Escritura solo con service_role key desde scripts locales o GitHub Actions.
- **Dashboard HTML:** actualmente embebe todos los datos como JSON. La Fase 2 migrará a lectura dinámica desde Supabase.

---

*Ministerio del Interior y Seguridad Pública · División de Coordinación Interministerial · 2026*
