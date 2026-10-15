# Before you run the Marketing Mix Model

The model learns from how sales moved when spend moved. If spend never moved, or moved only when demand did, no model can recover the answer. This page covers what has to be in place, and what happens when it is not.

## What do I need to run it at all?

- **A Claude account on any plan, Free included,** with code execution turned on. Skills do not run without it.
- **The skill uploaded.** In Claude: Customize > Skills > + > Create skill > Upload a skill.
- **One weekly CSV.** One row per week, a week date, sales or revenue in dollars, and one spend column per channel. The [data guide](data-guide.md) shows the layout.
- **History.** 52 weeks is the floor. 104 weeks is where seasons and trend come apart. 156 or more is better.
- **Spend that moved.** Each channel needs at least 8 weeks with spend. A channel that ran at the same level every week cannot be measured.

No connectors or MCP servers are needed. The skill works from the file you upload, inside your own Claude session. Nothing is sent anywhere else.

## What makes the answer trustworthy?

Most of these show up in the tool's model check when they are missing. Timing and missing sales do not, so check those yourself.

| What has to be true | Why it matters | What you see if it is not |
|---|---|---|
| Spend went up and down over time | The model reads a channel's effect from its swings | Wide ranges, Test first verdicts. A channel at the same level every week is left out and named |
| Channels did not always run together | Two channels that always move as one cannot be split | A warning that names the pair |
| Everything else that moves sales is in the file: price, promotions, big events | A missing driver gets credited to whatever media ran at the time | Misses that run in streaks, a directional verdict |
| Sales are in dollars and include every channel's sales | The model needs the full outcome, not one funnel's | Nothing flags it. Returns look too high or too low |
| Spend is recorded the week it ran, not the week it was billed | Carry-over math needs the real timing | Nothing flags it. Carry-over looks wrong |
| Weeks are continuous | Carry-over runs week to week | A stop when more than 10% of weeks are missing |

## What does the margin do?

Your gross margin sets break-even. At 50%, a channel needs $2 of sales for every $1 of spend to cover itself. At 40%, it needs $2.50. Every verdict moves with it, so use your real number.

## What about lift tests?

A geo test, holdout or platform lift study measures a channel directly. Give the skill the result as sales per $1 with its standard error, and the model holds that channel close to it. Tested channels move from guesses to anchors. This is the fastest way to settle a Test first channel.

## Readiness checklist

- [ ] Code execution is on in Claude
- [ ] The skill is uploaded
- [ ] One row per week, at least 52 weeks, ideally 104 or more
- [ ] Sales or revenue in dollars
- [ ] One spend column per channel, with spend in the name
- [ ] Each channel has at least 8 weeks of spend, and its spend moved
- [ ] Price, promotions and big events in the file, if they move your sales
- [ ] Your gross margin
- [ ] Lift test results, if you have any

The first five are required. The rest decide how far you can trust the answer.
