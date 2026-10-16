"""Cálculo de OEE con aritmética exacta (D11): enteros, Decimal para el ciclo ideal y Fraction para las razones."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from typing import Optional

from gemelo.dominio.tipos import Nivel


class EstadoCalculo(Enum):
    OK = "OK"
    SIN_TIEMPO_PLANIFICADO = "SIN_TIEMPO_PLANIFICADO"
    SIN_PRODUCCION = "SIN_PRODUCCION"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"


@dataclass(frozen=True)
class EntradaOEE:
    planificado_s: int
    paro_averia_s: int
    operacion_real_s: int
    piezas_total: int
    piezas_conformes: int
    ciclo_ideal_s: Decimal


@dataclass(frozen=True)
class ResultadoOEE:
    oee: Optional[Fraction]
    estado: EstadoCalculo
    disponibilidad: Optional[Fraction] = None
    rendimiento: Optional[Fraction] = None
    calidad: Optional[Fraction] = None


@dataclass(frozen=True)
class ResultadoCalidad:
    nivel: Nivel
    revisar_lote: bool


class CalculadorOEE:
    def calcular(self, entrada: EntradaOEE) -> ResultadoOEE:
        if entrada.planificado_s <= 0:
            return ResultadoOEE(None, EstadoCalculo.SIN_TIEMPO_PLANIFICADO)
        if entrada.operacion_real_s <= 0 or entrada.piezas_total <= 0:
            return ResultadoOEE(Fraction(0), EstadoCalculo.SIN_PRODUCCION)  # D5
        disponibilidad = Fraction(entrada.planificado_s - entrada.paro_averia_s, entrada.planificado_s)
        rendimiento = Fraction(entrada.ciclo_ideal_s) * entrada.piezas_total / entrada.operacion_real_s
        calidad = Fraction(entrada.piezas_conformes, entrada.piezas_total)  # D2: Conformes / Total
        oee = disponibilidad * rendimiento * calidad
        if oee < 0 or oee > 1:
            return ResultadoOEE(None, EstadoCalculo.FUERA_DE_RANGO, disponibilidad, rendimiento, calidad)
        return ResultadoOEE(oee, EstadoCalculo.OK, disponibilidad, rendimiento, calidad)

    def delta_piezas(self, actual: int, anterior: int, ancho_bits: int) -> int:
        """Diferencia de un contador de PLC que se desborda: aritmética módulo 2**ancho_bits."""
        return (actual - anterior) % (1 << ancho_bits)


def evaluar_calidad(calidad: Fraction) -> ResultadoCalidad:
    """RN006: menor de 95 % es Leve; menor de 90 % es Grave y exige revisar el lote."""
    if calidad < Fraction(9, 10):
        return ResultadoCalidad(Nivel.GRAVE, True)
    if calidad < Fraction(19, 20):
        return ResultadoCalidad(Nivel.LEVE, False)
    return ResultadoCalidad(Nivel.NORMAL, False)
