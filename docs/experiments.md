# 留下来的几组实验 / A few experiments worth keeping

比赛时试过的版本比这里多得多。没有把它们全部塞进仓库：一整排只差一个参数的 Python 文件，实在不太适合考古。这几组记录更能解释最终版是怎么走到那里的。

表里的分数都来自我反复观察过的开发测试，不是另外留出来的验证集。

I tried far more variants than appear here. A directory full of Python files that differ by one parameter would make a rather unkind archaeological site. These examples do a better job of explaining how I reached the final submission.

The scores below come from development tests I repeatedly observed, not a separate held-out evaluation set.

## 当时改了什么 / What changed

| 版本 | 改动 | 观察到的结果 | 当时的决定 |
| --- | --- | --- | --- |
| V4H | 在 40 本金场次滚动重估参数 | 18.20/20；记录总 PnL 283.83 | 留作基线 |
| V4I | 调整 40 本金压力状态下的价差 | 18.50/20；一场升到第一 | 保留 |
| V5D | RFQ 未成交后，尝试更窄的价差 | 18.20/20；两场小本金测试变差 | 回退 |
| V5E | 将估计值与开局先验混合 | 17.60/20 | 回退 |
| V5F | RFQ 活动较少时，用观察到的 FOK 价格作为软边界 | 与 V4I 的记录序列完全相同 | 没有看见收益 |
| V7A | 始终开启库存 reservation adjustment | 18.30/20；最差亏损变小，但另一场掉分 | 回退 |
| V7B | 只在高利用率时开启库存保护 | 与 V4I 的完整开发测试序列相同：18.50/20 | 最终提交 |

| Candidate | What changed | What I observed | Decision at the time |
| --- | --- | --- | --- |
| V4H | Rolling calibration in the 40-capital sessions | 18.20/20; recorded PnL 283.83 | Kept as a baseline |
| V4I | Adjusted the spread in the stressed 40-capital regime | 18.50/20; one session moved to first place | Kept |
| V5D | Narrower spread probes after unsuccessful RFQs | 18.20/20; two small-capital sessions worsened | Reverted |
| V5E | Blended estimates with an opening prior | 17.60/20 | Reverted |
| V5F | Used observed FOK prices as soft bounds after low RFQ activity | Same recorded vector as V4I | No demonstrated gain |
| V7A | Always-on inventory reservation adjustment | 18.30/20; smaller worst loss but a lower score in another session | Reverted |
| V7B | Inventory guard active only at high utilization | Same complete development vector as V4I: 18.50/20 | Final submission |

## 分数与风险，不总是同一个方向 / Score and risk can disagree

V7A / V7B 是这次过程里很典型的一段。V7A 把最差的记录亏损从 -7.05 缩小到 -4.06，却让另一个 case 失去满分。V7B 把库存调整收得更克制，保住了熟悉的结果。比赛结束前，我没有独立的测试集来判断哪种库存规则更能泛化，所以这里不替它们追认一个“理论上更好”。

The V7A / V7B decision captures a recurring trade-off. V7A reduced the worst recorded loss from -7.05 to -4.06, but another case lost full credit. V7B kept the adjustment in a less active form and preserved the familiar results. I had no separate evaluation set to establish which inventory rule generalized better, so neither gets a retrospective “better in theory” badge here.

## “没变化”也可能有好几种解释 / The many meanings of “no change”

几组对手方识别和 FOK 方向实验也没改变结果。但总收益没变化，不等于机制已经被证明没用：可能条件根本没触发，价格变化被按分舍入吃掉，或者另一个容量限制挡住了成交。比赛时日志有限，我经常没法把这些原因拆开。

[results/](../results/README.md) 里的 JSON 保留了从 HackerRank 手动抄下来的部分序列，方便重新比较。它们不是从第一天就自动记录的完整实验史——当时我首先是在学着把 bot 写出来，然后才意识到自己也需要学着把实验记下来。

Several counterparty and FOK-direction experiments also produced unchanged results. That does not explain why: a gate may never have activated, a price change may have rounded away, or another capacity limit may have prevented a fill. With the limited logs available during the competition, I often could not isolate those possibilities.

The JSON files in [results/](../results/README.md) preserve selected vectors manually transcribed from HackerRank. They make comparisons easier, but are not a complete experiment history recorded from day one. At first I was learning to build the bot; learning to keep useful experiment notes came a little later.
