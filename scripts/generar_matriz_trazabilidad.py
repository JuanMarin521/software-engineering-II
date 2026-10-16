"""Genera la matriz CE-xx ↔ HU ↔ tarea JIRA ↔ resultado a partir del informe JUnit de pytest."""

from __future__ import annotations

import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SALIDA = Path("tests/trazabilidad/matriz.csv")


def main() -> int:
    subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml=reporte.xml", "-p", "no:cacheprovider"], check=False)
    filas = []
    for caso in ET.parse("reporte.xml").getroot().iter("testcase"):
        props = {p.get("name"): p.get("value") for p in caso.iter("property")}
        if "caso" not in props:
            continue
        resultado = (
            "FALLO"
            if caso.find("failure") is not None or caso.find("error") is not None
            else ("OMITIDA" if caso.find("skipped") is not None else "OK")
        )
        filas.append((props["caso"], props.get("jira", ""), caso.get("name", ""), resultado))
    filas.sort()
    with SALIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["caso", "jira", "prueba", "resultado"])
        escritor.writerows(filas)
    print(f"{len(filas)} pruebas trazadas en {SALIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
