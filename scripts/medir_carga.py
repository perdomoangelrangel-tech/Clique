"""Mide cuánto aguanta el servidor: N personas simuladas apostando en mercados y en el casino a la vez.

    python scripts/medir_carga.py --personas 50 --segundos 30
    python scripts/medir_carga.py --url http://localhost:3000 ...     # contra un servidor que ya corre (crea cuentas en él)

Sin --url, arranca su propio server.py con una base vacía en una carpeta temporal y lo apaga al final: no toca tus datos.
Cada persona se registra, entra al mismo círculo, deja abierta su conexión en vivo (/api/stream) y repite sin pausa:
ver los mercados, apostar en el mercado, tirar los dados del casino y ver su saldo. Al final imprime peticiones por segundo
y la latencia p50/p95/p99 de cada tipo, en milisegundos. Es la línea base para la etapa C de ADR-006.
"""
import argparse
import http.client
import json
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIX = (("mercados", 25), ("apuesta_mercado", 30), ("dados", 30), ("saldo", 15))     # tipo de petición, peso
BET = 0.1                                                                          # la apuesta mínima: nadie se queda sin fichas


class Person:
    def __init__(self, host, port, name):
        self.host, self.port, self.name = host, port, name
        self.conn = http.client.HTTPConnection(host, port, timeout=30)
        self.cookie = None

    def call(self, method, path, body=None):
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        payload = json.dumps(body) if body is not None else None
        for attempt in (1, 2):                          # una conexión que el servidor cerró se abre de nuevo una vez
            try:
                self.conn.request(method, path, payload, headers)
                r = self.conn.getresponse()
                raw = r.read()
                break
            except (http.client.HTTPException, OSError):
                self.conn.close()
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
                if attempt == 2:
                    raise
        if r.getheader("Connection", "").lower() == "close":
            self.conn.close()
            self.conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
        cookie = r.getheader("Set-Cookie")
        if cookie and cookie.startswith("sid=") and "Max-Age=0" not in cookie:
            self.cookie = cookie.split(";")[0]
        try:
            return r.status, json.loads(raw or b"null")
        except ValueError:
            return r.status, None


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(log_path):
    port = free_port()
    data = tempfile.mkdtemp(prefix="clique-carga-")
    env = {**os.environ, "DATA_DIR": data, "PORT": str(port), "HOST": "127.0.0.1", "EMAIL_REQUIRED": "0", "PYTHONUNBUFFERED": "1"}
    env.pop("CLIQUE_ENV", None)
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"El servidor no arrancó; mira {log_path}")
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            c.request("GET", "/api/salud")
            if c.getresponse().status == 200:
                return proc, port, data, log
        except OSError:
            time.sleep(0.3)
    proc.kill()
    raise SystemExit(f"El servidor no respondió en 60 s; mira {log_path}")


def percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    k = min(len(sorted_values) - 1, max(0, math.ceil(p / 100 * len(sorted_values)) - 1))     # nearest rank
    return sorted_values[k]


def listen(host, port, cookie, stop):
    """The live connection every open screen keeps: read and throw away whatever arrives."""
    try:
        conn = http.client.HTTPConnection(host, port)    # no time limit: it is quiet until something happens
        conn.request("GET", "/api/stream", headers={"Cookie": cookie})
        r = conn.getresponse()
        while not stop.is_set() and r.fp.readline():
            pass
    except (http.client.HTTPException, OSError):
        pass


def set_up(host, port, n):
    """N people in one private circle, with one open market to bet on."""
    tag = format(random.getrandbits(24), "06x")
    people = [Person(host, port, f"carga_{tag}_{i}") for i in range(n)]
    for p in people:
        st, d = p.call("POST", "/api/auth/register", {"username": p.name, "password": "carga-123456"})
        if st != 200:
            raise SystemExit(f"No se pudo registrar a {p.name}: {st} {d}")
    owner = people[0]
    st, d = owner.call("POST", "/api/circles", {"name": f"Carga {tag}", "visibility": "private"})
    if st != 200:
        raise SystemExit(f"No se pudo crear el círculo: {st} {d}")
    cid, code = d["circle"]["id"], d["circle"]["inviteCode"]
    for p in people[1:]:
        st, d = p.call("POST", "/api/circles/join", {"code": code})
        if st != 200:
            raise SystemExit(f"{p.name} no pudo entrar al círculo: {st} {d}")
    st, d = owner.call("POST", "/api/markets", {"circleId": cid, "question": "¿Aguanta el servidor esta prueba de carga?"})
    if st != 200:
        raise SystemExit(f"No se pudo crear el mercado: {st} {d}")
    return people, d["market"]["id"]


