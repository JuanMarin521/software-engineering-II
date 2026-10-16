"""Motor de alertas: clasificación, contador de Grave sostenido, parada y escalamiento (RN001 a RN003, RN007)."""

from __future__ import annotations

import math
import threading
import uuid
from dataclasses import replace
from typing import Sequence, cast

from gemelo.constantes import UMBRAL_ESCALA_NS, UMBRAL_PARADA_NS
from gemelo.dominio.puertos import (
    CanalComandos,
    NotificadorService,
    Reloj,
    RepositorioHistorico,
)
from gemelo.dominio.tipos import (
    Alerta,
    EstadoVariable,
    EventoAlerta,
    Lectura,
    Nivel,
    OrdenParada,
    RegistroInmutable,
    ResultadoProceso,
    Rol,
    TipoEvento,
    Umbral,
    Variable,
)
from gemelo.errores import LecturaInvalidaError, OperationalError, RelojInconsistenteError

_ROLES_POR_NIVEL = {
    Nivel.LEVE: (Rol.OPERARIO, Rol.SUPERVISOR),
    Nivel.GRAVE: (Rol.SUPERVISOR, Rol.JEFE_MTTO),
}


def evento_a_registro(evento: EventoAlerta) -> RegistroInmutable:
    return RegistroInmutable(
        tipo="evento_alerta",
        t_utc=evento.t_utc,
        carga={"alerta_id": str(evento.alerta_id), "evento": evento.tipo.value, "actor": evento.actor},
    )


