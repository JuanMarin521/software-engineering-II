# Gemelo Digital — Planta IMEC S.A.S.

Núcleo de reglas del Gemelo Digital: lectura de PLC con reintentos, clasificación de alertas, orden de parada,
reconocimiento y escalamiento, cálculo exacto del OEE, cierre de turno y un historial inmutable.
Implementa el diseño del documento **RTF3 v2** (pruebas estructurales, caja blanca).

## Arquitectura

| Carpeta | Capa del diagrama de componentes |
|---|---|
| `src/gemelo/dominio/` | Lógica pura, sin E/S: `MotorAlertas`, `ClasificadorParos`, `CalculadorOEE`, `PlanificadorOEE`, `GestorTurno`, `ServicioAutorizacion`, tipos y puertos (`Protocol`) |
| `src/gemelo/borde/` | `AgenteBorde`, conectores OPC-UA y Modbus TCP, `BufferLocal` (SQLite) |
| `src/gemelo/controladores/` | `IngestaController`, `AlertasController`, `TurnosController`, `HistorialController` |
| `src/gemelo/infraestructura/` | Repositorio, `AuditoriaService`, `JobRetencion` |
| `db/esquema.sql` | Esquema PostgreSQL; el rol de la aplicación no tiene `UPDATE` ni `DELETE` |

Decisiones de diseño relevantes: duraciones como `int` en nanosegundos de un reloj inyectado (D9); `None`, `NaN`, infinito,
centinelas y subnormales producen una lectura inválida y nunca un nivel (D10); OEE con `Fraction` y `Decimal` (D11);
la orden de parada sale antes de persistir y una sola vez por episodio (D13).

## Instalación y ejecución

Requiere Python 3.12 o superior. Elija el bloque de su consola.

**Git Bash, Linux o macOS**

```bash
python -m venv .venv && source .venv/bin/activate    # en Git Bash de Windows: source .venv/Scripts/activate
pip install -e ".[dev]"

pytest -m "not integracion"                         # pruebas unitarias y de propiedades
pytest --cov=gemelo --cov-branch                    # con cobertura de ramas (umbral 85 %)
coverage json -o coverage.json && python scripts/verificar_cobertura_critica.py
ruff check . && mypy && xenon --max-absolute B src/ && bandit -q -r src
python scripts/generar_matriz_trazabilidad.py       # matriz CE-xx <-> HU <-> JIRA <-> resultado
```

**PowerShell (Windows)**: PowerShell 5 no admite `&&`; use una línea por comando o `;`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

pytest -m "not integracion"
pytest --cov=gemelo --cov-branch
coverage json -o coverage.json
python scripts/verificar_cobertura_critica.py
ruff check .
mypy
xenon --max-absolute B src/
bandit -q -r src
python scripts/generar_matriz_trazabilidad.py
```

Si PowerShell bloquea `Activate.ps1`, ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Las pruebas de integración (`-m integracion`) requieren PostgreSQL: cree la base con `db/esquema.sql` y defina
`GEMELO_PG_DSN` con el rol `gemelo_app`.

Ejecute siempre los comandos desde la raíz del proyecto (donde está `pyproject.toml`). `pytest` solo recoge la carpeta
`tests/`; si junto al proyecto hay otras carpetas con pruebas propias (por ejemplo una subcarpeta `gemelo_digital/`),
`ruff check .` también las analizaría: muévalas fuera del repositorio o ejecute `ruff check src tests scripts`.

## Pruebas y trazabilidad

Cada prueba lleva `@pytest.mark.ce("clave")`; `tests/conftest.py` deriva de ella el caso (`CE-xx`), la HU y la tarea de JIRA
(`tests/trazabilidad/casos.json`; si existe `jira.json`, también la tarea de JIRA). Los dobles de prueba (`FakeReloj`, mocks con `create_autospec`) permiten
simular timeouts, desconexiones y datos corruptos del PLC sin hardware.

## Calidad medida

| Verificación | Comando | Resultado |
|---|---|---|
| Pruebas | `pytest` | 168 pasan, 1 omitida (`h_bd`, requiere PostgreSQL) |
| Cobertura de líneas y ramas | `pytest --cov=gemelo --cov-branch` | 100 % |
| Módulos críticos | `python scripts/verificar_cobertura_critica.py` | 10 módulos con el 100 % de ramas |
| Estilo y código muerto | `ruff check .` | sin hallazgos |
| Tipos | `mypy` (estricto) | sin errores en 25 archivos |
| Complejidad | `xenon --max-absolute B src/` | aprobado (V(G) máximo 9) |
| Seguridad | `bandit -q -r src` | sin hallazgos |
| Mutación (Linux, macOS o WSL) | `mutmut run` | 366 de 376 mutantes detectados (97,3 %) |

Los 10 mutantes que sobreviven son equivalentes: seis cambian solo el texto de un mensaje de excepción, dos cambian la clave
de un `lock` por variable, uno cambia el tipo del argumento de `typing.cast` y otro el texto de un `TipoParoDesconocidoError`;
ninguno modifica el comportamiento observable.

## Estado del sprint

Implementado y probado: HU-01 a HU-05 (núcleo de reglas). Pendiente: adaptador PostgreSQL, simuladores OPC-UA/Modbus de
integración, capa HTTP (FastAPI) y planificador de tareas.
