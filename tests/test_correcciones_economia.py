"""Las diferencias D1 a D4 de equipo/contratos/reglas-economia.md que eran errores del código, cada una con su prueba.

D1  Los pagos del casino se redondean HACIA ABAJO al centavo. Antes, Limbo, Dice, Chicken, Mines y otros redondeaban a la
    mitad hacia arriba, y con apuestas chicas varios devolvían más del 100 %: una ganancia segura para quien la repetía.
D2  Al liquidar un mercado, cada posición ganadora cobra sus acciones redondeadas hacia abajo, como toda salida del LMSR.
D3  El reinicio de temporada pasa por el libro: deja su renglón y la auditoría sigue en cero.
D4  La entrada y el cobro de una mesa de póker se escriben en el libro con la razón "poker", también cuando el asiento se
    libera fuera de una petición (desde el reloj).

Ningún saldo se prepara a mano aquí: todo el dinero entra y sale por el libro.
"""
import math
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import circles, games, ledger, lmsr, markets, poker, seed, users    # noqa: E402
from backend.store import Store, store                                        # noqa: E402
from tests.helpers import fresh_store, restore_store_path                       # noqa: E402


def tearDownModule():
    restore_store_path()


def person(name, cash=None):
    """A new account (the $1,000 welcome goes through the ledger). With `cash`, the weekly account is brought to it, also
    through the ledger."""
    u = users.register(name, "secret123")
    if cash is not None:
        ledger.post(u, "weekly", cash - ledger.balance(u, "weekly"), "test")
    return u


def floor_cents(stake, mult):
    return math.floor(Decimal(repr(stake)) * Decimal(repr(mult)) * 100) / 100


def rig_cards(*tail):
    """A shuffle that leaves `tail` on top of the shoe: the first card dealt is the first one given."""
    def shuffle(items):
        items[-len(tail):] = list(reversed(tail))
        return items
    return shuffle


def card(r, s="S"):
    return {"r": r, "s": s}


