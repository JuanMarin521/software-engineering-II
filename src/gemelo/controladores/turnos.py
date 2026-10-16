"""Controlador de turnos: traduce las excepciones del cierre a códigos HTTP."""

from __future__ import annotations

from gemelo.dominio.gestor_turno import GestorTurno
from gemelo.dominio.tipos import RespuestaHTTP, Usuario
from gemelo.errores import CierreBloqueadoError, PermisoDenegadoError


class TurnosController:
    def __init__(self, gestor: GestorTurno) -> None:
        self._gestor = gestor

    def cerrar(self, turno_id: str, usuario: Usuario) -> RespuestaHTTP:
        try:
            self._gestor.cerrar_turno(turno_id, usuario)
        except PermisoDenegadoError:
            return RespuestaHTTP(403)
        except CierreBloqueadoError as exc:
            return RespuestaHTTP(409, {"motivo": exc.motivo.value})
        return RespuestaHTTP(200)
