"""Adaptadores de protocolo. El cliente del protocolo se inyecta: sin PLC físico no hay E/S en las pruebas."""

from __future__ import annotations

import struct
from enum import Enum
from typing import Protocol, Sequence

from gemelo.dominio.tipos import RawValue


class OrdenPalabras(Enum):
    ALTO_BAJO = "ALTO_BAJO"
    BAJO_ALTO = "BAJO_ALTO"


class ClienteOPCUA(Protocol):
    def leer_nodo(self, codigo: str) -> RawValue: ...
    def reconectar(self) -> None: ...


class ClienteModbus(Protocol):
    def leer_registros(self, codigo: str) -> Sequence[int]: ...
    def reconectar(self) -> None: ...


class ConectorOPCUA:
    def __init__(self, cliente: ClienteOPCUA) -> None:
        self._cliente = cliente

    def leer(self, codigo: str) -> RawValue:
        return self._cliente.leer_nodo(codigo)

    def reconectar(self) -> None:
        self._cliente.reconectar()


def decodificar_registros(regs: Sequence[int], orden: OrdenPalabras = OrdenPalabras.ALTO_BAJO) -> float:
    """Decodifica un float32 que ocupa dos registros uint16 según el orden de palabras."""
    alto, bajo = (regs[0], regs[1]) if orden is OrdenPalabras.ALTO_BAJO else (regs[1], regs[0])
    return float(struct.unpack(">f", struct.pack(">HH", alto, bajo))[0])


class ConectorModbusTCP:
    def __init__(self, cliente: ClienteModbus, orden_palabras: OrdenPalabras = OrdenPalabras.ALTO_BAJO) -> None:
        self._cliente = cliente
        self._orden = orden_palabras

    def decodificar_registros(self, regs: Sequence[int]) -> float:
        return decodificar_registros(regs, self._orden)

    def leer(self, codigo: str) -> RawValue:
        regs = self._cliente.leer_registros(codigo)
        if len(regs) == 2:
            return self.decodificar_registros(regs)
        valor = regs[0]
        return valor - 65536 if valor > 32767 else valor  # int16 con signo

    def reconectar(self) -> None:
        self._cliente.reconectar()
