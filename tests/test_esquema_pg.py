"""El esquema v1 (supabase/migrations/) sobre un Postgres local: aplica desde cero, cada tabla tiene seguridad por fila, y
de cada tabla hay una prueba de que OTRA persona no ve lo de alguien más (y de que el dueño sí lo ve, para que una tabla
cerrada a todos no pase por buena).

Sin psycopg y pgserver instalados, estas pruebas se omiten con un aviso (no fallan)."""
import unittest
import uuid

from backend.datos import pg_local

if pg_local.AVAILABLE:
    import psycopg
    from psycopg.types.json import Jsonb

ANA, BETO, CARLA = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()       # Ana y Beto comparten círculo; Carla no
CIRCLE, OTHER_CIRCLE, MARKET = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

# Para cada tabla: cómo contar las filas que son de Ana (o del círculo de Ana y Beto).
OF_ANA = {
    "profiles": ("select count(*) from profiles where id = %s", ANA),
    "circles": ("select count(*) from circles where id = %s", CIRCLE),
    "circle_members": ("select count(*) from circle_members where circle_id = %s", CIRCLE),
    "accounts": ("select count(*) from accounts where owner_id = %s", ANA),
    "ledger_transactions": ("select count(*) from ledger_transactions where idempotency_key = %s", "seed-ana"),
    # directo sobre la tabla, sin pasar por accounts: un join a una tabla que ya filtra escondería un libro abierto
    "ledger_entries": ("select count(*) from ledger_entries where account_id = %s", lambda: FIXTURE["ana_weekly"]),
    "markets": ("select count(*) from markets where id = %s", MARKET),
    "market_positions": ("select count(*) from market_positions where user_id = %s", ANA),
    "market_trades": ("select count(*) from market_trades where market_id = %s", MARKET),
    "casino_rounds": ("select count(*) from casino_rounds where user_id = %s", ANA),
    "week_snapshots": ("select count(*) from week_snapshots where user_id = %s", ANA),
    "week_closes": ("select count(*) from week_closes where circle_id = %s", CIRCLE),
    "week_standings": ("select count(*) from week_standings where circle_id = %s", CIRCLE),
    "week_rewards": ("select count(*) from week_rewards where circle_id = %s", CIRCLE),
}
FIXTURE = {}                       # ids que solo se conocen al sembrar
SHARED = {"app_settings"}          # la leen todos los que tienen sesión, a propósito (por ejemplo, si la compra está encendida)


def _fixture(dsn):
    with psycopg.connect(dsn, autocommit=True) as c:
        for uid, name in ((ANA, "ana"), (BETO, "beto"), (CARLA, "carla")):
            c.execute("insert into profiles (id, username) values (%s, %s)", (uid, name))
            c.execute("select open_accounts(%s)", (uid,))
        c.execute("insert into circles (id, name, invite_code, owner_id) values (%s, 'Los del viernes', 'ABC123', %s)", (CIRCLE, ANA))
        c.execute("insert into circles (id, name, invite_code, owner_id) values (%s, 'Solo Carla', 'ZZZ999', %s)", (OTHER_CIRCLE, CARLA))
        c.execute("insert into circle_members (circle_id, user_id) values (%s, %s), (%s, %s), (%s, %s)",
                  (CIRCLE, ANA, CIRCLE, BETO, OTHER_CIRCLE, CARLA))
        weekly = c.execute("select id from accounts where owner_id = %s and kind = 'weekly'", (ANA,)).fetchone()[0]
        FIXTURE["ana_weekly"] = weekly
        ext = c.execute("select system_account('external')").fetchone()[0]
        tx = c.execute("select post_transaction('seed-ana', 'weekly.allocation', %s)",
                       (Jsonb([{"account": ext, "amount": -100000}, {"account": weekly, "amount": 100000}]),)).fetchone()[0]
        c.execute("insert into markets (id, circle_id, creator_id, question, outcomes, liquidity_b, shares_q) "
                  "values (%s, %s, %s, '¿Llueve el sábado?', '{Sí,No}', 100, '{0,0}')", (MARKET, CIRCLE, ANA))
        c.execute("insert into market_positions (market_id, user_id, token, shares, invested) values (%s, %s, 'y0', 12.5, 500)", (MARKET, ANA))
        c.execute("insert into market_trades (market_id, user_id, kind, token, shares, amount, price) "
                  "values (%s, %s, 'buy', 'y0', 12.5, 500, 0.4)", (MARKET, ANA))
        c.execute("insert into casino_rounds (user_id, account, game, status, bet, state) "
                  "values (%s, 'weekly', 'blackjack', 'active', 500, '{\"shoe\": [\"AS\", \"KD\"]}')", (ANA,))
        c.execute("insert into week_snapshots (week, user_id, holding) values ('2026-10-05', %s, 100000)", (ANA,))
        c.execute("insert into week_closes (circle_id, week, finalized_at, reason) values (%s, '2026-10-05', now(), 'last')", (CIRCLE,))
        c.execute("insert into week_standings (circle_id, week, user_id, position, value, start_value, delta, active) "
                  "values (%s, '2026-10-05', %s, 1, 105000, 100000, 5000, true)", (CIRCLE, ANA))
        c.execute("insert into week_rewards (circle_id, week, user_id, amount, position, paid, transaction_id) "
                  "values (%s, '2026-10-05', %s, 40000, 1, true, %s)", (CIRCLE, ANA, tx))


