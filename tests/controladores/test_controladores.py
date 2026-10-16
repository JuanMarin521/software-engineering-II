"""HU-02, HU-04 y ingesta: orden de evaluación y códigos HTTP de los controladores."""

from __future__ import annotations

from uuid import uuid4

import pytest

from gemelo.controladores.alertas import AlertasController
from gemelo.controladores.ingesta import IngestaController, LoteLecturas
from gemelo.controladores.turnos import TurnosController
from gemelo.dominio.autorizacion import ServicioAutorizacion
from gemelo.dominio.motor_alertas import MotorAlertas
from gemelo.dominio.tipos import RegistroInmutable, Rol, Usuario
from gemelo.errores import CierreBloqueadoError, MotivoBloqueo, PermisoDenegadoError
from tests.dobles import T0_UTC, lectura, variable_presion


@pytest.fixture
def controlador(auditoria, repo, motor) -> AlertasController:
    return AlertasController(ServicioAutorizacion(), auditoria, repo, motor)


def _evento(nombre: str) -> RegistroInmutable:
    return RegistroInmutable("evento_alerta", T0_UTC, {"evento": nombre})


@pytest.mark.ce("a_403")
def test_sin_autorizacion_no_consulta_el_estado(controlador, auditoria, repo):
    respuesta = controlador.reconocer(uuid4(), Usuario("ins1", Rol.INSPECTOR))
    assert respuesta.status == 403
    auditoria.registrar.assert_called_once()
    repo.consultar.assert_not_called()


@pytest.mark.ce("a_404")
def test_alerta_inexistente(controlador, repo):
    repo.consultar.return_value = []
    assert controlador.reconocer(uuid4(), Usuario("sup1", Rol.SUPERVISOR)).status == 404
    repo.insertar.assert_not_called()


@pytest.mark.ce("a_409")
def test_alerta_cerrada(controlador, repo):
    repo.consultar.return_value = [_evento("CREADA"), _evento("CERRADA")]
    assert controlador.reconocer(uuid4(), Usuario("sup1", Rol.SUPERVISOR)).status == 409
    repo.insertar.assert_not_called()


@pytest.mark.ce("a_200")
def test_reconocimiento_exitoso(controlador, repo):
    repo.consultar.return_value = [_evento("CREADA")]
    respuesta = controlador.reconocer(uuid4(), Usuario("sup1", Rol.SUPERVISOR))
    assert respuesta.status == 200
    registro = repo.insertar.call_args.args[0]
    assert registro.carga["evento"] == "RECONOCIDA" and registro.carga["actor"] == "sup1"


def test_turnos_traduce_excepciones_a_http(mocker):
    gestor = mocker.Mock()
    controlador = TurnosController(gestor)
    usuario = Usuario("sup1", Rol.SUPERVISOR)
    assert controlador.cerrar("T1", usuario).status == 200
    gestor.cerrar_turno.side_effect = PermisoDenegadoError("x")
    assert controlador.cerrar("T1", usuario).status == 403
    gestor.cerrar_turno.side_effect = CierreBloqueadoError(MotivoBloqueo.ALERTAS_PENDIENTES)
    respuesta = controlador.cerrar("T1", usuario)
    assert respuesta.status == 409 and respuesta.cuerpo["motivo"] == "ALERTAS_PENDIENTES"


def test_ingesta_valida_el_lote_y_procesa_cada_lectura(mocker, repo, reloj, canal, notificador):
    motor = MotorAlertas(reloj, repo, canal, notificador)
    controlador = IngestaController(motor, {"PRES-01": variable_presion()}, repo)
    assert controlador.recibir_lote(LoteLecturas([])).status == 422
    assert controlador.recibir_lote(LoteLecturas([lectura(1.0)] * 501)).status == 422
    desconocida = lectura(1.0)
    desconocida = type(desconocida)("OTRA", 1.0, 0, desconocida.t_utc, desconocida.calidad)
    respuesta = controlador.recibir_lote(LoteLecturas([lectura(100.0), desconocida]))
    assert respuesta.status == 200 and dict(respuesta.cuerpo) == {"aceptadas": 1, "rechazadas": 1}
