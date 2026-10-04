# 策略怎么工作的 / How the strategy works

最终提交版留在 [bot.py](../bot.py)。[model.py](../model.py) 是为本地测试另外写的接口，没有把比赛平台的原始模板一起搬过来。这篇说明讲的是当时实际提交了什么，也保留了那些现在回头看并不完美的地方。

The final submission lives in [bot.py](../bot.py). [model.py](../model.py) is a separately written interface for local testing, rather than a copy of the platform template. These notes describe what I actually submitted, including the parts I would approach differently now.

## 定价：先把概率算明白 / Pricing: start with the probability

每张合约到期支付 `1{observable >= strike}`。所以，第一步是用题目给出的、或从历史数据估计的参数，计算事件发生的概率。比赛实现里没有贴现；这里的价格是模拟模型下的概率，不是从现实证券价格反推出的市场隐含概率。

FED 每天在离散网格上上涨、下跌或不变。转移概率会向目标利率倾斜，并截断到合法范围。定价时逐日递推各个利率状态的概率，同时保留模拟器的零利率边界和舍入规则。

两家公司的日对数收益由漂移、利率变化项、共同的行业冲击和各自的独立冲击组成。给定最终利率后，累计利率影响就是 `beta × 净利率变化`。因此，单公司 binary 的价格可以写成正态尾概率的混合，再用 FED 的终值分布加权。

零执行价的公司比较合约，可以转成两家公司估值的对数比事件。其剩余收益方差是 `var(AJR) + var(THR) - 2*cov(AJR, THR)`。共同因素是否抵消，取决于两家的因子暴露是否相同，不能因为都属于 AI 行业就直接划掉。

本地测试复现了比赛输出的六个参考定价。这说明“给定参数后怎么算”对上了，不代表参数估计也准确，更不代表所有市场参数都测过了。

A contract pays `1{observable >= strike}` at expiry. The first job is to calculate that event's probability under the supplied or estimated simulation parameters. The contest implementation has no discounting. These are model probabilities for the exercise, not probabilities implied by real traded securities.

FED moves up, down or stays on a discrete grid. Its transition probabilities tilt toward a target rate and are clipped to remain valid. The pricer propagates probability mass one day at a time, preserving the simulator's zero boundary and rounding rule.

Each company's daily log return contains drift, a rate-change term, a shared sector shock and an independent shock. Conditional on the final rate, the accumulated rate contribution is `beta × net rate change`. A single-company binary is therefore a mixture of normal tail probabilities, weighted by the FED terminal distribution.

A zero-strike company comparison becomes an event on the log ratio of the two valuations. Its residual return variance is `var(AJR) + var(THR) - 2*cov(AJR, THR)`. A common factor cancels only where the two factor loadings are equal—not simply because both companies work in AI.

The local tests reproduce the six reference prices printed during the competition. That checks the given-parameter calculation, not calibration accuracy or the full range of market parameters.

## 估计：模型也要从历史里学习 / Estimation: learning from history

warm-up 数据提供利率变化和公司对数收益。代码据此估计利率转移、公司利率 beta、漂移和剩余协方差矩阵。其中一些系数和二阶矩会向先验收缩；最终版的公司漂移使用未收缩的估计。

滚动重估只在初始本金至少为 40 时开启，但开局的 `model_ready` 标记保持不变。这是当时留下的实现选择：新数据可能改变模型，却不一定改变执行档位。代码里保留原样，便于对照比赛时的结果。

Warm-up observations provide rate changes and company log returns. The bot uses them to estimate rate transitions, company rate betas, drift and the residual covariance matrix. Some coefficients and second moments are shrunk toward priors; the final version uses the unshrunk company drift estimate.

Rolling re-estimation is enabled only when initial capital is at least 40, while the opening `model_ready` flag stays fixed. That is a limitation of the submitted implementation: new observations can change the model without changing the execution regime. It stays intact in the code so the recorded contest results remain comparable.

## RFQ 和 FOK：有理论价，还要决定怎么交易 / Quotes and FOKs

RFQ 围绕估计概率报出 bid 和 offer，再加上按分舍入、价差、现金预算和持仓限制。最终的价差和容量设置依赖模型是否 ready，以及初始本金档位。库存利用率较高时，还有一个幅度很小的报价中心偏移。

FOK 则先比较订单价格与估计价值，再检查整张订单数量的最坏损失。即使多个做市商接受后会分单，这里仍按全部成交检查，因此比较保守。以 1 卖出、以 0 买入这两种边界订单，每张的最大损失都是零。

RFQ quotes start around the estimated probability, then apply cent rounding, a spread, a cash budget and position limits. The final spread and capacity settings depend on model readiness and initial-capital buckets. A small inventory guard can shift the quote center at high utilization.

For FOKs, the bot compares the offered price with its estimated value and checks the worst-case loss of the full requested quantity. This is conservative: an accepted order can be shared among several makers. Selling at 1 or buying at 0 has zero maximum loss per contract.

## 现金账本：净仓位不是全部 / Cash: net inventory is not the whole story

按价格 `p` 买入 `q` 张，比赛会从可用现金中扣掉 `q*p`；卖出则扣掉 `q*(1-p)`。代码分别记录累计买入和累计卖出，即使两者抵消后的净仓位是零。

若到期支付为 `Y`，返还金额如下：

For a buy of `q` at price `p`, the competition debits `q*p` from available reserve cash. For a sell, it debits `q*(1-p)`. The bot records gross buys and sells separately, even when their net position is zero. With expiry payoff `Y`, the credit is:

```text
gross_bought * Y + gross_sold * (1 - Y)
```

同一合约先买后卖，不会在到期前释放这两笔现金预留。账本没有“我已经平仓了，你就通融一下”这个选项，所以只看净仓位会漏掉资金占用。

可用现金也不等于按模型估值的权益。比如以 0.40 买入十张，会占用四单位现金，即使模型认为它们每张值 0.60。提交版的利润缓冲条件直接使用预留后的现金，因此混合了交易表现与抵押占用。下一版应当把这两件事分开记。

Buying and then selling the same contract does not release either reserve before expiry. The ledger has no “but I've already closed the position” exception, which is why net inventory alone is not enough.

Available reserve also differs from marked equity. Buying ten contracts at 0.40 uses four units of reserve even if the model values each at 0.60. The submitted strategy's profit-cushion condition uses reserve cash, mixing trading performance with collateral usage. A future version should track those separately.

## 还没解决的部分 / What is still missing

这版没有利用 `counterparty_id` 学习对手方，也没有为估计价格给出经过校准的置信区间。主要持仓限制仍按单个合约设置，一些本金档位条件来自反复观察开发测试。那个小库存保护保住了记录中的分数，但我没有独立证明它能改善新市场上的表现。

This version does not learn from counterparty IDs or attach calibrated confidence intervals to its prices. Its main position limits are per contract, and several capital-specific conditions came from development-test experiments. The small inventory guard preserved the recorded score, but I did not independently establish that it helped in new markets.
