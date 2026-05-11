# Contexto del Proyecto — Dashboard Regional Chile

## Quién soy
Manuel Carvallo, asesor División de Coordinación Interministerial, Ministerio del Interior de Chile.

## Qué es este proyecto
Sistema de monitoreo de indicadores regionales para las 16 regiones de Chile. Dashboard HTML interactivo publicado en GitHub Pages / Vercel, con datos servidos desde Supabase en tiempo real.

**URL del dashboard (producción):**
https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html

**Repositorio GitHub:**
https://github.com/manuelcarvallo97-tech/dashboard-regional-chile

---

## Estado actual — Fase 2 completada ✅

### Arquitectura
```
GitHub Actions (lunes y jueves 10:00 AM Chile)
  BCE API ──► actualizar_datos.py ──► Supabase (fuente de verdad)
  LeyStop ──►

Supabase ──► fetch() ──► dashboard.html (GitHub Pages)
```

- **Base de datos:** Supabase PostgreSQL (no SQLite, no archivos locales)
- **Dashboard:** HTML estático que hace fetch() a Supabase al abrirse — sin servidor, sin build
- **Actualización:** GitHub Actions automático, sin intervención manual
- **Minuta PDF:** Botón en el header, genera PDF con jsPDF desde los datos cargados

### Lo que YA NO existe
- `generar_dashboard.py` ya no se usa para publicar (solo como referencia del JS)
- No hay datos embebidos en el HTML — todo viene de Supabase o JSON estáticos
- No hay `.bat` necesarios para publicar
- No se hace `git push` del `dashboard.html` para actualizar datos

---

## Stack técnico
- **Lenguaje:** Python 3.12
- **Base de datos:** Supabase (PostgreSQL) — nunca SQLite en producción
- **Dashboard:** HTML autónomo con Chart.js + fetch a Supabase
- **Publicación:** GitHub Pages (rama `main`) + Vercel (preview de `dev`)
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
| `registros_leystop` | Seguridad pública semanal por región | ~2.700 |
| `leystop_semanas` | Catálogo de semanas LeyStop | ~175 |
| `registros_bce` | PIB regional trimestral y anual | ~15.000 |
| `registros_bce_empleo` | Empleo mensual por región | ~6.000 |
| `registros_bcn` | Indicadores BCN SIIT | ~7.770 |
| `bce_catalogo` | Catálogo de series BCE | ~500 |
| `registros_adis` | ADIS RSH — vacío, pendiente | 0 |

**RLS activado en todas las tablas** — anon key solo puede leer, nunca escribir.

---

## Fuentes de datos y estado

### 1. BCE — Banco Central ✅
- PIB regional trimestral y anual (2010–2024)
- Empleo mensual 16 regiones (2010–2026)
- Script local: `bce_empleo.py`, `bce_api.py`
- Se actualiza automáticamente vía GitHub Actions

### 2. LeyStop Carabineros ✅ (parcial)
- Semanas 160–172 disponibles en Supabase
- Semanas 173+ bloqueadas por WAF — usar cable de red en el Ministerio y correr `actualizar_datos.py`
- Se actualiza automáticamente vía GitHub Actions (cuando no hay bloqueo WAF)

### 3. BCN SIIT ✅
- 7.770 registros, 16 regiones, 10 secciones
- Datos históricos — no se actualiza frecuentemente

### 4. Censo 2024 ✅
- Archivo estático: `censo_regiones.json` en el repo
- El dashboard hace `fetch("censo_regiones.json")` — no está en Supabase

### 5. CASEN 2024 ✅
- Archivo estático: `casen_regiones.json` en el repo
- El dashboard hace `fetch("casen_regiones.json")` — no está en Supabase

### 6. ADIS RSH 🔄 Pendiente
- Endpoint conocido pero `desagregadoTerritorialType` correcto aún no confirmado
- Login: `POST /authorization/login` con `{run: INT_sin_DV, password: MD5(pwd)}`
- Token: JWT Bearer en sessionStorage como `ngx-webstorage|session`

---

## Dashboard — módulos actuales

### Navegación (nav superior):
1. **🛡 Seguridad Pública** — LeyStop
   - Resumen por región, evolución temporal, actividad operativa, DMCS
2. **📈 PIB Regional** — BCE
   - Evolución, sectores productivos, resumen nacional
   - Frecuencia anual/trimestral, tablas ordenables
3. **💼 Empleo** — BCE/INE
   - Semáforo rojo >8%, ámbar >6–8%, verde <6%
   - Evolución por región, ranking
