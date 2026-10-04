# Binary Options Market Making

**中文** · [English](README.en.md)

这是我参加 2026 Akuna Virtual Trading Challenge 时写的做市机器人，也留着我一路追问、试错和改版本的痕迹。

合约到期不是 0 就是 1；轮到机器人做决策，就没有这么干脆了。

比赛期间能看到的测试最后做到 **18.5/20**，正式结果没有进入前三十。这中间的落差，值得我再学一遍。所以这个仓库不只有最后的代码，也留下了它是怎么长出来的。

## 从哪里开始的

一开始，我能理解 binary option 的收益，却不太理解做市的过程：RFQ 到底是谁来问价？客户买，我为什么是在卖？FOK 能不能只接一部分？每次运行测试，会不会把上一次的本金继续花掉？

我也没有一开始就写出一个完整的 bot。先取个名字，再用 `bid=0`、`offer=1`、`quantity=1` 跑起来，接着一点点补定价：FED 的离散状态转移、两家公司的估值分布、最后是公司之间的比较合约。中间还顺便补了 Python——包括那个很小、但足以让程序停下来的区别：`items` 和 `items()`。

定价样例对上了，收益却没跟着起飞。我先在 FOK 和价差上折腾了不少轮，后来才发现：**quantity 一直是 1**。价格改了不少，柜台上始终只有一张合约。把 `bid=0`、`offer=1` 这组边界报价的数量提到 10 后，一个开发测试的收益从 6 变成了 27。这次突破不在模型更复杂，而在终于找到真正卡住成交的地方。

之后试了主动报价数量、现金预算、库存偏移、滚动估计和订单反馈。有些有效，有些顾此失彼，还有不少让我再次发出那句熟悉的“还是没有变化”。版本也确实乱过，后来才养成保留稳定版、记录完整收益序列、一次比较一个改动的习惯。

更完整的过程在[中文复盘](docs/retrospective.zh-CN.md)和 [English retrospective](docs/retrospective.md) 里。[实验记录](docs/experiments.md)也留下了一些最后没采用的想法。

## 这个 bot 在做什么

交易的是三个模拟标的上的事件合约：利率 FED，以及两家虚构公司的估值 AJR、THR。事件发生，到期支付 1；否则支付 0。也有比较两家公司估值高低的合约。

机器人主要做四件事：

- 从历史数据估计参数，把事件概率转成理论价格。
- 回答 RFQ，给出双边价格和愿意成交的数量。
- 判断 FOK 的价格是否值得接，以及整张订单能否承担。
- 跟踪仓位和现金占用，让交易规模受到最坏损失约束。

这个比赛的现金机制很特别：平掉仓位不等于立刻拿回抵押金。因此 bot 还维护了自己的资金账本。公式和实现细节见[策略说明](docs/strategy.md)。

[bot.py](bot.py) 是最终提交的 V7B，保留了当时的策略，包括现在看来还需要改的分支。[model.py](model.py) 是赛后补的本地接口，不是原 HackerRank 模板。

## 留一份成绩单

| 开发测试记录 / Development results | V7B |
| --- | ---: |
| 总分 / Overall score | 18.50 / 20 |
| 16 个计分交易场景 / Scored trading sessions | 14.50 / 16 |
| 满分交易场景 / Full-credit sessions | 12 / 16 |
| 各场 PnL 之和 / Sum of session PnL | 284.76 |
| 这些运行中的破产次数 / Bankruptcies | 0 |

完整序列放在 [results/](results/)，是比赛期间手动保存的开发测试输出；官方最终评测的逐场结果我没有拿到。

有一场亏了 7.05，仍然拿到满分，因为其他做市商亏得更多。这场比赛让我很具体地理解了“收益”和“名次”为什么不是一回事。

## 在本地跑起来

Python 3.11 或更新版本即可，本地检查不需要额外安装包：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_results.py
python3 scripts/export_submission.py --output .local/submission.py
```

测试检查定价例子、资金账本和结算规则。最后一条命令导出 `MarketMaker` 类，供兼容的比赛模板使用；日常维护的源文件仍是 `bot.py`。

## 比赛结束了，bot 还可以上场

赛后找到的社区 [AkunaVirtualTradingChallenge2026Arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena)，提供了交易环境、公开场景和竞争机器人，可以继续在本地对战，也支持线上 bot 对战。

它不是 Akuna 官方隐藏测试的复刻，但很适合把“下一次会怎么样”变成一个能运行的实验。我加了本地适配器，跑完一轮 27 个公开场景，并把逐场结果留下来。Arena 保持为独立仓库，安装和使用方式见[双语运行说明](docs/arena.md)。

## 下次我会先做什么

我后期已经开始问：为什么一个改动只影响某个熟悉的测试？按初始本金写这么多门槛，是在理解风险，还是在记住题目？这些疑问是对的，只是当时没有及时配上一套独立验证。

现在再做，我会先准备更多市场、客户和竞争者，把一部分场景留在调参之外，再去改模型和报价。跨合约风险、定价不确定性、库存管理都值得继续研究，但得先有一个能分清“真进步”和“这次碰巧”的测试环境。

## 一路上的工具和参考

这一路也没少找 ChatGPT 和 Codex 帮忙：讲概念、查 Python 错误、讨论候选实现。我经常追问的还是“为什么”，以及“先写哪一部分，才能让我真的看懂”。有代码是一回事，知道它什么时候会失灵，是另一回事。

感谢 Akuna 出了这个让我认真折腾了一阵的题目。赛后也读了 [Luke Abraham 的项目](https://github.com/lukeabraham24777/akuna-virtual-trading-challenge)，并用到了 [strixthekiet 的 arena](https://github.com/strixthekiet/AkunaVirtualTradingChallenge2026Arena)。相关来源和复用说明在 [NOTICE](NOTICE.md)。
