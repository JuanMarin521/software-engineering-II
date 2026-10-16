"""Repositorio del historial. Solo expone insertar, consultar y la purga por retención (RN010)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Optional

from gemelo.dominio.puertos import FiltroHistorico, PoliticaRetencion, TokenJob
from gemelo.dominio.tipos import RegistroInmutable
from gemelo.errores import PermisoDenegadoError, PoliticaInvalidaError


class RepositorioEnMemoria:
    """Adaptador en memoria. El adaptador PostgreSQL aplica además privilegios sin UPDATE ni DELETE."""

    def __init__(self) -> None:
        self._registros: list[RegistroInmutable] = []
        self._lock = threading.Lock()

    def insertar(self, registro: RegistroInmutable) -> None:
        with self._lock:
            self._registros.append(registro)

    def consultar(self, filtro: FiltroHistorico) -> list[RegistroInmutable]:
        with self._lock:
            resultado = list(self._registros)
        if filtro.tipo is not None:
            resultado = [r for r in resultado if r.tipo == filtro.tipo]
        if filtro.alerta_id is not None:
            resultado = [r for r in resultado if r.carga.get("alerta_id") == str(filtro.alerta_id)]
        return resultado

    def purgar_por_retencion(self, politica: PoliticaRetencion, token: Optional[TokenJob]) -> int:
        if not isinstance(token, TokenJob):
            raise PermisoDenegadoError("la purga exige un TokenJob")
        if politica.dias <= 0:
            raise PoliticaInvalidaError("dias debe ser mayor que cero")
        corte = datetime.now(UTC) - timedelta(days=politica.dias)
        with self._lock:
            antes = len(self._registros)
            self._registros = [r for r in self._registros if r.t_utc >= corte]
            return antes - len(self._registros)
