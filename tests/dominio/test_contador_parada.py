"""HU-01: actualizar_contador, evaluar_parada (MC/DC) y procesar_lectura."""

from __future__ import annotations

import pytest

from gemelo.constantes import UMBRAL_PARADA_NS
from gemelo.dominio.tipos import EstadoVariable, Nivel
from gemelo.errores import OperationalError, RelojInconsistenteError
from tests.dobles import NS, lectura, variable_presion

T0 = 5 * NS


@pytest.mark.ce("u_inicio")
def test_grave_sin_contador_lo_inicia(motor):
    estado = EstadoVariable()
    nuevo = motor.actualizar_contador(estado, Nivel.GRAVE, T0)
    assert nuevo.inicio_grave_ns == T0 and estado.inicio_grave_ns is None


@pytest.mark.ce("u_cont")
def test_grave_con_contador_lo_conserva(motor):
    estado = EstadoVariable(Nivel.GRAVE, inicio_grave_ns=T0, ultima_lectura_ns=T0)
    assert motor.actualizar_contador(estado, Nivel.GRAVE, T0 + 10 * NS).inicio_grave_ns == T0


@pytest.mark.ce("u_reset")
@pytest.mark.parametrize("nivel", [Nivel.LEVE, Nivel.NORMAL])
def test_retorno_a_leve_o_normal_reinicia(motor, nivel):
    estado = EstadoVariable(Nivel.GRAVE, inicio_grave_ns=T0, ultima_lectura_ns=T0, orden_emitida=True)
    nuevo = motor.actualizar_contador(estado, nivel, T0 + NS)
    assert nuevo.inicio_grave_ns is None and nuevo.orden_emitida is False


@pytest.mark.ce("u_reloj")
def test_reloj_que_retrocede_lanza(motor):
    estado = EstadoVariable(ultima_lectura_ns=5 * NS)
    with pytest.raises(RelojInconsistenteError):
        motor.actualizar_contador(estado, Nivel.GRAVE, 4 * NS)
    assert estado.ultima_lectura_ns == 5 * NS


@pytest.mark.ce("u_inter")
def test_intermitencia_reinicia_el_contador(motor):
    estado = EstadoVariable()
    secuencia = [Nivel.GRAVE] * 21 + [Nivel.NORMAL] + [Nivel.GRAVE] * 21
    for i, nivel in enumerate(secuencia):
        estado = motor.actualizar_contador(estado, nivel, i * NS)
    ahora = (len(secuencia) - 1) * NS
    assert estado.inicio_grave_ns is not None
    assert ahora - estado.inicio_grave_ns == 20 * NS
    assert motor.evaluar_parada(estado, Nivel.GRAVE, ahora, True) is False


def _base(inicio: int | None = 0) -> EstadoVariable:
    return EstadoVariable(Nivel.GRAVE, inicio_grave_ns=inicio)


@pytest.mark.ce("p_base")
def test_mcdc_fila_base(motor):
    assert motor.evaluar_parada(_base(), Nivel.GRAVE, UMBRAL_PARADA_NS, True) is True


@pytest.mark.ce("p_nivel")
def test_mcdc_nivel(motor):
    assert motor.evaluar_parada(_base(), Nivel.LEVE, UMBRAL_PARADA_NS, True) is False


@pytest.mark.ce("p_inicio")
def test_mcdc_sin_inicio_no_lanza_typeerror(motor):
    assert motor.evaluar_parada(_base(None), Nivel.GRAVE, UMBRAL_PARADA_NS, True) is False


@pytest.mark.ce("p_29")
def test_mcdc_duracion_y_frontera(motor):
    assert motor.evaluar_parada(_base(), Nivel.GRAVE, 29_999_999_999, True) is False


@pytest.mark.ce("p_vp")
def test_mcdc_variable_que_no_es_de_parada(motor):
    assert motor.evaluar_parada(_base(), Nivel.GRAVE, UMBRAL_PARADA_NS, False) is False


@pytest.mark.ce("p_mas")
@pytest.mark.parametrize("duracion", [30_000_000_001, 10**15])
def test_frontera_superior_y_magnitud(motor, duracion):
    assert motor.evaluar_parada(_base(), Nivel.GRAVE, duracion, True) is True


