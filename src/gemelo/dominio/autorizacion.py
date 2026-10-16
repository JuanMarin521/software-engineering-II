"""Autorización de RN003: qué roles pueden reconocer alertas."""

from __future__ import annotations

from typing import Optional

from gemelo.dominio.tipos import Rol

ROLES_RECONOCEDORES = frozenset({Rol.OPERARIO, Rol.SUPERVISOR, Rol.JEFE_MTTO})


class ServicioAutorizacion:
    def puede_reconocer(self, rol: Optional[Rol]) -> bool:
        if rol is None:
            return False
        return rol in ROLES_RECONOCEDORES
