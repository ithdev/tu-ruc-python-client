import requests
from tu_ruc_python_client.constants import *
from tu_ruc_python_client.validations import validate, validateRuc


@validate
def get_contribuyente_by_search(search : str, page = 0):
    """
    Obtener contribuyente por busqueda
    :param search: RUC, CI o nombre del contribuyente
    :param page: Paginacion de la busqueda
    :return: JSON con la informacion del contribuyente
    """
    
    sufix = "api/contribuyente/search"
    response = requests.get(f"{URL}{sufix}?search={search}&page={page}")

    
    return response.json()['data']

@validateRuc
def get_contribuyente_by_ruc(ruc : str):
    """
    Obtener contribuyente por RUC
    :param ruc: RUC del contribuyente
    :return: JSON con la informacion del contribuyente
    """
    
    sufix = "api/contribuyente"
    response = requests.get(f"{URL}{sufix}/{ruc}")

    
    return response.json()['data']
