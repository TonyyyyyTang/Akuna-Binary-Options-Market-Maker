# A few experiments I kept notes on

I tried more variants than are useful to publish as near-duplicate Python files. These examples explain the decisions behind the final submission. The scores below refer to development tests which I repeatedly observed; they are not held-out validation.

| Candidate | What changed | What I observed | Decision at the time |
| --- | --- | --- | --- |
| V4H | Rolling calibration in the 40-capital sessions | 18.20/20, recorded PnL 283.83 | Kept as a baseline |
| V4I | Adjusted the spread in the stressed 40-capital regime | 18.50/20; one session moved to first place | Kept |
| V5D | Narrower spread probes after unsuccessful RFQs | 18.20/20; two small-capital sessions worsened | Reverted |
| V5E | Blended estimates with an opening prior | 17.60/20 | Reverted |
| V5F | Used observed FOK prices as soft bounds after low RFQ activity | Same recorded vector as V4I | No demonstrated gain |
| V7A | Always-on inventory reservation adjustment | 18.30/20; smaller worst loss but a lower score in another session | Reverted |
| V7B | Inventory guard active only at high utilization | Same complete development vector as V4I: 18.50/20 | Final submission |

The V7A/V7B decision illustrates the limit of the process. V7A made the worst recorded loss smaller, from -7.05 to -4.06, but another case lost full credit. V7B kept the idea in a less active form and preserved the familiar results. I did not have a separate evaluation set to establish whether either inventory rule generalized better.

Several counterparty and FOK-direction experiments also produced unchanged results. An unchanged aggregate does not by itself show why a mechanism failed: a gate may not have activated, a price change may have rounded away, or another capacity limit may have prevented a fill. During the competition I had limited logs and often could not isolate those possibilities.

The JSON files in `results/` preserve selected vectors transcribed from HackerRank. They make comparisons inspectable without suggesting that the entire development history was recorded systematically from day one.
