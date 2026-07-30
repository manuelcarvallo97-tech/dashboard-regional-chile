# Replicar el Dashboard Regional — descripción del panel + instrucciones para Claude Code

> Fuente analizada: `generar_dashboard.py` (3.523 líneas) y `dashboard.html` (~4,5 MB) del repo
> `dashboard-regional-chile`. Sitio en vivo: https://dashboard-regional-chile.vercel.app/

---

## PARTE 1 — Cómo está compuesto el panel (descripción exacta)

### 1.1 Arquitectura general `[Seguro]`

No es una app con backend en vivo. Es un **generador Python que produce un HTML estático autocontenido**:

```
bcn_indicadores.db (SQLite)  ─┐
censo_regiones.json          ─┼─►  generar_dashboard.py  ─►  dashboard.html
casen_regiones.json          ─┘        (consulta + arma)     (datos horneados
                                                              como constantes JS)
```

- `generar_dashboard.py` corre queries SQL (`registros_leystop`, `leystop_semanas`,
  `registros_bce`, `registros_bcn`) y lee los dos JSON.
- Convierte todo a JSON con `json.dumps(...)` y lo **incrusta como constantes JavaScript**
  dentro del HTML: `const SEG = {...}`, `const DELITOS = {...}`, `const PIB = {...}`,
  `const EMP = {...}`, `const CENSO = {...}`, `const CASEN = {...}`.
- El `dashboard.html` resultante **no consulta nada al abrirse**: todos los datos ya
  vienen dentro. Se publica en Vercel/GitHub Pages como archivo estático.
- (El README menciona un flujo Supabase en vivo, pero el generador que compartiste
  hornea los datos. Es un HTML estático, no un cliente que hace `fetch` a Supabase.)

### 1.2 Librerías `[Seguro]`

- **Chart.js 4.4.0** (CDN jsDelivr) — único motor de gráficos.
- **chartjs-plugin-datalabels 2.2.0** — etiquetas de valor sobre barras/donas.
- Nada de framework (sin React/Vue). CSS puro embebido en `<style>`. Vanilla JS.

### 1.3 Estructura de navegación — 6 módulos de nivel superior `[Seguro]`

Barra de módulos (`.mod-nav`, función JS `setModulo`). Cada módulo tiene un color de acento:

| Módulo | Color acento | Sub-pestañas |
|---|---|---|
| 📋 **Resumen** (ejecutivo) | mixto | *(sin sub-pestañas; consolida todo por región)* |
| 🛡 **Seguridad Pública** | verde `#16a34a` | Resumen por región · Evolución temporal · Actividad operativa · 🔴 DMCS |
| 📈 **PIB Regional** | azul `#2563eb` | Evolución · Sectores · Resumen nacional |
| 🏘 **Censo 2024** | morado `#7c3aed` | Demografía · Vivienda · Educación · Conectividad y Servicios |
| 💼 **Empleo** | verde `#059669` | Resumen · Evolución · Ranking |
| 🏠 **CASEN 2024** | rojo `#e11d48` | Pobreza · Pobreza severa · Multidimensional · Ingresos · Salud |

Patrón de interacción: `setModulo()` muestra/oculta `.modulo`; cada módulo tiene sub-pestañas
(`setTabSeg`, `setTabPib`, `setTabCenso`, `setTabEmp`, `setTabCasen`) que muestran/ocultan
`.section`. Todo con `display:none/block`, sin routing.

### 1.4 Composición de cada módulo (qué se muestra y cómo)

**📋 Resumen ejecutivo** — un selector de Región arriba (Nacional o una de las 16 regiones).
Muestra tarjetas consolidadas: Seguridad (KPIs LeyStop + Top-3 delitos + KPIs DMCS + barra
horizontal DMCS por tipo + dona DMCS), PIB (línea de evolución + KPIs per cápita/total/var/%
nacional + tabla Top-5 sectores), Empleo (KPIs tasa/trim. móvil/fuerza de trabajo + línea
tasa simple vs. trimestre móvil) y Censo (KPIs demográficos con ranking vs. nacional).

**🛡 Seguridad** — Resumen por región (filtros Semana + Región → grid de KPIs, gráfico de
controles y de incautaciones, tabla ordenable). Evolución temporal (líneas). Actividad
operativa (controles/fiscalizaciones/incautaciones). DMCS: KPIs + barra por región + dona de
distribución + tabla + evolución con selector de métrica y comparación.

**📈 PIB** — barra de Región. Evolución (línea con frecuencia anual/trimestral + rango de
años + KPIs de variación). Sectores (tabla por sector con var % y opción de mostrar variación).
Resumen nacional (tabla agregada).

