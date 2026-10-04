"""Small local data model for reading and testing the submitted strategy.

These classes are independently written compatibility objects for the public
competition interface. They do not contain Akuna's checker, order generator,
competitor strategies, or hidden tests. Prices and cash are measured in dollars.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, replace
from enum import Enum


FED_FUNDS_RATE_UNDERLYING_ID = 1
AJARAI_UNDERLYING_ID = 2
THERIODIC_UNDERLYING_ID = 3


@dataclass(frozen=True)
class Underlying:
    name: str
    underlying_id: int
    value: float


@dataclass(frozen=True)
class OptionLeg:
    underlying_id: int
    weight: float


@dataclass(frozen=True)
class BinaryOption:
    legs: tuple[OptionLeg, ...]
    option_id: int
    steps_until_expiry: int
    strike: float

    def __post_init__(self) -> None:
        if self.steps_until_expiry < 0 or not self.legs:
            raise ValueError("An option needs at least one leg and a nonnegative expiry")
        if any(leg.weight == 0 for leg in self.legs):
            raise ValueError("Option weights cannot be zero")
        if len({leg.underlying_id for leg in self.legs}) != len(self.legs):
            raise ValueError("Use one leg per underlying")

    def observable_value(self, values: dict[int, float]) -> float:
        return sum(leg.weight * values[leg.underlying_id] for leg in self.legs)

    def expiry_valuation(self, values: dict[int, float]) -> float:
        return float(self.observable_value(values) >= self.strike)

    def advance_step(self) -> BinaryOption:
        return replace(self, steps_until_expiry=max(0, self.steps_until_expiry - 1))


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class FokOrder:
    counterparty_id: int
    option_id: int
    order_type: OrderType
    price: float
    quantity: int


@dataclass(frozen=True)
class Quote:
    bid_price: float
    bid_quantity: int
    offer_price: float
    offer_quantity: int

    def __post_init__(self) -> None:
        if self.bid_quantity <= 0 or self.offer_quantity <= 0:
            raise ValueError("Both quoted quantities must be positive")
        if not 0 <= self.bid_price < self.offer_price <= 1:
            raise ValueError("Quote prices must satisfy 0 <= bid < offer <= 1")
        for price in (self.bid_price, self.offer_price):
            if not math.isfinite(price) or abs(100 * price - round(100 * price)) > 1e-6:
                raise ValueError("Quotes use whole cents")


class Position:
    def __init__(self) -> None:
        self.option_quantity_by_option_id: dict[int, int] = defaultdict(int)

    def add_option_quantity(self, option_id: int, quantity: int) -> None:
        self.option_quantity_by_option_id[option_id] += quantity


@dataclass(frozen=True)
class MarketHistory:
    values_by_underlying_id: dict[int, tuple[float, ...]]

    def __post_init__(self) -> None:
        lengths = {len(series) for series in self.values_by_underlying_id.values()}
        if len(lengths) > 1 or (lengths and 0 in lengths):
            raise ValueError("History series must have the same positive length")

    @property
    def num_days(self) -> int:
        return len(next(iter(self.values_by_underlying_id.values()), ()))


@dataclass(frozen=True)
class MarketParameters:
    ajarai_drift: float
    ajarai_idio_std_dev: float
    ajarai_rate_beta: float
    ajarai_sector_beta: float
    rate_down_probability: float
    rate_reversion_strength: float
    rate_up_probability: float
    sector_std_dev: float
    theriodic_drift: float
    theriodic_idio_std_dev: float
    theriodic_rate_beta: float
    theriodic_sector_beta: float
    rate_step: float = 0.25
    rate_target: float = 2.0

    def tilted_rate_probabilities(self, rate_value: float) -> tuple[float, float]:
        adjustment = self.rate_reversion_strength * (self.rate_target - rate_value)
        up = min(1.0, max(0.0, self.rate_up_probability + adjustment))
        down = min(1.0 - up, max(0.0, self.rate_down_probability - adjustment))
        return up, down

    def next_rate_value(self, rate_value: float, num_grid_steps: int) -> float:
        return max(0.0, round(rate_value + num_grid_steps * self.rate_step, 2))
