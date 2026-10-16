"""HU-01: reintentos, ciclo completo y buffer local, con el conector PLC simulado (pytest-mock)."""

from __future__ import annotations

import pytest

from gemelo.borde.agente import AgenteBorde
from gemelo.borde.conectores import ConectorModbusTCP, ConectorOPCUA
from gemelo.dominio.tipos import CalidadSenal, Umbral, Variable
from gemelo.errores import SinComunicacionError
from tests.dobles import lectura, variable_presion


@pytest.fixture
def agente(conector, reloj, buffer, mocker) -> AgenteBorde:
    return AgenteBorde(conector, reloj, [variable_presion()], buffer, envio=mocker.Mock(), dormir=mocker.Mock())


@pytest.mark.ce("r_retry")
def test_timeout_y_recuperacion(agente, conector):
    conector.leer.side_effect = [TimeoutError(), 87.5]
    assert agente.leer_con_reintentos("PRES-01") == 87.5
    assert conector.leer.call_count == 2


@pytest.mark.ce("r_agota")
def test_reintentos_agotados(agente, conector):
    conector.leer.side_effect = [TimeoutError()] * 3
    with pytest.raises(SinComunicacionError):
        agente.leer_con_reintentos("PRES-01")
    assert conector.leer.call_count == 3


@pytest.mark.ce("r_conn")
def test_interrupcion_de_conexion_reconecta(agente, conector):
    conector.leer.side_effect = [ConnectionResetError(), 87.5]
    assert agente.leer_con_reintentos("PRES-01") == 87.5
    conector.reconectar.assert_called_once()


def test_espera_creciente_entre_intentos(agente, conector):
    conector.leer.side_effect = [TimeoutError(), TimeoutError(), 1.0]
    agente.leer_con_reintentos("PRES-01")
    assert [c.args[0] for c in agente.dormir.call_args_list] == pytest.approx([0.1, 0.2])


@pytest.mark.ce("c_mixto")
def test_ciclo_con_una_variable_sin_comunicacion(conector, reloj, buffer, mocker):
    a = Variable("A", False, Umbral(1.0, 2.0), 0.0, 10.0)
    b = Variable("B", False, Umbral(1.0, 2.0), 0.0, 10.0)
    conector.leer.side_effect = lambda codigo: 5.0 if codigo == "B" else (_ for _ in ()).throw(TimeoutError())
    agente = AgenteBorde(conector, reloj, [a, b], buffer, envio=mocker.Mock(), dormir=mocker.Mock())
    lecturas = agente.ejecutar_ciclo()
    assert len(lecturas) == 2
    assert lecturas[0].valor is None and lecturas[0].calidad is CalidadSenal.BAD_SIN_COMUNICACION
    assert lecturas[1].calidad is CalidadSenal.GOOD


@pytest.mark.ce("e_buffer")
def test_backend_caido_no_pierde_lecturas(conector, reloj, buffer, mocker):
    envio = mocker.Mock(side_effect=ConnectionError("backend caído"))
    espia = mocker.spy(buffer, "guardar")
    agente = AgenteBorde(conector, reloj, [variable_presion()], buffer, envio=envio, dormir=mocker.Mock())
    lote = [lectura(100.0, 1), lectura(101.0, 2)]
    assert agente.enviar_lote(lote) is False
    assert espia.call_count == 1
    envio.side_effect = None
    assert agente.enviar_lote([lectura(102.0, 3)]) is True
    reenviadas = envio.call_args_list[-1].args[0]
    assert [x.valor for x in reenviadas] == [100.0, 101.0]
    assert all(x.diferida for x in reenviadas)


def test_reenvio_que_falla_vuelve_al_buffer(conector, reloj, buffer, mocker):
    envio = mocker.Mock(side_effect=[ConnectionError(), None, ConnectionError()])
    agente = AgenteBorde(conector, reloj, [variable_presion()], buffer, envio=envio, dormir=mocker.Mock())
    agente.enviar_lote([lectura(1.0, 1)])
    assert agente.enviar_lote([lectura(2.0, 2)]) is False
    assert len(buffer.drenar()) == 1


def test_adaptadores_delegan_en_el_cliente(mocker):
    opc = mocker.Mock()
    opc.leer_nodo.return_value = 12.5
    assert ConectorOPCUA(opc).leer("N1") == 12.5
    ConectorOPCUA(opc).reconectar()
    opc.reconectar.assert_called_once()
    modbus = mocker.Mock()
    modbus.leer_registros.side_effect = [[0x42AE, 0], [40000], [123]]
    conector = ConectorModbusTCP(modbus)
    assert conector.leer("R1") == 87.0
    assert conector.leer("R2") == 40000 - 65536  # int16 con signo
    assert conector.leer("R3") == 123
    conector.reconectar()
    modbus.reconectar.assert_called_once()
