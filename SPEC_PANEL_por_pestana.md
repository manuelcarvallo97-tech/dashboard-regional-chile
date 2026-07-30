# Especificación del panel, pestaña por pestaña — para Claude Code

> Objetivo: que Claude Code complete/corrija tu pestaña replicada para que quede **idéntica** a
> tu dashboard original (`generar_dashboard.py` → `dashboard.html`), con los MISMOS filtros,
> KPIs, gráficos, tablas y **cálculos**. Extraído directo del código, no de memoria.

---

## ⚠️ REGLA DE ORO — léela antes que nada

**La especificación más fiel de tus cálculos ES `generar_dashboard.py`.** No dejes que Claude
Code (ni nadie) reescriba las fórmulas "a mano": se pierde justo el trabajo que te costó dejar
bien. La instrucción correcta es:

> **Dale a Claude Code el archivo `generar_dashboard.py` como fuente de verdad y pídele que
> PORTE las funciones de render y las configs de Chart.js VERBATIM (copiadas), ajustando solo
> (a) el namespacing para no chocar con el panel del colega y (b) el origen de datos (Supabase
> en vez de SQLite). Que NO reinvente ninguna fórmula.**

Este documento es el mapa para que sepa QUÉ debe contener cada pestaña y detecte qué le falta.
Para el "cómo" exacto de cada número, la referencia es la función que se indica en cada sección.

---

## 0. Contexto técnico que Claude Code debe respetar

- **Motor de gráficos:** Chart.js 4.4.0 + plugin `chartjs-plugin-datalabels` 2.2.0 (CDN jsDelivr).
- **Formato numérico es-CL:** miles con punto, decimales con coma (`toLocaleString('es-CL')`).
  Positivo = verde (`.pos`), negativo = rojo (`.neg`).
- **Constantes de datos horneadas** (mismas formas que hoy): `SEG`, `DELITOS`, `PIB`, `EMP`,
  `CENSO`, `CASEN`. Origen actual: SQLite `bcn_indicadores.db` + `censo_regiones.json` +
  `casen_regiones.json`. Como tus datos ya están en el Supabase compartido, hay que decidir si
  la pestaña se sigue horneando desde el generador o se lee en vivo de Supabase (ver nota final).
- **Helpers compartidos a reutilizar tal cual:** `destroyChart` (destruye el chart antes de
  re-render, evita fugas), `num`, `pct`, `fmtCambio`, `clsCambio`, `sortDT` (ordenamiento de
  tablas al click, respetando filas especiales), `makeBarSeg`, `makeBarPib`, `makeLineMulti`,
  `makePie`, `makeHBar`, `downloadChart`, `downloadTable`.
- **Patrón de navegación:** `setModulo(id, btn)` (módulos) → dispara el render del módulo;
  `setTabSeg/Pib/Censo/Emp/Casen(tab, btn)` (sub-pestañas) → dispara el render de la sección.
- **Interacción tablas:** cada `<th>` (menos la 1ª columna) llama `sortDT('idTabla', colIndex)`.
  Filas especiales que NO se ordenan: `.nacional-row`, `.extra-row`, `.censo-nac-row`.

---

## 1. MÓDULO 📋 RESUMEN EJECUTIVO
**Función:** `renderResumenEjecutivo` · selects: `poblarSelectsResumenEjecutivo`
**Filtro:** Región (Nacional o 1 de 16) + Año desde/hasta (PIB) + Desde/Hasta (Empleo).

Consolida 4 bloques en tarjetas. Cada bloque replica lo esencial de su módulo:

- **🛡 Seguridad:** KPIs LeyStop [Delitos año a la fecha · Variación vs año ant. · Tasa/100k ·
  Delito más común] + Top-3 delitos + KPIs DMCS [DMCS año a la fecha · Variación · Tasa DMCS/100k
  con ranking regional · % del total] + barra horizontal DMCS por tipo (2026 vs 2025) + dona DMCS.
- **📈 PIB:** línea de evolución (vol. encadenado base 2018) + KPIs [PIB per cápita · PIB total ·
  Var. % anual · % PIB nacional] + tabla Top-5 sectores (MM$ enc., Var. %, % PIB nac.).