def work(person, market_id, until, samples, rng):
    requests = {
        "mercados": ("GET", "/api/markets", None),
        "apuesta_mercado": ("POST", f"/api/markets/{market_id}/trade", lambda: {"outcome": rng.randrange(2), "amount": BET}),
        "dados": ("POST", "/api/games/dice", lambda: {"amount": BET, "direction": "over", "target": 50}),
        "saldo": ("GET", "/api/me", None),
    }
    kinds, weights = zip(*MIX)
    while time.monotonic() < until:
        kind = rng.choices(kinds, weights)[0]
        method, path, body = requests[kind]
        started = time.perf_counter()
        try:
            status, _ = person.call(method, path, body() if body else None)
        except (http.client.HTTPException, OSError):
            status = 0
        samples.append((kind, time.perf_counter() - started, status))


def report(samples, seconds, people, out):
    by_kind = {}
    for kind, took, status in samples:
        by_kind.setdefault(kind, []).append((took, status))
    rows = []
    for kind in [k for k, _ in MIX] + ["total"]:
        group = [(t, s) for k, t, s in samples] if kind == "total" else by_kind.get(kind, [])
        times = sorted(t * 1000 for t, _ in group)
        failed = sum(1 for _, s in group if s != 200)
        rows.append((kind, len(group), len(group) / seconds, percentile(times, 50), percentile(times, 95), percentile(times, 99), failed))
    print("", file=out)
    print(f"Carga: {people} personas durante {seconds:.0f} s, sin pausas entre peticiones (Python {sys.version.split()[0]}, {sys.platform})", file=out)
    print(f"{'tipo':<17}{'peticiones':>11}{'por seg':>10}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'no 200':>8}", file=out)
    for kind, count, rps, p50, p95, p99, failed in rows:
        print(f"{kind:<17}{count:>11}{rps:>10.1f}{p50:>9.1f}{p95:>9.1f}{p99:>9.1f}{failed:>8}", file=out)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mide peticiones por segundo y latencia con N personas simuladas.")
    parser.add_argument("--personas", type=int, default=50)
    parser.add_argument("--segundos", type=float, default=30)
    parser.add_argument("--url", help="un servidor que ya corre (por omisión arranca uno propio con una base vacía)")
    parser.add_argument("--sin-vivo", action="store_true", help="no abre la conexión en vivo (/api/stream) de cada persona")
    parser.add_argument("--json", help="guarda los resultados en este archivo")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    proc = data = log = None
    if args.url:
        u = urllib.parse.urlparse(args.url)
        host, port = u.hostname, u.port or 80
    else:
        log_path = os.path.join(tempfile.gettempdir(), "clique-carga-servidor.log")
        proc, port, data, log = start_server(log_path)
        host = "127.0.0.1"
        print(f"Servidor propio en el puerto {port} (registro en {log_path})")
    stop = threading.Event()
    try:
        print(f"Preparando {args.personas} personas...")
        people, market_id = set_up(host, port, args.personas)
        if not args.sin_vivo:
            for p in people:
                threading.Thread(target=listen, args=(host, port, p.cookie, stop), daemon=True).start()
            time.sleep(0.5)
        samples = []                                    # list.append is safe across threads
        started = time.monotonic()
        until = started + args.segundos
        threads = [threading.Thread(target=work, args=(p, market_id, until, samples, random.Random(i)))
                   for i, p in enumerate(people)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - started
        rows = report(samples, elapsed, args.personas, sys.stdout)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump({"personas": args.personas, "segundos": elapsed, "vivo": not args.sin_vivo, "python": sys.version.split()[0],
                           "sistema": sys.platform, "filas": [dict(zip(("tipo", "peticiones", "por_seg", "p50_ms", "p95_ms", "p99_ms", "no_200"), r))
                                                             for r in rows]}, f, indent=2, ensure_ascii=False)
        return 0
    finally:
        stop.set()
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()
            shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
