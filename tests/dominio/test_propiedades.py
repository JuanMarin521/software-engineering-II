"""HU-01: propiedades con Hypothesis sobre clasificar (entradas aleatorias, incluidos NaN e infinito)."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from gemelo.dominio.motor_alertas import MotorAlertas
from gemelo.dominio.tipos import Nivel, Umbral
from gemelo.errores import LecturaInvalidaError
from tests.dobles import FakeReloj, lectura

PRENSA = Umbral(225.0, 240.0)
MOTOR = MotorAlertas(FakeReloj(), None, None, None)  # type: ignore[arg-type]


@given(st.floats(allow_nan=True, allow_infinity=True))
def test_clasificar_lanza_o_retorna_un_nivel(valor):
    try:
        nivel = MOTOR.clasificar(lectura(valor), PRENSA)
    except LecturaInvalidaError:
        assert not math.isfinite(valor)
    else:
        assert isinstance(nivel, Nivel) and math.isfinite(valor)


@given(st.floats(allow_nan=False, allow_infinity=False), st.floats(allow_nan=False, allow_infinity=False))
def test_el_nivel_nunca_decrece_si_el_valor_aumenta(a, b):
    bajo, alto = sorted((a, b))
    assert MOTOR.clasificar(lectura(bajo), PRENSA) <= MOTOR.clasificar(lectura(alto), PRENSA)