- **💼 Empleo:** KPIs [Tasa trim. móvil · Tasa desoc. nacional · Tasa trim. móvil nacional ·
  Var. anual trim. móvil (p.p.) · Var. anual tasa simple (p.p.) · Fuerza de trabajo] + línea
  tasa simple vs. trimestre móvil.
- **🏘 Censo:** KPIs demográficos con comparación vs. nacional y ranking [Población · Inmigrantes
  · Pueblos originarios · Edad promedio].

---

## 2. MÓDULO 🛡 SEGURIDAD PÚBLICA (acento verde #16a34a)

### 2.1 Resumen por región — `renderResumen`
- **Filtros:** Semana (`res-semana`) · Región (`res-region`, incluye "Todas las regiones").
- **KPIs (`kpi-resumen`):**
  - Casos año a la fecha = Σ `casos_anno_fecha`.
  - Variación año a la fecha = **promedio** de `var_anno_fecha` de las filas (verde si <0).
  - Casos última semana = Σ `casos_ultima_semana`.
  - Tasa por 100 mil hab. = **promedio** de `tasa_registro`.
- **Gráficos:**
  - `chart-tasa` — barra **horizontal**, Tasa/100mil por región ordenada desc.; color por umbral
    (>500 rojo, >400 ámbar, resto verde).
  - `chart-delitos` — barra horizontal, Nº de regiones donde cada delito es el principal.
- **Tabla `tabla-resumen`:** Región · Casos año a la fecha · Var. año % · Casos sem. actual ·
  Tasa/100mil · Principal delito. Orden inicial por casos desc.

### 2.2 Evolución temporal — `renderEvolucionSeg`
- **Filtros:** Región (`evo-seg-region`) · Indicador (`evo-seg-ind`): casos_anno_fecha /
  tasa_registro / casos_ultima_semana / casos_28dias / var_anno_fecha.
- **Gráficos:** `chart-evo-seg` (barras por semana; si es variación, verde/rojo por signo) +
  `chart-evo-delitos` (top delitos por semana, % del total; 5 series `mayor_registro_1..5` / `pct_1..5`).

### 2.3 Actividad operativa — `renderOperativo`
- **Filtro:** Semana (`op-semana`).
- **KPIs (`kpi-op`):** Controles realizados (Σ `controles`, "Identidad + vehicular") ·
  Fiscalizaciones (Σ `fiscalizaciones`) · Incautaciones armas (Σ `incautaciones`) ·
  Decomisos drogas (Σ `decomisos_anno`).
- **Gráficos:** `chart-controles` — barra horizontal apilada [Identidad / Vehicular] ·
  `chart-incaut` — barra horizontal [Armas de fuego / Armas blancas].

### 2.4 🔴 DMCS (Delitos de Mayor Connotación Social) — `renderDMCS` + `renderDMCSEvo`
- **Requiere** `DELITOS.tiene_datos`; si no, muestra aviso "Corre actualizar_datos.py".
- **Filtros:** Semana (`dmcs-semana`) · Región (`dmcs-region`) · Delito DMCS (`dmcs-delito`).
- **Lista DMCS fija** (11 tipos, nombres exactos LeyStop): HOMICIDIOS Y FEMICIDIOS; VIOLACIONES Y
  DELITOS SEXUALES; LESIONES GRAVES; LESIONES MENOS GRAVES; LESIONES LEVES; ROBOS CON VIOLENCIA E
  INTIMIDACIÓN; ROBOS POR SORPRESA; ROBOS EN LUGARES HABITADOS Y NO HABITADOS; ROBOS DE VEHÍCULOS
  Y SUS ACCESORIOS; OTROS ROBOS CON FUERZA EN LAS COSAS; HURTOS. (Filtrar por `es_dmcs === 1`.)
- **KPIs (`kpi-dmcs`):** DMCS año a la fecha (Σ `anno_fecha`) · Variación vs año ant.
  (`(anno_fecha − anno_fecha_ant)/anno_fecha_ant*100`) · DMCS última semana (Σ `ultima_semana`) ·
  % del total de delitos (DMCS / todos los delitos año a la fecha).
