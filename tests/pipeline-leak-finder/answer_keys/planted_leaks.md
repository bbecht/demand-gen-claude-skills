# Answer key: planted leaks

Written from the generator (`examples/pipeline-leak-finder/generate_sample.py`), not from the skill's output. Every test file comes from that generator with a different seed.

## What the generator plants

Pipeline: Discovery > Qualified > Demo > Proposal > Negotiation > Closed Won or Closed Lost. Deals are created January 2024 to September 2026. The export date is 15 September 2026.

| Stage | Planted chance of moving on |
|---|---|
| Discovery | 65%, plus or minus up to 3 points per quarter at random |
| Qualified | 72%, plus or minus up to 3 points per quarter at random. 6% of deals skip it and jump from Discovery to Demo |
| Demo | 45%, plus or minus up to 3 points per quarter. **2025 Q2: 70%.** The demo format that ran that quarter |
| Proposal | One in three proposals stalls: median 32 days in stage, 25% move on. The rest: median 10 days, 80% move on |
| Negotiation | Deals under $75,000: 90% close won. Deals of $75,000 or more: 45% |

Amounts: median about $30,000, $6,000 to $260,000. 60% of deals lost in Discovery or Qualified have no amount.

## What the tests check

Two kinds of check. The answer key tests recompute every number from the generator's own deal records, with their own code, and must match the skill exactly. The planted leak tests check the skill finds what was planted.

| Check | Why it follows from the plant |
|---|---|
| Moved on, lost here, still open, conversion, median days and stall line match the generator's records exactly, every stage, every file | The skill counts what happened. Nothing else |
| Deals a year, best quarter, target and fix value match a separate recomputation | Same method, written twice, no shared code |
| Demo to Proposal ranks first, best quarter 2025 Q2, evidence "holds up" | 70% against 45% on about 80 deals is far outside normal swing |
| Demo to Proposal has the lowest conversion | 45% is the lowest planted rate |
| Every other stage's best quarter reads "could be luck" or has too few quarters | Their swings are planted as noise |
| On 600 deals (test4) the headline fix reads "could be luck" | The same leak, on too few deals to call it proven. The skill must not overclaim |
| Proposal has the costliest wait. Past the stall line, win rate falls by 40% or more and by 25 points or more | Stalled proposals move on 25% of the time against 80% |
| Negotiation has the biggest typical lost deal | Big deals close half as often in Negotiation |
| Discovery has the most lost deals | 35% of every deal ever created is lost there |
| Qualified shows deals skipped through | 6% skip it |
| HubSpot and Salesforce layouts of the same sample give identical stage, fix and overview numbers | Same deals, different export |
