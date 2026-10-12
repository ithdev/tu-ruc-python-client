import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from httpx import ConnectError, Response

from tu_ruc_python_client import get_contribuyente_by_ruc, get_contribuyente_by_search

CONTRIBUYENTE = {
    "doc": 80024191,
    "razonSocial": "MINISTERIO DE PRUEBA",
    "dv": 6,
    "ruc": "80024191-6",
    "estado": "ACTIVO",
    "esPersonaJuridica": False,
    "esEntidadPublica": True,
}


def json_response(data, status=200, message="OK"):
    return Response(status, json={"data": data, "message": message})


class ClientTests(unittest.TestCase):
    def test_search_preserves_reserved_characters_and_accents(self):
        response = json_response({"contribuyentes": [], "paginas": 0})

        with patch("httpx.HTTPTransport.handle_request", return_value=response) as send:
            result = get_contribuyente_by_search("A&B ÑANDÚ + CIA", page=2)

        request = send.call_args.args[0]
        self.assertEqual(
            parse_qs(urlsplit(str(request.url)).query),
            {"search": ["A&B ÑANDÚ + CIA"], "page": ["2"]},
        )
        self.assertEqual(result, {"contribuyentes": [], "paginas": 0})

    def test_search_uses_first_page_by_default(self):
        response = json_response({"contribuyentes": [CONTRIBUYENTE], "paginas": 1})

        with patch("httpx.HTTPTransport.handle_request", return_value=response) as send:
            result = get_contribuyente_by_search("MINISTERIO")

        request = send.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.url.path, "/api/contribuyente/search")
        self.assertEqual(
            request.extensions["timeout"],
            dict(connect=None, read=None, write=None, pool=None),
        )
        self.assertEqual(
            parse_qs(urlsplit(str(request.url)).query),
            {"search": ["MINISTERIO"], "page": ["0"]},
        )
        self.assertEqual(result, {"contribuyentes": [CONTRIBUYENTE], "paginas": 1})

    def test_ruc_lookup_returns_contribuyente(self):
        response = json_response(CONTRIBUYENTE)

        with patch("httpx.HTTPTransport.handle_request", return_value=response) as send:
            result = get_contribuyente_by_ruc("80024191-6")

        request = send.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.url.path, "/api/contribuyente/80024191-6")
        self.assertEqual(
            request.extensions["timeout"],
            dict(connect=None, read=None, write=None, pool=None),
        )
        self.assertEqual(result, CONTRIBUYENTE)

    def test_search_returns_empty_results(self):
        response = json_response({"contribuyentes": [], "paginas": 0})
        with patch("httpx.HTTPTransport.handle_request", return_value=response):
            self.assertEqual(
                get_contribuyente_by_search("sin resultados"),
                {"contribuyentes": [], "paginas": 0},
            )

    def test_not_found_response_returns_none(self):
        response = json_response(
            None,
            status=400,
            message="No se encontraron registros con el ruc proveido. Resultado: 0",
        )
        with patch("httpx.HTTPTransport.handle_request", return_value=response):
            self.assertIsNone(get_contribuyente_by_ruc("99999999"))

    def test_connection_failure_reaches_the_caller(self):
        with patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=ConnectError("sin conexión"),
        ):
            with self.assertRaises(ConnectError):
                get_contribuyente_by_ruc("5898204-3")


if __name__ == "__main__":
    unittest.main()
