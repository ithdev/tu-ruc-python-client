import httpx

from tu_ruc_python_client.constants import URL
from tu_ruc_python_client.validations import (
    validate,
    validate_page,
    validate_ruc,
    validate_search,
    validateRuc,
)


class TuRucClient:
    """Cliente síncrono con conexiones reutilizables; cerrar al terminar."""

    def __init__(self, *, base_url: str = URL, timeout: float | None = 10.0):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
        )

    def get_contribuyente_by_search(self, search: str, page=0):
        validate_search(search)
        validate_page(page)
        response = self._client.get(
            "api/contribuyente/search",
            params={"search": search, "page": page},
        )
        return response.json()["data"]

    def get_contribuyente_by_ruc(self, ruc: str):
        validate_ruc(ruc)
        response = self._client.get(f"api/contribuyente/{ruc}")
        return response.json()["data"]

    def close(self):
        self._client.close()

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._client.__exit__(exc_type, exc_value, traceback)


class AsyncTuRucClient:
    """Cliente asíncrono con conexiones reutilizables; cerrar al terminar."""

    def __init__(self, *, base_url: str = URL, timeout: float | None = 10.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
        )

    async def get_contribuyente_by_search(self, search: str, page=0):
        validate_search(search)
        validate_page(page)
        response = await self._client.get(
            "api/contribuyente/search",
            params={"search": search, "page": page},
        )
        return response.json()["data"]

    async def get_contribuyente_by_ruc(self, ruc: str):
        validate_ruc(ruc)
        response = await self._client.get(f"api/contribuyente/{ruc}")
        return response.json()["data"]

    async def aclose(self):
        await self._client.aclose()

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._client.__aexit__(exc_type, exc_value, traceback)


@validate
def get_contribuyente_by_search(search: str, page=0):
    """
    Obtener contribuyente por busqueda
    :param search: RUC, CI o nombre del contribuyente
    :param page: Paginacion de la busqueda
    :return: JSON con la informacion del contribuyente
    """

    sufix = "api/contribuyente/search"
    response = httpx.get(
        f"{URL}{sufix}",
        params={"search": search, "page": page},
        timeout=None,
        follow_redirects=True,
    )

    return response.json()["data"]


@validateRuc
def get_contribuyente_by_ruc(ruc: str):
    """
    Obtener contribuyente por RUC
    :param ruc: RUC del contribuyente
    :return: JSON con la informacion del contribuyente
    """

    sufix = "api/contribuyente"
    response = httpx.get(f"{URL}{sufix}/{ruc}", timeout=None, follow_redirects=True)

    return response.json()["data"]
