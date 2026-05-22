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

## Estado actual — Fase 2 completa ✅

### Arquitectura
```
GitHub Actions (lunes y jueves 10:00 AM Chile)
  BCE API ──► actualizar_datos.py ──► Supabase (fuente de verdad)
  LeyStop ──►

Supabase ──► fetch() ──► dashboard.html (Vercel / GitHub Pages)
```

- **Base de datos:** Supabase PostgreSQL
- **Dashboard:** HTML estático con fetch() a Supabase — sin servidor, sin build
- **Actualización:** GitHub Actions automático lunes y jueves
- **Minuta PDF:** Botón en el header, genera PDF con jsPDF

### Lo que YA NO se usa
- `generar_dashboard.py` — no se usa para publicar (solo como referencia del JS base)
- No hay datos embebidos en el HTML
- No hay `.bat` necesarios para publicar
- No se hace `git push` del `dashboard.html` para actualizar datos

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
| `actualizar_datos.py` | Descarga BCE + LeyStop → SQLite → Supabase (incremental, on_conflict) |
| `cargar_historico_delitos.py` | Descarga delitos desagregados desde LeyStop |
| `sync_delitos_supabase.py` | Sube registros_leystop_delitos a Supabase con on_conflict |
| `migrate_to_supabase.py` | Migración histórica completa SQLite → Supabase |
| `generar_dashboard_v2.py` | Regenera dashboard.html desde generar_dashboard.py base |
| `parche_pdf_dashboard.py` | Inyecta botón PDF en dashboard.html |
| `censo_regiones.json` | Datos Censo 2024 (estático, no en Supabase) |
| `casen_regiones.json` | Datos CASEN 2024 (estático, no en Supabase) |
| `requirements.txt` | Dependencias Python |
| `.github/workflows/actualizar.yml` | GitHub Action lunes y jueves 10:00 AM |
| `generar_dashboard.py` | Script original (referencia JS — NO se usa para publicar) |

---

## Flujo de actualización

### Automático (GitHub Actions — lunes y jueves 10:00 AM)
```
BCE API → datos nuevos → Supabase → dashboard actualizado en tiempo real
LeyStop →
```

### Manual desde laptop (con cable de red)
```bash
# Actualizar BCE + LeyStop
python actualizar_datos.py

# Actualizar delitos DMCS (cuando haya semanas nuevas)
python cargar_historico_delitos.py --desde ULTIMA_SEMANA
python sync_delitos_supabase.py
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
- Usar **cable de red** en el Ministerio — WiFi bloquea GitHub, LeyStop y npm
- SSL del Ministerio requiere `verify=False` en requests a LeyStop
- Git requiere `http.sslVerify false` para conectar a GitHub desde el Ministerio
- La DB SQLite local (`bcn_indicadores.db`) nunca se sube a GitHub
- Las credenciales están en `.env` local y en GitHub Secrets
- GitHub Actions usa DB temporal en memoria (sin SQLite local)

---

## Pendiente

- **ADIS RSH** — población vulnerable por región (endpoint pendiente)
- **Limpieza repo** — eliminar archivos temporales: `d.id_semana`, `dashboard_actual.html`, `sync_faltantes.py`, `region_arica_y_parinacota.json`, `region_los_lagos.json`
