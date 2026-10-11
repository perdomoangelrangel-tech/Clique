"""Siembra una base de prueba usando la app de verdad, por HTTP, para que el archivo tenga todo lo que la app guarda.

    python -m backend.datos.sembrar [--salida data/db.json] [--semanas 1]

`scripts/seed.py` solo reinicia o borra una base que ya existe; esta herramienta la llena. Levanta el servidor en el mismo
proceso sobre un archivo nuevo, hace lo que haría un grupo de amigos (cuentas, círculos, mercados, los juegos, póker con
dinero real, préstamos, transferencias, tienda, bolsa, chats, votos de fondos) y cierra semanas moviendo el reloj de los
registros hacia atrás. Todo el dinero se mueve por las rutas de la app, así que el libro del archivo cuadra.

Las respuestas que no son 200 se anotan y se cuentan; no detienen la siembra (algunos juegos se pierden, algunos retos no
están listos). Sirve a `inventario` (el modelo real) y a `importar_archivo` (la simulación)."""
import argparse
import http.client
import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASSWORD = "secret123"
NAMES = ("alicia", "beto", "carla", "dani", "elena", "fede")


class Client:
    def __init__(self, port, log):
        self.port, self.cookie, self.log = port, None, log

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Content-Type": "application/json"}
        if self.cookie:
            h["Cookie"] = self.cookie
        conn.request(method, path, json.dumps(body or {}) if method != "GET" else None, h)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        sc = r.getheader("Set-Cookie")
        if sc and sc.startswith("sid=") and "Max-Age=0" not in sc:
            self.cookie = sc.split(";")[0]
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        self.log.append((method, path, r.status, data.get("error") if isinstance(data, dict) else None))
        return r.status, data

    def post(self, path, body=None):
        return self.call("POST", path, body)

    def get(self, path):
        return self.call("GET", path)


def _rid(tag, n=[0]):
    n[0] += 1
    return f"seed-{tag}-{n[0]:06d}"


def _casino(c, acct=None):
    extra = {"acct": acct} if acct else {}
    c.post("/api/games/limbo", {"amount": 5, "target": 2, **extra})
    c.post("/api/games/dice", {"amount": 5, "direction": "over", "target": 50, **extra})
    c.post("/api/games/coinflip", {"amount": 5, "side": "heads", **extra})
    c.post("/api/games/war", {"amount": 5, "tie": 1, "colouredTie": 1, **extra})
    c.post("/api/games/wheel", {"risk": "low", "amount": 5, **extra})
    c.post("/api/games/roulette", {"bets": [{"type": "red", "amount": 5}, {"type": "dozen", "value": 2, "amount": 1}], **extra})
    st, _ = c.post("/api/games/blackjack/deal", {"amount": 5, **extra})
    if st == 200:
        c.post("/api/games/blackjack/action", {"action": "stand"})
    if c.post("/api/games/chicken/start", {"amount": 5, "difficulty": "easy", **extra})[0] == 200:
        c.post("/api/games/chicken/step")
        c.post("/api/games/chicken/cashout")
    if c.post("/api/games/mines/start", {"amount": 5, "size": 25, "mines": 1, **extra})[0] == 200:
        c.post("/api/games/mines/pick", {"tile": 0})
        c.post("/api/games/mines/cashout")
    if c.post("/api/games/moles/start", {"amount": 5, "moles": 3, **extra})[0] == 200:
        c.post("/api/games/moles/pick", {"hole": 0})
        c.post("/api/games/moles/cashout")
    if c.post("/api/games/tower/start", {"amount": 5, "risk": "easy", **extra})[0] == 200:
        c.post("/api/games/tower/pick", {"tile": 0})
        c.post("/api/games/tower/cashout")
    if c.post("/api/games/hilo/start", {"amount": 5, **extra})[0] == 200:
        if c.post("/api/games/hilo/guess", {"pick": "higher"})[0] != 200:
            c.post("/api/games/hilo/guess", {"pick": "lower"})
        c.post("/api/games/hilo/cashout")
    if c.post("/api/games/rps/start", {"amount": 5, **extra})[0] == 200:
        c.post("/api/games/rps/play", {"pick": "rock"})
        c.post("/api/games/rps/cashout")
    c.post("/api/games/coinflip", {"amount": 1, "side": "tails", "demo": True})       # la cartera de práctica


