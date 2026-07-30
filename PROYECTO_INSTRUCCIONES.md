# Contexto del Proyecto — Dashboard Regional Chile

## Quién soy
Manuel Carvallo, asesor División de Coordinación Interministerial, Ministerio del Interior de Chile.

## Qué es este proyecto
Sistema de monitoreo de indicadores regionales para las 16 regiones de Chile. Dashboard HTML interactivo publicado en Vercel y GitHub Pages, con datos servidos desde Supabase en tiempo real.

**URL del dashboard (producción — usar esta):**
https://dashboard-regional-chile.vercel.app/

**Repositorio GitHub:**
https://github.com/manuelcarvallo97-tech/dashboard-regional-chile

---

## Entorno de desarrollo

- **Editor:** Visual Studio Code con Claude Code
- **Terminal de trabajo:** PowerShell o CMD dentro de VS Code
- **Carpeta local:** `C:\Users\manuel.carvallo\OneDrive - interior.gob.cl\Documentos\Scrap`
- **Python:** 3.12
- **Nota red:** usar **cable de red** en el Ministerio — WiFi bloquea GitHub, LeyStop, BCE y npm

---

## Estado actual — Fase 2 completa ✅

### Arquitectura
```
BCE API ──► actualizar_datos.py ──► SQLite (bcn_indicadores.db)
LeyStop ──►                                │
                                           ▼
                               generar_dashboard.py
                                           │
                                           ▼
                               dashboard.html (datos embebidos)
                                           │
                               git push ──► GitHub ──► Vercel
```

- **Base de datos local:** SQLite `bcn_indicadores.db` — fuente de verdad para la generación
- **Supabase:** también se sincroniza (módulos Seguridad, Empleo vía fetch), pero PIB y datos principales están embebidos en el HTML
- **Dashboard:** HTML generado por `generar_dashboard.py` con todos los datos embebidos en `const PIB`, `const DELITOS`, etc.
- **Actualización:** descargar datos → `python generar_dashboard.py` → `git add -f dashboard.html` → `git push`
- **GitHub Actions:** actualiza SQLite/Supabase automáticamente, pero NO regenera el HTML — eso se hace manualmente

### Flujo de actualización de datos PIB/datos embebidos
```bash
python actualizar_datos.py --solo-pib    # descarga BCE a SQLite
python generar_dashboard.py              # regenera dashboard.html con datos nuevos
git add -f dashboard.html
git commit -m "Actualizacion PIB YYYY"
git push origin main
```

---

## Stack técnico
- **Lenguaje:** Python 3.12
- **Base de datos:** Supabase (PostgreSQL)
- **Dashboard:** HTML autónomo con Chart.js + fetch a Supabase
- **Publicación:** Vercel (producción) + GitHub Pages (espejo)
- **Automatización:** GitHub Actions (`.github/workflows/actualizar.yml`)
- **Credenciales locales:** archivo `.env` (nunca en GitHub)

---

## Supabase

**URL:** `https://spkfoavwjadyxjlcgkhq.supabase.co`

