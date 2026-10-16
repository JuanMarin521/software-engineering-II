"""Auditoría: todo intento rechazado deja un registro inmutable."""

from __future__ import annotations

from gemelo.dominio.puertos import Reloj, RepositorioHistorico
from gemelo.dominio.tipos import RegistroInmutable


class AuditoriaService:
    def __init__(self, repositorio: RepositorioHistorico, reloj: Reloj) -> None:
        self._repo = repositorio
        self._reloj = reloj

    def registrar(self, usuario_id: str, accion: str, resultado: str) -> None:
        self._repo.insertar(
            RegistroInmutable(
                "auditoria", self._reloj.utc(), {"usuario": usuario_id, "accion": accion, "resultado": resultado}
            )
        )
