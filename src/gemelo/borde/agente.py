"""Agente de borde: lee los PLC con reintentos, normaliza y envía lotes (HU-01)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from gemelo.borde.buffer import BufferLocal
from gemelo.constantes import (
    ESPERA_BASE_S,
    MAX_INTENTOS_LECTURA,
    MIN_NORMAL_FLOAT32,
    SENTINELAS_ANALOGICAS,
)
from gemelo.dominio.puertos import ConectorPLC, Reloj
from gemelo.dominio.tipos import CalidadSenal, Lectura, RawValue, Variable
from gemelo.errores import SinComunicacionError

Envio = Callable[[Sequence[Lectura]], None]


@dataclass
class AgenteBorde:
    conector: ConectorPLC
    reloj: Reloj
    variables: Sequence[Variable]
    buffer: BufferLocal
    envio: Envio
    dormir: Callable[[float], None] = time.sleep
    max_intentos: int = MAX_INTENTOS_LECTURA

    def leer_con_reintentos(self, codigo: str) -> RawValue:
        for intento in range(1, self.max_intentos + 1):
            try:
                return self.conector.leer(codigo)
            except TimeoutError:
                self.dormir(ESPERA_BASE_S * intento)
            except ConnectionError:
                self.conector.reconectar()
        raise SinComunicacionError(codigo)

    def normalizar(self, crudo: RawValue, variable: Variable) -> Lectura:
        t_mono, t_utc = self.reloj.ahora_ns(), self.reloj.utc()

        def mala(calidad: CalidadSenal) -> Lectura:
            return Lectura(variable.codigo, None, t_mono, t_utc, calidad)

        if crudo is None:
            return mala(CalidadSenal.BAD_NULO)
        if isinstance(crudo, int) and crudo in SENTINELAS_ANALOGICAS:
            return mala(CalidadSenal.BAD_DESBORDAMIENTO)
        try:
            valor = float(crudo)
        except OverflowError:
            return mala(CalidadSenal.BAD_NO_FINITO)
        if not math.isfinite(valor):
            return mala(CalidadSenal.BAD_NO_FINITO)
        if 0 < abs(valor) < MIN_NORMAL_FLOAT32:
            return mala(CalidadSenal.BAD_DENORMAL)
        if valor < variable.rango_min or valor > variable.rango_max:
            return mala(CalidadSenal.BAD_FUERA_RANGO)
        return Lectura(variable.codigo, round(valor, variable.resolucion), t_mono, t_utc, CalidadSenal.GOOD)

    def ejecutar_ciclo(self) -> list[Lectura]:
        lecturas: list[Lectura] = []
        for variable in self.variables:
            try:
                crudo = self.leer_con_reintentos(variable.codigo)
            except SinComunicacionError:
                lecturas.append(
                    Lectura(
                        variable.codigo, None, self.reloj.ahora_ns(), self.reloj.utc(), CalidadSenal.BAD_SIN_COMUNICACION
                    )
                )
                continue
            lecturas.append(self.normalizar(crudo, variable))
        self.enviar_lote(lecturas)
        return lecturas

    def enviar_lote(self, lote: Sequence[Lectura]) -> bool:
        try:
            self.envio(lote)
        except (ConnectionError, TimeoutError):
            self.buffer.guardar(lote)  # sin pérdida de datos
            return False
        return self._reenviar_pendientes()

    def _reenviar_pendientes(self) -> bool:
        pendientes: Optional[list[Lectura]] = self.buffer.drenar()
        if not pendientes:
            return True
        try:
            self.envio(pendientes)
        except (ConnectionError, TimeoutError):
            self.buffer.guardar(pendientes)
            return False
        return True
