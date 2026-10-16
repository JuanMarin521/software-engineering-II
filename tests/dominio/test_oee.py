"""HU-03: clasificación de paros, cálculo exacto del OEE y planificador."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from gemelo.dominio.calculador_oee import CalculadorOEE, EntradaOEE, EstadoCalculo, ResultadoOEE, evaluar_calidad
from gemelo.dominio.clasificador_paros import ClasificadorParos, Paro, Penalizacion, TipoParo
from gemelo.dominio.planificador_oee import PlanificadorOEE, TurnoOEE, evaluar_eficiencia
from gemelo.dominio.tipos import Nivel
from gemelo.errores import ParoInvalidoError, TipoParoDesconocidoError

clasificador = ClasificadorParos()
calculador = CalculadorOEE()


@pytest.mark.ce("o_averia")
def test_averia_penaliza_disponibilidad():
    r = clasificador.clasificar(Paro(TipoParo.AVERIA, 1200, False))
    assert (r.penaliza, r.requiere_validacion) == (Penalizacion.DISPONIBILIDAD, False)


@pytest.mark.ce("o_cfprog")
@pytest.mark.parametrize("tipo, dur", [(TipoParo.CAMBIO_FORMATO, 1800), (TipoParo.ASEO_LINEA, 900)])
def test_cambio_o_aseo_programado_no_penaliza(tipo, dur):
    r = clasificador.clasificar(Paro(tipo, dur, True))
    assert (r.penaliza, r.requiere_validacion) == (Penalizacion.NINGUNA, False)


@pytest.mark.ce("o_cfno")
@pytest.mark.parametrize("tipo, dur", [(TipoParo.CAMBIO_FORMATO, 1800), (TipoParo.ASEO_LINEA, 900)])
def test_cambio_o_aseo_no_programado_penaliza_con_validacion(tipo, dur):
    r = clasificador.clasificar(Paro(tipo, dur, False))
    assert (r.penaliza, r.requiere_validacion) == (Penalizacion.DISPONIBILIDAD, True)


@pytest.mark.ce("o_micro")
def test_frontera_de_micro_parada():
    corta = clasificador.clasificar(Paro(TipoParo.MICRO_PARADA, 299, False))
    larga = clasificador.clasificar(Paro(TipoParo.MICRO_PARADA, 300, False))
    assert (corta.penaliza, corta.requiere_validacion) == (Penalizacion.RENDIMIENTO, False)
    assert (larga.penaliza, larga.requiere_validacion) == (Penalizacion.DISPONIBILIDAD, True)


@pytest.mark.ce("o_desc")
def test_tipo_desconocido_y_duracion_negativa():
    with pytest.raises(TipoParoDesconocidoError):
        clasificador.clasificar(Paro("OTRO", 10, False))
    with pytest.raises(ParoInvalidoError):
        Paro(TipoParo.AVERIA, -1, False)


def entrada(**kw) -> EntradaOEE:
    base = dict(
        planificado_s=28_800,
        paro_averia_s=0,
        operacion_real_s=28_800,
        piezas_total=14_400,
        piezas_conformes=14_400,
        ciclo_ideal_s=Decimal("2.0"),
    )
    base.update(kw)
    return EntradaOEE(**base)


@pytest.mark.ce("o_disp")
def test_disponibilidad_exacta():
    assert calculador.calcular(entrada(paro_averia_s=1_200)).disponibilidad == Fraction(23, 24)


@pytest.mark.ce("o_noplan")
def test_sin_tiempo_planificado():
    r = calculador.calcular(entrada(planificado_s=0))
    assert (r.oee, r.estado) == (None, EstadoCalculo.SIN_TIEMPO_PLANIFICADO)


@pytest.mark.ce("o_noprod")
@pytest.mark.parametrize("kw", [{"operacion_real_s": 0}, {"piezas_total": 0}])
def test_sin_produccion(kw):
    r = calculador.calcular(entrada(**kw))
    assert (r.oee, r.estado) == (Fraction(0), EstadoCalculo.SIN_PRODUCCION)


@pytest.mark.ce("o_conf")
def test_conformes_mayor_que_total():
    r = calculador.calcular(entrada(piezas_total=100, piezas_conformes=101, operacion_real_s=200))
    assert (r.oee, r.estado) == (None, EstadoCalculo.FUERA_DE_RANGO)


@pytest.mark.ce("o_uno")
def test_oee_exacto_de_uno_no_falla_por_redondeo():
    r = calculador.calcular(entrada())
    assert r.oee == Fraction(1, 1) and r.estado is EstadoCalculo.OK


@pytest.mark.ce("o_paro")
def test_paros_mayores_que_el_planificado():
    r = calculador.calcular(entrada(paro_averia_s=30_000))
    assert r.disponibilidad is not None and r.disponibilidad < 0
    assert (r.oee, r.estado) == (None, EstadoCalculo.FUERA_DE_RANGO)


@pytest.mark.ce("o_delta")
def test_desborde_de_contador_de_16_bits():
    assert calculador.delta_piezas(5, 65_530, 16) == 11
    assert calculador.delta_piezas(10, 4, 16) == 6


@pytest.mark.ce("o_cal")
@pytest.mark.parametrize(
    "calidad, nivel, lote",
    [
        (Fraction(95, 100), Nivel.NORMAL, False),
        (Fraction(949, 1000), Nivel.LEVE, False),
        (Fraction(90, 100), Nivel.LEVE, False),
        (Fraction(899, 1000), Nivel.GRAVE, True),
    ],
)
def test_umbrales_de_calidad(calidad, nivel, lote):
    r = evaluar_calidad(calidad)
    assert (r.nivel, r.revisar_lote) == (nivel, lote)


@pytest.mark.ce("o_efi")
@pytest.mark.parametrize(
    "ef, t, esperado",
    [
        (Fraction(79, 100), 3 * 3600, True),
        (Fraction(79, 100), 4 * 3600, False),
        (Fraction(79, 100), 5 * 3600, False),
        (Fraction(80, 100), 3 * 3600, False),
    ],
)
def test_eficiencia_estricta(ef, t, esperado):
    assert evaluar_eficiencia(ef, t, 8 * 3600) is esperado


def _planificador(mocker, resultados):
    calc = mocker.Mock()
    calc.calcular.side_effect = resultados
    notif = mocker.Mock()
    return PlanificadorOEE(calc, notif, lambda t: entrada()), calc, notif


def _res(oee: Fraction, rendimiento: Fraction = Fraction(1)) -> ResultadoOEE:
    return ResultadoOEE(oee, EstadoCalculo.OK, Fraction(1), rendimiento, Fraction(1))


@pytest.mark.ce("o_tick")
@pytest.mark.parametrize("oee, alerta", [(Fraction(13, 20), False), (Fraction(649, 1000), True)])
def test_alerta_estrategica(mocker, oee, alerta):
    plan, _, notif = _planificador(mocker, [_res(oee)])
    plan.tick([TurnoOEE("T1", 3600, 8 * 3600)], 0)
    asuntos = [c.args[0] for c in notif.notificar_mensaje.call_args_list]
    assert ("OEE estratégico bajo" in asuntos) is alerta


@pytest.mark.ce("o_exc")
def test_un_turno_con_falla_no_detiene_a_los_demas(mocker):
    plan, calc, _ = _planificador(mocker, [_res(Fraction(1)), RuntimeError("falla"), _res(Fraction(1))])
    turnos = [TurnoOEE(f"T{i}", 100, 8 * 3600) for i in range(3)]
    assert len(plan.tick(turnos, 0)) == 2 and calc.calcular.call_count == 3


def test_fuera_de_rango_y_eficiencia_generan_avisos(mocker):
    fuera = ResultadoOEE(None, EstadoCalculo.FUERA_DE_RANGO)
    plan, _, notif = _planificador(mocker, [fuera, _res(Fraction(7, 10), Fraction(79, 100))])
    plan.tick([TurnoOEE("T1", 100, 8 * 3600), TurnoOEE("T2", 3 * 3600, 8 * 3600)], 0)
    asuntos = [c.args[0] for c in notif.notificar_mensaje.call_args_list]
    assert asuntos == ["Error en datos", "Eficiencia baja"]


def test_paro_de_duracion_cero_es_valido():
    assert Paro(TipoParo.AVERIA, 0, False).duracion_s == 0
