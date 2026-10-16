"""Cierre y entrega de turno (RN009)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from gemelo.constantes import MAX_INTENTOS_CIERRE
from gemelo.dominio.puertos import Auditoria, NotificadorService, Reloj, RepositorioHistorico
from gemelo.dominio.tipos import RegistroInmutable, Rol, Usuario
from gemelo.errores import CierreBloqueadoError, ConsolidacionError, MotivoBloqueo, PermisoDenegadoError


class EstadoTurno(Enum):
    ABIERTO = "ABIERTO"
    CERRANDO = "CERRANDO"
    CERRADO = "CERRADO"


@dataclass
class Turno:
    id: str
    estado: EstadoTurno = EstadoTurno.ABIERTO
    alertas_sin_reconocer: int = 0
    entrante_confirmado: bool = False
    ids_alertas_pendientes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InformeTurno:
    turno_id: str
    resumen: dict[str, object]


@dataclass(frozen=True)
class ResultadoCierre:
    ok: bool


class AlmacenTurnos(Protocol):
    def obtener(self, turno_id: str) -> Turno: ...


class GestorTurno:
    def __init__(
        self,
        almacen: AlmacenTurnos,
        repositorio: RepositorioHistorico,
        auditoria: Auditoria,
        notificador: NotificadorService,
        reloj: Reloj,
        max_intentos: int = MAX_INTENTOS_CIERRE,
    ) -> None:
        self._almacen = almacen
        self._repo = repositorio
        self._auditoria = auditoria
        self._notificador = notificador
        self._reloj = reloj
        self._max_intentos = max_intentos
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def consolidar(self, turno: Turno) -> InformeTurno:
        return InformeTurno(turno.id, {"cerrado_utc": self._reloj.utc().isoformat()})

    def cerrar_turno(self, turno_id: str, usuario: Usuario) -> ResultadoCierre:
        if usuario.rol is not Rol.SUPERVISOR:
            self._auditoria.registrar(usuario.id, "CERRAR_TURNO", "DENEGADO")
            raise PermisoDenegadoError(usuario.id)
        turno = self._almacen.obtener(turno_id)
        with self._lock(turno_id):
            self._verificar_compuertas(turno)
            turno.estado = EstadoTurno.CERRANDO
            informe = self._consolidar_con_reintentos(turno)
            self._repo.insertar(RegistroInmutable("informe_turno", self._reloj.utc(), dict(informe.resumen, turno=turno.id)))
            turno.estado = EstadoTurno.CERRADO
        self._notificador.notificar_mensaje("Informe de turno", {"turno": turno.id}, (Rol.PLANEADOR, Rol.GERENTE))
        return ResultadoCierre(ok=True)

    def _verificar_compuertas(self, turno: Turno) -> None:
        if turno.estado is not EstadoTurno.ABIERTO:
            raise CierreBloqueadoError(MotivoBloqueo.TURNO_EN_CIERRE)
        if turno.alertas_sin_reconocer > 0:
            raise CierreBloqueadoError(MotivoBloqueo.ALERTAS_PENDIENTES, turno.ids_alertas_pendientes)
        if not turno.entrante_confirmado:
            raise CierreBloqueadoError(MotivoBloqueo.ENTRANTE_SIN_CONFIRMAR)

    def _consolidar_con_reintentos(self, turno: Turno) -> InformeTurno:
        for _ in range(self._max_intentos):
            try:
                return self.consolidar(turno)
            except ConsolidacionError:
                continue
        turno.estado = EstadoTurno.ABIERTO
        self._notificador.notificar_mensaje("Cierre de turno fallido", {"turno": turno.id}, (Rol.ADMIN,))
        raise CierreBloqueadoError(MotivoBloqueo.CONSOLIDACION_FALLIDA)

    def _lock(self, turno_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(turno_id, threading.Lock())
