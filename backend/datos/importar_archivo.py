"""El importador del archivo (db.json) al esquema de Postgres (supabase/migrations). Etapa A de ADR-006: solo simula.

    python -m backend.datos.importar_archivo --simular data/db.json

Lee el archivo sin tocarlo (no usa store.load, que haría copias y correría migraciones), arma el plan de lo que insertaría
en cada tabla y comprueba el dinero:

  * el saldo de cada cuenta de persona en el archivo (users[].balance y users[].accum) es la suma del libro importado;
  * renglón por renglón, el saldo que el archivo anotó después de cada movimiento ("b") es el que da el libro importado;
  * ninguna cuenta de persona queda negativa en ningún punto (post_transaction lo rechazaría);
  * no hay renglones del libro de alguien que no existe, ni datos que el esquema rechazaría (nombres, preguntas...).

Toda diferencia se lista y NO se corrige: decidir qué hacer con ella es del dueño. Sale con 0 si no hay diferencias y con 1
si las hay.

Cómo se pasa el libro de un lado a doble partida: el archivo anota un renglón por persona y cuenta (sin contrapartida).
Cada renglón se vuelve una transacción de dos líneas: la cuenta de la persona y una cuenta del sistema según la familia de
la razón (SYSTEM_FOR). Los resúmenes compactados (ledger_sum) entran como una transacción "import.carried" por cuenta, antes
de los renglones que siguen completos. Los renglones de 0 centavos (un tope que no movió nada) no se pueden asentar y se
cuentan aparte.

`aplicar(plan, dsn)` mete el plan en un Postgres (solo pruebas locales; nunca Supabase de producción, D9).
"""
import argparse
import json
import math
import re
import sys
import uuid
from collections import OrderedDict, defaultdict

NAMESPACE = uuid.UUID("5b7c4a32-8f0e-4b8e-9a51-3c1d2e0f6a77")      # fijo: el mismo archivo da siempre los mismos uuid

PERSON_ACCOUNTS = (("weekly", "balance"), ("accumulated", "accum"))
# La familia de la razón (lo que va antes del primer punto) -> la cuenta del sistema que es su contrapartida.
SYSTEM_FOR = {
    "casino": "casino", "market": "market", "poker": "poker", "stocks": "stocks", "store": "store",
    "weekly": "weekly", "challenge": "rewards", "milestone": "rewards", "transfer": "transfers", "loan": "loans",
    "deposit": "external", "welcome": "external", "voucher": "external", "opening": "opening", "import": "opening",
}
TABLES = ("profiles", "circles", "circle_members", "accounts", "ledger_transactions", "ledger_entries", "markets",
          "market_positions", "market_trades", "casino_rounds", "week_snapshots", "week_closes", "week_standings",
          "week_rewards")
USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")
TOKEN = re.compile(r"^[yn][0-9]{1,2}$")


def to_cents(x):
    """Igual que backend/ledger.py: dólares a centavos enteros, redondeando a la mitad hacia arriba."""
    return int(math.floor(float(x) * 100 + 0.5))


def uid_for(kind, legacy):
    return str(uuid.uuid5(NAMESPACE, f"clique:{kind}:{legacy}"))


def system_for(reason):
    return "system:" + SYSTEM_FOR.get(str(reason).split(".")[0], "other")


def _ts(ms):
    return None if ms is None else int(ms)


class Plan:
    def __init__(self):
        self.rows = OrderedDict((t, []) for t in TABLES)
        self.transactions = []              # {key, reason, meta, t, lines: [(cuenta, centavos)]}
        self.differences = []               # texto, una por diferencia
        self.notes = defaultdict(int)       # cosas que se saltan a propósito, contadas
        self.balances = {}                  # cuenta -> centavos según el libro importado

    def add(self, table, row):
        self.rows[table].append(row)

    def counts(self):
        out = OrderedDict((t, len(r)) for t, r in self.rows.items())
        out["ledger_transactions"] = len(self.transactions)
        out["ledger_entries"] = sum(len(t["lines"]) for t in self.transactions)
        return out


