#!/usr/bin/env python3
"""Run V7B locally against a separately downloaded community arena.

The external arena is supplied through --arena-dir. Nothing is downloaded or
sent to a public server by this script. Its public scenarios are not Akuna's
hidden tests.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARENA_REPOSITORY = "https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena"
REVIEWED_REVISION = "7a9f2e6f0eff5785d13873fd07c560f3c9728cf2"
REQUIRED_FILES = (
    "arena_model.py", "engine.py", "players.py", "testcases.py", "testcases.json", "truth.py",
)


def load_arena(path: Path):
    server = path.resolve() / "server"
    missing = [name for name in REQUIRED_FILES if not (server / name).is_file()]
    if missing:
        raise SystemExit(
            f"Arena checkout missing {', '.join(missing)} under {server}.\n"
            "Clone the upstream repository separately and pass its root to --arena-dir.\n"
            f"Upstream: {ARENA_REPOSITORY}"
        )
    sys.path.insert(0, str(server))
    sys.path.insert(0, str(PROJECT_ROOT))
    return tuple(importlib.import_module(name)
                 for name in ("arena_model", "engine", "players", "testcases", "model", "bot"))


def make_local_player(arena_model, players, local_model, strategy, batch_reserve: bool):
    """Keep exchange objects at the boundary and strategy objects inside V7B."""

    class LocalPlayer(players.Player):
        player_id = 1
        name = "ZCtrader_V7B"
        is_bot = False

        def __init__(self):
            self.maker = None

        @staticmethod
        def option(option):
            return local_model.BinaryOption(
                legs=tuple(local_model.OptionLeg(leg.underlying_id, leg.weight)
                           for leg in option.legs),
                option_id=option.option_id,
                steps_until_expiry=option.steps_until_expiry,
                strike=option.strike,
            )

        @staticmethod
        def underlyings(underlyings):
            return [local_model.Underlying(item.name, item.underlying_id, item.value)
                    for item in underlyings]

        async def init(self, underlyings, options, cash):
            self.maker = strategy.MarketMaker(
                self.underlyings(underlyings), [self.option(item) for item in options], cash,
            )
            self.name = self.maker.name

        async def warm_up(self, history):
            self.maker.warm_up(local_model.MarketHistory(dict(history.values_by_underlying_id)))

        async def quote_batch(self, requests):
            # The arena collects every quote before it delivers any fills. The optional
            # wrapper reserves a round's possible losses without altering V7B itself.
            opening_cash = self.maker.shadow_cash_balance
            quotes = []
            try:
                for option, counterparty_id in requests:
                    quote = self.maker.quote(self.option(option), counterparty_id)
                    if quote is None:
                        quotes.append(None)
                        continue
                    converted = arena_model.Quote(
                        quote.bid_price, quote.bid_quantity,
                        quote.offer_price, quote.offer_quantity,
                    )
                    quotes.append(converted)
                    if batch_reserve:
                        possible_loss = max(
                            quote.bid_price * quote.bid_quantity,
                            (1.0 - quote.offer_price) * quote.offer_quantity,
                        )
                        self.maker.shadow_cash_balance -= possible_loss
                return quotes
            finally:
                self.maker.shadow_cash_balance = opening_cash

        async def fok_batch(self, requests):
            opening_cash = self.maker.shadow_cash_balance
            decisions = []
            try:
                for option, order in requests:
                    converted = local_model.FokOrder(
                        order.counterparty_id, order.option_id,
                        local_model.OrderType(order.order_type.value), order.price, order.quantity,
                    )
                    accepted = bool(self.maker.respond_to_fok(self.option(option), converted))
                    decisions.append(accepted)
                    if batch_reserve and accepted:
                        cost = (1.0 - order.price if converted.order_type == local_model.OrderType.BUY
                                else order.price)
                        self.maker.shadow_cash_balance -= cost * order.quantity
                return decisions
            finally:
                self.maker.shadow_cash_balance = opening_cash

        async def trade_batch(self, trades):
            for option, price, quantity, counterparty_id in trades:
                self.maker.on_trade(self.option(option), price, quantity, counterparty_id)

        async def step_advance(self, underlyings, options):
            self.maker.on_step_advance(
                self.underlyings(underlyings), [self.option(item) for item in options],
            )

    return LocalPlayer()


def checkout_revision(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path.resolve()), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


async def run(args, modules):
    arena_model, engine, players, testcases, local_model, strategy = modules
    cases = testcases.load_test_cases()
    selected = sorted(cases) if args.cases is None else list(dict.fromkeys(args.cases))
    unknown = set(selected) - cases.keys()
    if unknown:
        raise SystemExit(f"Unknown cases: {sorted(unknown)}. Available: {sorted(cases)}")

    rows = []
    for seed in args.seeds:
        for number in selected:
            counts = Counter()
            faults = []
            events = []

            async def emit(kind, payload):
                counts[kind] += 1
                if kind in ("fault", "disqualified", "bankrupt"):
                    faults.append({"kind": kind, **payload})
                if args.events:
                    events.append({"kind": kind, **payload})

            local = make_local_player(arena_model, players, local_model, strategy, args.batch_reserve)
            field = [local, *players.make_reference_bots(first_player_id=2)]
            match = engine.MatchEngine(
                case=cases[number], players=field, emit=emit,
                match_id=number, world_seed=seed,
            )
            result = await match.run()
            own = next(item for item in result["results"] if item["player_id"] == 1)
            # A bankrupt maker is no longer sent step_advance; its local ledger can then
            # be stale. Only compare balances when it completed the session normally.
            cash_error = None
            if own["status"] == "OK" and local.maker is not None:
                cash_error = local.maker.shadow_cash_balance - match.ledgers[1].cash
            row = {
                "seed": seed, "case": number, "name": cases[number].name,
                "result": result, "event_counts": dict(counts), "fault_events": faults,
                "strategy_cash_error": cash_error,
                "model_ready_at_end": getattr(local.maker, "model_ready", None),
            }
            if args.events:
                row["events"] = events
            rows.append(row)
            print(f"seed {seed:>3} case {number:02d} {cases[number].name:<22} "
                  f"PnL {own['pl']:>9.4f}  rank {own['rank']}/{result['field_size']}  "
                  f"points {own['points']:.3f}  {own['status']}", flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arena-dir", required=True, type=Path, help="Root of a separate upstream checkout")
    parser.add_argument("--cases", nargs="+", type=int, help="Case numbers; omit to run all public cases")
    parser.add_argument("--seeds", nargs="+", type=int, default=[0], help="0 reproduces the case's own seed")
    parser.add_argument("--batch-reserve", action="store_true", help="Enable a post-contest batch risk reservation wrapper")
    parser.add_argument("--events", action="store_true", help="Include full public event records in the JSON result")
    parser.add_argument("--output", type=Path, help="JSON result path; default: .local/arena/<timestamp>.json")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("The upstream arena uses StrEnum and needs Python 3.11 or newer.")

    timestamp = datetime.now(timezone.utc)
    output = args.output or PROJECT_ROOT / ".local" / "arena" / f"results-{timestamp:%Y%m%dT%H%M%S%fZ}.json"
    if output.exists():
        raise SystemExit(f"Result file already exists: {output}. Choose a new --output path.")
    modules = load_arena(args.arena_dir)
    rows = asyncio.run(run(args, modules))
    document = {
        "created_at": timestamp.isoformat(), "python": platform.python_version(),
        "arena_repository": ARENA_REPOSITORY,
        "arena_revision": checkout_revision(args.arena_dir),
        "reviewed_revision": REVIEWED_REVISION,
        "strategy": "V7B", "batch_reserve": args.batch_reserve,
        "seeds": args.seeds, "notes": [
            "Community scenarios and scores; not official Akuna hidden tests.",
            "Seed 0 uses the public case seed. Other seeds change the world seed.",
            "Declared option books remain fixed when changing the world seed.",
            "Local calls do not reproduce network latency or WebSocket deadlines.",
        ],
        "runs": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved {len(rows)} local sessions to {output}")


if __name__ == "__main__":
    main()
