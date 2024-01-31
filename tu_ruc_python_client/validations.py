from tu_ruc_python_client.constants import *
from tu_ruc_python_client.exceptions import *


def validate_search (search : str):
    """
    Validaciones para el parametro de busqueda
    :param search: Parametro de busqueda
    :return: Parametro de busqueda
    """

    if not isinstance(search, str):
        raise ValueError('El parametro de busqueda debe ser un string')
    
    if len(search) < MIN_SEARCH_LENGTH:
        raise LengthError(f'El parametro de busqueda no puede ser menor a {MIN_SEARCH_LENGTH} caracteres')
    
    if len(search) > MAX_SEARCH_LENGTH:
        raise LengthError(f'El parametro de busqueda no puede ser mayor a {MAX_SEARCH_LENGTH} caracteres')
    
    return search


def validate_page (page : int):
    """
    Validaciones para el parametro de pagina
    :param page: Parametro de pagina
    :return: Parametro de pagina
    """

    if not isinstance(page, int):
        raise ValueError('El parametro de pagina debe ser un entero')
    
    if page < MIN_PAGE:
        raise LengthError(f'El parametro de pagina no puede ser menor a {MIN_PAGE}')
    
    if page > MAX_PAGE:
        raise LengthError(f'El parametro de pagina no puede ser mayor a {MAX_PAGE}')

    return page

def validate (function):
    """
    Decorador para validar parametros
    :param function: Funcion a decorar
    :return: Funcion decorada
    """

    def wrapper(*args, **kwargs):

        try:
            # Validar el parámetro de búsqueda
            if 'search' in kwargs:
                kwargs['search'] = validate_search(kwargs['search'])
            else:
                if len(args) > 0:
                    args = list(args)
                    args[0] = validate_search(args[0])
                else:
                    raise SearchParameterError('El parametro de busqueda es requerido')

            # Validar el parámetro de página
            if 'page' in kwargs:
                kwargs['page'] = validate_page(kwargs['page'])

            # Llamar a la función original solo si todas las validaciones pasan
            return function(*args, **kwargs)

        except (ValueError, LengthError, SearchParameterError) as e:
            raise e
    
    return wrapper