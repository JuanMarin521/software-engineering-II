"""Constantes de las reglas de negocio. Las duraciones son enteros en nanosegundos (D9)."""

NS_POR_S = 10**9

UMBRAL_PARADA_NS = 30 * NS_POR_S  # RN002: Grave sostenido 30 s (comparación inclusiva)
UMBRAL_ESCALA_NS = 600 * NS_POR_S  # RN003: 10 min sin reconocer (comparación estricta)
MICRO_PARADA_S = 300  # RN008: micro parada si dura menos de 5 min
MAX_INTENTOS_LECTURA = 3
ESPERA_BASE_S = 0.1  # espera de 100 ms por número de intento
MAX_INTENTOS_CIERRE = 3
TAMANO_MAX_LOTE = 500

SENTINELAS_ANALOGICAS = (32767, -32768)  # desborde y subdesborde de módulos analógicos
MIN_NORMAL_FLOAT32 = 1.1754943508222875e-38  # por debajo, el float32 es subnormal