**🏘 Censo** — Demografía (KPIs + estructura de edad + composición + tabla, con
filtros región/área/sexo y aviso "sin dato por sexo"). Vivienda (tipo de vivienda + tenencia).
Educación (nivel CINE + asistencia). Conectividad y Servicios (servicios básicos + brecha
digital + cocina + calefacción).

**💼 Empleo** — Resumen (KPIs + gráfico + tabla por región). Evolución (4 gráficos de líneas:
tasa, ocupados, fuerza de trabajo, desocupados). Ranking (barras de mayor/menor tasa +
desocupación + tabla). Distintivo: calcula **tasa de trimestre móvil** además de tasa simple.

**🏠 CASEN** — Pobreza (KPIs + evolución + índice FGT + tabla). Pobreza severa (KPIs + dona +
composición). Multidimensional (KPIs + carencias + dimensiones). Ingresos (por tipo + evolución
+ comparación). Salud (previsión + FONASA + problemas + GES).

### 1.5 Tipos de visualización `[Seguro]`

- **Gráficos (Chart.js):** líneas (evolución temporal), barras verticales y **barras
  horizontales** (`indexAxis:'y'`, para rankings/DMCS por tipo), y **doughnut/dona**
  (distribuciones y participación %). Con datalabels encima.
- **KPIs:** tarjetas `.kpi` con clase de color (`azul/verde/rojo/amber`) → borde izquierdo de
  color. Estructura: etiqueta (mayúsculas) + valor grande + subtítulo.
- **Tablas** (`table.dt`): encabezado oscuro `#1a1a2e`, **columnas ordenables al click**
  (▲/▼), filas especiales (`total`, `nacional-row`, `extra-row`, `censo-nac-row`), hover
  destacado, `overflow-x` responsivo, y botón **descargar CSV** por tabla.
- **Filtros:** selects estilizados (`.filtros`, `.fg`) para semana/región/año/frecuencia/métrica.

### 1.6 Identidad visual `[Seguro]`

Fondo `#f0f2f5`; header oscuro `#1a1a2e` sticky; tipografía system-ui; tarjetas blancas
`border-radius:12px` con sombra suave; acentos de color por módulo; formato de números
`es-CL` (miles con punto, decimales con coma); porcentajes y variaciones con verde (pos) /
rojo (neg).

### 1.7 Formateadores y utilidades JS reutilizables `[Seguro]`

`num()`, `fmtCambio()`, `fmtN/fmtP/fmtD()`, `fmtEmpNum/fmtEmpPer/fmtEmpMiles/fmtEmpVar()`,
`destroyChart()` (evita fugas de memoria de Chart.js al re-render), `sortTable`, descarga CSV.

---

## PARTE 2 — Instrucciones para Claude Code (replicar en el otro panel)

> ⚠️ **Lo que realmente importa no es copiar el HTML — es mapear los datos.** Copia estas
> instrucciones y pégaselas a Claude Code en la carpeta del nuevo panel.

### Prompt sugerido para Claude Code

