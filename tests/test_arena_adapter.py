"""Check the local boundary without installing or running the upstream arena."""

import unittest
from dataclasses import dataclass
from types import SimpleNamespace

import model
from scripts.run_arena import make_local_player


@dataclass
class ExchangeQuote:
    bid_price: float
    bid_quantity: int
    offer_price: float
    offer_quantity: int


class RecordingMaker:
    name = "adapter-test"

    def __init__(self, underlyings, options, cash):
        self.underlyings = underlyings
        self.options = options
        self.shadow_cash_balance = cash
        self.observed_cash = []
        self.orders = []
        self.fail_on_second = False

    def quote(self, option, counterparty_id):
        self.observed_cash.append(self.shadow_cash_balance)
        if self.fail_on_second and len(self.observed_cash) == 2:
            raise RuntimeError("test failure")
        return model.Quote(0.40, 2, 0.60, 2)

    def respond_to_fok(self, option, order):
        self.observed_cash.append(self.shadow_cash_balance)
        self.orders.append(order)
        return True


class ArenaAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def make_player(self, reserve=False):
        player = make_local_player(
            SimpleNamespace(Quote=ExchangeQuote), SimpleNamespace(Player=object),
            model, SimpleNamespace(MarketMaker=RecordingMaker), reserve,
        )
        self.option = SimpleNamespace(
            legs=(SimpleNamespace(underlying_id=2, weight=1.0),),
            option_id=1, steps_until_expiry=2, strike=100.0,
        )
        await player.init([SimpleNamespace(name="AJR", underlying_id=2, value=100.0)],
                          [self.option], 10.0)
        return player

    async def test_default_keeps_individual_quote_budget_and_converts_types(self):
        player = await self.make_player()
        quotes = await player.quote_batch([(self.option, 101), (self.option, 102)])
        self.assertEqual(player.maker.observed_cash, [10.0, 10.0])
        self.assertEqual(player.maker.shadow_cash_balance, 10.0)
        self.assertIsInstance(quotes[0], ExchangeQuote)
        self.assertIsInstance(player.maker.options[0], model.BinaryOption)
        self.assertEqual(quotes[0].bid_quantity, 2)

    async def test_opt_in_reserves_maximum_of_two_quote_sides(self):
        player = await self.make_player(reserve=True)
        await player.quote_batch([(self.option, 101), (self.option, 102)])
        self.assertEqual(player.maker.observed_cash[0], 10.0)
        self.assertAlmostEqual(player.maker.observed_cash[1], 9.2)
        self.assertEqual(player.maker.shadow_cash_balance, 10.0)

    async def test_exception_restores_real_cash(self):
        player = await self.make_player(reserve=True)
        player.maker.fail_on_second = True
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            await player.quote_batch([(self.option, 101), (self.option, 102)])
        self.assertEqual(player.maker.shadow_cash_balance, 10.0)

    async def test_fok_buy_is_maker_sell_and_reserves_full_quantity(self):
        player = await self.make_player(reserve=True)
        order = SimpleNamespace(counterparty_id=201, option_id=1,
                                order_type=SimpleNamespace(value="buy"), price=0.6, quantity=3)
        answers = await player.fok_batch([(self.option, order), (self.option, order)])
        self.assertEqual(answers, [True, True])
        self.assertAlmostEqual(player.maker.observed_cash[1], 8.8)
        self.assertEqual(player.maker.orders[0].order_type, model.OrderType.BUY)
        self.assertEqual(player.maker.shadow_cash_balance, 10.0)


if __name__ == "__main__":
    unittest.main()