- **Gráficos:** `chart-dmcs-regiones` — barra **horizontal**, DMCS por tipo, 2026 vs 2025 ·
  `chart-dmcs-pie` — dona de distribución (% con datalabels) · `chart-dmcs-evo` — evolución
  semanal (con selector de métrica `dmcs-evo-metrica` y comparar `dmcs-evo-comparar`).
- **Tabla `tabla-dmcs`:** Región · Total DMCS año · Var. % · DMCS última sem. · DMCS 28 días ·
  Delito más grave (el de mayor `umbral`). Paleta fija `DMCS_COLORES` (11 colores).

---

## 3. MÓDULO 📈 PIB REGIONAL (acento azul #2563eb)
**Barra de región:** `pib-region-sel` (`setRegionPib`). Fuente de verdad: **volumen encadenado
anual, base 2018** (`datos_enc_anual`); también hay trimestral.
**Indicadores (`PIB_INDICADORES` por frecuencia):** vol. encadenado (miles_enc), var. % (var_pct),
peso/participación (peso_enc), etc. — repórtalos desde el mismo objeto.

### 3.1 Evolución — `renderEvolucionPib`
- **Filtros:** Frecuencia (anual/trimestral) · Indicador · Año desde/hasta.
- **KPIs (`pib-kpi-evo`):** Último período · Año anterior (o "Mismo trim. año ant." si trimestral)
  · Promedio período · **CAGR (vol. encadenado)** vía `calcCAGR`.
- **Gráfico `pib-chart-evo`:** barras; verde/rojo por signo cuando es variación/peso, azul si nivel.

### 3.2 Sectores — `renderSectores`
- **Filtros:** Frecuencia · Indicador · Año desde/hasta · checkbox "Comparar año anterior"
  (`pib-sec-mostrar-var`) que añade columnas Var. % por período.
- **Tabla `tabla-sec`:** filas = sectores (+ fila total "PIB"), columnas = períodos (con Vol. enc.
  y Var. % si el check está activo) + columna **CAGR desde–hasta** destacada. Var. interanual
  encadenada vía `calcVarEnc`; CAGR vía `calcCAGR` (anual: enc[hasta]/enc[desde]; trimestral:
  anualiza sumando trimestres, año inicial exige 4). Nota al pie con metodología.

### 3.3 Resumen nacional — `renderResumenPib`
- **Filtros:** Frecuencia · Indicador · Año desde/hasta · checkbox comparar.
- Tabla agregada nacional (subtotal regionalizado + extrarregional). Variación nacional vía
  `calcVarNacional`, extrarregional vía `calcVarExtra`.

**Cálculos PIB clave a portar verbatim:** `getValPib`, `getEncAnual`, `getTrim`,
`getPIBNacional`, `calcPeso`/`calcPesoNacional`, `calcVarEnc`, `calcVarNacional`, `calcVarExtra`,
`calcCAGR`, `fmtPib`, `colorClsPib`.

---

## 4. MÓDULO 🏘 CENSO 2024 (acento morado #7c3aed)
**Selector de región compartido** entre sub-pestañas (se sincroniza al cambiar). Orden geográfico
**Norte→Sur** (`CENSO_ORDEN_NS`) + fila **Total nacional** (`CENSO_NAC`) al final de cada tabla.
Helpers: `cpct(parte,total)`, `fmtN`, `fmtP`, `fmtD`, `kpiCenso`, `makePie`, `makeHBar`.

### 4.1 Demografía — `renderCenso`
- **Filtros:** Región · Área (`censo-area`) · Sexo (`censo-sexo`: total/hombres/mujeres). Con sexo
  ≠ total muestra aviso "Sin dato por sexo" (`censo-sinDato-demo`) porque solo n_hombres/n_mujeres
  están desagregados.
- **KPIs:** Población · Hogares (+ pers/hogar) · Edad promedio · Inmigrantes (%) · Pueblos
  originarios (%) · Discapacidad (%). Todos como `cpct` sobre la población correspondiente.
- **Gráficos:** `censo-chart-edad` — barra de 7 tramos etarios (0–5, 6–13, 14–17, 18–24, 25–44,
  45–59, 60+) como % población · `censo-chart-comp` — dona Hombres/Mujeres.
