# Campaign Brief Builder sample

A synthetic B2B campaign to try the skill on, and everything it produces.

| File | What it is |
|---|---|
| `sample_strategy.md` | The strategy as a user would paste it. Start here |
| `sample_strategy.json` | The same strategy as Claude maps it for the script |
| `sample_rubric.json` | Claude's calls on checks 5 to 10 |
| `sample_brief.json` | The requirements Claude writes after approval |
| `sample_tool.html` | The interactive tool, CEO view. Download it and open it in a browser |
| `sample_brief.md` | The brief as Markdown, the same file the tool exports |
| `sample_requirements.csv` | The requirements as CSV, ready for any task tool |
| `build_sample.py` | Rebuilds the three outputs from the inputs: `python examples/campaign-brief-builder/build_sample.py` |

## Where does it come from?

Brasswick, its customers, its people and its agency are invented. Published under MIT with the rest of the repo.

## What should the skill find?

| Check | Result | Why |
|---|---|---|
| 1. Target reachable on budget | Pass | $90K buys 700 leads, 56 expected opportunities and $1.68M in pipeline against a $1.2M target |
| 2. Opportunities land before the due date | Flag | Leads from the last 2 weeks become opportunities after Mar 31, 2027. The $1.34M that lands in time still meets the target |
| 3. Every channel can buy an opportunity | Pass | The smallest channel, SDR outbound, buys 8 expected opportunities |
| 4. Sales capacity | Pass | 24.3 opportunities a month against 30 |
| 5 to 10 | Pass | Specific audience, an asset the CFO owns, a provable message, named reach for every channel, a credit rule, a named risk with an owner |

Verdict: Ready with flags. PR reads Not in this campaign, so the sample shows that case.

## How do I try it?

Upload nothing. Paste `sample_strategy.md` into Claude with the skill installed and say: "Pressure test this campaign. I'm the CEO." Swap in your own seat.
