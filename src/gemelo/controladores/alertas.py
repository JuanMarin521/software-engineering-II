"""Controlador de alertas: autorización, existencia y estado, en ese orden (D14)."""

from __future__ import annotations

from uuid import UUID

from gemelo.dominio.autorizacion import ServicioAutorizacion
from gemelo.dominio.motor_alertas import MotorAlertas
from gemelo.dominio.puertos import Auditoria, FiltroHistorico, RepositorioHistorico
from gemelo.dominio.tipos import RespuestaHTTP, TipoEvento, Usuario


class AlertasController:
    def __init__(
        self,
        autorizacion: ServicioAutorizacion,
        auditoria: Auditoria,
        repositorio: RepositorioHistorico,
        motor: MotorAlertas,
    ) -> None:
        self._autorizacion = autorizacion
        self._auditoria = auditoria
        self._repo = repositorio
        self._motor = motor

    def reconocer(self, alerta_id: UUID, usuario: Usuario) -> RespuestaHTTP:
        if not self._autorizacion.puede_reconocer(usuario.rol):
            self._auditoria.registrar(usuario.id, "RECONOCER_ALERTA", "DENEGADO")
            return RespuestaHTTP(403)
        eventos = self._repo.consultar(FiltroHistorico(tipo="evento_alerta", alerta_id=alerta_id))
        if not eventos:
            return RespuestaHTTP(404)
        if eventos[-1].carga.get("evento") == TipoEvento.CERRADA.value:
            return RespuestaHTTP(409)
        evento = self._motor.reconocer(alerta_id, usuario.id)
        return RespuestaHTTP(200, {"evento": evento.tipo.value})
