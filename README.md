# tu-ruc-python-client

![pipeline](https://github.com/ithdev/tu-ruc-python-client/blob/main/turuc.png?raw=true)

Cliente Python para consultar contribuyentes en la API de TuRuc Paraguay.
Incluye clientes síncrono y asíncrono con conexiones reutilizables mediante HTTPX.

## Instalación

Requiere Python 3.11 o posterior. La versión 0.1.0 se prueba con CPython
3.11, 3.12, 3.13, 3.14 y 3.15. Python no tiene una versión LTS oficial;
seguimos las [versiones con soporte de Python](https://devguide.python.org/versions/).

```bash
pip install tu_ruc_python_client
```

La instalación incluye `httpx>=0.28.1,<1` automáticamente. Requests deja de
ser una dependencia de ejecución del cliente.

## Cliente síncrono

Reutiliza una instancia para varias consultas. El bloque `with` cierra sus
conexiones al terminar, incluso si ocurre un error.

```python
from tu_ruc_python_client import TuRucClient

with TuRucClient() as client:
    resultados = client.get_contribuyente_by_search("juan perez", page=0)
    contribuyente = client.get_contribuyente_by_ruc("5898204-3")
    print(resultados)
    print(contribuyente)
```

## Cliente asíncrono

Reutiliza la misma instancia dentro de un bucle de eventos. `async with`
cierra sus conexiones; `asyncio.gather` permite realizar consultas concurrentes.

```python
import asyncio

from tu_ruc_python_client import AsyncTuRucClient


async def main():
    async with AsyncTuRucClient() as client:
        resultados = await asyncio.gather(
            client.get_contribuyente_by_search("juan perez"),
            client.get_contribuyente_by_search("maria lopez"),
        )
        print(resultados)


asyncio.run(main())
```

Crea el cliente fuera del bucle que realiza consultas para conservar las
conexiones. Los ejemplos muestran cargas pequeñas; para procesar lotes grandes,
limita la concurrencia según la capacidad de la API.

## Parámetros y respuestas

Ambos clientes exponen los mismos métodos:

| Método | Parámetros | Resultado |
|---|---|---|
| `get_contribuyente_by_search(search, page=0)` | Texto de 3–50 caracteres; página entera de 0–10 | Objeto con `contribuyentes` y `paginas` |
| `get_contribuyente_by_ruc(ruc)` | RUC o CI como texto, por ejemplo `5898204-3` | Objeto del contribuyente |

Los métodos devuelven el campo `data` de la respuesta JSON. Conservan el
comportamiento previo: `data: null` se devuelve como `None`, incluso en una
respuesta HTTP 400. No convierten automáticamente los estados HTTP en excepciones.
Las búsquedas preservan caracteres como `&`, `+`, espacios y acentos.

Los constructores aceptan argumentos opcionales por nombre:

```python
with TuRucClient(base_url="https://turuc.com.py/", timeout=10.0) as client:
    resultado = client.get_contribuyente_by_search("A&B ÑANDÚ + CIA")
```

`timeout` vale 10 segundos por defecto y se aplica a las fases de conexión,
lectura, escritura y espera de conexión disponible; no es un plazo total de la
consulta. `timeout=None` desactiva esos límites. Ambos clientes siguen
redirecciones. Si administras el ciclo de vida sin un bloque de contexto,
llama a `client.close()` o `await client.aclose()` al terminar.

## Migración desde las funciones anteriores

Las dos funciones siguen disponibles con sus parámetros y respuestas habituales:

```python
from tu_ruc_python_client import get_contribuyente_by_ruc, get_contribuyente_by_search

print(get_contribuyente_by_search("juan perez", page=2))
print(get_contribuyente_by_ruc("5898204-3"))
```

Cada llamada abre y cierra su propio cliente HTTP; para reutilizar conexiones
entre consultas, migra a `TuRucClient` o `AsyncTuRucClient`. Las funciones
conservan la ausencia de timeout y el seguimiento de redirecciones previos.

Los errores de transporte ahora pertenecen a HTTPX. Cambia las capturas de
`requests.exceptions.RequestException` por `httpx.RequestError`:

```python
import httpx

from tu_ruc_python_client import TuRucClient

try:
    with TuRucClient(timeout=10.0) as client:
        resultado = client.get_contribuyente_by_search("juan perez")
except httpx.TimeoutException:
    print("La consulta excedió el tiempo de espera")
except httpx.RequestError as exc:
    print(f"No se pudo completar la consulta: {exc}")
```

Para certificados de confianza personalizados, HTTPX utiliza `SSL_CERT_FILE`
o `SSL_CERT_DIR`; revisa la configuración si antes usabas `REQUESTS_CA_BUNDLE`.
Consulta las [diferencias con Requests](https://www.python-httpx.org/compatibility/)
y las [variables de entorno de HTTPX](https://www.python-httpx.org/environment_variables/).

## Desarrollo y pruebas

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
entorno de desarrollo. Ambos archivos se versionan. `--locked` exige que el lock
coincida con el proyecto, sin actualizarlo durante las comprobaciones.
El grupo `dev` contiene las herramientas de validación del paquete; esas
herramientas no forman parte de las dependencias de ejecución del cliente.
Los consumidores pueden seguir instalando el SDK con pip y resolver el rango
`httpx>=0.28.1,<1` sin utilizar nuestro lockfile.

Ruff 0.17.0 comprueba y formatea todo el código Python, incluidas las pruebas.
La configuración usa Python 3.11 como mínimo y activa
`E4`, `E7`, `E9` y `F` para errores básicos, `I` para ordenar imports, `UP`
para sintaxis compatible con ese mínimo y `B` para errores comunes.
El formato mantiene los valores predeterminados de Ruff; no se excluyen reglas
ni archivos Python del proyecto. Para aplicar correcciones automáticas y formato:

```bash
uv run --locked ruff check --fix .
uv run --locked ruff format .
```

Revisa los cambios y ejecuta las comprobaciones y pruebas antes de enviarlos.

Las pruebas comprueban el contrato HTTP de las funciones y los clientes.
Un servidor local permite verificar reutilización y cierre de conexiones,
además de concurrencia asíncrona. No consultan la API de producción.

Para construir y comprobar los paquetes con las herramientas fijadas:

```bash
uv build
uv run --locked twine check dist/*
```

`uv build` utiliza el backend `setuptools` fijado en `[build-system]`, en un
entorno de construcción aislado. Las dependencias del backend se resuelven
por separado del lockfile del proyecto.

Para añadir o quitar dependencias usa `uv add` y `uv remove`; para herramientas,
añade `--dev`. Para actualizar HTTPX dentro del rango permitido:

```bash
uv lock --upgrade-package httpx
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
```

Revisa y versiona los cambios de `pyproject.toml` y `uv.lock` que correspondan.

Para comprobar que el wheel instala sus propias dependencias, usa otro entorno:

```bash
uv venv .venv-wheel
uv pip install --python .venv-wheel/bin/python dist/*.whl
uv pip check --python .venv-wheel/bin/python
.venv-wheel/bin/python -c 'import tu_ruc_python_client'
.venv-wheel/bin/python -m unittest discover -s tests -v
```

La CI exige lint y formato correctos antes de construir una vez y probar ese
wheel en entornos limpios de Python
3.11–3.15. Los tags `0.1.0` o `v0.1.0` deben coincidir con la versión del
paquete; sólo se publican en PyPI después de que toda la matriz pase, usando
`uv publish` con los mismos artefactos comprobados y el secreto `PYPI_TOKEN`
existente, expuesto al comando como `UV_PUBLISH_TOKEN`.

## Contribuciones

Las contribuciones son bienvenidas. Para cambios importantes, primero abra un problema para discutir lo que le gustaría cambiar.

¡Gracias por contribuir!