**Anon key (solo lectura — se puede compartir):**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNwa2ZvYXZ3amFkeXhqbGNna2hxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczMjM0ODIsImV4cCI6MjA5Mjg5OTQ4Mn0.KdT1NtgJvDJmDzOUQY5kZX3BJgVQypygfA9_38nPJrM
```

**Service key:** en `.env` local y en GitHub Secrets — nunca compartir

### Tablas en Supabase

| Tabla | Descripción | Filas aprox. |
|-------|-------------|--------------|
| `registros_leystop` | Seguridad pública semanal por región | ~2.900 |
| `leystop_semanas` | Catálogo de semanas LeyStop | ~178 |
| `registros_leystop_delitos` | Delitos desagregados DMCS | ~8.736 |
| `registros_bce` | PIB regional trimestral y anual | ~15.000 |
| `registros_bce_empleo` | Empleo mensual por región | ~6.000 |
| `registros_bcn` | Indicadores BCN SIIT | ~7.770 |
| `bce_catalogo` | Catálogo de series BCE | ~500 |
| `registros_adis` | ADIS RSH — vacío, pendiente | 0 |

**RLS activado en todas las tablas** — anon key solo puede leer.

### Notas técnicas importantes sobre Supabase
- Períodos en `registros_bce` están en formato **DD-MM-YYYY** — el dashboard los normaliza con `_normalizarPeriodo()`
- `es_dmcs` en `registros_leystop_delitos` llega como **booleano** desde Supabase — el dashboard filtra con `(d.es_dmcs === 1 || d.es_dmcs === true)`
- El upsert usa `on_conflict` explícito para evitar errores 409

---

## Fuentes de datos y estado

### 1. BCE — Banco Central ✅
- PIB regional trimestral y anual (2010–2024)
- Empleo mensual 16 regiones (2010–2026-03)
- Se actualiza automáticamente vía GitHub Actions

#### Series PIB — estructura crítica

Las series del BCE tienen dos familias distintas con propósitos diferentes:

| Familia | Código | Tipo | Uso en dashboard |
|---------|--------|------|-----------------|
| `F035.PIB.FLU.R.CLP.2018.*` | Flujo/nivel | Miles de millones de pesos encadenados | **Tabla PIB anual** — `unidad_limpia = 'miles de millones de pesos encadenados'` |
| `F035.PIB.V12.R.CLP.2018.*` | Variación 12m | Porcentaje | Variación % interanual |
| Series `.A` | Anuales | — | Valores anuales |
| Series `.T` | Trimestrales | — | Valores trimestrales (Q1=enero, Q2=abril, Q3=julio, Q4=octubre) |

**Regla importante:** para actualizar el año en la tabla de PIB del dashboard, hay que bajar las series `FLU` (niveles), NO las `V12` (variación). Bajar solo `V12` llena la DB pero el dashboard no las muestra en la vista de año porque busca `unidad_limpia = 'miles de millones de pesos encadenados'`.

#### Script de actualización manual PIB
Usar `bajar_pib.py` (en la carpeta Scrap) que baja específicamente las series `F035.PIB.FLU.R.CLP.2018.*`:
```bash
python bajar_pib.py
```
Luego regenerar y publicar el dashboard (ver flujo más abajo).

#### Último período disponible (junio 2026)
- PIB trimestral FLU: `01-10-2025` (Q4 2025) — en Supabase y SQLite ✅
- PIB anual FLU: `01-01-2025` (año 2025) — en Supabase y SQLite ✅
- `bce_catalogo` tiene 3.655 series (catálogo completo BCE, no solo PIB) — no usar como fuente de series a actualizar

### 2. LeyStop — Seguridad ✅
- Semanas 160–178 en Supabase (semanas 1–19 de 2026)
- Se actualiza automáticamente vía GitHub Actions
- **Nota WAF:** usar cable de red — WiFi del Ministerio bloquea LeyStop

### 3. Delitos desagregados DMCS ✅
- 8.736 registros en Supabase (semanas 153–178)
- Semanas 14-18/2026 tienen datos parciales (LeyStop los publicó con retraso)
- Para actualizar: `python cargar_historico_delitos.py --desde ULTIMA_SEMANA --force`
- Luego sync: `python sync_delitos_supabase.py`

### 4. BCN SIIT ✅
- 7.770 registros históricos en Supabase

### 5. Censo 2024 ✅
- Archivo estático: `censo_regiones.json` en el repo
- fetch desde el browser — no está en Supabase

### 6. CASEN 2024 ✅
- Archivo estático: `casen_regiones.json` en el repo
- fetch desde el browser — no está en Supabase
- Los gráficos renderizan al hacer clic en la pestaña (comportamiento normal de Chart.js)

### 7. ADIS RSH 🔄 Pendiente
- `desagregadoTerritorialType` correcto aún no confirmado

---

## Dashboard — módulos y estado

| Módulo | Estado | Fuente |
|--------|--------|--------|
| 🛡 Seguridad Pública | ✅ Funcionando | Supabase registros_leystop |
| 🔍 DMCS | ✅ Funcionando | Supabase registros_leystop_delitos |
| 📈 PIB Regional | ✅ Funcionando | Supabase registros_bce |
| 💼 Empleo | ✅ Funcionando | Supabase registros_bce_empleo |
| 🏘 Censo 2024 | ✅ Funcionando | censo_regiones.json (estático) |
| 🏠 CASEN 2024 | ✅ Funcionando | casen_regiones.json (estático) |

---

## Archivos clave del repo

| Archivo | Descripción |
|---------|-------------|
| `dashboard.html` | Dashboard principal — fetch a Supabase + JSONs estáticos |
| `pdf_minuta.js` | Lógica generación PDF (jsPDF) |
| `actualizar_datos.py` | Descarga BCE + LeyStop → SQLite → Supabase (incremental). Flags: `--solo-pib`, `--solo-empleo`, `--solo-leystop`, `--desde YYYY-MM-DD` |
| `bajar_pib.py` | Script directo para bajar series PIB FLU (niveles) base 2018. Usar cuando `actualizar_datos.py --solo-pib` no funcione |
| `cargar_historico_delitos.py` | Descarga delitos desagregados desde LeyStop |
| `sync_delitos_supabase.py` | Sube registros_leystop_delitos a Supabase con on_conflict |
| `migrate_to_supabase.py` | Migración histórica completa SQLite → Supabase |
| `censo_regiones.json` | Datos Censo 2024 (estático, no en Supabase) |
| `casen_regiones.json` | Datos CASEN 2024 (estático, no en Supabase) |
| `requirements.txt` | Dependencias Python |
| `.github/workflows/actualizar.yml` | GitHub Action lunes y jueves 10:00 AM |
| `generar_dashboard.py` | Script original (referencia JS — NO se usa para publicar) |
| `generar_dashboard_v2.py` | Versión alternativa — tampoco se usa para publicar |
| `bcn_indicadores.db` | SQLite local (staging) — nunca se sube a GitHub |

---

## Flujo de actualización

### Automático (GitHub Actions — lunes y jueves 10:00 AM)
```
BCE API → datos nuevos → Supabase → dashboard actualizado en tiempo real
LeyStop →
```

### Manual desde laptop (con cable de red)
```bash
# Actualizar todo (BCE empleo + LeyStop)
python actualizar_datos.py

