"""Puertos (typing.Protocol): toda dependencia con efectos externos se inyecta por constructor."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Protocol, Sequence
from uuid import UUID

from gemelo.dominio.tipos import Alerta, OrdenParada, RawValue, RegistroInmutable, Rol


class Reloj(Protocol):
    def ahora_ns(self) -> int: ...
    def utc(self) -> datetime: ...


class ConectorPLC(Protocol):
    def leer(self, codigo: str) -> RawValue: ...
    def reconectar(self) -> None: ...


class FiltroHistorico:
    """Filtro de consulta del historial (todos los campos son opcionales)."""

    def __init__(self, tipo: Optional[str] = None, alerta_id: Optional[UUID] = None) -> None:
        self.tipo = tipo
        self.alerta_id = alerta_id


class TokenJob:
    """Credencial que solo el trabajo de retención posee (RN010)."""

    def __init__(self, origen: str) -> None:
        self.origen = origen


class PoliticaRetencion:
    def __init__(self, dias: int) -> None:
        self.dias = dias


class RepositorioHistorico(Protocol):
    def insertar(self, registro: RegistroInmutable) -> None: ...
    def consultar(self, filtro: FiltroHistorico) -> list[RegistroInmutable]: ...
    def purgar_por_retencion(self, politica: PoliticaRetencion, token: Optional[TokenJob]) -> int: ...


class CanalComandos(Protocol):
    def emitir(self, orden: OrdenParada) -> bool: ...


class NotificadorService(Protocol):
    def notificar(self, alerta: Alerta, roles: Sequence[Rol]) -> bool: ...
    def notificar_mensaje(self, asunto: str, detalle: Mapping[str, object], roles: Sequence[Rol]) -> bool: ...


class Auditoria(Protocol):
    def registrar(self, usuario_id: str, accion: str, resultado: str) -> None: ...
