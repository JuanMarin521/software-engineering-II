"""Fixtures y trazabilidad: la marca ce("clave") enlaza cada prueba con su caso CE, su HU y su tarea JIRA."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gemelo.dominio.puertos import (
    Auditoria,
    CanalComandos,
    ConectorPLC,
    NotificadorService,
    RepositorioHistorico,
)
from tests.dobles import FakeReloj

_DIR = Path(__file__).parent / "trazabilidad"
_CASOS = {c["k"]: c for c in json.loads((_DIR / "casos.json").read_text(encoding="utf-8"))["cases"]}
_JIRA = json.loads((_DIR / "jira.json").read_text(encoding="utf-8")) if (_DIR / "jira.json").exists() else {}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ce(clave): caso de prueba estructural del RTF3 (CE-xx)")
    config.addinivalue_line("markers", "hu(id): historia de usuario")
    config.addinivalue_line("markers", "jira(clave): tarea de JIRA")
    config.addinivalue_line("markers", "integracion: requiere servicios externos (PostgreSQL, simuladores)")
    config.addinivalue_line("markers", "rendimiento: mide tiempos de ejecución")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        marca = item.get_closest_marker("ce")
        if marca is None:
            continue
        caso = _CASOS[marca.args[0]]
        item.add_marker(pytest.mark.hu(caso["hu"]))
        item.user_properties.append(("caso", caso["id"]))
        clave_jira = _JIRA.get(marca.args[0])
        if clave_jira:
            item.add_marker(pytest.mark.jira(clave_jira))
            item.user_properties.append(("jira", clave_jira))


@pytest.fixture
def reloj() -> FakeReloj:
    return FakeReloj()


@pytest.fixture
def repo(mocker):
    return mocker.create_autospec(RepositorioHistorico, instance=True)


@pytest.fixture
def canal(mocker):
    mock = mocker.create_autospec(CanalComandos, instance=True)
    mock.emitir.return_value = True
    return mock


@pytest.fixture
def notificador(mocker):
    return mocker.create_autospec(NotificadorService, instance=True)


@pytest.fixture
def auditoria(mocker):
    return mocker.create_autospec(Auditoria, instance=True)


@pytest.fixture
def conector(mocker):
    return mocker.create_autospec(ConectorPLC, instance=True)


@pytest.fixture
def motor(reloj, repo, canal, notificador):
    from gemelo.dominio.motor_alertas import MotorAlertas

    return MotorAlertas(reloj, repo, canal, notificador)


@pytest.fixture
def buffer():
    from gemelo.borde.buffer import BufferLocal

    return BufferLocal(":memory:")