# Actualizar solo PIB con datos nuevos del BCE
python bajar_pib.py
# Luego publicar:
python generar_dashboard.py
git add -f dashboard.html
git commit --allow-empty -m "Actualizacion PIB YYYY"
git push origin main

# Actualizar delitos DMCS (cuando haya semanas nuevas)
python cargar_historico_delitos.py --desde ULTIMA_SEMANA
python sync_delitos_supabase.py
```

### Flags de actualizar_datos.py
```bash
python actualizar_datos.py                    # todo
python actualizar_datos.py --solo-pib         # solo PIB
python actualizar_datos.py --solo-empleo      # solo empleo
python actualizar_datos.py --solo-leystop     # solo LeyStop
python actualizar_datos.py --desde 2025-01-01 # forzar fecha inicio
```

---

## Cómo hacer cambios en el dashboard

### Flujo de trabajo
```
1. Trabajar en rama dev
2. Probar en Vercel preview
3. Merge a main → producción
```

### Estructura del dashboard.html
```
<head> → CSS + librerías (Chart.js, jsPDF)
<body>
  ├── Loader overlay (#app-loader)
  ├── Header + botón PDF
  ├── Nav módulos (.mod-nav)
  ├── Módulos HTML (#mod-seguridad, #mod-pib, #mod-empleo, #mod-censo, #mod-casen)
  └── <script>
        ├── Config Supabase (SUPA_URL, SUPA_KEY)
        ├── _normalizarPeriodo() ← convierte DD-MM-YYYY a YYYY-MM-DD
        ├── cargarDatos() — fetch async a Supabase + JSONs estáticos
        │     ├── registros_leystop + leystop_semanas → SEG
        │     ├── registros_leystop_delitos → DELITOS
        │     ├── registros_bce → PIB
        │     ├── registros_bce_empleo → EMP
        │     ├── censo_regiones.json → CENSO_DATA
        │     └── casen_regiones.json → CASEN
        ├── window.onload = async → await cargarDatos() → init UI
        ├── Módulo Seguridad
        ├── Módulo DMCS (filtra es_dmcs === 1 || true; selector solo semanas con datos)
        ├── Módulo PIB
        ├── Módulo Empleo
        ├── Módulo Censo (usa CENSO_DATA, no CENSO)
        └── Módulo CASEN
```

---

## Rama dev y colaboración

- **`main`** → producción (Vercel + GitHub Pages)
- **`dev`** → desarrollo (Vercel preview automático)
- Colaborador **Diego** — acceso solo lectura con anon key de Supabase

---

## Notas importantes
- Usar **cable de red** en el Ministerio — WiFi bloquea GitHub, LeyStop, BCE y npm
- SSL del Ministerio requiere `verify=False` en requests a LeyStop y BCE
- Git requiere `http.sslVerify false` para conectar a GitHub desde el Ministerio
- La DB SQLite local (`bcn_indicadores.db`) nunca se sube a GitHub
- Las credenciales están en `.env` local y en GitHub Secrets
- GitHub Actions usa DB temporal en memoria (sin SQLite local)

---

## Pendiente

- **ADIS RSH** — población vulnerable por región (endpoint pendiente)
