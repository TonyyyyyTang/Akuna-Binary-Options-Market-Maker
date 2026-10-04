"""Deterministic checks of the archived submission, not performance estimates."""

import ast
import hashlib
import inspect
import json
import math
import textwrap
import unittest
from dataclasses import replace

from bot import MarketMaker
from model import (
    AJARAI_UNDERLYING_ID as AJR,
    FED_FUNDS_RATE_UNDERLYING_ID as FED,
    THERIODIC_UNDERLYING_ID as THR,
    BinaryOption,
    FokOrder,
    MarketHistory,
    MarketParameters,
    OptionLeg,
    OrderType,
    Underlying,
)


def state(rate: float = 3.0, ajr: float = 500.0, thr: float = 600.0) -> list[Underlying]:
    return [Underlying("FED", FED, rate), Underlying("AJR", AJR, ajr), Underlying("THR", THR, thr)]


def option(uid: int = AJR, strike: float = 500.0, days: int = 1, oid: int = 1) -> BinaryOption:
    return BinaryOption((OptionLeg(uid, 1.0),), oid, days, strike)


def comparison(days: int = 1, oid: int = 1) -> BinaryOption:
    return BinaryOption((OptionLeg(THR, 1.0), OptionLeg(AJR, -1.0)), oid, days, 0.0)


def parameters() -> MarketParameters:
    # Values and rounded outputs recorded in the competition's THEORY diagnostic.
    return MarketParameters(
        ajarai_drift=0.001,
        ajarai_idio_std_dev=0.01,
        ajarai_rate_beta=-0.02,
        ajarai_sector_beta=1.0,
        rate_down_probability=0.2,
        rate_reversion_strength=0.1,
        rate_up_probability=0.25,
        sector_std_dev=0.02,
        theriodic_drift=0.0015,
        theriodic_idio_std_dev=0.012,
        theriodic_rate_beta=-0.015,
        theriodic_sector_beta=1.0,
    )


class PricingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = MarketMaker(state(), [], 10.0)

    def test_six_recorded_theory_examples(self) -> None:
        cases = (
            (option(FED, 3.0, 1), 0.7000),
            (option(FED, 3.5, 5), 0.0471),
            (option(AJR, 500.0, 1), 0.5309),
            (option(THR, 650.0, 10), 0.2068),
            (comparison(1), 1.0000),
            (comparison(10), 0.9999),
        )
        for contract, expected in cases:
            with self.subTest(contract=contract):
                actual = self.bot.price_option_from_parameters(parameters(), contract)
                # The source diagnostics print only four decimal places.
                self.assertAlmostEqual(actual, expected, delta=0.00005)

    def test_rate_distribution_preserves_probability_at_zero(self) -> None:
        distribution = self.bot._fed_terminal_distribution(parameters(), 5, 0.0)
        self.assertAlmostEqual(sum(distribution.values()), 1.0, places=12)
        self.assertTrue(all(rate >= 0 and probability >= 0 for rate, probability in distribution.items()))

    def test_company_comparison_shared_sector_cancels(self) -> None:
        symmetric = replace(
            parameters(),
            ajarai_drift=0.0,
            theriodic_drift=0.0,
            ajarai_rate_beta=0.0,
            theriodic_rate_beta=0.0,
            ajarai_idio_std_dev=0.01,
            theriodic_idio_std_dev=0.01,
        )
        first = self.bot.price_option_from_parameters(symmetric, comparison(10))
        second = self.bot.price_option_from_parameters(replace(symmetric, sector_std_dev=0.5), comparison(10))
        self.assertAlmostEqual(first, second, places=12)

    def test_expiry_includes_equality(self) -> None:
        self.assertEqual(self.bot.price_option_from_parameters(parameters(), option(AJR, 500.0, 0)), 1.0)
        self.assertEqual(self.bot.price_option_from_parameters(parameters(), option(AJR, 500.01, 0)), 0.0)

    def test_pricing_does_not_change_cash_or_positions(self) -> None:
        for _ in range(3):
            self.bot.price_option(comparison(10))
        self.assertEqual(self.bot.shadow_cash_balance, 10.0)
        self.assertEqual(dict(self.bot.position.option_quantity_by_option_id), {})


class CollateralTests(unittest.TestCase):
    def test_offsetting_trades_do_not_release_collateral_before_expiry(self) -> None:
        for settlement_ajr in (400.0, 600.0):
            with self.subTest(settlement_ajr=settlement_ajr):
                contract = option()
                maker = MarketMaker(state(), [contract], 10.0)
                maker.on_trade(contract, 0.20, 5, 101)
                maker.on_trade(contract, 0.80, -5, 102)
                self.assertEqual(maker.position.option_quantity_by_option_id[1], 0)
                self.assertAlmostEqual(maker.shadow_cash_balance, 8.0)
                self.assertEqual(maker.long_quantity_by_option_id[1], 5)
                self.assertEqual(maker.short_quantity_by_option_id[1], 5)
                maker.on_step_advance(state(ajr=settlement_ajr), [])
                # The gross long/short credits add to five in either outcome.
                self.assertAlmostEqual(maker.shadow_cash_balance, 13.0)
                self.assertEqual(maker.position.option_quantity_by_option_id[1], 0)
                self.assertNotIn(1, maker.held_option_by_id)
                maker.on_step_advance(state(ajr=settlement_ajr), [])
                self.assertAlmostEqual(maker.shadow_cash_balance, 13.0)

    def test_each_direction_has_the_correct_worst_loss_and_expiry_credit(self) -> None:
        cases = (
            (5, 400.0, 9.0, 9.0),
            (5, 600.0, 9.0, 14.0),
            (-5, 400.0, 6.0, 11.0),
            (-5, 600.0, 6.0, 6.0),
        )
        for quantity, settlement_ajr, before, after in cases:
            with self.subTest(quantity=quantity, settlement_ajr=settlement_ajr):
                contract = option()
                maker = MarketMaker(state(), [contract], 10.0)
                maker.on_trade(contract, 0.20, quantity, 101)
                self.assertAlmostEqual(maker.shadow_cash_balance, before)
                maker.on_step_advance(state(ajr=settlement_ajr), [contract.advance_step()])
                self.assertAlmostEqual(maker.shadow_cash_balance, after)

    def test_only_expiring_contracts_receive_credit(self) -> None:
        first, second = option(oid=1), option(days=2, oid=2)
        maker = MarketMaker(state(), [first, second], 10.0)
        maker.on_trade(first, 0.2, 2, 101)
        maker.on_trade(second, 0.3, 3, 101)
        maker.on_step_advance(state(ajr=600.0), [second.advance_step()])
        self.assertAlmostEqual(maker.shadow_cash_balance, 10.7)
        self.assertEqual(maker.position.option_quantity_by_option_id[2], 3)
        self.assertIn(2, maker.held_option_by_id)


