# Contribuir

## Entorno

El proyecto se gestiona con [uv](https://docs.astral.sh/uv/getting-started/installation/)
0.13.0. `.python-version` fija Python 3.15.0 para desarrollo; el paquete sigue
siendo compatible con Python 3.11–3.15. uv descarga el intérprete cuando hace falta.

Para instalar el entorno, comprobar el código y ejecutar las pruebas:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests -v
```

`pyproject.toml` declara las dependencias y `uv.lock` fija las versiones del
entorno de desarrollo; ambos archivos se versionan. `--locked` exige que el lock
coincida con el proyecto, sin actualizarlo durante las comprobaciones.

El grupo `dev` contiene las herramientas de validación; no forman parte de las
dependencias de ejecución. Quienes instalan el paquete con pip resuelven el
rango `httpx>=0.28.1,<1` sin usar nuestro lockfile.

## Lint y formato

Ruff comprueba y formatea todo el código Python, incluidas las pruebas. La
configuración usa Python 3.11 como mínimo y activa `E4`, `E7`, `E9` y `F` para
errores básicos, `I` para ordenar imports, `UP` para sintaxis compatible con ese
mínimo y `B` para errores comunes. El formato usa los valores predeterminados de
Ruff, sin excluir reglas ni archivos.

Para aplicar correcciones automáticas y formato:

```bash
uv run --locked ruff check --fix .
uv run --locked ruff format .
```

Revisa los cambios y ejecuta las comprobaciones y pruebas antes de enviarlos.

## Pruebas

Las pruebas comprueban el contrato HTTP de las funciones y los clientes. Un
servidor local permite verificar la reutilización y el cierre de conexiones,
además de la concurrencia asíncrona. No consultan la API de producción.

## Dependencias

Para añadir o quitar dependencias usa `uv add` y `uv remove`; para herramientas,
añade `--dev`. Para actualizar HTTPX dentro del rango permitido:

```bash
uv lock --upgrade-package httpx
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
```

Revisa y versiona los cambios de `pyproject.toml` y `uv.lock` que correspondan.

## Construir el paquete

```bash
uv build
uv run --locked twine check dist/*
```

`uv build` usa el backend `setuptools` fijado en `[build-system]`, en un entorno
de construcción aislado. Sus dependencias se resuelven por separado del lockfile.

Para comprobar que el wheel instala sus propias dependencias, usa otro entorno:

```bash
uv venv .venv-wheel
uv pip install --python .venv-wheel/bin/python dist/*.whl
uv pip check --python .venv-wheel/bin/python
.venv-wheel/bin/python -c 'import tu_ruc_python_client'
.venv-wheel/bin/python -m unittest discover -s tests -v
```

## Publicación

CI exige lint y formato correctos, construye el paquete una vez y prueba ese
wheel en entornos limpios con Python 3.11–3.15.

Para publicar, crea un tag `0.1.0` o `v0.1.0` que coincida con la versión del
paquete. Solo se publica en PyPI si toda la matriz pasa. El workflow usa
`uv publish` con los mismos artefactos comprobados y el secreto `PYPI_TOKEN`,
expuesto al comando como `UV_PUBLISH_TOKEN`.

Registra los cambios de cada versión en [CHANGELOG.md](CHANGELOG.md).
