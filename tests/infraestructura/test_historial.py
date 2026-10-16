"""HU-05: el historial es inmutable; la purga por retención es la única ruta de borrado."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from gemelo.controladores.historial import HistorialController
from gemelo.dominio.puertos import FiltroHistorico, PoliticaRetencion, TokenJob
from gemelo.dominio.tipos import RegistroInmutable, Rol, Usuario
from gemelo.errores import PermisoDenegadoError, PoliticaInvalidaError
from gemelo.infraestructura.auditoria import AuditoriaService
from gemelo.infraestructura.repositorio import RepositorioEnMemoria
from gemelo.infraestructura.retencion import JobRetencion
from tests.dobles import T0_UTC


@pytest.mark.ce("h_403")
@pytest.mark.parametrize("metodo", ["DELETE", "PUT", "PATCH"])
@pytest.mark.parametrize("rol", list(Rol))
def test_modificacion_manual_siempre_403(auditoria, rol, metodo):
    respuesta = HistorialController(auditoria).rechazar_modificacion(metodo, Usuario("u1", rol))
    assert respuesta.status == 403
    auditoria.registrar.assert_called_once_with("u1", metodo, "DENEGADO")


@pytest.mark.ce("h_guard")
def test_ninguna_ruta_de_escritura_en_el_repositorio():
    publicos = [n for n in dir(RepositorioEnMemoria) if not n.startswith("_")]
    prohibidos = [n for n in publicos if n.startswith(("update", "delete", "remove", "drop"))]
    assert prohibidos == []
    assert set(publicos) == {"insertar", "consultar", "purgar_por_retencion"}


@pytest.mark.ce("h_frozen")
def test_registro_inmutable():
    registro = RegistroInmutable("x", T0_UTC, {"k": 0})
    with pytest.raises(dataclasses.FrozenInstanceError):
        registro.tipo = "y"  # type: ignore[misc]
    with pytest.raises(TypeError):
        registro.carga["k"] = 1  # type: ignore[index]


@pytest.mark.ce("h_purga")
def test_purga_solo_con_token_y_politica_validos():
    repo = RepositorioEnMemoria()
    ahora = datetime.now(UTC)
    repo.insertar(RegistroInmutable("viejo", ahora - timedelta(days=100)))
    repo.insertar(RegistroInmutable("nuevo", ahora - timedelta(days=10)))
    with pytest.raises(PermisoDenegadoError):
        repo.purgar_por_retencion(PoliticaRetencion(90), None)
    with pytest.raises(PoliticaInvalidaError):
        repo.purgar_por_retencion(PoliticaRetencion(0), TokenJob("job"))
    assert len(repo.consultar(FiltroHistorico())) == 2
    assert JobRetencion(repo, PoliticaRetencion(90)).ejecutar() == 1
    assert [r.tipo for r in repo.consultar(FiltroHistorico())] == ["nuevo"]


@pytest.mark.ce("h_bd")
@pytest.mark.integracion
def test_rol_de_la_aplicacion_sin_update_ni_delete():
    import os

    dsn = os.environ.get("GEMELO_PG_DSN")
    psycopg = pytest.importorskip("psycopg")
    if not dsn:
        pytest.skip("defina GEMELO_PG_DSN con el rol de la aplicación (ver db/esquema.sql)")
    with psycopg.connect(dsn) as con:
        for sentencia in ("UPDATE evento_alerta SET evento = 'X'", "DELETE FROM evento_alerta"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                con.execute(sentencia)
            con.rollback()


def test_auditoria_y_consulta_filtrada(reloj):
    repo = RepositorioEnMemoria()
    AuditoriaService(repo, reloj).registrar("u1", "DELETE", "DENEGADO")
    repo.insertar(RegistroInmutable("otro", T0_UTC))
    registros = repo.consultar(FiltroHistorico(tipo="auditoria"))
    assert len(registros) == 1 and registros[0].carga["usuario"] == "u1"


def test_consulta_por_alerta_id():
    from uuid import uuid4

    repo = RepositorioEnMemoria()
    alerta = uuid4()
    repo.insertar(RegistroInmutable("evento_alerta", T0_UTC, {"alerta_id": str(alerta)}))
    repo.insertar(RegistroInmutable("evento_alerta", T0_UTC, {"alerta_id": str(uuid4())}))
    assert len(repo.consultar(FiltroHistorico(alerta_id=alerta))) == 1