```
Contexto: tengo un dashboard existente (generar_dashboard.py + dashboard.html) que genera un
HTML estático autocontenido con Chart.js. Quiero un panel NUEVO con EXACTAMENTE la misma
composición visual, estructura de navegación, tipos de gráficos, estilo de tablas y KPIs, pero
con MIS datos/indicadores.

Objetivo: reutilizar íntegro el sistema de diseño y el patrón de generación del dashboard
original, cambiando solo la capa de datos y las etiquetas.

Tareas, en orden:

1. LEE Y DOCUMENTA el original primero. Abre generar_dashboard.py e inventaria:
   - Las constantes JS que hornea (SEG, DELITOS, PIB, EMP, CENSO, CASEN) y el ESQUEMA EXACTO
     de cada objeto (qué claves, qué arrays, qué tipos).
   - Las queries SQL (tablas registros_leystop, leystop_semanas, registros_bce, registros_bcn)
     y los JSON (censo_regiones.json, casen_regiones.json) que las alimentan.
   - Todo el bloque <style> (cópialo tal cual: es el sistema de diseño).
   - Las funciones JS núcleo: setModulo, setTab*, destroyChart, num, fmtCambio, sortTable,
     descarga CSV, y los patrones new Chart({type:'line'|'bar'|'doughnut'}).
   Entrégame ese inventario como DATA_CONTRACT.md antes de escribir código.

2. MAPEA MIS DATOS al mismo contrato. Con MI fuente de datos [describe aquí: base, tablas,
   API o archivos], define para cada módulo del nuevo panel:
   - qué constante JS lo alimenta y con qué forma exacta (misma estructura que el original),
   - qué query o transformación produce esa constante.
   Si un módulo del original no aplica a mi caso, propónme con qué lo reemplazas (mismo layout,
   otro indicador). NO inventes datos: si falta una fuente, márcalo como TODO y déjalo vacío
   con mensaje "Sin datos disponibles".

3. GENERA generar_dashboard.py del nuevo panel reutilizando:
   - El MISMO <style> completo (idéntico look).
   - La MISMA barra de módulos .mod-nav y el MISMO patrón setModulo/setTab*.
   - Los MISMOS componentes: .kpi (azul/verde/rojo/amber), table.dt ordenable con descarga CSV,
     y las mismas configuraciones de Chart.js (colores, datalabels, tooltips es-CL, destroyChart
     antes de cada re-render).
   - Formato numérico es-CL (miles con punto, decimales con coma; verde=positivo, rojo=negativo).

4. VERIFICACIÓN (obligatoria antes de darme por listo):
   - Genera el HTML y ábrelo: confirma que cada módulo y sub-pestaña cambia sin errores en
     consola (F12 → Console limpia).
   - Verifica que cada gráfico renderiza con datos reales y que las tablas ordenan y exportan CSV.
   - Compárame lado a lado (captura o checklist) la navegación del nuevo panel vs. el original:
     mismos módulos, mismas sub-pestañas, mismos tipos de gráfico por sección.
   - Confirma que NO quedaron constantes vacías silenciosas (toda sección sin datos debe mostrar
     el mensaje "Sin datos disponibles", no un gráfico en blanco).

Reglas duras:
- Un solo archivo HTML autocontenido de salida (datos horneados, sin fetch en runtime), igual
  que el original.
- No cambies el sistema de diseño (colores, tipografía, radios, sombras, header sticky).
- Mantén los mismos formateadores y el mismo comportamiento de tablas/KPIs/charts.
- Si mi esquema de datos no calza con el contrato, dímelo y propón el ajuste mínimo — no fuerces.
```

### Lo que Claude Code necesita de ti para no fallar

1. **La fuente de datos del nuevo panel** (base + tablas + esquema, o los archivos). Sin esto,
   solo puede clonar la cáscara visual.
2. **El mapeo módulo→indicador**: qué mostrará cada uno de los 6 módulos (o cuáles quitas/cambias).
3. Acceso a la carpeta con `generar_dashboard.py`, `censo_regiones.json`, `casen_regiones.json`
   y, si es posible, `bcn_indicadores.db` como referencia del contrato de datos.

### Ruta rápida alternativa (si el nuevo panel usa los MISMOS datos, otro recorte)

Si "el otro panel" es el mismo dataset con distinto foco (p. ej. otra agrupación de regiones o
un subconjunto de indicadores), Claude Code puede **partir del `dashboard.html` existente**,
duplicar el bloque `<style>` y las funciones núcleo, y solo reescribir las secciones de módulos
y las queries — es cuestión de horas, no de reconstruir desde cero.

---

## PARTE 3 — TU CASO REAL: montar tu dashboard como una pestaña dentro del de tu colega

**Situación:** migraste tus datos a SU Supabase (ahora comparten base) y quieres que TU dashboard
aparezca como una pestaña dentro del panel de él.

### La verdad incómoda (léela antes de empezar)

1. **El riesgo son las colisiones, no los datos.** Tu HTML y el de él usan casi seguro los mismos
   nombres genéricos: funciones (`setModulo`, `setTab*`, `charts{}`, `num()`, `destroyChart`) y
   clases CSS (`.kpi`, `.card`, `table.dt`, `.mod-btn`, `.modulo`). Fusionar los dos archivos tal
   cual = las funciones y estilos de uno pisan al otro y **ambos paneles se rompen**.
2. **Compartir Supabase no conecta nada solo.** Tu `generar_dashboard.py` hornea desde SQLite
   (`bcn_indicadores.db`), no desde Supabase. Que tus datos vivan en su Supabase no hace que su
   dashboard los muestre: falta o repuntar el generador a Supabase, o dejar el tuyo como bloque
   embebido con sus datos horneados.

### Dos rutas — elige según cuánto quieras arriesgar

**RUTA A — iframe (recomendada, bajo riesgo).** Tu `dashboard.html` completo se embebe como
`<iframe>` dentro de una pestaña nueva del panel de él. **Cero colisiones** de CSS/JS porque cada
uno vive en su propio documento. Tú sigues generando tu HTML como hoy. Es lo más rápido y seguro.
Contras: dos scrollbars posibles y una costura visual leve entre ambos estilos.

