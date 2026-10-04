# Binary Options Market Making

[中文](README.md) · **English**

My market-making bot from the 2026 Akuna Virtual Trading Challenge, with the questions, experiments and occasional version confusion that came with it.

The contracts settle at either 0 or 1. The decisions leading up to that turned out to be rather less binary.

I got the development score up to **18.5/20**, then finished outside the top 30 in the official results. That gap is worth another look. This repo keeps the final code, but also the story of how I arrived at it.

## Where I started

I understood the binary payoff before I understood the market-making process. Who was sending the RFQs? If the customer was buying, why was I selling? Could I accept only part of a FOK? Would running a test spend the cash left over from the previous run?

I didn't write the whole bot in one go. First came a name, then a tiny version quoting `bid=0`, `offer=1`, `quantity=1`. I added the pricer a piece at a time: discrete transitions for FED, valuation distributions for the two companies, then contracts comparing them. I picked up some Python along the way—including the small but consequential difference between `items` and `items()`.

Matching the reference pricing examples didn't suddenly make the bot competitive. I spent several rounds on FOK filters and spreads before noticing that **quantity was still one**. The prices had changed; there was still only one contract on the counter. Increasing the quantity on the `bid=0`, `offer=1` quotes to ten raised one development case's profit from 6 to 27. The useful breakthrough wasn't a fancier model. It was finding what actually limited the trades.

After that came active sizing, cash budgets, inventory skew, rolling estimates and order feedback. Some helped, some traded one improvement for another, and plenty earned another familiar “still no change.” I also mixed up versions. Keeping a stable baseline, saving the full result vectors and comparing one change at a time became habits during the competition, not before it.

The longer story is in the [English retrospective](docs/retrospective.md), with a [Chinese version](docs/retrospective.zh-CN.md). The [experiment notes](docs/experiments.md) keep a few ideas that didn't make the final cut.

## What the bot does

It trades event contracts on three simulated underlyings: the FED interest rate and valuations of two fictional companies, AJR and THR. A contract pays one if its event happens at expiry and zero otherwise. There are also contracts comparing the two companies' valuations.

The bot has four main jobs:

- Estimate parameters from historical observations and turn event probabilities into theoretical prices.
- Answer RFQs with two-sided prices and quantities.
- Decide whether a FOK offers enough edge and whether the whole order is affordable.
- Track positions and cash tied up in collateral, limiting trade sizes by worst-case losses.

The cash accounting was a lesson of its own: closing a position doesn't immediately release the collateral held by the grader. The bot keeps a separate ledger for that reason. The formulas and implementation are in the [strategy notes](docs/strategy.md).

[bot.py](bot.py) is the final V7B submission, including the branches I'd rethink today. [model.py](model.py) is a local interface added afterwards, not the original HackerRank template.

## The recorded results

| Development results / 开发测试记录 | V7B |
| --- | ---: |
| Overall score / 总分 | 18.50 / 20 |
| Score across 16 trading sessions / 计分交易场景 | 14.50 / 16 |
| Full-credit sessions / 满分交易场景 | 12 / 16 |
| Sum of session PnL / 各场收益之和 | 284.76 |
| Bankruptcies in those runs / 破产次数 | 0 |

The full vectors are in [results/](results/), manually saved from the development tests. I don't have the per-case results from the official final evaluation.

In one session the bot lost 7.05 and still earned full credit because the other makers lost more. A fairly memorable way to learn that PnL and rank aren't the same thing.

## Run it locally

Python 3.11 or newer; the local checks need no extra packages:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_results.py
python3 scripts/export_submission.py --output .local/submission.py
```

The tests check pricing examples, the cash ledger and settlement rules. The last command exports the `MarketMaker` class for use with a compatible contest template; `bot.py` is still the maintained source.

## The competition ended. The bot can still trade.

After the competition I found the community [AkunaVirtualTradingChallenge2026Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena). It supplies an exchange, public scenarios and competing bots for local matches, and also supports live bot matches.

It isn't a replica of Akuna's official hidden tests, but it gives the next question somewhere to run. I added an offline adapter, ran all 27 public cases once and kept the per-case results. The arena stays in its own checkout; see the [bilingual setup guide](docs/arena.md).

## What I'd do first next time

Late in the competition I was already asking why a change only affected one familiar test, and whether all those initial-capital thresholds described risk or simply remembered the cases. Those were useful questions. I hadn't yet built an independent evaluation setup to answer them.

I'd now start with more markets, customers and competitors, keeping some scenarios out of the tuning loop. Cross-contract exposure, pricing uncertainty and inventory management are worth revisiting, but first I need tests that can distinguish a real improvement from a fortunate run.

## Tools and people along the way

ChatGPT and Codex helped me work through concepts, Python errors and possible implementations. I kept coming back to “why?” and “which part do we write first so I can actually understand it?” Having code and knowing where it might fail are different things.

Thanks to Akuna for a challenge that kept me occupied for quite a while. After the competition I also read [Luke Abraham's project](https://github.com/lukeabraham24777/akuna-virtual-trading-challenge) and used [strixthekiet's arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena). Sources and reuse details are in [NOTICE](NOTICE.md).