- **Tabla `censo-tabla-demo`:** Región · Población · % Mujeres · Prom. edad · % Inmigrantes ·
  % Pueblos orig. · % Discapacidad.

### 4.2 Vivienda — `renderCensoViv`
- **KPIs:** Viviendas ocupadas · Hogares (+ pers/hogar) · Jefatura mujer % · Hacinamiento % ·
  Irrecuperables % · Déficit cuantitativo %. Umbrales colorean (p.ej. hacinamiento >8 rojo).
- **Gráficos:** `censo-chart-tipo-viv` — dona 7 tipos (Casa/Depto/Mediagua/Pieza/Trad./Móvil/Otro),
  denominador = `n_vp` total · `censo-chart-tenencia` — dona 6 tenencias.
- **Tabla `censo-tabla-viv`:** Región · Viv. ocupadas · Prom. pers/hogar · % Hacinadas ·
  % Irrecuperables · % Déficit cuant. · % Allegados · % Jef. mujer.

### 4.3 Educación — `renderCensoEdu`
- **KPIs:** Prom. escolaridad (18+) · Analfabetismo % · (+ nivel CINE / asistencia).
- **Gráficos:** `censo-chart-cine` (nivel CINE) · `censo-chart-asist` (asistencia por nivel:
  parvularia/básica/media/superior).
- **Tabla `censo-tabla-edu`:** Región · Prom. escolaridad · % Sin escolaridad · % Analfabetismo ·
  % Parvularia (asist.) · % Primaria · % Secundaria · % Terciaria.

### 4.4 Conectividad y Servicios — `renderCensoCon`
- **Filtro extra:** Variable de brecha digital (`censo-digital-var`).
- **Gráficos:** `censo-chart-serv` (servicios básicos) · `censo-chart-digital` (brecha digital) ·
  `censo-chart-cocina` · `censo-chart-calef`.
- **Tabla `censo-tabla-con`:** Región · % Internet · % Agua pública · % Alcantarillado ·
  % Electricidad · % Retiro basura · % Sin saneamiento.

---

## 5. MÓDULO 💼 EMPLEO (acento verde #059669)
**Distintivo:** además de la tasa simple, calcula la **tasa de desocupación en trimestre móvil**
(estándar INE) y el **nacional ponderado** (no promedio simple).
Constante `EMP.datos[region]` con arrays alineados por `periodos`: `tasa`, `tasa_tm`, `ocupados`,
`ft`, `desocupados`. Región nacional = `'__NACIONAL__'`.

**Fórmulas a portar verbatim (críticas):**
- **Fuerza de trabajo:** `ft = ocupados / (1 − tasa/100)`.
- **Desocupados:** `desocupados = ft − ocupados`.
- **Tasa trimestre móvil** (`calc_tasa_tm`): para cada mes i (i≥2),
  `Σ desocupados[i-2..i] / Σ ft[i-2..i] * 100`; los 2 primeros meses = null.
- **Nacional:** suma ocupados y ft de todas las regiones por período; `tasa = desocupados_tot /
  ft_tot * 100` (ponderada). Igual para `tasa_tm` nacional.
- **Var. mensual/anual** (`empGetVarMes`/`empGetVarAnual`): diferencia en puntos vs. mes anterior
  / vs. mismo mes año anterior (i−12).

### 5.1 Resumen — `renderEmpResumen`
- **Filtros:** Período (`emp-res-periodo`) · Indicador (`emp-res-ind`: tasa / tasa_tm / ocupados /
  ft / desocupados).
- KPIs de resumen + gráfico principal (`emp-chart-resumen`) y de desocupados
  (`emp-chart-resumen-des`) + tabla por región (`emp-tabla-resumen`).

### 5.2 Evolución — `renderEmpEvolucion`
- **Filtros:** Año desde/hasta · Indicador principal (tasa/tasa_tm) · **checkboxes de regiones**
  (`emp-evo-region-list`, multi-selección; incluye Nacional resaltado en amarillo, línea punteada).
- **KPIs (`emp-kpi-evo`, sobre 1ª región):** Tasa actual · Promedio período · Máx. · Mín.
- **4 gráficos de líneas:** `emp-chart-evo-tasa` · `emp-chart-evo-ocup` · `emp-chart-evo-ft` ·
  `emp-chart-evo-des`. Multi-serie con `makeLineMulti`; leyenda si hay >1 región.

