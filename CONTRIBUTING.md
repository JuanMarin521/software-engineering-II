# Cómo contribuir

- **Ramas:** `feature/HU-xx-descripcion`. Una rama por historia o tarea.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/es/) con el tipo en inglés y la descripción en español: `tipo(ámbito): descripción en infinitivo (HU-xx)`. Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`, `perf`, `style`. Atómicos: un cambio lógico por commit, con su prueba y con las pruebas en verde. Cuando la tarea exista en JIRA, agregue su clave (`SCRUM-n`) al mensaje.
- **Pull Request:** use la plantilla; otro integrante lo revisa antes de integrar.
- **Pruebas primero:** cada caso `CE-xx` se escribe antes que el código que lo satisface y se marca con `@pytest.mark.ce("clave")`.
- **Sin residuos:** no se versionan archivos generados (`coverage.json`, `reporte.xml`, cachés) ni código sin usar.
