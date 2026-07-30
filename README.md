# Dashboard Regional Chile 🇨🇱

Dashboard interactivo de indicadores regionales para las 16 regiones de Chile, desarrollado para la División de Coordinación Interministerial del Ministerio del Interior y Seguridad Pública.

## 🌐 Ver el dashboard

**[👉 Abrir Dashboard](https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html)**

> Los datos se actualizan automáticamente cada lunes y jueves a las 10:00 AM (hora Chile) vía GitHub Actions.

---

## 📊 Módulos disponibles

| Módulo | Fuente | Frecuencia | Cobertura |
|--------|--------|------------|-----------|
| 🛡 Seguridad Pública | Carabineros · LeyStop | Semanal | 2026 |
| 📈 PIB Regional | Banco Central de Chile | Trimestral / Anual | 2010–2024 |
| 💼 Empleo | Banco Central de Chile / INE | Mensual | 2010–2026 |
| 🏘 Censo 2024 | INE Chile | Puntual | 2024 |
| 🏠 CASEN 2024 | MIDESO | Puntual | 2006–2024 |

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│         Lunes y jueves · 10:00 AM Chile              │
│                                                      │
│  BCE API ──► actualizar_datos.py ──► Supabase DB    │
│  LeyStop ──►                                         │
└──────────────────────────┬──────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Supabase   │  ← Fuente de verdad
                    │  PostgreSQL │
                    └──────┬──────┘
                           │ fetch()
                    ┌──────▼──────┐
                    │ dashboard   │  ← HTML estático
                    │    .html    │     en GitHub Pages
                    └─────────────┘
```

- **Base de datos:** Supabase (PostgreSQL) — datos históricos y actualizaciones incrementales
- **Dashboard:** HTML estático publicado en GitHub Pages — lee directo de Supabase en tiempo real
- **Actualización automática:** GitHub Actions corre los scrapers sin intervención manual
- **Minuta PDF:** Generada en el browser desde los datos cargados

---

## 🗂 Estructura del repositorio

```
📁 raíz
├── dashboard.html              ← Dashboard principal (GitHub Pages)
├── censo_regiones.json         ← Datos Censo 2024 (estático)
├── casen_regiones.json         ← Datos CASEN 2024 (estático)
│
├── actualizar_datos.py         ← Descarga BCE + LeyStop → sincroniza Supabase
├── migrate_to_supabase.py      ← Migración histórica completa a Supabase
├── generar_dashboard_v2.py     ← Regenera dashboard.html desde generar_dashboard.py
├── parche_pdf_dashboard.py     ← Inyecta botón de minuta PDF en el HTML
├── pdf_minuta.js               ← Lógica de generación PDF (jsPDF)
│
├── bce_api.py                  ← Descarga PIB desde API Banco Central
├── bce_empleo.py               ← Descarga empleo regional desde API BCE
├── bcn_scraper.py              ← Scraping indicadores BCN SIIT
├── leystop_scraper.py          ← Scraping seguridad desde LeyStop
├── preparar_casen.py           ← Procesa datos CASEN desde fuente
│
├── requirements.txt            ← Dependencias Python
├── vercel.json                 ← Configuración deploy Vercel
└── .github/workflows/
    └── actualizar.yml          ← GitHub Action (schedule lunes y jueves)
```

---

## 🔄 Flujo de actualización

### Automático (recomendado)
GitHub Actions corre cada lunes y jueves a las 10:00 AM sin intervención:

```
BCE API → datos nuevos → Supabase → dashboard actualizado en tiempo real
LeyStop →
```

Puedes dispararlo manualmente desde:
**[Actions → Actualizar datos → Run workflow](https://github.com/manuelcarvallo97-tech/dashboard-regional-chile/actions)**

### Manual (desde tu laptop)
```bash
python actualizar_datos.py
```
Descarga solo lo nuevo desde BCE y LeyStop, sube a Supabase. No requiere hacer push ni regenerar HTML.

---

## ⚙️ Instalación local

### Requisitos
- Python 3.10 o superior
- Conexión a internet (cable de red en el Ministerio — el WiFi bloquea GitHub y LeyStop)

```bash
pip install -r requirements.txt
```

### Credenciales (archivo `.env`)

```env
BDE_USER=tu@email.cl
BDE_PASS=tucontraseña
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...
```

> ⚠️ Nunca subas `.env` ni `bcn_indicadores.db` a GitHub (están en `.gitignore`)

---

## 🔑 Acceso a datos para colaboradores

El proyecto usa **Supabase** como base de datos central. Colaboradores externos pueden consumir los datos de solo lectura usando la `anon key`:

**URL:** `https://spkfoavwjadyxjlcgkhq.supabase.co`