def _correr(motor, reloj, n: int, valor: float = 250.0, es_vp: bool = True):
    variable = variable_presion(es_vp)
    resultados = []
    for _ in range(n):
        resultados.append(motor.procesar_lectura(lectura(valor), variable))
        reloj.avanzar(NS)
    return resultados


@pytest.mark.ce("x_unica")
def test_una_sola_orden_en_la_lectura_31(motor, reloj, canal):
    resultados = _correr(motor, reloj, 40)
    assert canal.emitir.call_count == 1
    assert [i for i, r in enumerate(resultados) if r.orden_emitida] == [30]
    assert motor._estados["PRES-01"].orden_emitida is True


@pytest.mark.ce("x_orden")
def test_la_orden_sale_antes_de_persistir(reloj, mocker):
    from gemelo.dominio.motor_alertas import MotorAlertas

    repo, canal, notificador = mocker.Mock(), mocker.Mock(), mocker.Mock()
    canal.emitir.return_value = True
    padre = mocker.Mock()
    padre.attach_mock(canal.emitir, "emitir")
    padre.attach_mock(repo.insertar, "insertar")
    _correr(MotorAlertas(reloj, repo, canal, notificador), reloj, 31)
    nombres = [(c[0], c[1][0].carga.get("evento") if c[0] == "insertar" else None) for c in padre.mock_calls]
    assert nombres.index(("emitir", None)) < nombres.index(("insertar", "ORDEN_PARADA"))


@pytest.mark.ce("x_canal")
def test_falla_del_canal_registra_y_notifica(motor, reloj, canal, repo, notificador):
    canal.emitir.return_value = False
    _correr(motor, reloj, 31)
    eventos = [c.args[0].carga["evento"] for c in repo.insertar.call_args_list]
    assert eventos.count("ORDEN_FALLIDA") == 1
    asuntos = [c.args[0] for c in notificador.notificar_mensaje.call_args_list]
    assert asuntos.count("Orden de parada sin confirmar") == 1


@pytest.mark.ce("x_dif")
def test_lectura_diferida_no_toca_el_estado(motor, repo, canal):
    resultado = motor.procesar_lectura(lectura(250.0, diferida=True), variable_presion())
    assert resultado.nivel is None and repo.insertar.call_count == 1
    canal.emitir.assert_not_called()
    assert "PRES-01" not in motor._estados


@pytest.mark.ce("x_bd")
def test_falla_de_bd_no_impide_la_orden(motor, reloj, canal, repo):
    repo.insertar.side_effect = OperationalError("caída")
    resultados = _correr(motor, reloj, 31)
    assert canal.emitir.call_count == 1
    assert resultados[-1].error_persistencia is True


def test_senal_invalida_genera_evento_y_aviso(motor, repo, notificador):
    resultado = motor.procesar_lectura(lectura(float("nan")), variable_presion())
    assert resultado.error == "SENAL_INVALIDA" and resultado.nivel is None
    assert repo.insertar.call_count == 1 and notificador.notificar_mensaje.call_count == 1


def test_reloj_inconsistente_se_reporta_sin_lanzar(motor, reloj):
    reloj.ns = 10 * NS
    motor.procesar_lectura(lectura(100.0), variable_presion())
    reloj.ns = 5 * NS
    assert motor.procesar_lectura(lectura(100.0), variable_presion()).error == "RELOJ"


def test_regreso_a_normal_cierra_la_alerta(motor, reloj, repo, notificador):
    _correr(motor, reloj, 2, valor=230.0)
    _correr(motor, reloj, 1, valor=100.0)
    eventos = [c.args[0].carga["evento"] for c in repo.insertar.call_args_list]
    assert eventos == ["CREADA", "CERRADA"]
    assert notificador.notificar.call_count == 1
    assert motor._estados["PRES-01"].alerta_id is None


def test_variable_que_no_es_de_parada_no_emite(motor, reloj, canal):
    _correr(motor, reloj, 45, es_vp=False)
    canal.emitir.assert_not_called()


def test_normal_sin_alerta_previa_no_genera_evento(motor, reloj, repo):
    from dataclasses import replace

    motor._estados["PRES-01"] = replace(EstadoVariable(), nivel=Nivel.LEVE, ultima_lectura_ns=0)
    reloj.avanzar(NS)
    motor.procesar_lectura(lectura(100.0), variable_presion())
    repo.insertar.assert_not_called()