def plan_from(d):
    """El plan de importación de un archivo ya leído (el dict de db.json)."""
    p = Plan()
    users = d.get("users", {})
    _profiles(p, users)
    _circles(p, d.get("circles", {}), users)
    _ledger(p, d, users)
    _markets(p, d.get("markets", {}), users)
    _casino(p, d, users)
    _weeks(p, d, users)
    return p


def _profiles(p, users):
    for legacy, u in users.items():
        name = u.get("username", "")
        if not USERNAME.match(name or ""):
            p.differences.append(f"profiles: el nombre {name!r} de {legacy} no cabe en el esquema (3 a 20 letras, números o _)")
        profile = u.get("profile") or {}
        p.add("profiles", {"id": uid_for("user", legacy), "legacy_id": legacy, "username": name,
                           "look": {k: v for k, v in profile.items() if k != "bio"}, "bio": profile.get("bio", ""),
                           "suspended": bool(u.get("suspended")), "deleted": bool(u.get("deleted")),
                           "created_at": _ts(u.get("createdAt"))})
        for kind, _ in PERSON_ACCOUNTS:
            p.add("accounts", {"ref": ("person", legacy, kind), "owner_id": uid_for("user", legacy), "kind": kind, "enabled": True})
        p.add("accounts", {"ref": ("person", legacy, "chips"), "owner_id": uid_for("user", legacy), "kind": "chips", "enabled": False})


def _circles(p, circles, users):
    for legacy, c in circles.items():
        if not 2 <= len(c.get("name", "")) <= 40:
            p.differences.append(f"circles: el nombre del círculo {legacy} no cabe en el esquema (2 a 40 caracteres)")
        if c.get("ownerId") not in users:
            p.differences.append(f"circles: el dueño {c.get('ownerId')} del círculo {legacy} no existe")
        p.add("circles", {"id": uid_for("circle", legacy), "legacy_id": legacy, "name": c.get("name", ""),
                          "description": c.get("description", ""), "emoji": c.get("emoji", ""),
                          "visibility": c.get("visibility", "private"), "invite_code": c.get("inviteCode"),
                          "owner_id": uid_for("user", c.get("ownerId")), "created_at": _ts(c.get("createdAt"))})
        for member, joined in (c.get("members") or {}).items():
            if member not in users:
                p.differences.append(f"circle_members: {member} es miembro de {legacy} pero no existe")
                continue
            p.add("circle_members", {"circle_id": uid_for("circle", legacy), "user_id": uid_for("user", member),
                                     "joined_at": _ts(joined)})


def _post(p, key, reason, account, cents, meta, t):
    system = ("system", system_for(reason))
    p.transactions.append({"key": key, "reason": reason, "meta": meta, "t": t, "lines": [(account, cents), (system, -cents)]})
    for acct, c in ((account, cents), (system, -cents)):
        p.balances[acct] = p.balances.get(acct, 0) + c


