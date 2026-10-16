"""Trabajo de retención: única ruta que elimina datos del historial."""

from __future__ import annotations

from gemelo.dominio.puertos import PoliticaRetencion, RepositorioHistorico, TokenJob


class JobRetencion:
    def __init__(self, repositorio: RepositorioHistorico, politica: PoliticaRetencion) -> None:
        self._repo = repositorio
        self._politica = politica
        self._token = TokenJob("job_retencion")

    def ejecutar(self) -> int:
        return self._repo.purgar_por_retencion(self._politica, self._token)
