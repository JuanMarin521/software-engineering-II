"""Controlador de ingesta: traduce un lote HTTP en llamadas al motor de alertas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from gemelo.constantes import TAMANO_MAX_LOTE
from gemelo.dominio.motor_alertas import MotorAlertas
from gemelo.dominio.puertos import RepositorioHistorico
from gemelo.dominio.tipos import Lectura, RegistroInmutable, RespuestaHTTP, Variable


@dataclass(frozen=True)
class LoteLecturas:
    lecturas: Sequence[Lectura]


class IngestaController:
    def __init__(self, motor: MotorAlertas, variables: Mapping[str, Variable], repositorio: RepositorioHistorico) -> None:
        self._motor = motor
        self._variables = variables
        self._repo = repositorio

    def recibir_lote(self, lote: LoteLecturas) -> RespuestaHTTP:
        if not lote.lecturas or len(lote.lecturas) > TAMANO_MAX_LOTE:
            return RespuestaHTTP(422, {"error": "tamano de lote invalido"})
        aceptadas = rechazadas = 0
        for lectura in lote.lecturas:
            variable = self._variables.get(lectura.variable_codigo)
            if variable is None:
                rechazadas += 1
                continue
            self._repo.insertar(
                RegistroInmutable(
                    "lectura",
                    lectura.t_utc,
                    {
                        "variable": lectura.variable_codigo,
                        "valor": lectura.valor,
                        "calidad": lectura.calidad.value,
                        "diferida": lectura.diferida,
                    },
                )
            )
            self._motor.procesar_lectura(lectura, variable)
            aceptadas += 1
        return RespuestaHTTP(200, {"aceptadas": aceptadas, "rechazadas": rechazadas})
