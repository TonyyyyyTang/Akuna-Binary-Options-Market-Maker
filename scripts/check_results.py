#!/usr/bin/env python3
"""Recalculate totals from manually recorded development results."""

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def validate(result: dict) -> None:
    assert result["score_context"] == "observed_development_tests"
    assert result["scored_cases"] == list(range(5, 21))
    assert len(result["pnl"]) == len(result["scores"]) == 16
    assert all(math.isfinite(x) for x in result["pnl"])
    assert all(0 <= x <= 1 for x in result["scores"])
    assert math.isclose(sum(result["pnl"]), result["total_scored_pnl"], abs_tol=0.005)
    assert math.isclose(sum(result["scores"]), result["scored_score"], abs_tol=1e-9)
    assert math.isclose(result["scored_score"] + 4, result["overall_score"], abs_tol=1e-9)


def main() -> None:
    print("Manually recorded development results; not final hidden-test scores.")
    print(f"{'Version':<10} {'Score /20':>10} {'Trading PnL':>13} {'Full-credit cases':>19}")
    for path in sorted((ROOT / "results").glob("v*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        validate(result)
        full = sum(x == 1 for x in result["scores"])
        print(f"{result['version']:<10} {result['overall_score']:>10.2f} "
              f"{result['total_scored_pnl']:>13.2f} {full:>16}/16")


if __name__ == "__main__":
    main()
