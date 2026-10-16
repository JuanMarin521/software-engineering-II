"""HU-02: autorización por rol y escalamiento de alertas Leves."""

from __future__ import annotations

import sys
import time
from uuid import uuid4

import pytest

from gemelo.dominio.autorizacion import ServicioAutorizacion
from gemelo.dominio.tipos import Alerta, Nivel, Rol, TipoEvento
from gemelo.errores import RolDesconocidoError
from tests.dobles import NS

MIN10 = 600 * NS


@pytest.mark.ce("a_ok")
@pytest.mark.parametrize("rol", [Rol.OPERARIO, Rol.SUPERVISOR, Rol.JEFE_MTTO])
def test_roles_permitidos(rol):
    assert ServicioAutorizacion().puede_reconocer(rol) is True


@pytest.mark.ce("a_no")
@pytest.mark.parametrize("rol", [Rol.INSPECTOR, Rol.PLANEADOR, Rol.GERENTE, Rol.ADMIN])
def test_roles_no_permitidos(rol):
    assert ServicioAutorizacion().puede_reconocer(rol) is False


@pytest.mark.ce("a_none")
def test_rol_nulo_o_desconocido():
    assert ServicioAutorizacion().puede_reconocer(None) is False
    with pytest.raises(RolDesconocidoError):
        Rol.desde_texto("admin ")
    assert Rol.desde_texto("ADMIN") is Rol.ADMIN


def _leve(inicio_ns: int = 0, reconocida: str | None = None, nivel: Nivel = Nivel.LEVE) -> Alerta:
    return Alerta(uuid4(), "PRES-01", nivel, inicio_ns, 230.0, reconocida)


@pytest.mark.ce("s_front")
@pytest.mark.parametrize("edad, cantidad", [(MIN10 - 1, 0), (MIN10, 0), (MIN10 + 1, 1)])
def test_frontera_de_diez_minutos_estricta(motor, edad, cantidad):
    eventos = motor.escalar_pendientes((_leve(),), edad)
    assert len(eventos) == cantidad
    assert all(e.tipo is TipoEvento.ESCALADA for e in eventos)


@pytest.mark.ce("s_idem")
def test_reconocidas_y_graves_no_escalan(motor):
    alertas = (_leve(reconocida="u1"), _leve(nivel=Nivel.GRAVE))
    assert motor.escalar_pendientes(alertas, 12 * 60 * NS) == []


@pytest.mark.ce("s_masa")
@pytest.mark.rendimiento
def test_vacia_y_masiva_sin_mutar_la_entrada(reloj):
    from gemelo.dominio.motor_alertas import MotorAlertas

    class Nulo:
        """Doble ligero sin registro de llamadas: mide la lógica y no el costo de Mock."""

        def __getattr__(self, nombre):
            return lambda *a, **k: True

    motor = MotorAlertas(reloj, Nulo(), Nulo(), Nulo())
    assert motor.escalar_pendientes((), MIN10 * 2) == []
    alertas = tuple(_leve(inicio_ns=0, reconocida="u" if i % 4 == 0 else None) for i in range(10_000))
    copia = tuple(alertas)
    inicio = time.perf_counter()
    eventos = motor.escalar_pendientes(alertas, MIN10 + 1)
    if sys.gettrace() is None:  # bajo coverage la instrumentación inflaría el tiempo medido
        assert time.perf_counter() - inicio < 0.25
    assert len(eventos) == 7_500 and alertas == copia
