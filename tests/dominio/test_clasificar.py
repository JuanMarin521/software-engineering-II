"""HU-01: MotorAlertas.clasificar y la invariante de Umbral."""

from __future__ import annotations

import math

import pytest

from gemelo.dominio.tipos import Nivel, Umbral
from gemelo.errores import LecturaInvalidaError, UmbralInvalidoError
from tests.dobles import lectura

PRENSA = Umbral(225.0, 240.0)


@pytest.mark.ce("k_none")
def test_lectura_nula_lanza(motor):
    with pytest.raises(LecturaInvalidaError):
        motor.clasificar(lectura(None), PRENSA)


@pytest.mark.ce("k_nan")
def test_nan_no_se_clasifica_como_normal(motor):
    with pytest.raises(LecturaInvalidaError):
        motor.clasificar(lectura(float("nan")), PRENSA)


@pytest.mark.ce("k_inf")
def test_infinito_lanza(motor):
    with pytest.raises(LecturaInvalidaError):
        motor.clasificar(lectura(float("inf")), PRENSA)


@pytest.mark.ce("k_adv")
@pytest.mark.parametrize(
    "valor, esperado",
    [(224.9, Nivel.NORMAL), (225.0, Nivel.NORMAL), (math.nextafter(225.0, math.inf), Nivel.LEVE)],
)
def test_frontera_de_advertencia(motor, valor, esperado):
    assert motor.clasificar(lectura(valor), PRENSA) is esperado


@pytest.mark.ce("k_crit")
@pytest.mark.parametrize("valor, esperado", [(240.0, Nivel.LEVE), (math.nextafter(240.0, math.inf), Nivel.GRAVE)])
def test_frontera_critica(motor, valor, esperado):
    assert motor.clasificar(lectura(valor), PRENSA) is esperado


@pytest.mark.ce("k_vib")
@pytest.mark.parametrize("valor, esperado", [(4.5, Nivel.NORMAL), (4.6, Nivel.LEVE), (7.1, Nivel.LEVE), (7.2, Nivel.GRAVE)])
def test_umbrales_de_vibracion(motor, valor, esperado):
    assert motor.clasificar(lectura(valor), Umbral(4.5, 7.1)) is esperado


@pytest.mark.ce("k_umbral")
def test_umbral_inconsistente_no_existe():
    with pytest.raises(UmbralInvalidoError):
        Umbral(advertencia=240.0, critico=225.0)
    with pytest.raises(UmbralInvalidoError):
        Umbral(advertencia=float("nan"), critico=225.0)
