"""Tipos de datos del dominio. Las dataclasses son inmutables: una actualización crea un objeto nuevo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Union
from uuid import UUID

from gemelo.errores import RolDesconocidoError, UmbralInvalidoError

RawValue = Union[int, float, None]


class Nivel(IntEnum):
    NORMAL = 0
    LEVE = 1
    GRAVE = 2


class CalidadSenal(Enum):
    GOOD = "GOOD"
    BAD_NULO = "BAD_NULO"
    BAD_DESBORDAMIENTO = "BAD_DESBORDAMIENTO"
    BAD_NO_FINITO = "BAD_NO_FINITO"
    BAD_DENORMAL = "BAD_DENORMAL"
    BAD_FUERA_RANGO = "BAD_FUERA_RANGO"
    BAD_SIN_COMUNICACION = "BAD_SIN_COMUNICACION"


class Rol(Enum):
    OPERARIO = "OPERARIO"
    SUPERVISOR = "SUPERVISOR"
    JEFE_MTTO = "JEFE_MTTO"
    INSPECTOR = "INSPECTOR"
    PLANEADOR = "PLANEADOR"
    GERENTE = "GERENTE"
    ADMIN = "ADMIN"

    @classmethod
    def desde_texto(cls, texto: str) -> "Rol":
        """Coincidencia exacta: un texto con espacios o en minúsculas no es un rol."""
        try:
            return cls(texto)
        except ValueError as exc:
            raise RolDesconocidoError(texto) from exc


@dataclass(frozen=True)
class Usuario:
    id: str
    rol: Optional[Rol]


@dataclass(frozen=True)
class Umbral:
    advertencia: float
    critico: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.advertencia) and math.isfinite(self.critico)):
            raise UmbralInvalidoError("los umbrales deben ser finitos")
        if self.advertencia >= self.critico:
            raise UmbralInvalidoError("advertencia debe ser menor que critico")


@dataclass(frozen=True)
class Variable:
    codigo: str
    es_variable_parada: bool
    umbral: Umbral
    rango_min: float
    rango_max: float
    resolucion: int = 3


@dataclass(frozen=True)
class Lectura:
    variable_codigo: str
    valor: Optional[float]
    t_mono_ns: int
    t_utc: datetime
    calidad: CalidadSenal
    diferida: bool = False


@dataclass(frozen=True)
class EstadoVariable:
    nivel: Nivel = Nivel.NORMAL
    inicio_grave_ns: Optional[int] = None
    ultima_lectura_ns: Optional[int] = None
    orden_emitida: bool = False
    alerta_id: Optional[UUID] = None


class TipoEvento(Enum):
    CREADA = "CREADA"
    RECONOCIDA = "RECONOCIDA"
    ESCALADA = "ESCALADA"
    CERRADA = "CERRADA"
    ORDEN_PARADA = "ORDEN_PARADA"
    ORDEN_FALLIDA = "ORDEN_FALLIDA"
    SENAL_INVALIDA = "SENAL_INVALIDA"


@dataclass(frozen=True)
class Alerta:
    id: UUID
    variable_codigo: str
    nivel: Nivel
    inicio_ns: int
    valor_pico: float
    reconocida_por: Optional[str] = None


@dataclass(frozen=True)
class EventoAlerta:
    alerta_id: UUID
    tipo: TipoEvento
    t_utc: datetime
    actor: Optional[str] = None


@dataclass(frozen=True)
class OrdenParada:
    variable_codigo: str
    t_utc: datetime
    motivo: str


@dataclass(frozen=True)
class ResultadoProceso:
    nivel: Optional[Nivel]
    orden_emitida: bool
    error: Optional[str] = None
    error_persistencia: bool = False


@dataclass(frozen=True)
class RespuestaHTTP:
    status: int
    cuerpo: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegistroInmutable:
    tipo: str
    t_utc: datetime
    carga: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # La carga queda de solo lectura: asignar un elemento lanza TypeError.
        object.__setattr__(self, "carga", MappingProxyType(dict(self.carga)))