def _week_of_activity(cs, ids, circle_ids, admin_password, rounds=2):
    a, b, c, d, e, f = cs
    from backend import config        # noqa: F401  (el servidor ya lo cargó)
    # fondos agregados por votación, en las dos cuentas (el resto del grupo vota)
    for who, acct, amount in ((a, "accumulated", 400), (b, "accumulated", 400), (c, "weekly", 50)):
        st, out = who.post("/api/wallet/deposit", {"amount": amount, "password": admin_password, "account": acct})
        vote = out.get("vote") if st == 200 else None
        if vote and vote.get("status") == "open":
            for voter in cs:
                if voter is not who:
                    voter.post(f"/api/fundvotes/{vote['id']}/vote", {"favor": True})
    # mercados: crear, comprar, vender, comentar
    mids = []
    for owner, cid in ((a, circle_ids[0]), (b, circle_ids[1])):
        st, out = owner.post("/api/markets", {"circleId": cid, "question": "¿Quién llega tarde el viernes?",
                                               "outcomes": ["Beto", "Carla", "Nadie"], "category": "General"})
        if st == 200:
            mids.append(out["market"]["id"])
        st, out = owner.post("/api/markets", {"circleId": cid, "question": "¿Llueve el sábado en la tarde?"})
        if st == 200:
            mids.append(out["market"]["id"])
    for m in mids:
        for who in cs:
            who.post(f"/api/markets/{m}/trade", {"outcome": 0, "amount": 20, "requestId": _rid("trade")})
            who.post(f"/api/markets/{m}/trade", {"outcome": 1, "amount": 10})
        c.post(f"/api/markets/{m}/trade", {"action": "sell", "outcome": 0, "shares": 2})
        d.post(f"/api/markets/{m}/comments", {"text": "Esto ya está decidido"})
    if mids:
        a.post(f"/api/markets/{mids[0]}/resolve", {"outcome": 0})
    # el casino, en las dos cuentas
    for _ in range(rounds):
        for who in cs:
            _casino(who)
    _casino(a, "accumulated")
    # póker con dinero real
    st, out = a.post("/api/poker/tables", {"name": "Viernes", "visibility": "public"})
    if st == 200 and out.get("table"):
        tid = out["table"]["id"]
        a.post(f"/api/poker/tables/{tid}/settings", {"money": "real", "bigBlind": 1, "smallBlind": 0.5, "stack": 100})
        b.post("/api/poker/join", {"id": tid, "confirm": True})
        a.post(f"/api/poker/tables/{tid}/vote", {"accept": True})
        b.post(f"/api/poker/tables/{tid}/vote", {"accept": True})
        a.post(f"/api/poker/tables/{tid}/start")
        for who in (a, b, a, b):
            who.post(f"/api/poker/tables/{tid}/action", {"action": "fold"})
        b.post(f"/api/poker/tables/{tid}/leave")
        a.post(f"/api/poker/tables/{tid}/leave")
    # préstamo
    for m in mids[:1]:                                                 # una apuesta grande deja su cuenta bajo la asignación
        e.post(f"/api/markets/{m}/trade", {"outcome": 2, "amount": 400})
    for amount in (200, 50, 10, 1):                                    # lo que alcance a pedir según lo que tiene
        if e.post("/api/loans/borrow", {"amount": amount, "confirm": True, "requestId": _rid("loan")})[0] == 200:
            break
    e.post("/api/loans/repay", {"amount": 5, "requestId": _rid("repay")})
    # transferencias entre amigos, en las dos cuentas
    for to in ids[1:]:                                                 # al primer amigo que tenga lugar en su cuenta semanal
        if a.post("/api/transfers", {"to": to, "amount": 2, "password": "transfer-pw-1", "confirm": True,
                                     "account": "weekly", "requestId": _rid("xfer"), "note": "lo del taxi"})[0] == 200:
            break
    a.post("/api/transfers", {"to": ids[1], "amount": 15, "password": "transfer-pw-1", "confirm": True,
                              "account": "weekly", "requestId": _rid("xfer"), "note": "lo del taxi"})
    b.post("/api/transfers", {"to": ids[0], "amount": 5, "password": "transfer-pw-1", "confirm": True,
                              "account": "accumulated", "requestId": _rid("xfer")})
    # tienda y bolsa (cuenta acumulada)
    for who in (a, b):
        who.post("/api/store/buy", {"item": "frame_lime", "requestId": _rid("buy")})
        who.post("/api/store/equip", {"item": "frame_lime"})
        st, q = who.post("/api/stocks/quote", {"symbol": "NEXO", "side": "buy", "shares": 1})
        if st == 200:
            who.post("/api/stocks/trade", {"quoteId": q["quoteId"], "requestId": _rid("stock")})
    # retos, hitos, avisos
    for who in cs:
        st, ch = who.get("/api/challenges")
        for item in (ch.get("challenges") or ch.get("items") or []) if isinstance(ch, dict) else []:
            if isinstance(item, dict) and item.get("id"):
                who.post("/api/challenges/claim", {"id": item["id"]})
        st, pr = who.get("/api/progress")
        for tier in (pr.get("milestones") or []) if isinstance(pr, dict) else []:
            if isinstance(tier, dict) and tier.get("id"):
                who.post("/api/milestones/claim", {"id": tier["id"]})
        who.post("/api/inbox/seen", {})


class Clock:
    """Mueve el reloj de toda la app (todo sale de time.time) para sembrar semanas pasadas y luego volver al presente."""

    def __init__(self):
        self.real, self.offset = time.time, 0.0

    def __enter__(self):
        time.time = lambda: self.real() - self.offset
        return self

    def __exit__(self, *exc):
        time.time = self.real
        return False

    def days_ago(self, days):
        self.offset = days * 86400.0


