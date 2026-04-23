"""
actualizar_readme.py
====================
Agrega una entrada al changelog del README.md.
Se llama desde desarrollar.bat o manualmente.

Uso:
    python actualizar_readme.py "Pestaña Seguridad - nuevo filtro de provincia"
    python actualizar_readme.py "PIB - comparación regional" --version 1.3
"""

import sys
import re
from datetime import datetime
from pathlib import Path

README = Path(__file__).parent / "README.md"

def actualizar_changelog(descripcion: str, version: str = None):
    if not README.exists():
        print(f"ERROR: no se encuentra {README}")
        return False

    with open(README, encoding="utf-8") as f:
        content = f.read()

    # Detectar la última versión del changelog
    versiones = re.findall(r'\|\s*([\d.]+)\s*\|', content)
    if versiones and not version:
        version = versiones[-1]  # Usar la última versión existente

    if not version:
        version = "1.0"

    fecha = datetime.now().strftime("%b %Y")
    nueva_fila = f"| {version} | {fecha} | {descripcion} |"

    # Insertar antes del cierre de la tabla changelog
    # Buscar la última fila de la tabla (línea con | antes de ---)
    marker = "\n---\n\n*Ministerio"
    if marker in content:
        # Insertar la nueva fila justo antes del cierre
        insert_point = content.rfind("| 1.", 0, content.find(marker))
        # Encontrar el fin de esa línea
        end_of_last_row = content.find("\n", insert_point) + 1
        content = content[:end_of_last_row] + nueva_fila + "\n" + content[end_of_last_row:]
    else:
        print("AVISO: no se encontró la sección changelog en README.md")
        return False

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"README actualizado: {nueva_fila}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python actualizar_readme.py \"descripción del cambio\" [--version X.Y]")
        sys.exit(1)

    descripcion = sys.argv[1]
    version = None
    if "--version" in sys.argv:
        idx = sys.argv.index("--version")
        if idx + 1 < len(sys.argv):
            version = sys.argv[idx + 1]

    ok = actualizar_changelog(descripcion, version)
    sys.exit(0 if ok else 1)
