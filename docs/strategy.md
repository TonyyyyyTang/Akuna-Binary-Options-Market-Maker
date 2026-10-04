# Strategy notes

The final submitted strategy is kept in `bot.py`. The local interface in `model.py` is independently written for testing; the original platform template is not redistributed here.

## Pricing

A contract pays `1{observable >= strike}` at expiry. The bot computes the probability of that event under the supplied or estimated simulation parameters. There is no discounting in the contest implementation. These probabilities are model prices for this exercise, not market-implied probabilities from traded securities.

FED moves up, down or stays on a discrete grid. Its transition probabilities are tilted toward a target rate and clipped to remain valid. The pricing routine propagates probability mass for each remaining day. It keeps the zero boundary and the simulator's rounding rule.

For each company, daily log returns follow a drift, a rate-change contribution, a shared sector shock and an independent shock. Conditional on the final rate, the accumulated rate contribution is beta times the net rate change. A single-company binary is therefore a mixture of normal tail probabilities weighted by the FED terminal distribution.

The zero-strike company comparison is an event on the log ratio of the two valuations. Its residual return variance is `var(AJR) + var(THR) - 2*cov(AJR, THR)`. A common factor cancels only to the extent that the two factor loadings are equal.

The local tests reproduce the six reference values printed during the competition. That checks the given-parameter calculation, not calibration accuracy or the full range of market parameters.

## Estimation

Warm-up observations supply rate changes and company log returns. The bot estimates rate transitions, company rate betas, drift and the residual covariance matrix. Some coefficients and second moments are shrunk toward priors. The final version uses the unshrunk company drift estimate.

Rolling re-estimation is enabled only for initial capital of at least 40. The opening readiness flag is preserved. This is a historical implementation choice with a clear limitation: accumulating more observations may not change the execution regime. It is retained so the archived strategy has the same behavior as the submission.

## Quotes and FOKs

RFQ quotes are centered around the estimated probability, with cent rounding, a spread, a cash budget and position limits. The final spread and capacity settings depend on readiness and initial-capital buckets. A high-utilization inventory guard can shift the quote center by a small amount.

FOK decisions compare the offered price with the estimated value, then check the worst-case loss of the full requested quantity. The full-quantity check is conservative because the order can be shared among accepting makers. Exact boundary orders, selling at 1 or buying at 0, have zero maximum loss per contract.

## Cash accounting

For a buy of `q` at price `p`, the competition debits `q*p` from the reserve. For a sell it debits `q*(1-p)`. The bot records gross buys and sells separately, even when the net position is zero.

At expiry, with payoff `Y`, the credit is:

```text
gross_bought * Y + gross_sold * (1 - Y)
```

Buying and then selling the same contract does not release those reserves before expiry. This is why net inventory alone is insufficient for the cash ledger.

Available reserve is also different from marked equity. Buying ten contracts at 0.40 consumes four units of reserve even if their current model value is 0.60. The submitted strategy's profit-cushion condition uses reserve cash and therefore mixes trading performance with collateral usage. A future version should maintain those quantities separately.

## Limits of this version

The strategy does not learn from counterparty IDs. It has no calibrated confidence intervals for estimated prices. Its main position limits are per contract, and several capital-specific conditions came from development-test experiments. The small inventory guard preserved the recorded score but was not independently shown to help new markets.