def _leave_a_poker_table_open(c, d):
    """Una mesa de fichas de juego con dos personas sentadas, para que la base tenga una mesa viva."""
    st, out = c.post("/api/poker/tables", {"name": "Mesa del sábado", "visibility": "public"})
    if st == 200 and out.get("table"):
        d.post("/api/poker/join", {"id": out["table"]["id"]})


def seed(path, weeks=1, log=None):
    """Crea `path` desde cero con actividad de `weeks` semanas cerradas más la semana en curso. Devuelve la bitácora de
    llamadas [(método, ruta, estado, error)]."""
    log = [] if log is None else log
    sys.path.insert(0, ROOT)
    import server                                         # noqa: E402
    from backend import config, economy, exchange, stockengine, weekly
    from backend.store import store

    if os.path.exists(path):
        os.remove(path)
    clock = Clock().__enter__()
    keep = economy.LEDGER_KEEP
    economy.LEDGER_KEEP = 30                          # que el libro se compacte y la base tenga resúmenes (ledger_sum)
    clock.days_ago(7 * weeks + 2)
    store.path = os.path.abspath(path)
    store.data = {}
    store.load()
    store.data["meta"]["requirements_from"] = "9999-12-31"
    market_path = os.path.join(os.path.dirname(store.path), "market.json")      # la bolsa vive en su propio archivo
    if os.path.exists(market_path):
        os.remove(market_path)
    exchange.engine = stockengine.Engine(path=market_path)
    exchange.engine.load()
    weekly.tick()                                     # la primera vuelta: anota la semana en curso y sus retos
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        cs = [Client(port, log) for _ in NAMES]
        ids = []
        for cl, name in zip(cs, NAMES):
            st, out = cl.post("/api/auth/register", {"username": name, "password": PASSWORD,
                                                        "email": f"{name}@example.com"})
            if st != 200:
                raise RuntimeError(f"no se pudo crear la cuenta {name}: {out}")
            ids.append(out["user"]["id"])
            cl.post("/api/transfers/password", {"loginPassword": PASSWORD, "newPassword": "transfer-pw-1"})
            cl.post("/api/profile", {"bio": f"Hola, soy {name}"})
        a = cs[0]
        for other, name in zip(cs[1:], NAMES[1:]):                     # todos amigos de todos, de ida y vuelta
            a.post("/api/friends/request", {"username": name})
            other.post("/api/friends/accept", {"userId": ids[0]})
        cs[1].post("/api/friends/request", {"username": NAMES[2]})
        cs[2].post("/api/friends/accept", {"userId": ids[1]})
        circle_ids = []
        for owner, name, members in ((cs[0], "Los del viernes", cs[1:]), (cs[1], "Oficina", cs[2:5])):
            st, out = owner.post("/api/circles", {"name": name, "visibility": "private"})
            cid, code = out["circle"]["id"], out["circle"]["inviteCode"]
            circle_ids.append(cid)
            for m in members:
                m.post("/api/circles/join", {"code": code})
            owner.post(f"/api/circles/{cid}/punishments", {"text": "Invita los tacos"})
        st, out = a.post("/api/chats/dm", {"userId": ids[1]})
        if st == 200:
            a.post(f"/api/chats/{out['chat']['id']}/send", {"text": "¿Vas el viernes?"})
        st, out = a.post("/api/chats/group", {"name": "Tacos", "members": ids[1:4]})
        if st == 200:
            cs[2].post(f"/api/chats/{out['chat']['id']}/send", {"text": "Yo llevo las tortillas"})
        for w in range(weeks):                                         # cada semana pasada, y su cierre
            clock.days_ago(7 * (weeks - w) + 1)
            with server.LOCK:
                weekly.tick()
            _week_of_activity(cs, ids, circle_ids, config.ADMIN_PASSWORD)
        clock.days_ago(0)
        with server.LOCK:
            weekly.tick()                                              # cierra la última semana: premios, préstamos, reinicio
            store.save()
        _week_of_activity(cs, ids, circle_ids, config.ADMIN_PASSWORD, rounds=1)
        _leave_a_poker_table_open(cs[2], cs[3])
        with server.LOCK:
            store.save()
            exchange.engine.write(exchange.engine.snapshot())
    finally:
        srv.shutdown()
        srv.server_close()
        economy.LEDGER_KEEP = keep
        clock.__exit__()
    return log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--salida", default=os.path.join(ROOT, "data", "db.json"))
    ap.add_argument("--semanas", type=int, default=1)
    args = ap.parse_args(argv)
    log = seed(args.salida, args.semanas)
    bad = [x for x in log if x[2] != 200]
    print(f"Base sembrada en {args.salida}: {len(log)} llamadas, {len(bad)} sin 200.")
    for m, p, s, err in bad:
        print(f"  {s} {m} {p}: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
