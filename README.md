# Dashboard Regional Chile 🇨🇱

Dashboard interactivo de indicadores regionales para las 16 regiones de Chile, desarrollado para la División de Coordinación Interministerial del Ministerio del Interior y Seguridad Pública.

## 🌐 Ver el dashboard

**[👉 Abrir Dashboard](https://manuelcarvallo97-tech.github.io/dashboard-regional-chile/dashboard.html)**

> `main` → producción (GitHub Pages) · `dev` → desarrollo activo

---

## 📊 Módulos disponibles

| Módulo | Fuente | Frecuencia | Cobertura | Estado |
|--------|--------|------------|-----------|--------|
| 🛡 Seguridad Pública | Carabineros · LeyStop | Semanal | 2026 | ✅ Activo |
| 📈 PIB Regional | Banco Central de Chile | Trimestral / Anual | 2010–2025 | ✅ Activo |
| 💼 Empleo | Banco Central de Chile / INE | Mensual | 2010–2026 | ✅ Activo |
| 🏘 Censo 2024 | INE Chile | Puntual | 2024 | ✅ Activo |
| 🏠 CASEN 2024 | MIDESO | Bienal | 2024 | ✅ Activo |

### 🛡 Seguridad Pública — pestañas

| Pestaña | Descripción |
|---------|-------------|
| Resumen por región | Casos año a la fecha, variación %, tasa por 100 mil hab. Filtro por semana y región. |
| Evolución temporal | Serie histórica por región e indicador |
| Actividad operativa | Controles, fiscalizaciones, incautaciones por región |
| 🔴 DMCS | Delitos de Mayor Connotación Social — valores absolutos, comparación año anterior, evolución semanal con línea punteada año anterior |

---

## 🗂 Archivos clave

```
📁 raíz del repositorio
├── dashboard.html                  ← Dashboard publicado en GitHub Pages
├── README.md                       ← Este archivo
├── generar_dashboard.py            ← Genera dashboard.html desde SQLite ⭐
├── actualizar_datos.py             ← Descarga incremental BCE + LeyStop
├── cargar_historico_delitos.py     ← Carga inicial tabla DMCS (correr 1 vez)
├── parche_pdf_dashboard.py         ← Agrega botón Minuta PDF al dashboard
├── actualizar_datos.bat            ← ⭐ Script principal de actualización
├── desarrollar.bat                 ← Regenera HTML y sube a rama dev
├── bce_api.py                      ← Descarga PIB desde API BCE
├── bce_empleo.py                   ← Descarga empleo regional desde API BCE
├── bcn_scraper.py                  ← Scraping BCN SIIT
├── limpiar_datos.py                ← Limpieza y normalización datos BCE
├── leystop_scraper.py              ← Scraping LeyStop histórico
├── censo_regiones.json             ← Datos Censo 2024 procesados
└── casen_regiones.json             ← Datos CASEN 2024 procesados
```

> `bcn_indicadores.db`, `env.local`, `*.db` → en `.gitignore`, nunca se suben

---

## 🗄 Estructura SQLite (`bcn_indicadores.db`)

| Tabla | Descripción | Filas aprox. |
|-------|-------------|-------------|
| `registros_leystop` | LeyStop — resumen semanal por región (top-5 delitos) | ~2.700 |
| `registros_leystop_delitos` | LeyStop — 21 tipos de delito × semana × región | ~50.000 |
| `leystop_semanas` | Catálogo de semanas LeyStop | ~175 |
| `registros_bce` | BCE — PIB trimestral/anual por región | ~5.000 |
| `registros_bce_empleo` | BCE — Empleo mensual por región | ~4.000 |
| `registros_bcn` | BCN SIIT — indicadores varios | ~7.700 |
| `bce_catalogo` | Catálogo de series BCE | — |
| `registros_adis` | ADIS RSH — pendiente integración | vacía |

---

## 🚀 Flujo de trabajo

### Actualización semanal de datos (producción)

```
Doble clic en actualizar_datos.bat
```

Hace todo: descarga BCE + LeyStop → genera HTML → aplica parche PDF → sube a `main` → publica en GitHub Pages.

**Requisitos:**
- Cable de red (el WiFi del Ministerio bloquea GitHub y LeyStop)
- `git config http.sslVerify false` configurado al menos una vez

### Desarrollo de mejoras al dashboard

```
Doble clic en desarrollar.bat
```

Regenera el HTML con los últimos cambios en `generar_dashboard.py` y sube a la rama `dev` (sin tocar producción).

Cuando el cambio esté aprobado, pasar a producción:

```bash
git checkout main
git merge dev
git push origin main
git checkout dev
```

### Carga histórica de delitos DMCS (solo una vez)

```bash
python cargar_historico_delitos.py
```

Descarga el array completo de 21 tipos de delito para todas las semanas disponibles en la DB. Tarda ~20 minutos. Es inteligente: si se interrumpe y se vuelve a correr, salta lo ya descargado.

---

## ⚙️ Instalación desde cero

### Requisitos

```bash
pip install pandas requests python-dotenv
```

### Credenciales (`env.local`)

```
BDE_USER=tu@email.cl
BDE_PASS=tucontraseña
```

### Primera ejecución completa

```bash
python bce_api.py                    # PIB regional
python bce_empleo.py                 # Empleo regional
python bcn_scraper.py                # Indicadores BCN
python limpiar_datos.py              # Normalización BCE
python leystop_scraper.py            # Seguridad histórico
python cargar_historico_delitos.py   # Delitos desagregados
python generar_dashboard.py          # Generar HTML
```

---

## 🔗 Fuentes de datos

| Fuente | URL | Acceso |
|--------|-----|--------|
| Banco Central de Chile | [si3.bcentral.cl](https://si3.bcentral.cl) | Registro gratuito |
| BCN SIIT | [siit.bcn.cl](https://siit.bcn.cl) | Público |
| LeyStop Carabineros | [leystop.carabineros.cl](https://leystop.carabineros.cl) | Público |
| Censo 2024 INE | [ine.gob.cl](https://ine.gob.cl) | Público |
| CASEN 2024 MIDESO | [observatorio.ministeriodesarrollosocial.gob.cl](https://observatorio.ministeriodesarrollosocial.gob.cl) | Público |
| ADIS RSH | [adis.gob.cl](https://adis.gob.cl) | Cuenta institucional — pendiente |

---

## 📝 Notas técnicas

- El dashboard es un **HTML autónomo** — todos los datos están embebidos al momento de generar. No requiere servidor ni conexión para visualizarse.
- Compatible con Chrome, Firefox, Edge y Safari modernos.
- Optimizado para pantallas ≥ 1280px.
- SSL del Ministerio requiere `verify=False` en requests a LeyStop y `git config http.sslVerify false` para GitHub.

---

## 📋 Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | Ene 2026 | Dashboard inicial: PIB, Empleo, Censo, Seguridad básica |
| 1.1 | Feb 2026 | Módulo CASEN 2024 |
| 1.2 | Abr 2026 | Pestaña DMCS con datos reales de LeyStop Registros |
| 1.2 | Abr 2026 | Filtro de región en Resumen de Seguridad |
| 1.2 | Abr 2026 | Comparación año anterior en evolución DMCS |
| 1.2 | Abr 2026 | Rama `dev` / `main` para desarrollo vs producción |
| 1.2 | Apr 2026 | Se refactorizó completamente el módulo PIB Regional del dashboard para trabajar exclusivamente en términos reales: se corrigió un bug que mezclaba series anuales y trimestrales causando valores inflados en el primer trimestre de cada año, se eliminaron los indicadores en pesos corrientes reemplazándolos por volumen encadenado a precios del año anterior en toda la cadena de cálculo (Python y JavaScript), y se agregaron dos nuevas métricas a las tablas de Sectores productivos y Resumen nacional: la variación interanual real por cada período del rango seleccionado (vs mismo trimestre del año anterior en frecuencia trimestral) y el CAGR calculado dinámicamente según los filtros de año definidos por el usuario. |
| 1.2 | Apr 2026 | Toggle var% PIB + fix regiones vacias |
| 1.2 | Apr 2026 | Toggle var% PIB + fix regiones vacias |
| 1.2 | Apr 2026 | arreglo de los rios |
| 1.2 | Apr 2026 | +checkbox |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | fix PIB toggle var CAGR |
| 1.2 | Apr 2026 | ajustes en pestaña Censo |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | orden de regiones |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | arreglo final regiones solo para censo, otras con error |
| 1.2 | Apr 2026 | ultimo arreglo |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | modificaciones CENSO |
| 1.2 | Apr 2026 | arreglo dashboard |
| 1.2 | Apr 2026 | arreglos finales censo |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | Actualizacion dashboard |
| 1.2 | Apr 2026 | fix censo |
| 1.2 | Apr 2026 | fix censo |
| 1.2 | Apr 2026 | arreglos empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |
| 1.2 | Apr 2026 | fix empleo |

---

*Ministerio del Interior y Seguridad Pública · División de Coordinación Interministerial*
