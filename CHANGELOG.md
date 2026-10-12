# Changelog

## 0.1.0 — 2026-10-12

- El mínimo pasa de Python 3.8 a Python 3.11; la CI verifica CPython 3.11–3.15.
- HTTPX (`httpx>=0.28.1,<1`) reemplaza a Requests como dependencia de ejecución.
  Los errores de transporte pasan a la familia `httpx.RequestError`.
- Los nuevos `TuRucClient` y `AsyncTuRucClient` reutilizan conexiones y permiten
  cerrarlas con `with`/`async with` o `close()`/`aclose()`. Admiten `base_url`
  y `timeout`; el timeout predeterminado es de 10 segundos por fase.
- Las funciones existentes conservan sus parámetros y respuestas, las llamadas
  aisladas sin timeout y el seguimiento de redirecciones.
- Las búsquedas conservan `&`, `+`, espacios y acentos mediante parámetros
  HTTP codificados correctamente.
- uv 0.13.0 gestiona desarrollo, pruebas, construcción y publicación. Se añade
  `uv.lock`, Python 3.15.0 en `.python-version` y un grupo `dev` para validar
  distribuciones. Sustituye los archivos `requirements-build.in` y `.txt`.
- Ruff 0.17.0 unifica lint y formato de código fuente y pruebas,
  con Python 3.11 como objetivo. La CI exige ambas comprobaciones antes de
  construir; se normalizan imports y formato conservando la API pública.
- El empaquetado conserva el backend `setuptools`, la licencia MIT y las
  versiones soportadas. El lock de desarrollo no restringe las dependencias
  de quienes instalan el SDK.
- Las pruebas verifican el contrato público, las conexiones contra un servidor
  local y el wheel instalado. La publicación de tags depende de esas comprobaciones.