4. **🏘 Censo 2024** — INE
   - Demografía, Vivienda, Educación, Conectividad
5. **🏠 CASEN 2024** — MIDESO
   - Pobreza, ingresos, salud, vulnerabilidad

### Funcionalidad especial:
- **Botón "Minuta Regional PDF"** en el header — genera PDF con jsPDF
  - Secciones: Geográfico, Demográfico, Población Vulnerable, Economía, Educación, Salud, Vivienda, Seguridad, Mercado Laboral
  - Funciona con los datos ya cargados desde Supabase

---

## Archivos clave del repo

| Archivo | Descripción |
|---------|-------------|
| `dashboard.html` | Dashboard principal — hace fetch a Supabase |
| `pdf_minuta.js` | Lógica generación PDF (inyectado por parche) |
| `actualizar_datos.py` | Descarga BCE + LeyStop → SQLite local → Supabase |
| `generar_dashboard_v2.py` | Regenera dashboard.html desde generar_dashboard.py base |
| `parche_pdf_dashboard.py` | Inyecta botón PDF en dashboard.html |
| `migrate_to_supabase.py` | Migración histórica completa SQLite → Supabase |
| `censo_regiones.json` | Datos Censo 2024 (estático, no en Supabase) |
| `casen_regiones.json` | Datos CASEN 2024 (estático, no en Supabase) |
| `requirements.txt` | Dependencias Python |
| `.github/workflows/actualizar.yml` | GitHub Action lunes y jueves 10:00 AM |
| `generar_dashboard.py` | Script original (referencia del JS — NO se usa para publicar) |

---

## Cómo hacer cambios en el dashboard

### Flujo de trabajo
```
1. Trabajar en rama dev
2. Probar en Vercel preview (deploy automático de dev)
3. Merge a main → GitHub Pages se actualiza
```

### Para cambios en el HTML/JS del dashboard:
El `dashboard.html` tiene toda la lógica en una sola página. La estructura es:

```
<head> → CSS + librerías (Chart.js, jsPDF)
<body>
  ├── Loader overlay (#app-loader)
  ├── Header + botón PDF
  ├── Nav módulos (.mod-nav)
  ├── Módulos HTML (#mod-seguridad, #mod-pib, #mod-empleo, #mod-censo, #mod-casen)
  └── <script>
        ├── Config Supabase (SUPA_URL, SUPA_KEY)
        ├── cargarDatos() — fetch async a Supabase + JSON estáticos
        ├── window.onload = async → await cargarDatos() → init UI
        ├── Módulo Seguridad (renderResumen, renderEvolucionSeg, renderOperativo, renderDMCS)
        ├── Módulo PIB (renderEvolucionPib, renderSectores, renderResumenPib)
        ├── Módulo Empleo (renderResumenEmp, renderEvolucionEmp, renderRankingEmp)
        ├── Módulo Censo (renderCenso, renderCensoViv, renderCensoEdu, renderCensoCon)
        └── Módulo CASEN (renderCasenPob, renderCasenIngreso, renderCasenSalud)
```

### Para regenerar el dashboard.html desde cero:
```bash
python generar_dashboard.py      # genera base
python parche_pdf_dashboard.py   # inyecta botón PDF
# Luego git add dashboard.html pdf_minuta.js && git push origin dev
```

### Para actualizar datos manualmente:
```bash
python actualizar_datos.py
# Descarga BCE + LeyStop → guarda en SQLite local → sube a Supabase
# NO requiere git push
```

---

## Rama dev y colaboración

- **`main`** → producción (GitHub Pages)
- **`dev`** → desarrollo (Vercel preview automático)
- Colaborador **Diego** tiene acceso de solo lectura vía anon key de Supabase

---

## Notas importantes
- Red WiFi del Ministerio bloquea GitHub, LeyStop y npm → **usar cable de red**
- SSL del Ministerio requiere `verify=False` en requests a LeyStop
- Git requiere `http.sslVerify false` para conectar a GitHub desde el Ministerio
- La DB SQLite local (`bcn_indicadores.db`) nunca se sube a GitHub
- Las credenciales están en `.env` local y en GitHub Secrets
- GitHub Actions crea una DB temporal en memoria cuando no hay SQLite local

---

## Pendiente

- **ADIS RSH** — Población vulnerable (bloqueado: `desagregadoTerritorialType` correcto pendiente)
- **LeyStop semanas 173+** — Bloqueado por WAF, usar cable de red
- **Módulo Población Vulnerable** en el dashboard (cuando se resuelva ADIS)
