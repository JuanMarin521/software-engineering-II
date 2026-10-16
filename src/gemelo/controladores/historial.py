"""El historial es inmutable: cualquier método de escritura se rechaza, también para el administrador (RN010)."""

from __future__ import annotations

from gemelo.dominio.puertos import Auditoria
from gemelo.dominio.tipos import RespuestaHTTP, Usuario


class HistorialController:
    def __init__(self, auditoria: Auditoria) -> None:
        self._auditoria = auditoria

    def rechazar_modificacion(self, metodo: str, usuario: Usuario) -> RespuestaHTTP:
        self._auditoria.registrar(usuario.id, metodo, "DENEGADO")
        return RespuestaHTTP(403)
