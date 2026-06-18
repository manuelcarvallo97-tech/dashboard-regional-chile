"""
fix_generar_resumen.py
Inyecta el modulo Resumen Ejecutivo permanentemente en generar_dashboard.py
extrayendo el HTML y JS desde el dashboard.html actual.
Solo ejecutar una vez.
"""
import sys

# ── Leer archivos ──────────────────────────────────────────────
with open('dashboard.html', 'r', encoding='utf-8') as f:
    dash = f.read()

with open('generar_dashboard.py', 'r', encoding='utf-8') as f:
    gen = f.read()

# ── Verificar que generar_dashboard.py no haya sido ya parcheado ──
if 'mod-resumen' in gen:
    print('AVISO: generar_dashboard.py ya contiene mod-resumen — ya fue parcheado.')
    sys.exit(0)

# ── Verificar que dashboard.html tiene el Resumen ─────────────
HTML_START = '<div class="modulo active" id="mod-resumen">'
HTML_END   = '</div><!-- /mod-resumen -->'
JS_MARKER  = '// RESUMEN EJECUTIVO'
if HTML_START not in dash or HTML_END not in dash or JS_MARKER not in dash:
    print('ERROR: dashboard.html no contiene el modulo Resumen Ejecutivo.')
    print('Restaura dashboard.html desde git antes de ejecutar este script.')
    sys.exit(1)

# ── 1. Extraer HTML block del mod-resumen ─────────────────────
hi = dash.index(HTML_START)
hj = dash.index(HTML_END) + len(HTML_END)
resumen_html = dash[hi:hj]
print(f'HTML block extraido: {len(resumen_html)} chars')

# ── 2. Extraer JS block (desde el comentario RESUMEN EJECUTIVO hasta el } final) ──
# El JS empieza con la linea de === antes del comentario
ji_comment = dash.index(JS_MARKER)
# Retroceder al '// ===' que precede al comentario
ji = dash.rindex('// ══', 0, ji_comment)
# Termina en el '\n}' justo antes de '\n</script>'
# El renderResumenEjecutivo cierra con '}' solo (sin ';') antes de '</script>'
JS_END_SEQ = '\n}\n</script>'
jj = dash.index(JS_END_SEQ, ji) + 2  # incluye '\n}'
resumen_js = dash[ji:jj]
print(f'JS block extraido: {len(resumen_js)} chars')

# ── 3. Verificar ausencia de triple comillas (romperia el string Python) ───
assert '"""' not in resumen_html, 'ERROR: HTML block contiene triple comillas dobles'
assert '"""' not in resumen_js,   'ERROR: JS block contiene triple comillas dobles'
assert "'''" not in resumen_html, 'ERROR: HTML block contiene triple comillas simples'
assert "'''" not in resumen_js,   'ERROR: JS block contiene triple comillas simples'

# ── 4. Construir bloque de definicion de variables Python ─────
# Usar repr() para mayor seguridad (maneja cualquier caracter especial)
var_block = (
    '\n# ── Resumen Ejecutivo — HTML y JS embebidos directamente por el generador ──\n'
    f'resumen_html_block = {repr(resumen_html)}\n\n'
    f'resumen_js_block = {repr(resumen_js)}\n\n'
)

# ── 5. Aplicar los 9 cambios a generar_dashboard.py ─────────────

errors = []

def apply_replace(code, old, new, desc):
    if old not in code:
        errors.append(f'Cambio "{desc}": patron no encontrado')
        return code
    return code.replace(old, new, 1)

# 5a. Insertar variables Python antes de html = f"""
OLD_5A = '\nhtml = f"""<!DOCTYPE html>'
NEW_5A = var_block + '\nhtml = f"""<!DOCTYPE html>'
gen = apply_replace(gen, OLD_5A, NEW_5A, '5a: insertar variables')

