# A bot, many test runs, and a useful reality check

[中文](retrospective.zh-CN.md)

This was my first attempt at making a market in binary options. The payoff was easy enough to understand: an event happens, the contract pays one; otherwise, zero. The exchange took a little more getting used to.

Who was I trading with? Why did an RFQ hide the customer's direction? Why couldn't I accept just part of a FOK? And how could selling a contract for 20 cents tie up more cash than buying it?

I also asked whether running a test would change the bot's cash balance in the next run. That is probably the best description of my starting point. I was learning the market mechanics and parts of Python as I went, with ChatGPT and Codex helping me unpack the rules, debug errors and turn ideas into code I could actually follow.

## First, keep the lights on

The first bot bought at 0, sold at 1, quoted one contract on each side and ignored almost every FOK. It was excellent at avoiding trouble and rather less interested in trading.

It passed 19 out of 20 tests. The remaining pricing test failed first because I returned `None`, then because I returned 0.5 for everything. Meanwhile, the green trading tests were mostly telling me that the bot had survived. The short diagnostic sessions rewarded that; the longer sessions could still award partial credit to a bot sitting near the bottom of the ranking.

So I started reading the PnLs and rankings, not just the pass count.

I built the pricer a piece at a time: the discrete FED process, the two companies, then contracts comparing their valuations. Along the way, I learned why `distribution.items()` needs parentheses, what type annotations do, and why people write `for _ in ...`. Writing something small enough to test and explain was much more useful to me than receiving a finished wall of code.

Eventually the supplied-parameter examples matched the logged reference values. That settled one question: given the model, could I calculate the probability? Estimating that model from a short history was still a separate problem.

## The breakthrough was hiding in `quantity=1`

I spent a while on FOKs. The direction, price and size were all visible, so deciding yes or no felt more approachable than competing for RFQ flow with a two-sided quote.

But after enough tiny changes, I began asking whether we were polishing the wrong part of the bot. Some adjustments did nothing. Others changed the PnL by a few cents. The goal was to compete in the sessions, not to produce the world's most carefully considered rejection of a FOK.

Then came the fairly unglamorous discovery: we were still quoting one contract.

Changing boundary-price quantity from 1 to 10 took one development session's PnL from 6 to 27. Buying at 0 or selling at 1 had zero worst-case loss under the challenge's rules, so these fills did not need the same sizing treatment as active quotes. Active size still had to fit the cash budget and inventory limit.

That became a useful debugging habit. If a change did nothing, I checked whether it could actually reach the market. Was quantity capped? Was the cash floor binding? Did the position limit, cent rounding or `model_ready` branch quietly switch it off?

## A small collection of almost-identical versions

From there I tried different half-spreads, capital-scaled sizes, rolling parameter estimates and inventory adjustments. I also explored counterparty markouts, signals from FOK prices and directions, and small spread changes after RFQs that failed to trade.

Some ideas had no visible effect. Some helped one session and hurt another. An always-on inventory adjustment improved the worst recorded session but cost a first-place finish elsewhere. A later guard kept the inventory idea and activated only at high utilization; its development results were exactly the same as the earlier baseline.

I also got my versions mixed up. Names like “new version” stopped being useful surprisingly quickly. I began saving all sixteen PnLs and scores, keeping a stable baseline and comparing one candidate at a time. The tidy experiment records in this repo arrived after the untidy part.

The scoring added another wrinkle. More total profit was not always worth more points. A large improvement in a session I already won could earn nothing extra; a small ranking change elsewhere could matter a lot. In one session, losing money still earned full credit because every other maker lost more. An unusual result to celebrate, but those were the rules.

## What 18.5 did—and didn't—tell me

The final V7B reached **18.5/20 on the development tests**: 14.5/16 across the scored trading sessions, with twelve of those sixteen earning full credit. In the final competition results, **I did not finish in the top 30**.

I had already been asking about hidden tests. Why did an inventory rule affect only one familiar case? Were the initial-capital thresholds reasonable risk controls, or were they becoming shortcuts for recognising the test set? Those were useful questions, but I did not give them a proper independent evaluation before the deadline. I kept coming back to the same result vectors to choose the next change.

Without the final per-session results, I cannot say exactly what caused the final ranking. I can point to things I would now revisit: smaller-capital sessions keep their opening parameter estimates; `model_ready` can stay fixed as more observations arrive; several execution rules use capital buckets; and a “profit cushion” condition uses collateral cash, which can also fall because money is tied up in open positions.

The visible score was encouraging. It was not a certificate that the bot would behave well in a different market.

## Keeping the project going

After the contest, I read other participants' code and found the community arena. Having a local environment means I can inspect trades and test more than the same familiar sixteen sessions. It does not give me the official hidden tests, but it gives me a much better place to work.

Next, I want to separate markets used for tuning from markets used for checking the result, vary the history length and market conditions, and reconcile the cash ledger after fills and expiry. I would also revisit learning in every capital regime, pricing uncertainty and risk shared across contracts.

Counterparty learning and RL are still interesting directions. I did not implement RL during the competition. Before trying it, I want an environment I trust and a simple baseline worth beating.

I am keeping this repo as a record of the whole attempt, including the ideas that went nowhere. The part I want to carry forward is the habit of asking what a result actually shows: whether a change reached the exchange, whether it addressed the real constraint, and whether it still works somewhere I haven't already spent hours tuning it.
