"""Recorrido periódico de los turnos para publicar el OEE y emitir alertas (RN004, RN005)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Sequence

from gemelo.dominio.calculador_oee import CalculadorOEE, EntradaOEE, EstadoCalculo, ResultadoOEE
from gemelo.dominio.puertos import NotificadorService
from gemelo.dominio.tipos import Rol

log = logging.getLogger(__name__)
LIMITE_EFICIENCIA = Fraction(4, 5)
LIMITE_OEE_ESTRATEGICO = Fraction(13, 20)


@dataclass
class TurnoOEE:
    id: str
    transcurrido_s: int
    duracion_s: int


def antes_de_la_mitad(transcurrido_s: int, duracion_s: int) -> bool:
    """Comparación estricta y en enteros: en la mitad exacta ya no se alerta."""
    return transcurrido_s * 2 < duracion_s


def evaluar_eficiencia(rendimiento: Fraction, transcurrido_s: int, duracion_s: int) -> bool:
    return rendimiento < LIMITE_EFICIENCIA and antes_de_la_mitad(transcurrido_s, duracion_s)


class PlanificadorOEE:
    def __init__(
        self,
        calculador: CalculadorOEE,
        notificador: NotificadorService,
        armar_entrada: Callable[[TurnoOEE], EntradaOEE],
    ) -> None:
        self._calculador = calculador
        self._notificador = notificador
        self._armar_entrada = armar_entrada

    def tick(self, turnos: Sequence[TurnoOEE], ahora_ns: int) -> list[ResultadoOEE]:
        resultados: list[ResultadoOEE] = []
        for turno in turnos:
            try:
                resultado = self._calculador.calcular(self._armar_entrada(turno))
            except Exception:  # un turno con falla no detiene a los demás
                log.exception("error calculando el OEE del turno %s", turno.id)
                continue
            resultados.append(resultado)
            self._emitir_alertas(turno, resultado)
        return resultados

    def _emitir_alertas(self, turno: TurnoOEE, resultado: ResultadoOEE) -> None:
        if resultado.estado is EstadoCalculo.FUERA_DE_RANGO:
            self._notificador.notificar_mensaje("Error en datos", {"turno": turno.id}, (Rol.SUPERVISOR,))
            return
        if resultado.rendimiento is not None and evaluar_eficiencia(
            resultado.rendimiento, turno.transcurrido_s, turno.duracion_s
        ):
            self._notificador.notificar_mensaje("Eficiencia baja", {"turno": turno.id}, (Rol.PLANEADOR,))
        if (
            resultado.oee is not None
            and resultado.oee < LIMITE_OEE_ESTRATEGICO
            and antes_de_la_mitad(turno.transcurrido_s, turno.duracion_s)
        ):
            self._notificador.notificar_mensaje("OEE estratégico bajo", {"turno": turno.id}, (Rol.GERENTE,))