def _ledger(p, d, users):
    rows_of, sums_of = d.get("ledger", {}), d.get("ledger_sum", {})
    for legacy in sorted(set(rows_of) | set(sums_of)):
        if legacy not in users:
            p.differences.append(f"ledger: hay renglones del libro de {legacy}, que no existe")
    for legacy, u in users.items():
        for kind, field in PERSON_ACCOUNTS:
            account = ("person", legacy, kind)
            p.balances.setdefault(account, 0)
            carried, n_carried = 0, 0
            for week in (sums_of.get(legacy) or {}).values():
                for cell in (week.get(kind) or {}).values():
                    carried += int(cell["c"])
                    n_carried += int(cell["n"])
            if carried < 0:
                p.differences.append(f"ledger: los resúmenes de {legacy}/{kind} suman {carried} centavos: la cuenta quedaría negativa")
            if carried:
                _post(p, f"import:{legacy}:{kind}:carried", "import.carried", account, carried,
                      {"legacy": True, "rows": n_carried}, None)
            elif n_carried:
                p.notes["resúmenes que suman 0 (no se asientan)"] += 1
            running = carried
            for r in rows_of.get(legacy) or []:
                if r.get("a") != kind:
                    continue
                c = int(r["c"])
                running += c
                if running < 0:
                    p.differences.append(f"ledger: {legacy}/{kind} queda en {running} centavos después del renglón {r.get('id')}")
                if "b" in r and int(r["b"]) != running:
                    p.differences.append(f"ledger: el renglón {r.get('id')} de {legacy}/{kind} anota un saldo de {r['b']} "
                                         f"centavos y el libro importado da {running}")
                if c == 0:
                    p.notes["renglones de 0 centavos (no se asientan)"] += 1
                    continue
                meta = {k: v for k, v in (("legacy_id", r.get("id")), ("txid", r.get("i")), ("ref", r.get("x")),
                                          ("note", r.get("n")), ("external", bool(r.get("e")))) if v}
                _post(p, f"import:{legacy}:{r.get('id')}", r.get("r") or "other", account, c, meta, r.get("t"))
            have = to_cents(u.get(field, 0.0))
            if have != p.balances[account]:
                p.differences.append(f"saldo: {u.get('username')} ({legacy}) tiene {have} centavos en {kind} en el archivo "
                                     f"y el libro importado suma {p.balances[account]} (diferencia {have - p.balances[account]})")
    systems = sorted({line[0] for t in p.transactions for line in t["lines"] if line[0][0] == "system"})
    for s in systems:
        p.add("accounts", {"ref": s, "owner_id": None, "kind": "system", "system_code": s[1].split(":", 1)[1], "enabled": True})


def _markets(p, markets, users):
    for legacy, m in markets.items():
        outcomes = m.get("outcomes") or []
        if not 5 <= len(m.get("question", "")) <= 160:
            p.differences.append(f"markets: la pregunta del mercado {legacy} no cabe en el esquema (5 a 160 caracteres)")
        if not 2 <= len(outcomes) <= 12:
            p.differences.append(f"markets: el mercado {legacy} tiene {len(outcomes)} resultados (el esquema pide de 2 a 12)")
        if m.get("creatorId") not in users:
            p.differences.append(f"markets: quien creó el mercado {legacy} ({m.get('creatorId')}) no existe")
        p.add("markets", {"id": uid_for("market", legacy), "legacy_id": legacy,
                          "circle_id": uid_for("circle", m["circleId"]) if m.get("circleId") else None,
                          "creator_id": uid_for("user", m.get("creatorId")), "question": m.get("question", ""),
                          "description": m.get("description", ""), "category": m.get("category", "General"),
                          "emoji": m.get("emoji", ""), "outcomes": outcomes, "liquidity_b": repr(float(m.get("b", 0))),
                          "shares_q": [repr(float(x)) for x in m.get("q") or []], "status": m.get("status"),
                          "winner": m.get("winner"), "volume": to_cents(m.get("volume", 0)),
                          "closes_at": _ts(m.get("closesAt")), "created_at": _ts(m.get("createdAt")),
                          "resolved_at": _ts(m.get("resolvedAt"))})
        for who, tokens in (m.get("positions") or {}).items():
            for token, pos in tokens.items():
                if not TOKEN.match(token):
                    p.differences.append(f"market_positions: la ficha {token!r} del mercado {legacy} no tiene la forma y0/n1")
                p.add("market_positions", {"market_id": uid_for("market", legacy), "user_id": uid_for("user", who),
                                           "token": token, "shares": repr(float(pos.get("shares", 0))),
                                           "invested": to_cents(pos.get("invested", 0)), "settled": bool(pos.get("settled")),
                                           "payout": to_cents(pos["payout"]) if pos.get("payout") is not None else None})
        for t in m.get("trades") or []:
            p.add("market_trades", {"market_id": uid_for("market", legacy), "user_id": uid_for("user", t.get("u")),
                                    "kind": t.get("k"), "token": t.get("token"), "shares": repr(float(t.get("shares", 0))),
                                    "amount": to_cents(t.get("amount", 0)), "price": repr(float(t.get("price", 0))),
                                    "created_at": _ts(t.get("t"))})


