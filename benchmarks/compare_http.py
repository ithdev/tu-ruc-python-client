"""Compare HTTP transports against a private local HTTP/1.1 server."""

import argparse
import asyncio
import json
import math
import multiprocessing
import os
import platform
import socket
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, nullcontext
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from time import perf_counter, sleep

import httpx
import requests

PAYLOAD = {
    "data": {"doc": 1234567, "dv": 8, "ruc": "1234567-8", "razonSocial": "JUAN PÉREZ"},
    "message": "Consulta exitosa",
}
BODY = json.dumps(PAYLOAD, ensure_ascii=False).encode("utf-8")
HEADERS = {
    "User-Agent": "tu-ruc-local-benchmark",
    "Accept": "application/json",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
}
CASES = [
    "requests_get",
    "httpx_get",
    "requests_session",
    "httpx_client",
    "requests_threads",
    "httpx_threads",
    "httpx_async",
]


def serve(control, delay_ms):
    """Own the server in a separate process; control uses a private pipe."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.server.counter_lock:
                self.server.connection_count += 1
                self.connection_id = self.server.connection_count

        def do_GET(self):
            if delay_ms:
                sleep(delay_ms / 1000)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(BODY)))
            self.send_header("X-Connection-ID", str(self.connection_id))
            self.end_headers()
            self.wfile.write(BODY)

        def log_message(self, *_):
            pass

    class Server(ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True

    with Server(("127.0.0.1", 0), Handler) as server:
        server.connection_count = 0
        server.counter_lock = threading.Lock()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        control.send(server.server_port)
        control.recv()
        server.shutdown()
        thread.join()
    control.close()


def make_client(kind):
    if kind.startswith("requests"):
        client = requests.Session()
        client.trust_env = False
        client.headers.update(HEADERS)
        client.mount(
            "http://",
            requests.adapters.HTTPAdapter(
                pool_connections=1, pool_maxsize=1, max_retries=0, pool_block=True
            ),
        )
        return client
    return httpx.Client(
        headers=HEADERS,
        trust_env=False,
        http2=False,
        limits=httpx.Limits(
            max_connections=1, max_keepalive_connections=1, keepalive_expiry=None
        ),
    )


def checked_connection(response):
    assert response.status_code == 200, response.status_code
    assert response.json() == PAYLOAD, "Unexpected JSON payload"
    return int(response.headers["X-Connection-ID"])


def sync_requests(get, url, count):
    latencies = []
    connections = set()
    for _ in range(count):
        started = perf_counter()
        response = get(url)
        connections.add(checked_connection(response))
        response.close()
        latencies.append((perf_counter() - started) * 1000)
    return latencies, connections


def metrics(elapsed, batches):
    latencies = [value for values, _ in batches for value in values]
    connections = set().union(*(ids for _, ids in batches))
    return {
        "wall_seconds": elapsed,
        "throughput_requests_per_second": len(latencies) / elapsed,
        "latency_median_ms": statistics.median(latencies),
        "latency_p95_ms": sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1],
        "connections_used": len(connections),
        "requests_completed": len(latencies),
    }


def sequential(kind, url, count, warmup):
    context = (
        nullcontext() if kind in {"requests_get", "httpx_get"} else make_client(kind)
    )
    with context as client:
        if kind == "requests_get":
            # Empty proxy URLs force loopback traffic to stay local, including
            # when the caller has HTTP_PROXY / ALL_PROXY set in the environment.
            get = partial(
                requests.get,
                headers=HEADERS,
                timeout=10,
                proxies={"http": "", "https": ""},
            )
        elif kind == "httpx_get":
            get = partial(httpx.get, headers=HEADERS, timeout=10, trust_env=False)
        else:
            get = partial(client.get, timeout=10)
        sync_requests(get, url, warmup)
        started = perf_counter()
        batch = sync_requests(get, url, count)
        return metrics(perf_counter() - started, [batch])


def threaded(kind, url, count, warmup, concurrency):
    started = []
    ready = threading.Barrier(
        concurrency + 1, timeout=30, action=lambda: started.append(perf_counter())
    )

    def worker(client, index):
        get = partial(client.get, timeout=10)
        sync_requests(get, url, warmup)
        ready.wait()
        return sync_requests(
            get, url, count // concurrency + (index < count % concurrency)
        )

    with ExitStack() as stack:
        clients = [stack.enter_context(make_client(kind)) for _ in range(concurrency)]
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(worker, client, index)
                for index, client in enumerate(clients)
            ]
            ready.wait()
            batches = [future.result() for future in futures]
            return metrics(perf_counter() - started[0], batches)


async def async_requests(client, url, count):
    latencies = []
    connections = set()
    for _ in range(count):
        started = perf_counter()
        response = await client.get(url, timeout=10)
        connections.add(checked_connection(response))
        await response.aclose()
        latencies.append((perf_counter() - started) * 1000)
    return latencies, connections


async def asynchronous(url, count, warmup, concurrency):
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
        keepalive_expiry=None,
    )
    async with httpx.AsyncClient(
        headers=HEADERS, trust_env=False, http2=False, limits=limits
    ) as client:
        await asyncio.gather(
            *(async_requests(client, url, warmup) for _ in range(concurrency))
        )
        tasks = [
            asyncio.create_task(
                async_requests(
                    client, url, count // concurrency + (index < count % concurrency)
                )
            )
            for index in range(concurrency)
        ]
        started = perf_counter()
        batches = await asyncio.gather(*tasks)
        return metrics(perf_counter() - started, batches)


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def nonnegative_float(value):
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=positive_int, default=300)
    parser.add_argument("--concurrency", type=positive_int, default=8)
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument(
        "--warmup",
        type=positive_int,
        default=5,
        help="untimed requests per client/worker before each run",
    )
    parser.add_argument(
        "--delays-ms", type=nonnegative_float, nargs="+", default=[0, 10]
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("results.json")
    )
    args = parser.parse_args()
    if args.requests < args.concurrency:
        parser.error("--requests must be at least --concurrency")
    if sys.flags.optimize:
        parser.error("run without -O so status/payload assertions remain active")

    result = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "os": platform.system(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "load_average_start": os.getloadavg(),
            "packages": {
                name: version(name)
                for name in ["requests", "urllib3", "httpx", "httpcore", "h11", "anyio"]
            },
        },
        "settings": {
            "requests_per_run": args.requests,
            "concurrency": args.concurrency,
            "repeats": args.repeats,
            "warmup_per_client_or_worker": args.warmup,
            "delays_ms": args.delays_ms,
            "payload_bytes": len(BODY),
            "http_version": "1.1",
            "tls": False,
            "server_tcp_nodelay": True,
            "order": "rotate by round; reverse every other round",
        },
        "runs": [],
    }
    context = multiprocessing.get_context("spawn")
    for delay in args.delays_ms:
        control, server_control = context.Pipe()
        server = context.Process(
            target=serve, args=(server_control, delay), daemon=True
        )
        server.start()
        server_control.close()
        try:
            port = control.recv()
            url = f"http://127.0.0.1:{port}/api/contribuyente/1234567-8"
            for repeat in range(args.repeats):
                offset = repeat % len(CASES)
                order = CASES[offset:] + CASES[:offset]
                if repeat % 2:
                    order.reverse()
                for position, case in enumerate(order):
                    match case:
                        case (
                            "requests_get"
                            | "httpx_get"
                            | "requests_session"
                            | "httpx_client"
                        ):
                            row = sequential(case, url, args.requests, args.warmup)
                            concurrency = 1
                        case "requests_threads" | "httpx_threads":
                            row = threaded(
                                case, url, args.requests, args.warmup, args.concurrency
                            )
                            concurrency = args.concurrency
                        case "httpx_async":
                            row = asyncio.run(
                                asynchronous(
                                    url, args.requests, args.warmup, args.concurrency
                                )
                            )
                            concurrency = args.concurrency
                    assert row["requests_completed"] == args.requests
                    row.update(
                        case=case,
                        delay_ms=delay,
                        repeat=repeat + 1,
                        position=position + 1,
                        concurrency=concurrency,
                    )
                    result["runs"].append(row)
                    print(
                        f"delay={delay:g} ms round={repeat + 1} {case:18} "
                        f"{row['throughput_requests_per_second']:8.1f} req/s "
                        f"p95={row['latency_p95_ms']:7.3f} ms "
                        f"connections={row['connections_used']}",
                        flush=True,
                    )
        finally:
            control.send("stop")
            server.join(timeout=10)
            if server.is_alive():
                server.terminate()
                server.join()
            control.close()
    result["environment"]["load_average_end"] = os.getloadavg()
    result["summary"] = []
    for delay in args.delays_ms:
        for case in CASES:
            rows = [
                row
                for row in result["runs"]
                if row["delay_ms"] == delay and row["case"] == case
            ]
            summary = {
                "case": case,
                "delay_ms": delay,
                "concurrency": rows[0]["concurrency"],
            }
            for key in [
                "wall_seconds",
                "throughput_requests_per_second",
                "latency_median_ms",
                "latency_p95_ms",
                "connections_used",
            ]:
                values = [row[key] for row in rows]
                summary[key] = {
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                }
            result["summary"].append(summary)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
