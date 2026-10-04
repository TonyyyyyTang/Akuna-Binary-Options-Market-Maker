# 比赛结束，机器人还能继续练 / Keeping the bot in training

## 这个 arena 是什么？ / What is this arena?

[Akuna Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena) 是 strixthekiet 做的社区项目：交易所模拟器、公开场景，以及让不同做市机器人对战的 WebSocket 服务。比赛结束之后，bot 总算不用跟着一起退休了。

它不是官方 hidden test。arena 的评分满分是 27，与我比赛中记录的开发测试 18.5/20 是两把不同的尺子。

在线设计中，策略留在自己的电脑上。服务器发送行情、询价和 FOK 订单，客户端返回报价和接受决定。两个参考对手分别是固定价差做市商和 lattice 做市商。公开场景覆盖短历史、小资金、知情订单流、波动率变化和市场状态切换，适合拿来检查一个在少量重复测试中成长起来的策略。

[Akuna Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena) is a community project by strixthekiet: an exchange simulator, public scenarios and a WebSocket server for matching different makers. The competition is over; the bot doesn't have to retire with it.

It does not contain the official hidden tests. Its 27-point score and my recorded 18.5/20 competition development score measure different things.

In live play, a strategy stays on its owner's machine. The server sends market states, RFQs and FOK orders; the client returns quotes and decisions. The two reference opponents are a fixed-width maker and a lattice maker. Public scenarios cover short histories, thin capital, informed flow, changing volatility and regime shifts—useful tests for a strategy developed against a small, repeated set of cases.

## 在本地跑起来 / Running locally

我加了一个离线适配器，不用连接社区对战就能使用交易所。上游源码放在单独的 checkout 中，这个仓库提供引用和自己的适配代码，不重新发布对方源码；检查时，上游还没有许可证。此次接入检查的版本是 `7a9f2e6f0eff5785d13873fd07c560f3c9728cf2`。

I added an offline adapter, so this repository can use the exchange without joining a community match. Keep the arena in a separate checkout: this repo links to the original project and supplies its own adapter rather than republishing the upstream source, which had no license when reviewed. The revision reviewed for this integration is `7a9f2e6f0eff5785d13873fd07c560f3c9728cf2`.

从本仓库根目录运行 / Run from this repository's root:

```bash
git clone https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena ../akuna-arena
git -C ../akuna-arena checkout 7a9f2e6f0eff5785d13873fd07c560f3c9728cf2
python3 scripts/run_arena.py --arena-dir ../akuna-arena --cases 1 7 18 --seeds 0 1 2
```

需要 Python 3.11 或更新版本。离线交易所模块只用标准库；FastAPI 等依赖只在架设服务器时需要。去掉 `--cases` 会运行全套场景，`--events` 保留详细事件，`--output` 指定 JSON 输出路径。默认结果放在被 Git 忽略的 `.local/arena/`。

正常结束的场次会记录 checkout 版本、seed、分数、PnL、运行故障，以及策略现金账本与交易所余额的差值。

Python 3.11 or newer is required. The offline exchange modules use the standard library; FastAPI dependencies are needed only for hosting a server. Omit `--cases` for the full suite, add `--events` for detailed event records, and use `--output` to choose a JSON path. Default results go under `.local/arena/`, which is excluded from Git.

For normally completed sessions, the adapter records the checkout revision, seed, score, PnL, faults and the difference between the strategy's cash balance and the exchange's balance.

## 新 seed 不等于新宇宙 / A new seed is not a whole new world

seed `0` 复现各场景原本的随机世界；其他 seed 会改变行情和订单流，但预先定义的期权簿不变。因此，多跑 seed 有帮助，却只是验证的一部分。本地 runner 也不会复现在线服务器的网络延迟和响应期限。

另一个细节：arena 在分配同价成交时，会消耗订单流的随机数。因此，策略变了，即使用同一个 seed，后续订单也不保证完全相同。

Seed `0` reproduces each case's original world. Other seeds change market and order streams, but the declared option book stays fixed. A seed sweep helps; it is still only one kind of validation. The local runner also does not reproduce the live server's network latency or deadlines.

One more detail: tie allocation consumes the flow random stream. Changing the strategy can therefore change later orders even when the seed stays the same.

## 一处接口差异：整轮报价先到，成交回调后到 / A batching wrinkle

arena 会先收集整轮报价，再通知成交。V7B 每次询价都用“此刻的现金”检查预算，多个同时成交的报价因此可能重复使用同一份资金。默认适配器保留提交版行为。

可选的 `--batch-reserve` 在回答整轮请求时，临时预留潜在最大损失；真实成交到来之前，再恢复现金账本。这是赛后实验，不是偷偷修改比赛提交版。它只处理跨请求的现金预留，没有同时预留单合约持仓容量，所以还不是完整的组合风险控制器。

The arena collects a whole round of quotes before sending trade callbacks. V7B checks each request against its current cash, so simultaneous fills can use the same budget more than once. The default adapter preserves the submitted behavior.

The optional `--batch-reserve` flag temporarily reserves possible losses while answering the round, then restores the cash balance before actual fills arrive. This is a post-competition experiment, not a change to the archived strategy. It reserves cash across the batch, but not per-contract position capacity, so it is not a complete portfolio-risk controller.

## 第一次本地跑分 / First local run

接好适配器后，我用各场景原本的 seed 跑了全部 27 场，也用同一个冻结策略测试了可选的批量现金预留。

After adding the adapter, I ran all 27 public cases at their original seeds, then ran the same frozen strategy with the optional batch cash-reservation wrapper.

| 模式 / Adapter mode | 分数 / Points /27 | 总 PnL / Sum of PnL | 故障 / Faults | 破产 / Bankruptcies |
| --- | ---: | ---: | ---: | ---: |
| 提交版行为 / Submitted behavior | 17.0 | 108.5357 | 0 | 0 |
| 批量现金预留 / Optional batch reservation | 17.5 | 94.5465 | 0 | 0 |

所有场次结束时，策略与交易所的现金账本一致。逐场记录分别在[提交版结果](../results/arena_submitted_seed0.json)和[批量预留结果](../results/arena_batch_reserve_seed0.json)中。接口跑通了，是个好开始；但一套固定公开场景，还不足以判断哪个模式是更好的策略。

在线对战或自行架设服务器，请看上游 [README](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/README.md) 和[协议说明](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/PROTOCOL.md)。这个仓库没有验证托管服务器目前是否在线。

The strategy and exchange cash balances agreed at the end of every run. Per-case records are in the [submitted-mode results](../results/arena_submitted_seed0.json) and [batch-reservation results](../results/arena_batch_reserve_seed0.json). The integration works, which is a good start; one fixed public suite does not establish which mode is the better strategy.

For live play or hosting, follow the upstream [README](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/README.md) and [protocol](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena/blob/main/PROTOCOL.md). This repository has not confirmed whether the hosted server is currently available.