def _casino(p, d, users):
    for legacy, u in users.items():
        for account, history in (("weekly", u.get("history")), ("accumulated", (u.get("accGame") or {}).get("history"))):
            for h in history or []:
                p.add("casino_rounds", {"legacy_id": h.get("id"), "user_id": uid_for("user", legacy), "account": account,
                                        "game": h.get("game"), "status": "finished", "bet": to_cents(h.get("bet", 0)),
                                        "payout": to_cents(h.get("payout", 0)),
                                        "multiplier": None if h.get("mult") is None else repr(float(h["mult"])),
                                        "detail": h.get("detail", ""), "state": None, "created_at": _ts(h.get("t")),
                                        "finished_at": _ts(h.get("t"))})
        if u.get("demo"):
            p.notes["carteras de práctica (no son dinero; no se migran)"] += 1
    for key, games in (d.get("games") or {}).items():
        legacy, _, acc = key.partition(":")
        if legacy not in users:
            p.differences.append(f"casino_rounds: hay rondas en curso de {legacy}, que no existe")
            continue
        for game, state in (games or {}).items():
            if not isinstance(state, dict) or state.get("status") not in (None, "active", "playing"):
                continue
            p.add("casino_rounds", {"legacy_id": state.get("id"), "user_id": uid_for("user", legacy),
                                    "account": "accumulated" if acc == "acc" else "weekly", "game": game, "status": "active",
                                    "bet": to_cents(state.get("bet", 0)), "payout": None, "multiplier": None, "detail": "",
                                    "state": state, "created_at": _ts(state.get("t")), "finished_at": None})


def _weeks(p, d, users):
    for week, holdings in (d.get("snapshots") or {}).items():
        for legacy, value in holdings.items():
            p.add("week_snapshots", {"week": week, "user_id": uid_for("user", legacy), "holding": to_cents(value)})
    reward_keys = {}
    for legacy, rows in (d.get("ledger") or {}).items():
        for r in rows:
            if r.get("i"):
                reward_keys[(legacy, r["i"])] = f"import:{legacy}:{r.get('id')}"
    for cid, c in (d.get("circles") or {}).items():
        for week, rc in (c.get("recaps") or {}).items():
            circle = uid_for("circle", cid)
            p.add("week_closes", {"circle_id": circle, "week": week, "finalized_at": _ts(rc.get("finalizedAt")),
                                  "reason": rc.get("reason", "last"), "loser_ids": [uid_for("user", x) for x in rc.get("loserIds") or []],
                                  "punishment": rc.get("punishment"), "note": rc.get("note", ""), "awards": rc.get("awards") or [],
                                  "rules": rc.get("rules") or {}, "active": rc.get("active", 0), "scale": repr(float(rc.get("scale", 1))),
                                  "served": bool(rc.get("served"))})
            for s in rc.get("standings") or []:
                p.add("week_standings", {"circle_id": circle, "week": week, "user_id": uid_for("user", s.get("userId")),
                                         "position": s.get("position"), "value": to_cents(s.get("value", 0)),
                                         "start_value": to_cents(s.get("start", 0)), "delta": to_cents(s.get("delta", 0)),
                                         "moves": s.get("moves", 0), "active": bool(s.get("active")),
                                         "out_by_minimum": bool(s.get("out")), "reward_note": s.get("rewardNote", ""),
                                         "requirements": s.get("req") or {}})
            for who, rw in (rc.get("rewards") or {}).items():
                tx_key = reward_keys.get((who, rw.get("txid"))) if rw.get("paid") else None
                if rw.get("paid") and tx_key is None:
                    p.notes["premios pagados cuyo renglón ya estaba compactado (sin transacción enlazada)"] += 1
                p.add("week_rewards", {"circle_id": circle, "week": week, "user_id": uid_for("user", who),
                                       "amount": int(rw.get("amount", 0)), "position": rw.get("position"),
                                       "paid": bool(rw.get("paid")), "transaction_key": tx_key})


