"""Dobles de prueba reutilizables (sección 6.1 del RTF3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gemelo.dominio.tipos import CalidadSenal, Lectura, Umbral, Variable

NS = 10**9
T0_UTC = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


class FakeReloj:
    """Reloj controlable: simula 30 s o 10 min sin esperar."""

    def __init__(self, ahora_ns: int = 0) -> None:
        self.ns = ahora_ns

    def ahora_ns(self) -> int:
        return self.ns

    def utc(self) -> datetime:
        return T0_UTC + timedelta(microseconds=self.ns // 1000)

    def avanzar(self, ns: int) -> None:
        self.ns += ns


def variable_presion(es_vp: bool = True) -> Variable:
    return Variable("PRES-01", es_vp, Umbral(225.0, 240.0), 0.0, 400.0)


def lectura(
    valor: float | None, t_ns: int = 0, calidad: CalidadSenal = CalidadSenal.GOOD, diferida: bool = False
) -> Lectura:
    return Lectura("PRES-01", valor, t_ns, T0_UTC, calidad, diferida)