# 5b. Nav: agregar Resumen como primer boton activo
OLD_5B = "  <div class=\"mod-btn active\" onclick=\"setModulo('seguridad',this)\">\U0001f6e1 Seguridad Pública</div>"
NEW_5B = (
    "  <div class=\"mod-btn active\" onclick=\"setModulo('resumen',this)\">\U0001f4cb Resumen</div>\n"
    "  <div class=\"mod-btn\" onclick=\"setModulo('seguridad',this)\">\U0001f6e1 Seguridad Pública</div>"
)
gen = apply_replace(gen, OLD_5B, NEW_5B, '5b: nav Resumen')

# 5c. Quitar active de mod-seguridad
OLD_5C = '<div class="modulo active" id="mod-seguridad">'
NEW_5C = '<div class="modulo" id="mod-seguridad">'
gen = apply_replace(gen, OLD_5C, NEW_5C, '5c: mod-seguridad sin active')

# 5d. MOD_LABELS: agregar entrada 'resumen'
OLD_5D = "const MOD_LABELS = {{'empleo':'\U0001f4bc Empleo · BCE/INE',"
NEW_5D = "const MOD_LABELS = {{'resumen':'\U0001f4cb Resumen Ejecutivo','empleo':'\U0001f4bc Empleo · BCE/INE',"
gen = apply_replace(gen, OLD_5D, NEW_5D, '5d: MOD_LABELS resumen')

# 5e. setModulo: agregar handler de resumen
OLD_5E = "  if(id === 'seguridad') renderResumen();"
NEW_5E = (
    "  if(id === 'resumen') {{ poblarSelectsResumenEjecutivo(); renderResumenEjecutivo(); }}\n"
    "  if(id === 'seguridad') renderResumen();"
)
gen = apply_replace(gen, OLD_5E, NEW_5E, '5e: setModulo resumen handler')

# 5f. hdr-sub default a 'resumen'
OLD_5F = "  document.getElementById('hdr-sub').textContent = MOD_LABELS['seguridad'];"
NEW_5F = "  document.getElementById('hdr-sub').textContent = MOD_LABELS['resumen'];"
gen = apply_replace(gen, OLD_5F, NEW_5F, '5f: hdr-sub resumen')

# 5g. Insertar mod-resumen HTML despues de mod-casen y antes del script CASEN
OLD_5G = '</div><!-- /mod-casen -->\n\n<script>'
NEW_5G = '</div><!-- /mod-casen -->\n\n{resumen_html_block}\n\n<script>'
gen = apply_replace(gen, OLD_5G, NEW_5G, '5g: insertar mod-resumen HTML')

# 5h. Insertar JS block antes de initCasen (en el bloque script CASEN)
OLD_5H = '\nfunction initCasen(){{'
NEW_5H = '\n{resumen_js_block}\n\nfunction initCasen(){{'
gen = apply_replace(gen, OLD_5H, NEW_5H, '5h: insertar resumen JS')

# 5i. Llamadas de init en window.onload
OLD_5I = '  // CASEN 2024\n  initCasen();'
NEW_5I = (
    '  // CASEN 2024\n  initCasen();\n\n'
    '  // Resumen Ejecutivo\n'
    '  poblarSelectsResumenEjecutivo();\n'
    '  renderResumenEjecutivo();'
)
gen = apply_replace(gen, OLD_5I, NEW_5I, '5i: window.onload init resumen')

# ── 6. Reportar errores si los hay ────────────────────────────
if errors:
    print('\nERRORES — no se escribio el archivo:')
    for e in errors:
        print(f'  ✗ {e}')
    sys.exit(1)

# ── 7. Escribir generar_dashboard.py parcheado ────────────────
with open('generar_dashboard.py', 'w', encoding='utf-8') as f:
    f.write(gen)

print('\n✅ generar_dashboard.py parcheado con exito:')
print(f'   HTML block: {len(resumen_html):,} chars')
print(f'   JS block:   {len(resumen_js):,} chars')
print('\nPasos siguientes:')
print('  1. python generar_dashboard.py   # regenerar dashboard.html con el Resumen incluido')
print('  2. git add -f dashboard.html generar_dashboard.py')
print('  3. git commit -m "fix: incluir Resumen Ejecutivo permanentemente en generar_dashboard.py"')
print('  4. git push origin main')