### 5.3 Ranking — `renderEmpRanking`
- **Filtro:** Período (`emp-rank-periodo`).
- **Gráficos:** `emp-chart-rank-alta` (top-5 mayor tasa, barra H + línea promedio nacional
  punteada) · `emp-chart-rank-baja` (top-5 menor) · `emp-chart-rank-des` (top-5 desocupados abs.).
- **Tabla `emp-tabla-ranking`:** fila **Nacional (prom. ponderado)** primero, luego # · Región ·
  Tasa % · Tasa trim. móvil % · Var. mensual · Var. anual · Desocupados · Ocupados · Fuerza
  trabajo. Colorea filas sobre/bajo el promedio nacional.

---

## 6. MÓDULO 🏠 CASEN 2024 (acento rojo #e11d48)
**Selector de región** por sub-pestaña (sincronizado). Helpers: `casenReg`, `fp` (%), `fm`
($ miles), `fdiff` (Δ p.p.), `clsDiff`, tablas con `cTHead`/`cTRow`, charts `mkLineC/mkBarC/
mkBarHC/mkPieC`. Datos en `CASEN.datos[region]` con sub-objetos por temática y años como claves.

### 6.1 Pobreza — `renderCasenPob`
- **KPIs:** Pobreza total 2024 · Pobreza extrema 2024 · Variación 2022→2024 (Δ p.p.) ·
  Brecha FGT1 2024 · Severidad FGT2 2024 · No pobreza 2024.
- **Gráficos:** `cp-evo` (líneas pobreza extrema vs. no extrema, años `CASEN.años_pob`) ·
  `cp-fgt` (FGT1 Brecha vs. FGT2 Severidad).
- **Tabla `cp-tabla`:** Región · Pobreza total 2024 · Pobreza extrema 2024 · Var. 2022→2024 ·
  FGT1 Brecha · FGT2 Severidad. (Colorea >15 rojo, <10 verde.)

### 6.2 Pobreza severa — `renderCasenSevera`
- **KPIs:** Pobreza Severa 2024 · 2022 · Variación 2022→2024 · Solo pob. ingresos 2024.
- **Gráficos:** `csv-pie` (dona: Severa / Solo ingresos / Solo multidim. / No pobreza) ·
  `csv-comp` (barras 2022 vs 2024 por región).
- **Tabla `csv-tabla`:** Región · Pob. Severa 2024 · 2022 · Solo Ingresos · Solo Multidim.

### 6.3 Multidimensional — `renderCasenMulti`
- **KPIs:** Incidencia hogares 2024 (met. 2024) · Incidencia personas 2024 · Var. hogares
  2022→2024 · Met. 2015 comparación.
- **Gráficos:** `cm-car` (barra H % hogares carentes por indicador, `CASEN.indicadores_multi`) ·
  `cm-dim` (dona contribución por dimensión, `CASEN.dimensiones_multi`).
- **Tabla `cm-tabla`:** Región · Hogares 2024 (met.2024) · Hogares 2022 (met.2024) · Personas
  2024 · Hogares 2024 (met.2015).

### 6.4 Ingresos — `renderCasenIngreso`
- **Filtro:** Tipo de ingreso (`ci-tipo`).
- **KPIs:** [tipo] 2024 ($ miles/hogar) · Var. nominal 2022→2024 (`(v24/v22−1)*100`) ·
  Relación vs RM 2024 (`(v24/rm24−1)*100`) · Pobreza relativa 2024 (<50% mediana) ·
  Ingreso autónomo 2024 (% del monetario) · Subsidios monetarios 2024 (%).
- **Gráficos:** `ci-evo` (evolución 2006–2024 del tipo) · `ci-prel` (% <50% mediana) ·
  `ci-comp` (barras Autónomo % vs Subsidios % por región).
- **Tabla `ci-tabla`:** Región · Ing. monetario 2024 · Ing. del trabajo 2024 · Pob. relativa 2024
  · % Autónomo 2024.