class MotorAlertas:
    def __init__(
        self,
        reloj: Reloj,
        repositorio: RepositorioHistorico,
        canal: CanalComandos,
        notificador: NotificadorService,
    ) -> None:
        self._reloj = reloj
        self._repo = repositorio
        self._canal = canal
        self._notificador = notificador
        self._estados: dict[str, EstadoVariable] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---- unidades puras (se prueban con datos en memoria) ----
    def clasificar(self, lectura: Lectura, umbral: Umbral) -> Nivel:
        valor = lectura.valor
        if valor is None or not math.isfinite(valor):
            raise LecturaInvalidaError(f"lectura sin valor utilizable en {lectura.variable_codigo}")
        if valor > umbral.critico:
            return Nivel.GRAVE
        if valor > umbral.advertencia:
            return Nivel.LEVE
        return Nivel.NORMAL

    def actualizar_contador(self, estado: EstadoVariable, nivel: Nivel, ahora_ns: int) -> EstadoVariable:
        ultima = estado.ultima_lectura_ns
        if ultima is not None and ahora_ns < ultima:
            raise RelojInconsistenteError(f"ahora_ns {ahora_ns} es menor que {ultima}")
        if nivel is not Nivel.GRAVE:
            return replace(estado, nivel=nivel, inicio_grave_ns=None, ultima_lectura_ns=ahora_ns, orden_emitida=False)
        inicio = ahora_ns if estado.inicio_grave_ns is None else estado.inicio_grave_ns
        return replace(estado, nivel=nivel, inicio_grave_ns=inicio, ultima_lectura_ns=ahora_ns)

    def evaluar_parada(self, estado: EstadoVariable, nivel: Nivel, ahora_ns: int, es_vp: bool) -> bool:
        return (
            nivel is Nivel.GRAVE
            and estado.inicio_grave_ns is not None
            and ahora_ns - estado.inicio_grave_ns >= UMBRAL_PARADA_NS
            and es_vp
        )

    # ---- flujo de una lectura ----
    def procesar_lectura(self, lectura: Lectura, variable: Variable) -> ResultadoProceso:
        if lectura.diferida:
            self._insertar_seguro(self._registro_lectura(lectura))
            return ResultadoProceso(nivel=None, orden_emitida=False)
        with self._lock(variable.codigo):
            estado = self._estados.get(variable.codigo, EstadoVariable())
            try:
                nivel = self.clasificar(lectura, variable.umbral)
            except LecturaInvalidaError:
                return self._senal_invalida(lectura)
            ahora_ns = self._reloj.ahora_ns()
            try:
                nuevo = self.actualizar_contador(estado, nivel, ahora_ns)
            except RelojInconsistenteError:
                return ResultadoProceso(nivel=None, orden_emitida=False, error="RELOJ")
            nuevo, orden_emitida, falla_bd = self._emitir_parada_si_corresponde(nuevo, nivel, ahora_ns, variable)
            nuevo, falla_evento = self._registrar_cambio_de_nivel(estado, nuevo, cast(float, lectura.valor), variable)
            self._estados[variable.codigo] = nuevo
            return ResultadoProceso(nivel=nivel, orden_emitida=orden_emitida, error_persistencia=falla_bd or falla_evento)

    def reconocer(self, alerta_id: uuid.UUID, actor: str) -> EventoAlerta:
        evento = EventoAlerta(alerta_id, TipoEvento.RECONOCIDA, self._reloj.utc(), actor)
        self._repo.insertar(evento_a_registro(evento))
        return evento

    def escalar_pendientes(self, alertas: Sequence[Alerta], ahora_ns: int) -> list[EventoAlerta]:
        eventos: list[EventoAlerta] = []
        for alerta in alertas:
            if (
                alerta.nivel is Nivel.LEVE
                and alerta.reconocida_por is None
                and ahora_ns - alerta.inicio_ns > UMBRAL_ESCALA_NS
            ):
                evento = EventoAlerta(alerta.id, TipoEvento.ESCALADA, self._reloj.utc())
                self._repo.insertar(evento_a_registro(evento))
                escalada = Alerta(alerta.id, alerta.variable_codigo, Nivel.GRAVE, alerta.inicio_ns, alerta.valor_pico)
                self._notificador.notificar(escalada, _ROLES_POR_NIVEL[Nivel.GRAVE])
                eventos.append(evento)
        return eventos

    # ---- auxiliares ----
    def _lock(self, codigo: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(codigo, threading.Lock())

    def _registro_lectura(self, lectura: Lectura) -> RegistroInmutable:
        return RegistroInmutable(
            tipo="lectura",
            t_utc=lectura.t_utc,
            carga={
                "variable": lectura.variable_codigo,
                "valor": lectura.valor,
                "calidad": lectura.calidad.value,
                "diferida": lectura.diferida,
            },
        )

    def _insertar_seguro(self, registro: RegistroInmutable) -> bool:
        """Inserta y retorna True si la base de datos falló (la excepción se captura)."""
        try:
            self._repo.insertar(registro)
        except OperationalError:
            return True
        return False

    def _senal_invalida(self, lectura: Lectura) -> ResultadoProceso:
        evento = EventoAlerta(uuid.uuid4(), TipoEvento.SENAL_INVALIDA, self._reloj.utc())
        falla = self._insertar_seguro(evento_a_registro(evento))
        self._notificador.notificar_mensaje(
            "Señal inválida",
            {"variable": lectura.variable_codigo, "calidad": lectura.calidad.value},
            (Rol.SUPERVISOR, Rol.JEFE_MTTO),
        )
        return ResultadoProceso(nivel=None, orden_emitida=False, error="SENAL_INVALIDA", error_persistencia=falla)

    def _emitir_parada_si_corresponde(
        self, estado: EstadoVariable, nivel: Nivel, ahora_ns: int, variable: Variable
    ) -> tuple[EstadoVariable, bool, bool]:
        if estado.orden_emitida or not self.evaluar_parada(estado, nivel, ahora_ns, variable.es_variable_parada):
            return estado, False, False
        orden = OrdenParada(variable.codigo, self._reloj.utc(), "GRAVE sostenido 30 s")
        ack = self._canal.emitir(orden)  # la orden sale ANTES de persistir (D13)
        tipo = TipoEvento.ORDEN_PARADA if ack else TipoEvento.ORDEN_FALLIDA
        alerta_id = estado.alerta_id if estado.alerta_id is not None else uuid.uuid4()
        falla = self._insertar_seguro(evento_a_registro(EventoAlerta(alerta_id, tipo, orden.t_utc)))
        if not ack:
            self._notificador.notificar_mensaje(
                "Orden de parada sin confirmar", {"variable": variable.codigo}, (Rol.SUPERVISOR, Rol.JEFE_MTTO)
            )
        return replace(estado, orden_emitida=ack, alerta_id=alerta_id), ack, falla

    def _registrar_cambio_de_nivel(
        self, anterior: EstadoVariable, nuevo: EstadoVariable, valor: float, variable: Variable
    ) -> tuple[EstadoVariable, bool]:
        if nuevo.nivel == anterior.nivel:
            return nuevo, False
        if nuevo.nivel is Nivel.NORMAL:
            if nuevo.alerta_id is None:
                return nuevo, False
            evento = EventoAlerta(nuevo.alerta_id, TipoEvento.CERRADA, self._reloj.utc())
            falla = self._insertar_seguro(evento_a_registro(evento))
            return replace(nuevo, alerta_id=None), falla
        alerta_id = nuevo.alerta_id if nuevo.alerta_id is not None else uuid.uuid4()
        evento = EventoAlerta(alerta_id, TipoEvento.CREADA, self._reloj.utc())
        falla = self._insertar_seguro(evento_a_registro(evento))
        alerta = Alerta(alerta_id, variable.codigo, nuevo.nivel, nuevo.ultima_lectura_ns or 0, valor)
        self._notificador.notificar(alerta, _ROLES_POR_NIVEL[nuevo.nivel])
        return replace(nuevo, alerta_id=alerta_id), falla