**Anon key (solo lectura):**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNwa2ZvYXZ3amFkeXhqbGNna2hxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczMjM0ODIsImV4cCI6MjA5Mjg5OTQ4Mn0.KdT1NtgJvDJmDzOUQY5kZX3BJgVQypygfA9_38nPJrM
```

### Tablas disponibles

| Tabla | Descripción | Filas aprox. |
|-------|-------------|--------------|
| `registros_leystop` | Seguridad pública semanal por región | ~2.700 |
| `leystop_semanas` | Catálogo de semanas LeyStop | ~175 |
| `registros_bce` | PIB regional trimestral y anual | ~15.000 |
| `registros_bce_empleo` | Empleo mensual por región | ~6.000 |
| `registros_bcn` | Indicadores BCN SIIT | ~7.770 |
| `bce_catalogo` | Catálogo de series BCE | ~500 |

### Ejemplo de consulta (JavaScript)
```javascript
const res = await fetch(
  'https://spkfoavwjadyxjlcgkhq.supabase.co/rest/v1/registros_leystop?select=*&order=id_semana.desc&limit=100',
  { headers: { 'apikey': 'ANON_KEY', 'Authorization': 'Bearer ANON_KEY' } }
);
const data = await res.json();
```

### Ejemplo de consulta (Python)
```python
import requests

SUPA_URL = "https://spkfoavwjadyxjlcgkhq.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

r = requests.get(
    f"{SUPA_URL}/rest/v1/registros_leystop",
    headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
    params={"select": "*", "order": "id_semana.desc", "limit": "100"}
)
data = r.json()
```

---

## 🔗 Fuentes de datos

| Fuente | URL | Acceso |
|--------|-----|--------|
| Banco Central de Chile (BDE) | [si3.bcentral.cl](https://si3.bcentral.cl) | Requiere registro gratuito |
| BCN SIIT | [siit.bcn.cl](https://siit.bcn.cl) | Público |
| LeyStop Carabineros | [leystop.carabineros.cl](https://leystop.carabineros.cl) | Público |
| ADIS RSH | [adis.gob.cl](https://adis.gob.cl) | Requiere cuenta institucional |
| Censo 2024 INE | [ine.gob.cl](https://ine.gob.cl) | Público |
| CASEN 2024 | [ministeriodesarrollosocial.gob.cl](https://ministeriodesarrollosocial.gob.cl) | Público |

---

## 🔐 Conexión ADIS

Se agregó el script `conexion_adis.py` para probar la autenticación ADIS e invocar los endpoints de estadísticas socioeconómicas.

Variables de entorno opcionales en `.env`:

```env
ADIS_URL=https://adis.gob.cl
ADIS_RUN=11111111
ADIS_PASS=tuClaveADIS
ADIS_RECAPTCHA_TOKEN=token_recaptcha_si_lo_tienes
```

Ejemplo de uso:

```bash
python conexion_adis.py --login
python conexion_adis.py --get-filtros-persona
python conexion_adis.py --frecuentes --payload-file cuerpo.json
```

---

## 📋 Pendiente (Fase siguiente)

- **ADIS RSH** — Población vulnerable por región (bloqueado: `desagregadoTerritorialType` pendiente)
- **LeyStop semanas 173+** — Bloqueado por WAF (esperar y correr `actualizar_datos.py` con cable de red)

---

## 📝 Notas técnicas

- El dashboard es un **HTML estático** que hace `fetch()` a Supabase al abrirse — no requiere servidor
- Las tablas tienen **Row Level Security** activado — la anon key solo permite lectura
- Compatible con Chrome, Firefox, Edge y Safari modernos
- Optimizado para pantallas ≥ 1280px
- En la red del Ministerio usar **cable de red** (el WiFi bloquea GitHub, LeyStop y npm)

---

*Ministerio del Interior y Seguridad Pública · División de Coordinación Interministerial*
