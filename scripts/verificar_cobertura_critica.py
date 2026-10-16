"""Falla (código de salida distinto de 0) si un módulo crítico no tiene el 100 % de sus ramas cubiertas (AC-Q1).

Uso (Git Bash, Linux o macOS):
    pytest --cov=gemelo --cov-branch --cov-report=
    coverage json -o coverage.json
    python scripts/verificar_cobertura_critica.py

En PowerShell, ejecute cada comando en su propia línea (PowerShell 5 no admite `&&`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MODULOS_CRITICOS = (
    "src/gemelo/borde/agente.py",
    "src/gemelo/dominio/motor_alertas.py",
    "src/gemelo/dominio/clasificador_paros.py",
    "src/gemelo/dominio/calculador_oee.py",
    "src/gemelo/dominio/planificador_oee.py",
    "src/gemelo/dominio/gestor_turno.py",
    "src/gemelo/dominio/autorizacion.py",
    "src/gemelo/controladores/alertas.py",
    "src/gemelo/controladores/historial.py",
    "src/gemelo/infraestructura/repositorio.py",
)


def _normalizar(ruta: str) -> str:
    """En Windows coverage escribe las rutas con barra invertida; se unifican con barra normal."""
    return ruta.replace("\\", "/")


def main(ruta: str = "coverage.json") -> int:
    archivos = json.loads(Path(ruta).read_text(encoding="utf-8"))["files"]
    datos = {_normalizar(nombre): valor for nombre, valor in archivos.items()}
    fallos = []
    for modulo in MODULOS_CRITICOS:
        if modulo not in datos:
            fallos.append(f"{modulo}: no aparece en {ruta} (ejecute pytest --cov desde la raíz del proyecto)")
            continue
        resumen = datos[modulo]["summary"]
        if resumen["covered_branches"] != resumen["num_branches"] or resumen["missing_lines"] != 0:
            fallos.append(f"{modulo}: ramas {resumen['covered_branches']}/{resumen['num_branches']}")
    for linea in fallos:
        print("SIN COBERTURA TOTAL:", linea)
    if not fallos:
        print(f"OK: {len(MODULOS_CRITICOS)} módulos críticos con el 100 % de ramas cubiertas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
