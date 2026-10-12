import asyncio
import itertools
import json
import queue
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from test_client import CONTRIBUYENTE, json_response

from tu_ruc_python_client import (
    AsyncTuRucClient,
    TuRucClient,
    get_contribuyente_by_ruc,
)
from tu_ruc_python_client.exceptions import LengthError


@contextmanager
def local_api(before_response=lambda: None):
    requests = queue.Queue()
    closed = queue.Queue()
    connection_ids = itertools.count(1)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection_id = next(connection_ids)

        def do_GET(self):
            requests.put((self.connection_id, self.path))
            before_response()
            url = urlsplit(self.path)
            status = 200
            headers = {}
            data = CONTRIBUYENTE
            message = "OK"
            if url.path.startswith("/redirect/"):
                status = 302
                headers["Location"] = "/api/contribuyente/80024191-6"
            elif url.path.endswith("/search"):
                search = parse_qs(url.query)["search"][0]
                data = {"contribuyentes": [CONTRIBUYENTE], "paginas": 1}
                if search == "sin resultados":
                    data = {"contribuyentes": [], "paginas": 0}
            elif url.path.endswith("/99999999"):
                status = 400
                data = None
                message = (
                    "No se encontraron registros con el ruc proveido. Resultado: 0"
                )
            body = json.dumps({"data": data, "message": message}).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # Read-timeout tests close the socket before the server replies.
                pass

        def finish(self):
            try:
                super().finish()
            finally:
                closed.put(self.connection_id)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.base_url = f"http://127.0.0.1:{server.server_port}/"
    server.requests = requests
    server.closed = closed
    worker = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}
    )
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


