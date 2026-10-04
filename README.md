# Binary Options Market Making

My submission and notes from the 2026 Akuna Virtual Trading Challenge.

This was my first binary-options market-making project. I understood the 0-or-1 payoff, but RFQs, FOK orders and the competition's cash accounting were new to me. My first questions were fairly basic: who was the bot trading against, when could I run it, and what actually happened to the cash after a trade?

The final version scored **18.5/20 on the tests available during development**. I **did not finish in the top 30 in the final results**. I have kept both facts here. The project taught me how to build a working market maker, and the final result showed how much my testing process still needed to improve.

## What the bot does

The contracts pay one if an event happens at expiry and zero otherwise. They reference a simulated interest rate (FED), two fictional company valuations (AJR and THR), or which company is worth more.

The bot estimates parameters from historical observations, prices those events, returns two-sided RFQ quotes, and accepts or rejects FOK orders. Trade sizes are limited by worst-case losses and inventory capacity. It maintains a separate collateral ledger because closing a position does not immediately release the cash held by the competition's grader.

[`bot.py`](bot.py) contains the final V7B strategy. Its trading logic is preserved, including the heuristics I would now reconsider. [`model.py`](model.py) supplies a small, independently written interface for running it locally; it is not the original HackerRank template.

## The part that changed my thinking

I started with a bid of 0, an offer of 1 and a quantity of one. That gave me something which could survive the trading tests while I added the pricer, one contract type at a time.

Correct pricing did not suddenly make the bot competitive. I spent quite a while adjusting FOK filters and spreads, often getting exactly the same results back. Eventually I noticed that quantity was still one. Increasing the size at the zero-loss boundary prices moved one development case's profit from 6 to 27. Extending sizing to active quotes made the available capital matter much more.

Later I tried inventory skew, rolling estimates, counterparty feedback and order-flow signals. Some changes did nothing; others helped one case and hurt another. I also got my versions mixed up. Saving the full result vectors and keeping a stable version became useful habits partway through the competition, rather than something I had planned from the start.

The longer version of this story is in [my retrospective](docs/retrospective.md), with [Chinese notes](docs/retrospective.zh-CN.md). The [strategy notes](docs/strategy.md) explain the pricing and cash accounting; the [experiment notes](docs/experiments.md) include ideas I decided not to keep.

## Recorded development results

| Measure | V7B |
| --- | ---: |
| Development test score | 18.50 / 20 |
| Score across the 16 trading sessions | 14.50 / 16 |
| Trading sessions with full credit | 12 / 16 |
| Sum of recorded trading-session PnL | 284.76 |
| Bankruptcies in those recorded runs | 0 |
| Final competition outcome | Outside the top 30 |

These are manually recorded development outputs, not a final hidden-test score or a return on a real account. The full vectors are in [`results/`](results/). In one session the bot lost 7.05 and still earned full credit because the other makers lost more. That was a useful reminder that the contest ranked makers within each session.

## Run the local checks

Python 3.11 or newer, with no additional packages:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_results.py
python3 scripts/export_submission.py --output .local/submission.py
```

The tests cover the supplied-parameter pricing examples and the cash and settlement rules. They do not establish profitability in new markets. The exporter prints the class for use with a compatible contest template; `bot.py` remains the maintained source.

## Testing after the competition

The community [AkunaVirtualTradingChallenge2026Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena) provides a separate exchange and public scenarios. It supports local matches and live matches between bots. It does not reproduce Akuna's official hidden tests.

This repository includes an offline adapter so the submitted bot can be tested against the arena's reference makers. The arena stays in a separate checkout, with credit to its author. I ran all 27 public cases once to check the integration and kept the per-case results. See [the arena instructions](docs/arena.md) for setup, reproducible runs and differences from the competition interface.

## What I would change next

I repeatedly evaluated candidates against the same tests. Some choices ended up depending on initial-capital buckets because they worked in those observed cases. I had not set aside a separate group of markets before tuning.

I would now start with broader evaluation: different histories, market parameters, customers and competitors, with some cases kept out of the tuning loop. Then I would revisit the frozen model-readiness switch, distinguish pricing uncertainty from available cash, and manage exposure across related contracts. Adding another trading feature would come after that.

## Assistance and sources

I used ChatGPT and Codex for explanations, Python debugging, candidate implementations and code review. I ran the submissions, questioned assumptions, compared the outputs and chose which versions to retain. The unsuccessful experiments are part of the record too.

The contest design belongs to Akuna Capital. The arena belongs to [strixthekiet](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena). I also read [Luke Abraham's repository](https://github.com/lukeabraham24777/akuna-virtual-trading-challenge) after the competition; it helped me think more carefully about calibration and validation. Those post-competition observations are not presented as features I implemented during the contest.

This is a personal project, not an official Akuna repository.
