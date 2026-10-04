# Continuing after the competition

[Akuna Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena)
is a community project by strixthekiet. It provides an exchange simulator, public
scenarios, and a WebSocket server for playing against other people's makers.
It does not contain the official hidden tests. Its 27-point score is a separate
measurement from my recorded 18.5/20 competition development score.

The live design keeps a strategy on its owner's machine. The server sends market
states, quote requests, and FOK orders; the client returns prices and decisions.
The two reference opponents are a fixed-width maker and a lattice maker. The
public scenarios include short histories, thin capital, informed flow, changing
volatility, and regime shifts. They are useful places to look for weaknesses in
a strategy that was developed against a small, repeated test set.

I have added an offline adapter so that this repository can use the exchange
without connecting to a community match. The arena source remains in a separate
checkout: I am linking to the original project rather than republishing its
code. The revision reviewed for this integration is
`7a9f2e6f0eff5785d13873fd07c560f3c9728cf2`.

```bash
git clone https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena ../akuna-arena
git -C ../akuna-arena checkout 7a9f2e6f0eff5785d13873fd07c560f3c9728cf2
python3 scripts/run_arena.py --arena-dir ../akuna-arena --cases 1 7 18 --seeds 0 1 2
```

Python 3.11 or newer is required. The offline exchange modules use the standard
library; the FastAPI dependencies are needed only for hosting a server. Omit
`--cases` to run the full suite, add `--events` to keep the detailed event records,
and use `--output` to choose a JSON result path. Default results go under
`.local/arena/`, which is excluded from Git. The adapter reports the checkout
revision, seed, score, PnL, faults, and the difference between the strategy's
cash balance and the exchange's balance when a session completes normally.

Seed `0` reproduces each case's original world. Other seeds change its market and
order streams. The declared option book stays fixed, so a seed sweep is still
only one kind of validation. The local runner also does not reproduce the live
server's network latency and deadlines.

There is one compatibility issue I want to make visible. The arena collects a
whole round of quotes before sending any trade callbacks. V7B checks each quote
against its current cash, so several simultaneous fills can consume a budget
more than once. The default adapter preserves that submitted behavior. The
optional `--batch-reserve` flag temporarily reserves possible losses as it
answers the round, then restores the cash balance before actual fills arrive.
It is a post-competition experiment, not a change to the archived strategy. It
reserves cash across the batch, but does not reserve per-contract position
capacity. It is not a complete portfolio-risk controller.

## First local run

I ran the 27 public cases at their original seeds after adding the adapter. The
same frozen strategy was also run with the batch cash-reservation wrapper.

| Adapter mode | Arena points /27 | Sum of PnL | Faults | Bankruptcies |
| --- | ---: | ---: | ---: | ---: |
| Submitted behavior | 17.0 | 108.5357 | 0 | 0 |
| Optional batch reservation | 17.5 | 94.5465 | 0 | 0 |

The strategy and exchange cash balances agreed at the end of all these runs.
Per-case results are in [`results/`](../results/arena_submitted_seed0.json).
These runs verify that the integration works; one fixed public suite does not
establish which mode is a better strategy. The arena's tie allocation consumes
the flow random stream, so the same seed also does not guarantee identical later
orders when the strategy changes.

For live play or hosting an arena, follow the upstream
[README](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/README.md)
and [protocol](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/PROTOCOL.md).
The hosted server's availability has not been confirmed by this repository.