class ReusableClientTests(unittest.TestCase):
    def test_client_reuses_connection_and_context_closes_it(self):
        with local_api() as server:
            client = TuRucClient(base_url=server.base_url)
            self.addCleanup(client.close)
            with client:
                self.assertEqual(
                    client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
                self.assertEqual(
                    client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
                first = server.requests.get(timeout=2)
                second = server.requests.get(timeout=2)
                self.assertEqual(first[0], second[0])
            self.assertEqual(server.closed.get(timeout=2), first[0])

    def test_search_preserves_encoding_pagination_and_base_path(self):
        with local_api() as server:
            with TuRucClient(base_url=server.base_url + "gateway") as client:
                result = client.get_contribuyente_by_search("A&B ÑANDÚ + CIA", page=2)
            url = urlsplit(server.requests.get(timeout=2)[1])
            self.assertEqual(url.path, "/gateway/api/contribuyente/search")
            self.assertEqual(
                parse_qs(url.query), {"search": ["A&B ÑANDÚ + CIA"], "page": ["2"]}
            )
            self.assertEqual(result, {"contribuyentes": [CONTRIBUYENTE], "paginas": 1})

    def test_empty_search_and_http_error_preserve_data(self):
        with local_api() as server:
            with TuRucClient(base_url=server.base_url) as client:
                self.assertEqual(
                    client.get_contribuyente_by_search("sin resultados"),
                    {"contribuyentes": [], "paginas": 0},
                )
                self.assertIsNone(client.get_contribuyente_by_ruc("99999999"))

    def test_redirects_are_followed(self):
        with local_api() as server:
            with TuRucClient(base_url=server.base_url + "redirect/") as client:
                self.assertEqual(
                    client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
            self.assertEqual(
                server.requests.get(timeout=2)[1],
                "/redirect/api/contribuyente/80024191-6",
            )
            self.assertEqual(
                server.requests.get(timeout=2)[1], "/api/contribuyente/80024191-6"
            )

    def test_explicit_close_closes_the_connection(self):
        with local_api() as server:
            client = TuRucClient(base_url=server.base_url)
            self.addCleanup(client.close)
            client.get_contribuyente_by_ruc("80024191-6")
            connection_id = server.requests.get(timeout=2)[0]
            client.close()
            self.assertEqual(server.closed.get(timeout=2), connection_id)
            with self.assertRaises(RuntimeError):
                client.get_contribuyente_by_ruc("80024191-6")

    def test_context_closes_connection_when_caller_raises(self):
        with local_api() as server:
            client = TuRucClient(base_url=server.base_url)
            self.addCleanup(client.close)
            with self.assertRaisesRegex(ValueError, "caller failure"):
                with client:
                    client.get_contribuyente_by_ruc("80024191-6")
                    raise ValueError("caller failure")
            self.assertEqual(
                server.closed.get(timeout=2), server.requests.get(timeout=2)[0]
            )

    def test_read_timeout_reaches_the_caller(self):
        release_response = threading.Event()
        with local_api(lambda: release_response.wait(timeout=2)) as server:
            try:
                with TuRucClient(base_url=server.base_url, timeout=0.02) as client:
                    with self.assertRaises(httpx.ReadTimeout):
                        client.get_contribuyente_by_ruc("80024191-6")
            finally:
                release_response.set()

    def test_legacy_functions_use_separate_connections(self):
        with local_api() as server:
            with patch("tu_ruc_python_client.client.URL", server.base_url):
                get_contribuyente_by_ruc("80024191-6")
                first = server.requests.get(timeout=2)[0]
                self.assertEqual(server.closed.get(timeout=2), first)
                get_contribuyente_by_ruc("80024191-6")
                second = server.requests.get(timeout=2)[0]
                self.assertEqual(server.closed.get(timeout=2), second)
            self.assertNotEqual(first, second)

    def test_existing_validation_rules_apply_before_network(self):
        with local_api() as server, TuRucClient(base_url=server.base_url) as client:
            with self.assertRaises(LengthError):
                client.get_contribuyente_by_search("ab")
            with self.assertRaises(LengthError):
                client.get_contribuyente_by_search("MINISTERIO", page=11)
            with self.assertRaises(ValueError):
                client.get_contribuyente_by_ruc("invalid")

    def test_default_timeout_and_disabling_timeout(self):
        with patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=lambda _: json_response(CONTRIBUYENTE),
        ) as send:
            with TuRucClient() as client:
                client.get_contribuyente_by_ruc("80024191-6")
            default_timeout = send.call_args.args[0].extensions["timeout"]
            with TuRucClient(timeout=None) as client:
                client.get_contribuyente_by_ruc("80024191-6")
            disabled_timeout = send.call_args.args[0].extensions["timeout"]
        self.assertEqual(
            default_timeout, dict(connect=10.0, read=10.0, write=10.0, pool=10.0)
        )
        self.assertEqual(
            disabled_timeout, dict(connect=None, read=None, write=None, pool=None)
        )

    def test_transport_error_reaches_the_caller(self):
        with patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=httpx.ConnectError("sin conexión"),
        ):
            with TuRucClient() as client:
                with self.assertRaises(httpx.RequestError):
                    client.get_contribuyente_by_ruc("80024191-6")


class AsyncReusableClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_reuses_connection_and_context_closes_it(self):
        with local_api() as server:
            client = AsyncTuRucClient(base_url=server.base_url)
            self.addAsyncCleanup(client.aclose)
            async with client:
                self.assertEqual(
                    await client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
                self.assertEqual(
                    await client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
                first = server.requests.get(timeout=2)
                second = server.requests.get(timeout=2)
                self.assertEqual(first[0], second[0])
            self.assertEqual(server.closed.get(timeout=2), first[0])

    async def test_search_preserves_encoding_pagination_and_base_path(self):
        with local_api() as server:
            async with AsyncTuRucClient(base_url=server.base_url + "gateway") as client:
                result = await client.get_contribuyente_by_search(
                    "A&B ÑANDÚ + CIA", page=2
                )
            url = urlsplit(server.requests.get(timeout=2)[1])
            self.assertEqual(url.path, "/gateway/api/contribuyente/search")
            self.assertEqual(
                parse_qs(url.query), {"search": ["A&B ÑANDÚ + CIA"], "page": ["2"]}
            )
            self.assertEqual(result, {"contribuyentes": [CONTRIBUYENTE], "paginas": 1})

    async def test_empty_search_and_http_error_preserve_data(self):
        with local_api() as server:
            async with AsyncTuRucClient(base_url=server.base_url) as client:
                self.assertEqual(
                    await client.get_contribuyente_by_search("sin resultados"),
                    {"contribuyentes": [], "paginas": 0},
                )
                self.assertIsNone(await client.get_contribuyente_by_ruc("99999999"))

    async def test_redirects_are_followed(self):
        with local_api() as server:
            async with AsyncTuRucClient(
                base_url=server.base_url + "redirect/"
            ) as client:
                self.assertEqual(
                    await client.get_contribuyente_by_ruc("80024191-6"), CONTRIBUYENTE
                )
            self.assertEqual(
                server.requests.get(timeout=2)[1],
                "/redirect/api/contribuyente/80024191-6",
            )
            self.assertEqual(
                server.requests.get(timeout=2)[1], "/api/contribuyente/80024191-6"
            )

    async def test_explicit_aclose_closes_the_connection(self):
        with local_api() as server:
            client = AsyncTuRucClient(base_url=server.base_url)
            self.addAsyncCleanup(client.aclose)
            await client.get_contribuyente_by_ruc("80024191-6")
            connection_id = server.requests.get(timeout=2)[0]
            await client.aclose()
            self.assertEqual(server.closed.get(timeout=2), connection_id)
            with self.assertRaises(RuntimeError):
                await client.get_contribuyente_by_ruc("80024191-6")

    async def test_context_closes_connection_when_caller_raises(self):
        with local_api() as server:
            client = AsyncTuRucClient(base_url=server.base_url)
            self.addAsyncCleanup(client.aclose)
            with self.assertRaisesRegex(ValueError, "caller failure"):
                async with client:
                    await client.get_contribuyente_by_ruc("80024191-6")
                    raise ValueError("caller failure")
            self.assertEqual(
                server.closed.get(timeout=2), server.requests.get(timeout=2)[0]
            )

    async def test_read_timeout_reaches_the_caller(self):
        release_response = threading.Event()
        with local_api(lambda: release_response.wait(timeout=2)) as server:
            try:
                async with AsyncTuRucClient(
                    base_url=server.base_url, timeout=0.02
                ) as client:
                    with self.assertRaises(httpx.ReadTimeout):
                        await client.get_contribuyente_by_ruc("80024191-6")
            finally:
                release_response.set()

    async def test_requests_can_be_in_flight_concurrently(self):
        release_response = threading.Event()
        with local_api(lambda: release_response.wait(timeout=5)) as server:
            async with AsyncTuRucClient(base_url=server.base_url) as client:
                calls = [
                    asyncio.create_task(client.get_contribuyente_by_ruc("80024191-6")),
                    asyncio.create_task(client.get_contribuyente_by_ruc("80024191-6")),
                ]
                try:
                    first = await asyncio.to_thread(server.requests.get, timeout=2)
                    second = await asyncio.to_thread(server.requests.get, timeout=2)
                    self.assertNotEqual(first[0], second[0])
                    self.assertFalse(any(call.done() for call in calls))
                finally:
                    release_response.set()
                    results = await asyncio.gather(*calls)
                self.assertEqual(results, [CONTRIBUYENTE, CONTRIBUYENTE])

    async def test_existing_validation_rules_apply_before_network(self):
        with local_api() as server:
            async with AsyncTuRucClient(base_url=server.base_url) as client:
                with self.assertRaises(LengthError):
                    await client.get_contribuyente_by_search("ab")
                with self.assertRaises(LengthError):
                    await client.get_contribuyente_by_search("MINISTERIO", page=11)
                with self.assertRaises(ValueError):
                    await client.get_contribuyente_by_ruc("invalid")

    async def test_default_timeout_and_disabling_timeout(self):
        with patch(
            "httpx.AsyncHTTPTransport.handle_async_request",
            side_effect=lambda _: json_response(CONTRIBUYENTE),
        ) as send:
            async with AsyncTuRucClient() as client:
                await client.get_contribuyente_by_ruc("80024191-6")
            default_timeout = send.call_args.args[0].extensions["timeout"]
            async with AsyncTuRucClient(timeout=None) as client:
                await client.get_contribuyente_by_ruc("80024191-6")
            disabled_timeout = send.call_args.args[0].extensions["timeout"]
        self.assertEqual(
            default_timeout, dict(connect=10.0, read=10.0, write=10.0, pool=10.0)
        )
        self.assertEqual(
            disabled_timeout, dict(connect=None, read=None, write=None, pool=None)
        )

    async def test_transport_error_reaches_the_caller(self):
        with patch(
            "httpx.AsyncHTTPTransport.handle_async_request",
            side_effect=httpx.ConnectError("sin conexión"),
        ):
            async with AsyncTuRucClient() as client:
                with self.assertRaises(httpx.RequestError):
                    await client.get_contribuyente_by_ruc("80024191-6")


if __name__ == "__main__":
    unittest.main()
