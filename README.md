# tu-ruc-python-client
![pipeline](https://github.com/ithdev/tu-ruc-python-client/blob/main/turuc.png?raw=true)

Cliente Python para la API de TuRuc Paraguay

Esta biblioteca proporciona funciones para realizar consultas a una API de contribuyentes. Permite buscar contribuyentes por un término de búsqueda y paginación, así como obtener información detallada sobre un contribuyente específico a través de su número de RUC o CI.

## Instalación

Instala la biblioteca a través de pip:
```bash
pip install tu_ruc_python_client
```

Importa las funciones que necesitas en tu código:

```python
# Opción 1
from tu_ruc_python_client import get_contribuyente_by_search, get_contribuyente_by_ruc


# Opción 2
from tu_ruc_python_client import *
```

## Uso
### `get_contribuyente_by_search(search, page)`

> [!TIP]
> Se recomienda usar esta función para integración con sistemas.

#### Parametros
- `search` (str): Término de búsqueda.
- `page` (int): Número de página de resultados.

#### Ejemplo de uso

```python
from tu_ruc_python_client import get_contribuyente_by_search

print (get_contribuyente_by_search('juan perez'))

print (get_contribuyente_by_search('juan perez', page=2))

print (get_contribuyente_by_search('5898204-3'))
``` 

---
### `get_contribuyente_by_ruc(ruc)`

#### Parametros
- `ruc` (str): Número de RUC.

#### Ejemplo de uso

```python
from tu_ruc_python_client import get_contribuyente_by_ruc

print (get_contribuyente_by_ruc('5898204-3'))
```

## Contribuciones
Las contribuciones son bienvenidas. Para cambios importantes, primero abra un problema para discutir lo que le gustaría cambiar.

¡Gracias por contribuir!