### 6.5 Salud — `renderCasenSalud` (+ `renderCasenPrest`)
- **Filtro:** Tipo de prestación (`cs-prest-tipo`).
- **KPIs:** FONASA 2024 · Isapre 2024 · Recibió atención médica · Tuvo problema p/ atenderse ·
  Cubierto AUGE-GES 2024.
- **Gráficos:** `cs-prev` (dona previsión: FONASA/Isapre/FF.AA./Ninguno) · `cs-fon` (líneas FONASA
  vs Isapre, `CASEN.años_sal`) · `cs-prob` (% con problemas, `CASEN.años_prob`) · `cs-ges` (Sí/No
  cubierto AUGE-GES, `CASEN.años_ges`) · `cs-prest` (barra por región del tipo de prestación).
- **Tabla `cs-tabla`:** Región · FONASA 2024 · Isapre 2024 · Recibió atención · Tuvo problemas ·
  Cubierto AUGE-GES.

---

## 7. Prompt final para pegar a Claude Code

```
Tengo un dashboard original completo (generar_dashboard.py + dashboard.html) y una pestaña que
ya integré en el panel de un colega, pero quedó MUY pobre (pocos gráficos, sin filtros, faltan
KPIs y tablas). Quiero que mi pestaña quede IDÉNTICA al original, sin reinventar cálculos.

Fuente de verdad: generar_dashboard.py (te lo adjunto) y este SPEC_PANEL_por_pestana.md.

Haz esto:
1. Lee generar_dashboard.py y el SPEC. Para CADA módulo y sub-pestaña del SPEC, compara contra lo
   que hoy tiene mi pestaña integrada y dame un CHECKLIST de lo que falta (filtros, KPIs, gráficos,
   tablas), sección por sección. No escribas código todavía.
2. Completa lo que falta PORTANDO VERBATIM del original: las funciones de render (renderResumen,
   renderDMCS, renderEvolucionPib, renderSectores, renderCenso*, renderEmp*, renderCasen*), los
   helpers (destroyChart, num, sortDT, makeBar*, makeLineMulti, makePie, mk*C, fmt*) y las configs
   de Chart.js. NO reescribas fórmulas: cópialas. Cálculos que deben quedar exactos: tasa trimestre
   móvil (calc_tasa_tm), ft=ocupados/(1−tasa/100), nacional ponderado, calcVarEnc/calcCAGR de PIB,
   FGT y variaciones CASEN, tasas y % DMCS.
3. Adapta SOLO dos cosas: (a) namespacing para no chocar con el panel del colega (prefija funciones,
   variables globales, IDs y clases CSS que colisionen), y (b) el origen de datos: como mis datos ya
   están en el Supabase compartido, dime si conviene seguir horneando las constantes (SEG/PIB/EMP/
   CENSO/CASEN/DELITOS) desde el generador o leerlas en vivo de Supabase, y implementa esa opción
   manteniendo EXACTAMENTE la misma forma de cada constante que espera el JS.
4. Verifica: abre el resultado, consola limpia (F12), cada filtro cambia el render, cada gráfico y
   tabla aparece con datos reales, las tablas ordenan y exportan CSV, y NINGUNA pestaña del colega
   se rompió. Dame el checklist final marcado.

Regla dura: cero fórmulas reinventadas. Si una fórmula del original no se puede portar por falta de
un campo en Supabase, dímelo y no la aproximes.
```

---

## 8. Nota sobre el origen de datos (decisión que debes tomar tú)

Tu generador **hornea** los datos desde SQLite. Ahora que están en el Supabase compartido tienes
dos caminos, y conviene que le digas a Claude Code cuál:

- **(A) Seguir horneando:** el generador lee de Supabase (en vez de SQLite), arma las mismas
  constantes JS y produce el HTML estático. Menos cambios en el front, pero hay que regenerar para
  actualizar. `[Probable]` es lo más rápido y de menor riesgo dado que tu JS ya espera esas formas.
- **(B) Fetch en vivo:** la pestaña lee de Supabase al abrirse (como quizás hace el panel del
  colega). Más "vivo", pero exige reescribir la carga de datos y validar cada forma. `[Suposición]`
  solo vale la pena si el resto del panel del colega ya funciona así y quieres consistencia.
