# tu-ruc-python-client

![Tu RUC y Python](https://github.com/ithdev/tu-ruc-python-client/blob/main/turuc.png?raw=true)

Cliente Python para consultar contribuyentes en la API de
[TuRuc Paraguay](https://turuc.com.py/). Incluye un cliente síncrono y uno
asíncrono que reutilizan sus conexiones.

## Instalación

Requiere Python 3.11 o posterior.

```bash
pip install tu_ruc_python_client
```

La instalación incluye su única dependencia, [HTTPX](https://www.python-httpx.org/).

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
cierra sus conexiones; `asyncio.gather` permite hacer consultas concurrentes.

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

Crea el cliente una sola vez, fuera del código que repite las consultas, para
conservar las conexiones. Para procesar lotes grandes, limita la concurrencia
según la capacidad de la API.

## Parámetros y respuestas

Ambos clientes exponen los mismos métodos:

| Método                                        | Parámetros                                             | Resultado                                |
| --------------------------------------------- | ------------------------------------------------------ | ---------------------------------------- |
| `get_contribuyente_by_search(search, page=0)` | Texto de 3 a 50 caracteres; página entera de 0 a 10    | Objeto con `contribuyentes` y `paginas`  |
| `get_contribuyente_by_ruc(ruc)`               | RUC o CI como texto, por ejemplo `5898204-3`           | Objeto del contribuyente                 |

Los métodos devuelven el campo `data` de la respuesta JSON de la API:

- Si la API no devuelve datos, el resultado es `None`, también ante un error
  HTTP como 400.
- Los estados HTTP de error no se convierten en excepciones.
- Puedes buscar textos con `&`, `+`, espacios y acentos; se envían tal cual.

### Configuración

Los constructores aceptan estos argumentos opcionales por nombre:

```python
with TuRucClient(base_url="https://turuc.com.py/", timeout=10.0) as client:
    resultado = client.get_contribuyente_by_search("A&B ÑANDÚ + CIA")
```

- `timeout`: 10 segundos por defecto. Se aplica por separado a la conexión, la
  lectura, la escritura y la espera de una conexión libre; no limita la duración
  total de la consulta. `timeout=None` desactiva los límites.
- Ambos clientes siguen las redirecciones.

Si no usas un bloque `with`, cierra el cliente al terminar con `client.close()`
o `await client.aclose()`.

## Errores

- **Parámetros inválidos:** los métodos lanzan `ValueError` o
  `tu_ruc_python_client.exceptions.LengthError` antes de consultar la API.
- **Fallos de red y timeouts:** se propagan los errores de HTTPX
  (`httpx.RequestError` y sus subclases).

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

## Migración desde las funciones anteriores

Las dos funciones siguen disponibles con sus parámetros y respuestas habituales:

```python
from tu_ruc_python_client import get_contribuyente_by_ruc, get_contribuyente_by_search

print(get_contribuyente_by_search("juan perez", page=2))
print(get_contribuyente_by_ruc("5898204-3"))
```

Cada llamada abre y cierra su propio cliente HTTP, sin timeout y siguiendo las
redirecciones, como antes. Para reutilizar conexiones entre consultas, migra a
`TuRucClient` o `AsyncTuRucClient`.

La biblioteca ya no usa Requests, sino HTTPX:

- Cambia las capturas de `requests.exceptions.RequestException` por
  `httpx.RequestError`.
- Si usabas `REQUESTS_CA_BUNDLE` para certificados propios, usa `SSL_CERT_FILE`
  o `SSL_CERT_DIR`.
- Si tu proyecto usa Requests directamente, decláralo como dependencia propia.

Consulta las [diferencias con Requests](https://www.python-httpx.org/compatibility/)
y las [variables de entorno de HTTPX](https://www.python-httpx.org/environment_variables/).

## Cambios

Consulta [CHANGELOG.md](https://github.com/ithdev/tu-ruc-python-client/blob/main/CHANGELOG.md)
para conocer los cambios de cada versión.

## Contribuciones

Las contribuciones son bienvenidas. Para cambios importantes, abre primero un
issue para comentar lo que te gustaría cambiar. Para preparar el entorno de
desarrollo, consulta
[CONTRIBUTING.md](https://github.com/ithdev/tu-ruc-python-client/blob/main/CONTRIBUTING.md).
