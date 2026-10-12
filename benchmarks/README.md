# Comparación local de Requests y HTTPX

La migración a HTTPX **no demuestra una mejora general de velocidad**. Con un
retardo de servicio de 10 ms, los clientes síncronos reutilizados rindieron
prácticamente igual; la concurrencia mejoró el throughput de ambas bibliotecas.
En este entorno, `AsyncClient` fue más lento que los hilos con igual límite de
concurrencia, y `httpx.get` por llamada fue más lento que `requests.get`.

Se midieron exclusivamente transportes HTTP con un JSON sintético de 116 bytes.
No se midió el SDK completo ni se consultó la API de TuRuc. Los resultados están
en [results.json](results.json); el programa es [compare_http.py](compare_http.py).

Para reproducir con **CPython 3.15.0**, desde la raíz del repositorio:

```bash
uv run --isolated --no-project --python 3.15.0 \
  --with-requirements benchmarks/requirements.txt \
  python benchmarks/compare_http.py
```

La instalación descarga paquetes; las mediciones sólo usan `127.0.0.1`.
uv prepara un entorno aislado con las versiones directas y transitivas fijadas
en [requirements.txt](requirements.txt). Este archivo conserva el entorno de
la medición original independientemente de las actualizaciones de `uv.lock`;
Requests no se agrega a las dependencias de ejecución del SDK.
`--help` permite cambiar número de peticiones,
concurrencia, repeticiones, calentamiento, retardos y archivo de salida. No usar
`python -O`: el programa lo rechaza porque desactivaría las verificaciones.

Metodología:

- Servidor HTTP/1.1 con keep-alive en un **proceso separado**, puerto efímero y
  `TCP_NODELAY` activado en los sockets aceptados. Los transportes instalados
  también activan `TCP_NODELAY` en sus conexiones TCP. Sin TLS, compresión ni
  proxy; cabeceras comunes y timeout de 10 segundos.
- 300 peticiones medidas por caso, 5 repeticiones y dos escenarios: sin retardo
  añadido y con `sleep(0.010)` en el servidor por petición. El segundo escenario
  representa tiempo de servicio artificial, no una red real de latencia fija.
- 5 peticiones de calentamiento por cliente o trabajador antes de cada medición.
  Se excluyen creación de clientes, arranque de trabajadores, calentamiento y
  cierre en los casos reutilizados. En `requests.get` y `httpx.get`, la creación
  y el cierre del cliente **por petición** forman parte del tiempo medido.
- Comparación secuencial: una `Session` o un `Client` reutilizados, frente a las
  dos funciones `get` aisladas. Comparación concurrente: `ThreadPoolExecutor`
  con 8 trabajadores y una sesión/cliente exclusivo por trabajador en ambos
  transportes síncronos; `AsyncClient` compartido con 8 tareas y un máximo de
  8 conexiones y 8 conexiones keep-alive. El trabajo se reparte en grupos de
  37 o 38 peticiones por trabajador/tarea: todos completan exactamente 300.
- El orden de los casos rota por repetición y se invierte en las repeticiones
  alternas. Los dos escenarios se ejecutan en orden 0 ms y 10 ms.
- Cada respuesta debe tener estado 200 y coincidir con el JSON esperado,
  incluido su parseo completo. La latencia se mide desde el inicio de cada GET
  hasta terminar su lectura, parseo, comprobación y cierre. No incluye espera
  antes de que un trabajador empiece su siguiente petición. El tiempo total
  sí incluye la coordinación del lote; throughput = peticiones / tiempo total.
- El p95 de cada repetición usa rango más próximo: elemento
  `ceil(0.95 × 300)` de las latencias ordenadas. Las tablas muestran la **mediana
  de cada métrica entre las cinco repeticiones**, no el p95 agregado de todas
  las peticiones. JSON conserva los resultados de cada repetición y su orden;
  no guarda cada latencia individual.
- El servidor asigna un identificador a cada conexión TCP aceptada. “Conexiones”
  cuenta identificadores distintos usados en las peticiones medidas, incluidas
  conexiones abiertas durante el calentamiento; no significa nuevas conexiones
  abiertas durante la ventana cronometrada. Un pool puede usar menos conexiones
  que su límite: el caso async sin retardo usó 6 de las 8 permitidas.

Resultados del **11 de octubre de 2026**, CPython 3.15.0, Linux x86_64,
16 CPU lógicas, Requests 2.34.2 y HTTPX 0.28.1. La carga media de un minuto del
host pasó de 2.61 a 3.73. No hubo aislamiento de CPU ni control exclusivo del
host. Se validaron 21 000 respuestas medidas, además del calentamiento.

**Retardo artificial: 0 ms.**

