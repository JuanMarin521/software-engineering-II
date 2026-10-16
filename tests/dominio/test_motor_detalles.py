"""Refuerzo de pruebas guiado por mutación: valores exactos de retornos, cargas y destinatarios."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from gemelo.dominio.tipos import EstadoVariable, Nivel, OrdenParada, ResultadoProceso, Rol
from tests.dobles import NS, T0_UTC, lectura, variable_presion


def _correr(motor, reloj, n, valor):
    resultados = []
    for _ in range(n):
        resultados.append(motor.procesar_lectura(lectura(valor), variable_presion()))
        reloj.avanzar(NS)
    return resultados


def test_lectura_diferida_se_persiste_con_su_carga_y_retorna_sin_orden(motor, repo):
    resultado = motor.procesar_lectura(lectura(250.0, diferida=True), variable_presion())
    assert resultado == ResultadoProceso(nivel=None, orden_emitida=False)
    registro = repo.insertar.call_args.args[0]
    assert registro.tipo == "lectura" and registro.t_utc == T0_UTC
    assert dict(registro.carga) == {"variable": "PRES-01", "valor": 250.0, "calidad": "GOOD", "diferida": True}


def test_reloj_inconsistente_retorna_el_resultado_exacto(motor, reloj):
    reloj.ns = 10 * NS
    motor.procesar_lectura(lectura(100.0), variable_presion())
    reloj.ns = 5 * NS
    assert motor.procesar_lectura(lectura(100.0), variable_presion()) == ResultadoProceso(None, False, error="RELOJ")


def test_resultados_exactos_y_orden_de_parada_completa(motor, reloj, canal):
    resultados = _correr(motor, reloj, 31, 250.0)
    assert resultados[0] == ResultadoProceso(Nivel.GRAVE, False, None, False)
    assert resultados[29] == ResultadoProceso(Nivel.GRAVE, False, None, False)
    assert resultados[30] == ResultadoProceso(Nivel.GRAVE, True, None, False)
    orden = canal.emitir.call_args.args[0]
    assert orden == OrdenParada("PRES-01", T0_UTC + timedelta(seconds=30), "GRAVE sostenido 30 s")


def test_lectura_normal_retorna_nivel_normal(motor, reloj):
    assert _correr(motor, reloj, 1, 100.0)[0] == ResultadoProceso(Nivel.NORMAL, False, None, False)


@pytest.mark.parametrize(
    "valor, nivel, roles",
    [(230.0, Nivel.LEVE, (Rol.OPERARIO, Rol.SUPERVISOR)), (250.0, Nivel.GRAVE, (Rol.SUPERVISOR, Rol.JEFE_MTTO))],
)
def test_alerta_notificada_con_sus_campos_y_roles(motor, reloj, repo, notificador, valor, nivel, roles):
    _correr(motor, reloj, 1, valor)
    alerta, destinatarios = notificador.notificar.call_args.args
    assert (alerta.variable_codigo, alerta.nivel, alerta.inicio_ns, alerta.valor_pico) == ("PRES-01", nivel, 0, valor)
    assert tuple(destinatarios) == roles
    registro = repo.insertar.call_args_list[0].args[0]
    assert registro.tipo == "evento_alerta" and registro.t_utc == T0_UTC
    assert dict(registro.carga) == {"alerta_id": str(alerta.id), "evento": "CREADA", "actor": None}
    assert isinstance(alerta.id, UUID)


def test_cierre_de_alerta_conserva_el_id(motor, reloj, repo):
    _correr(motor, reloj, 1, 230.0)
    creada = repo.insertar.call_args_list[0].args[0].carga["alerta_id"]
    _correr(motor, reloj, 1, 100.0)
    cerrada = repo.insertar.call_args_list[1].args[0]
    assert dict(cerrada.carga) == {"alerta_id": creada, "evento": "CERRADA", "actor": None}


def test_senal_invalida_con_carga_y_destinatarios_exactos(motor, repo, notificador):
    resultado = motor.procesar_lectura(lectura(float("nan")), variable_presion())
    assert resultado == ResultadoProceso(None, False, "SENAL_INVALIDA", False)
    asunto, detalle, roles = notificador.notificar_mensaje.call_args.args
    assert asunto == "Señal inválida" and dict(detalle) == {"variable": "PRES-01", "calidad": "GOOD"}
    assert tuple(roles) == (Rol.SUPERVISOR, Rol.JEFE_MTTO)
    assert repo.insertar.call_args.args[0].carga["evento"] == "SENAL_INVALIDA"


def test_orden_fallida_notifica_con_detalle_y_roles(motor, reloj, canal, notificador, repo):
    canal.emitir.return_value = False
    _correr(motor, reloj, 31, 250.0)
    asunto, detalle, roles = notificador.notificar_mensaje.call_args.args
    assert asunto == "Orden de parada sin confirmar" and dict(detalle) == {"variable": "PRES-01"}
    assert tuple(roles) == (Rol.SUPERVISOR, Rol.JEFE_MTTO)
    assert repo.insertar.call_args.args[0].carga["evento"] == "ORDEN_FALLIDA"


def test_orden_de_parada_comparte_el_id_de_la_alerta(motor, reloj, repo):
    _correr(motor, reloj, 31, 250.0)
    ids = {c.args[0].carga["alerta_id"] for c in repo.insertar.call_args_list}
    assert len(ids) == 1 and repo.insertar.call_args.args[0].carga["evento"] == "ORDEN_PARADA"


def test_reconocer_retorna_el_evento_completo(motor, reloj, repo):
    alerta = uuid4()
    evento = motor.reconocer(alerta, "sup1")
    assert (evento.alerta_id, evento.t_utc, evento.actor) == (alerta, reloj.utc(), "sup1")
    assert repo.insertar.call_args.args[0].carga["actor"] == "sup1"


def test_contador_acepta_el_mismo_instante_y_actualiza_los_campos(motor):
    estado = EstadoVariable(Nivel.LEVE, ultima_lectura_ns=5 * NS)
    nuevo = motor.actualizar_contador(estado, Nivel.GRAVE, 5 * NS)  # igual: no es retroceso
    assert nuevo.nivel is Nivel.GRAVE and nuevo.ultima_lectura_ns == 5 * NS and nuevo.inicio_grave_ns == 5 * NS
    otro = motor.actualizar_contador(nuevo, Nivel.LEVE, 6 * NS)
    assert otro.nivel is Nivel.LEVE and otro.ultima_lectura_ns == 6 * NS


def test_escalamiento_mide_la_edad_con_inicio_distinto_de_cero(motor, repo, notificador, reloj):
    from gemelo.dominio.tipos import Alerta

    alerta = Alerta(uuid4(), "PRES-01", Nivel.LEVE, 7 * NS, 230.0)
    assert motor.escalar_pendientes((alerta,), 7 * NS + 600 * NS) == []  # edad exacta: no escala
    eventos = motor.escalar_pendientes((alerta,), 7 * NS + 600 * NS + 1)
    assert len(eventos) == 1
    assert (eventos[0].alerta_id, eventos[0].t_utc, eventos[0].actor) == (alerta.id, reloj.utc(), None)
    escalada, roles = notificador.notificar.call_args.args
    assert (escalada.id, escalada.variable_codigo, escalada.nivel) == (alerta.id, "PRES-01", Nivel.GRAVE)
    assert (escalada.inicio_ns, escalada.valor_pico) == (7 * NS, 230.0)
    assert tuple(roles) == (Rol.SUPERVISOR, Rol.JEFE_MTTO)
    registro = repo.insertar.call_args.args[0]
    assert dict(registro.carga) == {"alerta_id": str(alerta.id), "evento": "ESCALADA", "actor": None}


def test_el_inicio_de_la_alerta_es_el_instante_de_la_lectura(motor, reloj, notificador):
    reloj.ns = 7 * NS
    motor.procesar_lectura(lectura(230.0), variable_presion())
    assert notificador.notificar.call_args.args[0].inicio_ns == 7 * NS


def test_contador_actualiza_la_ultima_lectura_en_grave(motor):
    estado = EstadoVariable(Nivel.GRAVE, inicio_grave_ns=5 * NS, ultima_lectura_ns=5 * NS)
    assert motor.actualizar_contador(estado, Nivel.GRAVE, 6 * NS).ultima_lectura_ns == 6 * NS


def test_normal_sin_alerta_previa_retorna_sin_falla(motor, reloj):
    from dataclasses import replace

    motor._estados["PRES-01"] = replace(EstadoVariable(), nivel=Nivel.LEVE, ultima_lectura_ns=0)
    reloj.avanzar(NS)
    assert motor.procesar_lectura(lectura(100.0), variable_presion()).error_persistencia is False


def test_la_alerta_se_cierra_con_su_id_tras_una_parada(motor, reloj, repo):
    _correr(motor, reloj, 31, 250.0)
    _correr(motor, reloj, 1, 100.0)
    eventos = [c.args[0] for c in repo.insertar.call_args_list]
    ids = {e.carga["alerta_id"] for e in eventos}
    assert (
        len(ids) == 1
        and eventos[-1].carga["evento"] == "CERRADA"
        and eventos[-1].t_utc == reloj.utc() - timedelta(seconds=1)
    )
    assert eventos[-2].t_utc == T0_UTC + timedelta(seconds=30)  # la orden conserva el instante de emisión


def test_senal_invalida_con_falla_de_bd_la_reporta(motor, repo):
    from gemelo.errores import OperationalError

    repo.insertar.side_effect = OperationalError("caída")
    resultado = motor.procesar_lectura(lectura(float("nan")), variable_presion())
    assert resultado.error_persistencia is True
    registro_t = repo.insertar.call_args.args[0].t_utc
    assert registro_t == motor._reloj.utc()


def test_la_transicion_leve_a_grave_conserva_el_id_de_la_alerta(motor, reloj, repo, notificador):
    _correr(motor, reloj, 1, 230.0)
    _correr(motor, reloj, 1, 250.0)
    ids = {c.args[0].carga["alerta_id"] for c in repo.insertar.call_args_list}
    assert len(ids) == 1
    assert notificador.notificar.call_args_list[0].args[0].id == notificador.notificar.call_args_list[1].args[0].id


def test_parada_sin_alerta_previa_genera_y_conserva_un_id_valido(motor, reloj, repo):
    motor._estados["PRES-01"] = EstadoVariable(Nivel.GRAVE, inicio_grave_ns=0, ultima_lectura_ns=0)
    reloj.avanzar(30 * NS)
    assert motor.procesar_lectura(lectura(250.0), variable_presion()).orden_emitida is True
    carga = repo.insertar.call_args.args[0].carga
    assert carga["evento"] == "ORDEN_PARADA" and UUID(carga["alerta_id"])
    assert str(motor._estados["PRES-01"].alerta_id) == carga["alerta_id"]


def test_senal_invalida_genera_un_id_de_evento_valido(motor, repo):
    motor.procesar_lectura(lectura(float("nan")), variable_presion())
    assert UUID(repo.insertar.call_args.args[0].carga["alerta_id"])