def simulate(path):
    with open(path, "r", encoding="utf-8") as f:
        return plan_from(json.load(f))


def report(plan, out=sys.stdout):
    w = out.write
    w("Lo que se insertaría, por tabla:\n")
    for table, n in plan.counts().items():
        w(f"  {table:22} {n:>8}\n")
    people = sum(1 for k in plan.balances if k[0] == "person")
    w(f"\nCuentas de persona revisadas: {people}. Cuentas del sistema: "
      f"{', '.join(sorted(k[1] for k in plan.balances if k[0] == 'system')) or 'ninguna'}.\n")
    for what, n in sorted(plan.notes.items()):
        w(f"  (aparte) {what}: {n}\n")
    if plan.differences:
        w(f"\n{len(plan.differences)} diferencias (se listan, no se corrigen):\n")
        for diff in plan.differences:
            w(f"  - {diff}\n")
    else:
        w("\n0 diferencias: el saldo de cada cuenta en el archivo es la suma de su libro importado.\n")


# ---------------------------------------------------------------- aplicar en un Postgres local (pruebas)

def aplicar(plan, dsn):
    """Mete el plan en la base `dsn` (con las migraciones ya aplicadas). Las personas, círculos y demás se insertan
    directo; el dinero entra SOLO por post_transaction, en el orden del archivo. Devuelve {cuenta del plan: id en Postgres}."""
    import datetime

    import psycopg
    from psycopg.types.json import Jsonb

    def ts(ms):
        return None if ms is None else datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)

    ids = {}
    with psycopg.connect(dsn, autocommit=False) as c:
        for r in plan.rows["profiles"]:
            c.execute("insert into profiles (id, legacy_id, username, look, bio, suspended, deleted_at, created_at) "
                      "values (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))",
                      (r["id"], r["legacy_id"], r["username"], Jsonb(r["look"]), r["bio"], r["suspended"],
                       ts(r["created_at"]) if r["deleted"] else None, ts(r["created_at"])))
        for r in plan.rows["accounts"]:
            ids[r["ref"]] = c.execute("insert into accounts (owner_id, kind, system_code, enabled) values (%s, %s, %s, %s) "
                                      "returning id", (r["owner_id"], r["kind"], r.get("system_code"), r["enabled"])).fetchone()[0]
        for r in plan.rows["circles"]:
            c.execute("insert into circles (id, legacy_id, name, description, emoji, visibility, invite_code, owner_id, created_at) "
                      "values (%s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))",
                      (r["id"], r["legacy_id"], r["name"], r["description"], r["emoji"], r["visibility"], r["invite_code"],
                       r["owner_id"], ts(r["created_at"])))
        for r in plan.rows["circle_members"]:
            c.execute("insert into circle_members (circle_id, user_id, joined_at) values (%s, %s, coalesce(%s, now()))",
                      (r["circle_id"], r["user_id"], ts(r["joined_at"])))
        c.commit()
        keys = {}
        for t in plan.transactions:
            with c.transaction():
                c.execute("set local role service_role")
                keys[t["key"]] = c.execute("select post_transaction(%s, %s, %s, %s)",
                                           (t["key"], t["reason"], Jsonb([{"account": ids[a], "amount": v} for a, v in t["lines"]]),
                                            Jsonb(t["meta"]))).fetchone()[0]
        for r in plan.rows["markets"]:
            c.execute("insert into markets (id, legacy_id, circle_id, creator_id, question, description, category, emoji, outcomes, "
                      "liquidity_b, shares_q, status, winner, volume, closes_at, created_at, resolved_at) values "
                      "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::numeric, %s::numeric[], %s, %s, %s, %s, coalesce(%s, now()), %s)",
                      (r["id"], r["legacy_id"], r["circle_id"], r["creator_id"], r["question"], r["description"], r["category"],
                       r["emoji"], r["outcomes"], r["liquidity_b"], r["shares_q"], r["status"], r["winner"], r["volume"],
                       ts(r["closes_at"]), ts(r["created_at"]), ts(r["resolved_at"])))
        for r in plan.rows["market_positions"]:
            c.execute("insert into market_positions (market_id, user_id, token, shares, invested, settled, payout) "
                      "values (%s, %s, %s, %s::numeric, %s, %s, %s)",
                      (r["market_id"], r["user_id"], r["token"], r["shares"], r["invested"], r["settled"], r["payout"]))
        for r in plan.rows["market_trades"]:
            c.execute("insert into market_trades (market_id, user_id, kind, token, shares, amount, price, created_at) "
                      "values (%s, %s, %s, %s, %s::numeric, %s, %s::numeric, coalesce(%s, now()))",
                      (r["market_id"], r["user_id"], r["kind"], r["token"], r["shares"], r["amount"], r["price"], ts(r["created_at"])))
        for r in plan.rows["casino_rounds"]:
            c.execute("insert into casino_rounds (legacy_id, user_id, account, game, status, bet, payout, multiplier, detail, state, "
                      "created_at, finished_at) values (%s, %s, %s, %s, %s, %s, %s, %s::numeric, %s, %s, coalesce(%s, now()), %s)",
                      (r["legacy_id"], r["user_id"], r["account"], r["game"], r["status"], r["bet"], r["payout"], r["multiplier"],
                       r["detail"], Jsonb(r["state"]) if r["state"] is not None else None, ts(r["created_at"]), ts(r["finished_at"])))
        for r in plan.rows["week_snapshots"]:
            c.execute("insert into week_snapshots (week, user_id, holding) values (%s, %s, %s)", (r["week"], r["user_id"], r["holding"]))
        for r in plan.rows["week_closes"]:
            c.execute("insert into week_closes (circle_id, week, finalized_at, reason, loser_ids, punishment, note, awards, rules, "
                      "active, scale, served) values (%s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s, %s::numeric, %s)",
                      (r["circle_id"], r["week"], ts(r["finalized_at"]), r["reason"], r["loser_ids"],
                       Jsonb(r["punishment"]) if r["punishment"] is not None else None, r["note"], Jsonb(r["awards"]),
                       Jsonb(r["rules"]), r["active"], r["scale"], r["served"]))
        for r in plan.rows["week_standings"]:
            c.execute("insert into week_standings (circle_id, week, user_id, position, value, start_value, delta, moves, active, "
                      "out_by_minimum, reward_note, requirements) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                      (r["circle_id"], r["week"], r["user_id"], r["position"], r["value"], r["start_value"], r["delta"], r["moves"],
                       r["active"], r["out_by_minimum"], r["reward_note"], Jsonb(r["requirements"])))
        for r in plan.rows["week_rewards"]:
            c.execute("insert into week_rewards (circle_id, week, user_id, amount, position, paid, transaction_id) "
                      "values (%s, %s, %s, %s, %s, %s, %s)",
                      (r["circle_id"], r["week"], r["user_id"], r["amount"], r["position"], r["paid"], keys.get(r["transaction_key"])))
        c.commit()
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description="Simula importar el archivo de datos de Clique a Postgres.")
    ap.add_argument("--simular", metavar="DB_JSON", required=True, help="el archivo db.json a revisar (no se modifica)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    plan = simulate(args.simular)
    report(plan)
    return 1 if plan.differences else 0


if __name__ == "__main__":
    sys.exit(main())
