"""Clasificación de paros (RN008). Función pura sobre un Paro inmutable."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gemelo.constantes import MICRO_PARADA_S
from gemelo.errores import ParoInvalidoError, TipoParoDesconocidoError


class TipoParo(Enum):
    AVERIA = "AVERIA"
    CAMBIO_FORMATO = "CAMBIO_FORMATO"
    ASEO_LINEA = "ASEO_LINEA"
    MICRO_PARADA = "MICRO_PARADA"


class Penalizacion(Enum):
    NINGUNA = "NINGUNA"
    DISPONIBILIDAD = "DISPONIBILIDAD"
    RENDIMIENTO = "RENDIMIENTO"


@dataclass(frozen=True)
class Paro:
    tipo: object  # TipoParo; un valor fuera del Enum se rechaza en clasificar
    duracion_s: int
    programado_en_of: bool

    def __post_init__(self) -> None:
        if self.duracion_s < 0:
            raise ParoInvalidoError("duracion_s no puede ser negativa")


@dataclass(frozen=True)
class ClasificacionParo:
    penaliza: Penalizacion
    requiere_validacion: bool


class ClasificadorParos:
    def clasificar(self, paro: Paro) -> ClasificacionParo:
        tipo = paro.tipo
        if tipo is TipoParo.AVERIA:
            return ClasificacionParo(Penalizacion.DISPONIBILIDAD, False)
        if tipo in (TipoParo.CAMBIO_FORMATO, TipoParo.ASEO_LINEA):
            if paro.programado_en_of:
                return ClasificacionParo(Penalizacion.NINGUNA, False)
            return ClasificacionParo(Penalizacion.DISPONIBILIDAD, True)  # D4
        if tipo is TipoParo.MICRO_PARADA:
            if paro.duracion_s < MICRO_PARADA_S:
                return ClasificacionParo(Penalizacion.RENDIMIENTO, False)
            return ClasificacionParo(Penalizacion.DISPONIBILIDAD, True)  # D3
        raise TipoParoDesconocidoError(str(tipo))