def _count_as(dsn, who, sql, arg, role="authenticated"):
    """Cuántas filas ve `who`. Para anon (sin sesión) un "permiso denegado" cuenta como no ver nada."""
    with psycopg.connect(dsn) as c:
        try:
            with c.transaction():
                pg_local.as_user(c, who)
                c.execute(f"set local role {role}")
                return c.execute(sql, (arg() if callable(arg) else arg,)).fetchone()[0]
        except psycopg.errors.InsufficientPrivilege:
            if role == "anon":
                return 0
            raise


@unittest.skipUnless(pg_local.AVAILABLE, pg_local.WHY_NOT)
class EsquemaBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = pg_local.fresh_database()
        _fixture(cls.dsn)

    def tables(self):
        with psycopg.connect(self.dsn) as c:
            return {r[0]: r[1] for r in c.execute("select tablename, rowsecurity from pg_tables where schemaname = 'public'")}


class LasMigracionesAplicanDesdeCero(EsquemaBase):
    def test_every_migration_applies_on_an_empty_database(self):
        self.assertGreaterEqual(len(pg_local.migration_files()), 3)
        self.assertEqual(set(self.tables()), set(OF_ANA) | SHARED)

    def test_money_columns_are_whole_cents(self):
        """Ninguna columna de dinero es float ni numeric: bigint (ADR-003). Las numeric que quedan no son dinero."""
        not_money = {("markets", "liquidity_b"), ("markets", "shares_q"), ("market_positions", "shares"),
                     ("market_trades", "shares"), ("market_trades", "price"), ("casino_rounds", "multiplier"),
                     ("week_closes", "scale")}
        with psycopg.connect(self.dsn) as c:
            rows = c.execute("select table_name, column_name, data_type from information_schema.columns "
                             "where table_schema = 'public' and data_type in ('real', 'double precision', 'numeric', 'ARRAY', 'money')").fetchall()
        for table, column, kind in rows:
            if kind == "ARRAY" and (table, column) in {("markets", "outcomes"), ("week_closes", "loser_ids")}:
                continue
            self.assertIn((table, column), not_money, f"{table}.{column} es {kind}: el dinero va en bigint")
            self.assertNotIn(kind, ("real", "double precision", "money"))


class CadaTablaTieneSeguridadPorFila(EsquemaBase):
    def test_row_level_security_is_on_for_every_table(self):
        self.assertEqual([t for t, on in self.tables().items() if not on], [])

    def test_every_table_has_a_test_that_another_person_cannot_see_it(self):
        self.assertEqual(set(self.tables()) - SHARED - set(OF_ANA), set())
        for table in OF_ANA:
            self.assertTrue(hasattr(OtroUsuarioNoLaVe, f"test_{table}"), table)


def _not_visible_test(table):
    sql, arg = OF_ANA[table]

    def test(self):
        self.assertGreater(_count_as(self.dsn, ANA, sql, arg), 0, f"Ana tendría que ver lo suyo en {table}")
        self.assertEqual(_count_as(self.dsn, CARLA, sql, arg), 0, f"Carla no tendría que ver lo de Ana en {table}")
        self.assertEqual(_count_as(self.dsn, CARLA, sql, arg, role="anon"), 0, f"sin sesión no se ve nada de {table}")
    test.__name__ = f"test_{table}"
    test.__doc__ = f"{table}: Carla, que no comparte círculo con Ana, no ve lo de Ana."
    return test


class OtroUsuarioNoLaVe(EsquemaBase):
    pass


for _table in OF_ANA:
    setattr(OtroUsuarioNoLaVe, f"test_{_table}", _not_visible_test(_table))


class LosDelCirculoSiSeVen(EsquemaBase):
    def test_a_circle_mate_sees_the_circle_but_not_the_money(self):
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["profiles"]), 1)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["markets"]), 1)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["week_standings"]), 1)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["accounts"]), 0)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["ledger_entries"]), 0)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["market_positions"]), 0)
        self.assertEqual(_count_as(self.dsn, BETO, *OF_ANA["casino_rounds"]), 0)


class NadieEscribeDesdeElNavegador(EsquemaBase):
    def test_no_table_takes_writes_from_a_signed_in_person(self):
        attempts = {
            "profiles": "update profiles set bio = 'x' where id = auth.uid()",
            "accounts": "update accounts set balance = balance + 1 where owner_id = auth.uid()",
            "ledger_entries": "delete from ledger_entries",
            "ledger_transactions": "insert into ledger_transactions (idempotency_key, reason, request_hash) values ('h', 'h', 'h')",
            "circle_members": f"insert into circle_members (circle_id, user_id) values ('{CIRCLE}', auth.uid())",
            "market_positions": "update market_positions set shares = 1000 where user_id = auth.uid()",
            "casino_rounds": "update casino_rounds set payout = 100000, status = 'finished' where user_id = auth.uid()",
            "week_rewards": "update week_rewards set amount = 99999999 where user_id = auth.uid()",
            "app_settings": "update app_settings set value = 'true' where key = 'purchases_enabled'",
        }
        for table, sql in attempts.items():
            with self.subTest(table=table):
                with psycopg.connect(self.dsn) as c:
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        with c.transaction():
                            pg_local.as_user(c, ANA)
                            c.execute(sql)


class ElEstadoDeUnaRondaNoSeVe(EsquemaBase):
    def test_the_cards_of_a_round_in_progress_are_not_readable_from_the_browser(self):
        """El estado de una ronda (la baraja, dónde están las minas) decide el resultado; el navegador no lo lee (D8)."""
        self.assertEqual(_count_as(self.dsn, ANA, "select count(*) from casino_rounds where user_id = %s", ANA), 1)
        with psycopg.connect(self.dsn) as c:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with c.transaction():
                    pg_local.as_user(c, ANA)
                    c.execute("select state from casino_rounds")


if __name__ == "__main__":
    unittest.main()