class CasinoPaysDownToTheCent(unittest.TestCase):
    """D1. Each case is a stake where rounding half up would pay a cent more than the multiplier is worth."""

    def setUp(self):
        fresh_store()
        self.u = person("ana")

    def won(self, before):
        return round(ledger.balance(self.u, "weekly") - before, 2)

    def test_dice(self):
        before = ledger.balance(self.u, "weekly")
        with mock.patch.object(games, "rand_below", return_value=0):               # a roll that wins "under 94.28"
            r = games.dice(self.u, {"amount": 0.10, "direction": "under", "target": 94.28})
        self.assertEqual(r["mult"], 1.05)
        self.assertEqual(r["payout"], 0.10)                                            # 0.105, never 0.11
        self.assertEqual(self.won(before), 0.0)

    def test_limbo(self):
        with mock.patch.object(games, "rand_unit", return_value=0.001):
            r = games.limbo(self.u, {"amount": 0.10, "target": 1.05})
        self.assertTrue(r["win"])
        self.assertEqual(r["payout"], 0.10)                                            # 0.105

    def test_coinflip(self):
        with mock.patch.object(games, "rand_below", return_value=0):                   # heads
            r = games.coinflip(self.u, {"amount": 0.10, "side": "heads"})
        self.assertEqual(r["payout"], 0.19)                                            # 0.198

    def test_chicken(self):
        games.chicken_start(self.u, {"amount": 0.10, "difficulty": "easy"})
        with mock.patch.object(games, "rand_unit", return_value=0.5):
            games.chicken_step(self.u)
        self.assertEqual(games.chicken_state(self.u)["payoutNow"], 0.10)              # what the page shows is what is paid
        self.assertEqual(games.chicken_cashout(self.u)["payout"], 0.10)              # 0.105

    def test_mines(self):
        with mock.patch.object(games, "shuffle", side_effect=lambda items: items):     # the only mine is tile 0
            games.mines_start(self.u, {"amount": 0.10, "size": 49, "mines": 1})
        for tile in (1, 2, 3):
            games.mines_pick(self.u, {"tile": tile})
        self.assertEqual(games.mines_state(self.u)["payoutNow"], 0.10)
        self.assertEqual(games.mines_cashout(self.u)["payout"], 0.10)                # 0.105

    def test_moles(self):
        games.moles_start(self.u, {"amount": 0.11, "moles": 3})
        with mock.patch.object(games, "shuffle", side_effect=lambda items: items):     # moles in holes 0, 1, 2
            games.moles_pick(self.u, {"hole": 0})
        self.assertEqual(games.moles_cashout(self.u)["payout"], 0.24)                # 0.2464... is 0.24; half up gave 0.25

    def test_tower(self):
        with mock.patch.object(games, "shuffle", side_effect=lambda items: items):     # the trap is tile 0 on every row
            games.tower_start(self.u, {"amount": 0.10, "risk": "easy"})
        games.tower_pick(self.u, {"tile": 1})
        self.assertEqual(games.tower_cashout(self.u)["payout"], 0.12)                # 0.128

    def test_blackjack_natural(self):
        before = ledger.balance(self.u, "weekly")
        with mock.patch.object(games, "shuffle", side_effect=rig_cards(card("A"), card("5"), card("K"), card("6"))):
            r = games.blackjack_deal(self.u, {"amount": 0.11})
        self.assertEqual(r["hands"][0]["result"], "blackjack")
        self.assertEqual(r["payout"], 0.27)                                            # 3:2 on 0.11 is 0.275
        self.assertEqual(self.won(before), 0.16)

    def test_war_surrender(self):
        poor = person("broke", cash=0.11)
        with mock.patch.object(games, "shuffle", side_effect=rig_cards(card("7", "H"), card("7", "S"))):
            r = games.war(poor, {"amount": 0.11})
        self.assertEqual(r["outcome"], "surrender")
        self.assertEqual(r["payout"], 0.05)                                            # half of 0.11 is 0.055
        self.assertEqual(ledger.balance(poor, "weekly"), 0.05)

    def test_no_stake_ever_returns_more_than_the_game_says(self):
        """Every multiplier of Dice, Limbo, Coinflip, Chicken and Mines, for the small stakes where a rounded cent matters most
        ($0.10 up to $0.50 for Dice, $1.00 for Limbo and Mines, $2.00 for the rest), paid the way the game pays it: the return
        never passes the game's own RTP."""
        stakes = [c / 100 for c in range(10, 201)]

        def worst(cases, upto=len(stakes)):
            return max((games.pay(a, m) * p / a, label, a) for m, p, label in cases for a in stakes[:upto])

        dice = [(games.dice_odds("under", c)[1], c / 10000, f"dice {c}") for c in range(1, games.DICE_MAX_CHANCE + 1)]
        limbo = [(t / 100, games.LIMBO_RTP * 100 / t, f"limbo {t / 100}x") for t in range(101, 2001)]
        coin = [(games.coin_mult(n), 0.5 ** n, f"coinflip {n}") for n in range(1, games.COIN_MAX_FLIPS + 1)]
        chicken = [(games.chicken_mult(d, k), c["p"] ** k, f"chicken {d} {k}") for d, c in games.CHICKEN.items()
                   for k in range(1, c["lanes"] + 1)]
        mines = [(games.mines_mult(s, n, k), math.comb(s - n, k) / math.comb(s, k), f"mines {s}/{n}/{k}")
                 for s in games.MINES_SIZES for n in range(1, s, 3) for k in range(1, min(5, s - n) + 1)]
        for rtp, cases, upto in ((games.DICE_RTP, dice, 41), (games.LIMBO_RTP, limbo, 91), (games.COIN_RTP, coin, 191),
                                 (games.CHICKEN_RTP, chicken, 191), (games.MINES_RTP_PCT / 100, mines, 91)):
            ret, label, stake = worst(cases, upto)
            with self.subTest(label=label):
                self.assertLessEqual(ret, rtp + 1e-9, f"{label} at ${stake:.2f} returns {ret:.4%}")

    def test_pay_is_exact_for_big_stakes_too(self):
        self.assertEqual(games.pay(1_000_000_000.01, 1.98), 1_980_000_000.01)
        self.assertEqual(games.pay(0.29, 2), 0.58)
        self.assertEqual(games.pay(12.34, 1), 12.34)
        self.assertEqual(games.pay(5, 0), 0.0)


