"""Excepciones del dominio. Cada camino de error del diseño tiene su excepción propia."""

from __future__ import annotations

from enum import Enum


class MotivoBloqueo(Enum):
    ALERTAS_PENDIENTES = "ALERTAS_PENDIENTES"
    ENTRANTE_SIN_CONFIRMAR = "ENTRANTE_SIN_CONFIRMAR"
    CONSOLIDACION_FALLIDA = "CONSOLIDACION_FALLIDA"
    TURNO_EN_CIERRE = "TURNO_EN_CIERRE"


class GemeloError(Exception):
    """Base de las excepciones del Gemelo Digital."""


class LecturaInvalidaError(GemeloError, ValueError):
    """La lectura no tiene un valor finito y utilizable."""


class UmbralInvalidoError(GemeloError, ValueError):
    """El umbral de advertencia no es menor que el crítico."""


class RelojInconsistenteError(GemeloError):
    """El reloj monotónico retrocedió respecto de la última lectura."""


class SinComunicacionError(GemeloError):
    """Se agotaron los reintentos de lectura de un PLC."""


class RolDesconocidoError(GemeloError, ValueError):
    """El texto no corresponde a ningún rol."""


class PermisoDenegadoError(GemeloError):
    """El usuario o el token no está autorizado para la acción."""


class ParoInvalidoError(GemeloError, ValueError):
    """La duración de un paro no puede ser negativa."""


class TipoParoDesconocidoError(GemeloError, ValueError):
    """El tipo de paro no está en la tabla de decisión de RN008."""


class ConsolidacionError(GemeloError):
    """Falló la consolidación del informe de turno."""


class CierreBloqueadoError(GemeloError):
    def __init__(self, motivo: MotivoBloqueo, detalle: tuple[str, ...] = ()) -> None:
        super().__init__(motivo.value)
        self.motivo = motivo
        self.detalle = detalle


class PoliticaInvalidaError(GemeloError, ValueError):
    """La política de retención exige dias mayor que cero."""


class OperationalError(GemeloError):
    """Falla de la base de datos (el adaptador traduce la excepción del controlador)."""
