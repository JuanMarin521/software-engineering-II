"""Buffer local en disco (SQLite) para no perder lecturas si el backend no responde."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime
from typing import Sequence

from gemelo.dominio.tipos import CalidadSenal, Lectura


class BufferLocal:
    def __init__(self, ruta: str = ":memory:") -> None:
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS lectura (id INTEGER PRIMARY KEY AUTOINCREMENT, variable TEXT NOT NULL, "
            "valor REAL, t_mono_ns INTEGER NOT NULL, t_utc TEXT NOT NULL, calidad TEXT NOT NULL)"
        )

    def guardar(self, lote: Sequence[Lectura]) -> None:
        with self._con:
            self._con.executemany(
                "INSERT INTO lectura (variable, valor, t_mono_ns, t_utc, calidad) VALUES (?, ?, ?, ?, ?)",
                [(x.variable_codigo, x.valor, x.t_mono_ns, x.t_utc.isoformat(), x.calidad.value) for x in lote],
            )

    def drenar(self) -> list[Lectura]:
        """Retorna las lecturas pendientes en orden cronológico, marcadas como diferidas, y las elimina."""
        filas = self._con.execute(
            "SELECT id, variable, valor, t_mono_ns, t_utc, calidad FROM lectura ORDER BY id"
        ).fetchall()
        with self._con:
            self._con.execute("DELETE FROM lectura")
        return [
            replace(
                Lectura(f[1], f[2], f[3], datetime.fromisoformat(f[4]), CalidadSenal(f[5])),
                diferida=True,
            )
            for f in filas
        ]