| Caso | Concurrencia | Tiempo total (s) | Peticiones/s, mediana [mín–máx] | Latencia mediana / p95 (ms) | Conexiones |
|---|---:|---:|---:|---:|---:|
| `requests.get` por llamada | 1 | 0.267 | 1125.4 [1080.6–1178.8] | 0.870 / 1.087 | 300 |
| `httpx.get` por llamada | 1 | 1.987 | 151.0 [132.4–159.3] | 5.360 / 6.882 | 300 |
| `requests.Session` reutilizada | 1 | 0.148 | 2021.6 [1823.1–2183.2] | 0.481 / 0.591 | 1 |
| `httpx.Client` reutilizado | 1 | 0.136 | 2199.2 [1592.9–2339.1] | 0.432 / 0.576 | 1 |
| Requests + hilos, sesión por trabajador | 8 | 0.155 | 1936.8 [1900.4–2054.4] | 3.342 / 7.718 | 8 |
| HTTPX + hilos, cliente por trabajador | 8 | 0.131 | 2291.5 [2037.1–2352.8] | 3.013 / 6.926 | 8 |
| `httpx.AsyncClient` compartido | 8 | 0.298 | 1005.1 [929.1–1061.4] | 5.565 / 6.865 | 6 |

**Retardo artificial: 10 ms.**

| Caso | Concurrencia | Tiempo total (s) | Peticiones/s, mediana [mín–máx] | Latencia mediana / p95 (ms) | Conexiones |
|---|---:|---:|---:|---:|---:|
| `requests.get` por llamada | 1 | 3.628 | 82.7 [78.8–84.2] | 12.058 / 12.589 | 300 |
| `httpx.get` por llamada | 1 | 5.378 | 55.8 [54.1–57.6] | 16.598 / 18.221 | 300 |
| `requests.Session` reutilizada | 1 | 3.425 | 87.6 [86.7–88.7] | 11.384 / 11.751 | 1 |
| `httpx.Client` reutilizado | 1 | 3.434 | 87.4 [85.1–88.9] | 11.243 / 11.620 | 1 |
| Requests + hilos, sesión por trabajador | 8 | 0.439 | 684.0 [651.3–699.4] | 11.343 / 12.706 | 8 |
| HTTPX + hilos, cliente por trabajador | 8 | 0.437 | 687.3 [644.0–707.0] | 11.270 / 13.097 | 8 |
| `httpx.AsyncClient` compartido | 8 | 0.527 | 569.5 [406.9–633.0] | 13.152 / 17.306 | 8 |

Lectura de los resultados:

- Con 10 ms añadidos, `Session` y `Client` reutilizados alcanzaron **87.6 y
  87.4 peticiones/s**: diferencia de −0.2 % para HTTPX y rangos solapados.
  Con 8 hilos llegaron a **684.0 y 687.3 peticiones/s**, también con rangos
  solapados. Estos datos no justifican afirmar que HTTPX síncrono sea más rápido.
- En ese escenario, Requests con hilos logró **7.8 veces** el throughput de su
  sesión secuencial; HTTPX async logró **6.5 veces** el de su cliente secuencial.
  Es una comparación de **concurrencia**, no una prueba de superioridad de un
  transporte. A igual concurrencia, async alcanzó **569.5 peticiones/s**, un
  16.7 % menos que Requests con hilos y con mayor p95 mediano.
- Sin retardo, la mediana de HTTPX reutilizado fue 8.8 % superior a la de
  `Session`, pero los rangos se solapan. Async quedó por debajo de los otros
  clientes reutilizados. El resultado de 10 ms muestra que esta diferencia
  local sin espera no se puede generalizar a servicios remotos.
- Las llamadas aisladas a HTTPX tuvieron **86.6 % menos throughput** que
  Requests sin retardo y **32.5 % menos** con 10 ms. No se debe presentar la
  sustitución de `requests.get` por `httpx.get` como una optimización de velocidad.
- La reutilización redujo las conexiones usadas de **300 a 1** en ambos
  transportes secuenciales. Sin retardo, el throughput aumentó 1.8 veces para
  Requests y 14.6 veces para HTTPX frente a su respectivo `get` aislado. Esa
  diferencia conjunta incluye evitar creación de clientes y conexiones; no se
  atribuye exclusivamente al pooling TCP.

La muestra usa localhost, un JSON pequeño, un servidor Python con hilos y un
retardo artificial. No mide DNS remoto, TLS, HTTP/2, respuesta de producción,
respuestas grandes, límites de tasa, recursos del servidor real ni consumo de
CPU/memoria del cliente. Las repeticiones describen variación de esta ejecución;
no son un intervalo de confianza ni un pronóstico de velocidad de TuRuc.
Los parámetros por defecto del entorno también difieren en los casos aislados:
HTTPX usa `trust_env=False`; Requests fuerza proxies vacíos porque su función
`get` no expone `trust_env`, y conserva el resto de su comportamiento ambiental.

La elección de HTTPX se puede justificar por su API síncrona/asíncrona y el
control explícito del ciclo de vida del cliente. Para consultas repetidas,
conviene reutilizar el cliente. Cualquier afirmación de mejora de velocidad del
SDK debe verificarse con su carga representativa y límites reales.

Referencias oficiales: [clientes y pooling de HTTPX](https://www.python-httpx.org/advanced/clients/),
[uso asíncrono y reutilización de AsyncClient](https://www.python-httpx.org/async/),
[sesiones de Requests](https://requests.readthedocs.io/en/latest/user/advanced/#session-objects).