**RUTA B — fusión nativa (más limpia, más trabajo y riesgo).** Se pliegan tus módulos dentro del
HTML de él, **prefijando todos los IDs, clases y nombres de función** (p. ej. `mnl_setModulo`,
`.mnl-kpi`, `mnlCharts`) para que no choquen, y se unifica la carga de datos. Queda un solo panel
sin costuras, pero exige tocar mucho y probar a fondo.

### Antes de tocar nada, responde/averigua

- ¿El dashboard de tu colega **lee en vivo de Supabase** (`createClient` + `fetch`) o también es
  un **HTML estático horneado**? Esto decide si tu pestaña debe leer en vivo o venir pre-horneada.
- En el Supabase compartido, ¿tus tablas quedaron con **nombres propios** o pudieron **colisionar**
  con las de él? (Confirma que la migración las dejó con prefijo o esquema separado.)

### Prompt para Claude Code — RUTA A (iframe)

```
Tengo dos dashboards HTML estáticos con Chart.js. Quiero AÑADIR el mío como una pestaña nueva
dentro del panel de un colega, con MÍNIMO riesgo de romper el suyo.

1. Abre AMBOS archivos: el dashboard del colega [ruta] y el mío (dashboard.html generado por
   generar_dashboard.py). Identifica en el del colega dónde está su barra de pestañas/navegación
   de nivel superior y su patrón de mostrar/ocultar secciones.
2. Añade una pestaña nueva (ej. "Panel Regional (Manuel)") a SU navegación, siguiendo su mismo
   markup y estilo de botón, que muestre un contenedor con un <iframe> apuntando a mi dashboard.html.
3. NO fusiones CSS ni JS de los dos: el iframe aísla todo. Solo agrega el botón, el contenedor y
   el handler de su navegación para mostrarlo/ocultarlo como sus otras pestañas.
4. Ajusta el iframe: width:100%, height suficiente (o auto-resize por postMessage si su dashboard
   lo permite), sin borde, para que se vea integrado.
5. VERIFICA: abre el resultado, comprueba que TODAS las pestañas de él siguen funcionando sin
   errores en consola, que mi panel carga completo dentro del iframe, y que no hay dobles
   scrollbars molestos. Reporta consola limpia (F12).

Regla dura: no debe romperse ninguna función ni estilo existente del dashboard del colega.
```

### Prompt para Claude Code — RUTA B (fusión nativa, si quieres un solo panel sin iframe)

```
Quiero integrar mis módulos dentro del dashboard HTML de un colega como pestañas nativas, sin
iframe, evitando colisiones de CSS/JS.

1. Abre ambos archivos e inventaria TODOS los nombres que pueden chocar: funciones globales
   (setModulo, setTab*, num, fmt*, destroyChart, charts), variables globales (SEG, PIB, EMP,
   CENSO, CASEN, DELITOS, charts) y clases/IDs CSS (.kpi, .card, table.dt, .mod-btn, .modulo,
   .section, .tabs). Entrégame la lista de colisiones ANTES de tocar código.
2. Prefija TODO lo mío con un namespace (ej. "mnl"): funciones -> mnlSetModulo; variables ->
   MNL_SEG; clases -> .mnl-kpi; IDs -> #mnl-... Reescribe mi <style> y mi JS con ese prefijo.
3. Inserta mis módulos como pestañas nuevas dentro de SU barra de navegación, reutilizando su
   mecanismo de mostrar/ocultar. Copia mi <style> prefijado y mi JS prefijado sin alterar los suyos.
4. Unifica los datos: como mis datos ya están en el Supabase compartido, decide conmigo si mi
   pestaña (a) se sigue horneando desde generar_dashboard.py (regenerando el bloque de datos), o
   (b) se convierte a fetch en vivo de Supabase igual que el resto de su panel. NO inventes datos.
5. VERIFICA a fondo: consola limpia, TODAS las pestañas (suyas y mías) cambian bien, cada gráfico
   y tabla renderiza, y no hay estilos filtrados de un módulo a otro. Dame un checklist final.

Regla dura: ni una sola función, variable o clase mía sin prefijar. Cero regresiones en su panel.
```

### Mi recomendación `[Probable]`

Empieza por la **Ruta A (iframe)**. Te da el resultado visible de inmediato sin poner en riesgo el
panel de tu colega, y si más adelante quieres la integración fina, migras a la Ruta B con calma.
El riesgo de la Ruta B hecha de una sola vez es pasar horas cazando por qué un estilo o una función
compartida rompió una pestaña que antes andaba.
