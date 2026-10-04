# What I learned building this bot

I entered the challenge without having built a binary-options market maker before. The financial definition was straightforward: the contract pays either zero or one. Understanding the exchange took longer. I wanted to know whether I was trading against other participants or preset bots, what RFQs revealed, and why selling a cheap contract could use more cash than buying it.

I also asked whether running the tests would affect the bot's cash in later runs. Looking back, that question captures where I started: I was still trying to distinguish the program, the simulation and a trading account.

## Getting something to run

The first version was deliberately small. It quoted 0 to buy and 1 to sell, with quantity one, and ignored almost every FOK. The trading tests passed because the bot survived. The pricing test failed because a placeholder returned `None`, and then because the replacement returned 0.5 for every contract.

Passing 19 out of 20 sounded promising until I understood what a pass meant. The short diagnostic sessions awarded full credit for avoiding errors and bankruptcy. The longer sessions still gave partial credit to a maker that survived while barely trading. I needed to read the PnLs and rankings, not just count green tests.

I built the pricer in stages. First came the discrete FED process, then the individual companies, then comparisons between them. At the same time I was learning Python details such as why `distribution.items()` needs parentheses and how type annotations differ from assignment. Breaking the code into pieces I could run made it much easier to follow.

The supplied-parameter pricing examples eventually matched the logged reference values. That was a useful checkpoint. It established that I could calculate a probability from the model; it did not tell me how accurately I could estimate the model from a short history.

## Spending too long on the wrong constraint

I initially focused on FOK orders because their direction, price and quantity are visible before accepting them. It seemed easier to make a careful yes-or-no decision than to compete through a two-sided RFQ quote.

After many small adjustments, I started questioning whether that was the right priority. I kept getting the same outputs back. Even when the prices changed, the bot was often offering only one contract. The size limit was restricting how much difference the pricing changes could make.

Increasing boundary-price quantity from one to ten produced the clearest early improvement. In one development session, PnL went from 6 to 27. Those fills had zero worst-case loss at the quoted price. Active quotes needed a different treatment: quantity had to fit both the cash budget and the inventory limit.

That experience changed how I debugged the strategy. When a parameter did not affect the result, I began looking for another constraint that prevented it from reaching the exchange: quantity, a cash floor, a position cap, a rounding tick, or a model-readiness branch.

## Experiments and version confusion

The later code did not arrive in one clean design. I tried wider and narrower spreads, capital-scaled sizes, rolling calibration and several inventory rules. I also tried counterparty markouts, signals from FOK prices and directions, and small spread probes after repeated unsuccessful RFQs.

Some experiments had no observable effect. Others produced a trade-off that was hard to judge. An always-on inventory adjustment improved the worst recorded session but made another session lose its first-place score. A later guard kept the inventory idea but activated only at high utilization; its development result vector was identical to the previous baseline.

By then there were too many similar versions. I started keeping the full PnL and score vectors rather than relying on a name like "new version." I retained a stable version and compared each candidate with it. This discipline came out of getting confused; it was not how the project began.

I also learned that total PnL was an awkward target for this contest. Making much more money in a session where the bot was already first did not increase the score. Small changes in another session could change the ranking and therefore the score. One losing session still earned full credit because everyone else lost more.

## The result, and the limit of my evidence

The final V7B version reached 18.5/20 on the development tests, including 14.5/16 across the scored trading sessions. Twelve of those sixteen sessions earned full credit. I did not finish in the top 30 in the final competition results.

I had worried about hidden tests during development, particularly when a rule only affected one familiar case. That concern was justified, but I did not build a sufficiently independent evaluation process before the deadline. I kept returning to the same result vectors to decide which changes were good.

I cannot identify the exact reason for the final ranking without the final per-session results. There are concrete weaknesses in the code, though. The smaller-capital sessions keep their opening parameter estimates. The readiness flag can remain fixed even after more observations arrive. Several execution rules depend on capital buckets. The collateral balance is also used in a "profit cushion" condition even though cash can fall simply because it is tied up in open positions.

Those choices helped preserve observed development results. I had not established that they were good decisions across new environments.

## What the next version would need

After the contest I read other participants' code and found the community arena. That made the missing piece clearer: I needed a way to run more markets without treating each familiar test as a target.

I would vary sample length, market parameters, order flow and competition, and decide in advance which markets to keep out of tuning. I would check the collateral ledger after every fill and expiry. On the strategy side, I would allow learning in every capital regime and attach a measure of uncertainty to each price estimate before adjusting spreads and size.

Counterparty learning and reinforcement learning remain interesting ideas. I did not implement RL in this competition. I would want a trustworthy environment and a simpler baseline before using it, so that an impressive simulated result had something meaningful to compare with.

I used AI throughout the project. It helped explain unfamiliar concepts and generate code, and it sometimes suggested more complexity than the evidence supported. My most useful contribution was asking why a change did nothing, noticing when the objective had drifted, and insisting that the code be built in pieces I could understand. I am keeping the project because those questions are useful beyond this particular competition.
