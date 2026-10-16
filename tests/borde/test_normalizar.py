"""HU-01: guardas de AgenteBorde.normalizar y decodificación de registros Modbus."""

from __future__ import annotations

import math
import struct

import pytest

from gemelo.borde.agente import AgenteBorde
from gemelo.borde.conectores import OrdenPalabras, decodificar_registros
from gemelo.dominio.tipos import CalidadSenal, Nivel, Umbral, Variable
from tests.dobles import lectura, variable_presion


@pytest.fixture
def agente(conector, reloj, buffer, mocker) -> AgenteBorde:
    return AgenteBorde(conector, reloj, [variable_presion()], buffer, envio=mocker.Mock(), dormir=mocker.Mock())


@pytest.mark.ce("n_none")
def test_crudo_nulo_es_bad_nulo(agente):
    resultado = agente.normalizar(None, variable_presion())
    assert resultado.valor is None and resultado.calidad is CalidadSenal.BAD_NULO


@pytest.mark.ce("n_centinela")
@pytest.mark.parametrize("centinela", [32767, -32768])
def test_centinela_es_desbordamiento(agente, centinela):
    resultado = agente.normalizar(centinela, variable_presion())
    assert resultado.valor is None and resultado.calidad is CalidadSenal.BAD_DESBORDAMIENTO


@pytest.mark.ce("n_nonfinito")
@pytest.mark.parametrize("crudo", [float("nan"), float("inf"), float("-inf"), 10**400])
def test_no_finito_no_se_propaga(agente, crudo):
    resultado = agente.normalizar(crudo, variable_presion())
    assert resultado.valor is None and resultado.calidad is CalidadSenal.BAD_NO_FINITO


@pytest.mark.ce("n_denormal")
def test_subnormal_se_rechaza(agente):
    resultado = agente.normalizar(2.39e-41, variable_presion())
    assert resultado.valor is None and resultado.calidad is CalidadSenal.BAD_DENORMAL


@pytest.mark.ce("n_rango")
@pytest.mark.parametrize("crudo", [-0.1, 1e38])
def test_fuera_de_rango_fisico(agente, crudo):
    resultado = agente.normalizar(crudo, variable_presion())
    assert resultado.valor is None and resultado.calidad is CalidadSenal.BAD_FUERA_RANGO


@pytest.mark.ce("n_ok")
@pytest.mark.parametrize("crudo, esperado", [(87, 87.0), (87.5, 87.5)])
def test_valor_valido_retorna_float(agente, crudo, esperado):
    resultado = agente.normalizar(crudo, variable_presion())
    assert resultado.calidad is CalidadSenal.GOOD
    assert type(resultado.valor) is float and resultado.valor == esperado


@pytest.mark.ce("n_float32")
def test_float32_se_redondea_a_la_resolucion(agente, motor):
    crudo = struct.unpack(">f", struct.pack(">f", 0.1))[0]
    assert crudo == 0.10000000149011612
    variable = Variable("V-01", False, Umbral(0.05, 0.1), 0.0, 10.0, resolucion=3)
    leida = agente.normalizar(crudo, variable)
    assert leida.valor == 0.1
    assert motor.clasificar(leida, variable.umbral) is Nivel.LEVE  # sin redondeo sería GRAVE


@pytest.mark.ce("n_modbus")
def test_orden_de_palabras_invertido_se_detecta(agente):
    assert decodificar_registros([0x42AE, 0x0000], OrdenPalabras.ALTO_BAJO) == 87.0
    invertido = decodificar_registros([0x0000, 0x42AE], OrdenPalabras.ALTO_BAJO)
    assert math.isclose(invertido, 2.39e-41, rel_tol=1e-2)
    assert agente.normalizar(invertido, variable_presion()).calidad is CalidadSenal.BAD_DENORMAL


def test_orden_de_palabras_configurable():
    assert decodificar_registros([0x0000, 0x42AE], OrdenPalabras.BAJO_ALTO) == 87.0


def test_lectura_helper_es_valida():
    assert lectura(1.0).valor == 1.0
