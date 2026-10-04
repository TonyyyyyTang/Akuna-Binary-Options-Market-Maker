# 留下来的成绩单 / Recorded results

这些序列是我比赛期间从 HackerRank 手动复制下来的。Case 5–20 是 16 个计分交易场景，前四个测试占另外四分。这里保留了几个关键版本，也留了失败的尝试；并不是每次改动都值得庆祝。

I copied these vectors from HackerRank during development. Cases 5–20 are the sixteen scored trading sessions; the first four tests account for the remaining four points. I kept a few key versions and some unsuccessful experiments. Not every change deserved a celebration.

V7B 和 V4I 的记录完全相同。我们反复跑的是同一组开发测试，不是提前留出的独立验证集。正式比赛没有进入前三十，具体名次和最终评测的逐场分数目前没有记录。

V7B and V4I have identical recorded outputs. These were repeated runs of the development cases, not a separate holdout set. I finished outside the top 30; I don't have an exact final rank or a final per-case breakdown.

在仓库根目录运行下面这条命令，可以重新计算总分和收益。收益之和只是各个独立模拟场景的 PnL 相加，不是一个账户的投资回报。

Run this from the repository root to recompute the totals. The PnL sum adds up independent simulation sessions; it isn't the investment return of a single account.

```bash
python3 scripts/check_results.py
```

Arena 的 JSON 是赛后新跑的实验，规则和分数尺度都不同，请和比赛记录分开看。

The arena JSON files are post-competition runs with different rules and scoring. Keep them separate from the contest records.