class ExecutionTests(unittest.TestCase):
    def test_unsupported_contract_uses_ten_lots_at_zero_risk_boundaries(self) -> None:
        contract = replace(comparison(), strike=100.0)
        maker = MarketMaker(state(), [contract], 10.0)
        quote = maker.quote(contract, 101)
        self.assertEqual((quote.bid_price, quote.offer_price), (0.0, 1.0))
        self.assertEqual((quote.bid_quantity, quote.offer_quantity), (10, 10))

    def test_zero_risk_fok_orders_are_accepted_without_a_ready_model(self) -> None:
        contract = option()
        maker = MarketMaker(state(), [contract], 10.0)
        for side, price in ((OrderType.BUY, 1.0), (OrderType.SELL, 0.0)):
            with self.subTest(side=side):
                self.assertTrue(maker.respond_to_fok(contract, FokOrder(101, 1, side, price, 100)))
        self.assertEqual(maker.shadow_cash_balance, 10.0)

    def test_invalid_fok_inputs_are_rejected(self) -> None:
        contract = option()
        maker = MarketMaker(state(), [contract], 10.0)
        for price, quantity in ((math.nan, 1), (math.inf, 1), (-0.01, 1), (1.01, 1), (0.2, 0)):
            with self.subTest(price=price, quantity=quantity):
                self.assertFalse(maker.respond_to_fok(contract, FokOrder(101, 1, OrderType.SELL, price, quantity)))

    def test_full_fok_risk_is_checked_before_possible_split(self) -> None:
        contract = option(THR, 1.0)
        maker = MarketMaker(state(), [contract], 10.0)
        maker.model_ready = True
        self.assertTrue(maker.respond_to_fok(contract, FokOrder(101, 1, OrderType.SELL, 0.01, 5)))
        self.assertFalse(maker.respond_to_fok(contract, FokOrder(101, 1, OrderType.SELL, 0.01, 11)))

    def test_active_quotes_fit_the_available_collateral(self) -> None:
        contract = option()
        maker = MarketMaker(state(), [contract], 40.0)
        maker.model_ready = True
        for cash in (40.0, 30.0, 24.0):
            with self.subTest(cash=cash):
                maker.shadow_cash_balance = cash
                quote = maker.quote(contract, 101)
                available = max(0.0, cash - 24.0)
                self.assertLessEqual(quote.bid_price * quote.bid_quantity, available + 1e-12)
                self.assertLessEqual((1.0 - quote.offer_price) * quote.offer_quantity, available + 1e-12)


class ArchivedBehaviorTests(unittest.TestCase):
    def test_class_matches_the_frozen_v7b_executable_ast(self) -> None:
        # A formatting change may alter comments/docstrings; it must not silently
        # turn the published competition submission into a post-contest strategy.
        tree = ast.parse(textwrap.dedent(inspect.getsource(MarketMaker))).body[0]
        for item in ast.walk(tree):
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and item.body:
                first = item.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    if isinstance(first.value.value, str):
                        item.body.pop(0)
        def structure(value):
            if isinstance(value, ast.AST):
                # Python 3.12 added type_params; this source has no generic
                # definitions, so ignore that empty field across Python versions.
                return [type(value).__name__, [
                    [field, structure(child)]
                    for field, child in ast.iter_fields(value)
                    if field != "type_params"
                ]]
            if isinstance(value, list):
                return [structure(child) for child in value]
            return value

        serialized = json.dumps(structure(tree), ensure_ascii=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        self.assertEqual(digest, "0edfabfdda72871a7e511d733b228ff47377f939617684a4edcd70c42ee6c489")

    def test_short_opening_history_keeps_the_readiness_gate_closed(self) -> None:
        # This documents a limitation of the submitted strategy, not a goal for
        # future versions: 20 observations contain only 19 transitions.
        rates = tuple(2.0 + 0.25 * (i % 2) for i in range(20))
        history = MarketHistory({FED: rates, AJR: (500.0,) * 20, THR: (600.0,) * 20})
        maker = MarketMaker(state(), [], 40.0)
        maker.warm_up(history)
        self.assertFalse(maker.model_ready)
        for day in range(25):
            maker.on_step_advance(state(rate=2.0 + 0.25 * (day % 2)), [])
        self.assertGreaterEqual(maker.warmup_num_transitions, 20)
        self.assertFalse(maker.model_ready)


if __name__ == "__main__":
    unittest.main()