class MarketPayoutRoundsDown(unittest.TestCase):
    """D2."""

    def test_a_winning_position_is_paid_its_shares_rounded_down(self):
        fresh_store()
        owner, bettor = person("owner"), person("bettor")
        c = circles.create(owner, {"name": "Crew"})
        circles.join(bettor, c["id"], c["inviteCode"])
        for cents in range(100, 2000):                             # find a stake whose shares end in half a cent or more
            m = markets.create(owner, {"circleId": c["id"], "question": "Will it rain on Friday?"})
            shares = markets.quote(m, bettor, {"action": "buy", "outcome": 0, "amount": cents / 100})["shares"]
            if (shares * 100) % 1 >= 0.5:
                break
        markets.trade(bettor, m, {"action": "buy", "outcome": 0, "amount": cents / 100})
        before = ledger.balance(bettor, "weekly")
        markets.resolve(owner, m, 0)
        paid = round(ledger.balance(bettor, "weekly") - before, 2)
        self.assertEqual(paid, lmsr.floor_cents(shares))
        self.assertLessEqual(paid, shares)


class NewSeasonGoesThroughTheLedger(unittest.TestCase):
    """D3."""

    def test_the_reset_is_written_down_and_the_books_still_balance(self):
        path = os.path.join(tempfile.mkdtemp(), "db.json")
        s = Store(path)
        s.load()
        saved = store.data
        store.data = s.data
        try:
            rich, poor = person("rich", cash=5000), person("poor", cash=40)
        finally:
            store.data = saved
        seed.new_season(s.data)
        store.data = s.data
        try:
            for u in (rich, poor):
                self.assertEqual(ledger.balance(u, "weekly"), 1000.0)
                self.assertEqual(ledger.audit(u), {"weekly": 0, "accumulated": 0})
                self.assertEqual(ledger.entries(u, limit=1)[0]["reason"], "season.reset")
                self.assertTrue(ledger.entries(u, limit=1)[0]["external"])
        finally:
            store.data = saved
        self.assertNotIn(rich["id"], store.data.get("ledger", {}), "the rows belong to the database that was reset")


class PokerRowsSayPoker(unittest.TestCase):
    """D4."""

    def test_buying_in_and_cashing_out_are_written_as_poker_whoever_calls(self):
        fresh_store()
        us = [person(n, cash=500) for n in ("ann", "bobby")]
        t = poker.create(us[0], {"name": "Table", "visibility": "public"})
        poker.join(us[1], t["id"], t["code"])
        poker.set_settings(us[0], t, {"money": "real", "bigBlind": 1, "smallBlind": 0.5, "stack": 100})
        for u in us:
            poker.vote(u, t, True)
        poker.start(us[0], t)
        self.assertEqual(ledger.entries(us[1], limit=1)[0]["reason"], "poker")
        h = t["hand"]
        poker.act(users.get(t["seats"][h["toAct"]]["userId"]), t, "fold")         # heads-up: one fold ends the hand
        for u in us:                                                   # called directly: no request, no route to name the row
            poker.leave(u, t)
        for u in us:
            self.assertEqual(ledger.entries(u, limit=1)[0]["reason"], "poker")
            self.assertEqual(ledger.audit(u), {"weekly": 0, "accumulated": 0})


if __name__ == "__main__":
    unittest.main()
