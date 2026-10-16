"""HU-04: compuertas, reintentos y concurrencia del cierre de turno."""

from __future__ import annotations

import threading
import time

import pytest

from gemelo.dominio.gestor_turno import EstadoTurno, GestorTurno, InformeTurno, Turno
from gemelo.dominio.tipos import Rol, Usuario
from gemelo.errores import CierreBloqueadoError, ConsolidacionError, MotivoBloqueo, PermisoDenegadoError

SUPERVISOR = Usuario("sup1", Rol.SUPERVISOR)


@pytest.fixture
def turno() -> Turno:
    return Turno("T1", alertas_sin_reconocer=0, entrante_confirmado=True)


@pytest.fixture
def gestor(turno, repo, auditoria, notificador, reloj, mocker) -> GestorTurno:
    almacen = mocker.Mock()
    almacen.obtener.return_value = turno
    return GestorTurno(almacen, repo, auditoria, notificador, reloj)


@pytest.mark.ce("t_rol")
def test_rol_no_autorizado(gestor, auditoria, mocker):
    consolidar = mocker.spy(gestor, "consolidar")
    with pytest.raises(PermisoDenegadoError):
        gestor.cerrar_turno("T1", Usuario("op1", Rol.OPERARIO))
    auditoria.registrar.assert_called_once()
    consolidar.assert_not_called()


@pytest.mark.ce("t_pend")
def test_alertas_sin_reconocer_bloquean(gestor, turno):
    turno.alertas_sin_reconocer = 1
    turno.ids_alertas_pendientes = ("a1",)
    with pytest.raises(CierreBloqueadoError) as exc:
        gestor.cerrar_turno("T1", SUPERVISOR)
    assert exc.value.motivo is MotivoBloqueo.ALERTAS_PENDIENTES and exc.value.detalle == ("a1",)
    assert turno.estado is EstadoTurno.ABIERTO


@pytest.mark.ce("t_ent")
def test_entrante_sin_confirmar_bloquea(gestor, turno):
    turno.entrante_confirmado = False
    with pytest.raises(CierreBloqueadoError) as exc:
        gestor.cerrar_turno("T1", SUPERVISOR)
    assert exc.value.motivo is MotivoBloqueo.ENTRANTE_SIN_CONFIRMAR


@pytest.mark.ce("t_ok")
def test_cierre_exitoso(gestor, turno, repo, notificador, mocker):
    consolidar = mocker.spy(gestor, "consolidar")
    assert gestor.cerrar_turno("T1", SUPERVISOR).ok is True
    assert consolidar.call_count == 1 and repo.insertar.call_count == 1
    assert turno.estado is EstadoTurno.CERRADO
    roles = notificador.notificar_mensaje.call_args.args[2]
    assert set(roles) == {Rol.PLANEADOR, Rol.GERENTE}


@pytest.mark.ce("t_retry")
def test_falla_y_recuperacion(gestor, turno, mocker):
    consolidar = mocker.patch.object(gestor, "consolidar", side_effect=[ConsolidacionError(), InformeTurno("T1", {})])
    gestor.cerrar_turno("T1", SUPERVISOR)
    assert consolidar.call_count == 2 and turno.estado is EstadoTurno.CERRADO


@pytest.mark.ce("t_agota")
def test_reintentos_agotados(gestor, turno, notificador, mocker):
    consolidar = mocker.patch.object(gestor, "consolidar", side_effect=[ConsolidacionError()] * 3)
    with pytest.raises(CierreBloqueadoError) as exc:
        gestor.cerrar_turno("T1", SUPERVISOR)
    assert exc.value.motivo is MotivoBloqueo.CONSOLIDACION_FALLIDA
    assert consolidar.call_count == 3 and turno.estado is EstadoTurno.ABIERTO
    assert Rol.ADMIN in notificador.notificar_mensaje.call_args.args[2]


@pytest.mark.ce("t_conc")
def test_cierres_concurrentes_generan_un_solo_informe(gestor, repo, mocker):
    def lento(turno: Turno) -> InformeTurno:
        time.sleep(0.05)
        return InformeTurno(turno.id, {})

    mocker.patch.object(gestor, "consolidar", side_effect=lento)
    resultados: list[object] = []

    def cerrar() -> None:
        try:
            resultados.append(gestor.cerrar_turno("T1", SUPERVISOR))
        except CierreBloqueadoError as exc:
            resultados.append(exc.motivo)

    hilos = [threading.Thread(target=cerrar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert repo.insertar.call_count == 1
    assert MotivoBloqueo.TURNO_EN_CIERRE in resultados


def test_consolidar_produce_un_informe(gestor, turno):
    assert gestor.consolidar(turno).turno_id == "T1"
