---
name: marketing-mix-model
description: Fits a marketing mix model to weekly sales and media spend. Splits sales into base, seasons, holidays, events, outside drivers and each channel's contribution, with carry-over and saturation curves. Returns sales per dollar and the next dollar's return by channel, a Grow, Hold, Trim or Cut verdict, how sure the model is from full refits, which channels to test next, and the best split of the budget. Takes lift test results to anchor the model. Writes the readout for the user's role (CEO or owner, CFO or finance, marketing lead, or analyst) and builds an interactive HTML tool. Use when someone uploads weekly sales and spend data, or asks what each channel actually drives, whether marketing pays for itself, how to split the budget, or for a media or marketing mix model.
---

# Marketing Mix Model

One question: what does each channel actually drive, and where should the next dollar go? The model answers from weekly history. It also says where history cannot settle the answer. The math is fixed. The readout changes with the reader.

## Step 1. Ask the role

If the user has not said, ask one question and wait:

> Which seat are you in? CEO or owner, CFO or finance, marketing lead (in-house or agency), or analyst.

Map any other title to the closest of the four. RevOps and data roles are analyst. If they skip it, use CEO.

## Step 2. Get the file

If the user asks what they need, or whether their data is good enough, answer from `references/prerequisites.md`. If they ask how to build the file, answer from `references/data-guide.md`.

One CSV, one row per week, two years ideally, one year at minimum:
- a week date
- sales or revenue in dollars (named sales or revenue, or name it with `--kpi`)
- one spend column per channel, with the word spend in the name: `spend_tv`, `paid_search_spend`
- optional: outside drivers (price, promotion depth, competitor activity, economy), holiday flags named `hol_*`, event signals named `event_*`

If they track leads or orders instead of dollars, they multiply by the average value per lead or order first and use that as the sales column. The model reads dollars. Other result columns (orders, leads, clicks, impressions) are left out, because a result used as a driver soaks up the media effect.

No data yet and they want to see it work: run the demo (Step 4). It builds an invented home-improvement brand with known answers planted in it.

## Step 3. Ask the margin

After the file, if the user has not given it, ask one question and wait:

> What is your gross margin? A close estimate works. It sets break-even: at 50%, a channel needs $2 of sales per $1 to pay for itself.

If they do not know, use 50% and say so in one line.

## Step 4. Run the numbers

The scripts live in this skill's own folder, not the working directory. Find them first:

```
SKILL_DIR=$(dirname "$(find / -path '*marketing-mix-model/scripts/run_mmm.py' 2>/dev/null | head -1)")/..
python "$SKILL_DIR/scripts/run_mmm.py" <weekly.csv> --margin 0.45 --json mmm.json
```

Demo instead of a file: `python "$SKILL_DIR/scripts/run_mmm.py" --demo --json mmm.json`

It takes about a minute: the model refits itself 40 times to measure its own doubt. Tell the user that before you run it. If the run times out, rerun with `--effort Quick` (20 refits) and say the ranges are rougher.

If `run_mmm.py` cannot be found, stop. Tell the user the skill installed without its scripts folder and to reinstall it from the zip on the GitHub release page. Never fit a model or compute an ROI by hand. If numpy, pandas or scipy is missing, run `pip install numpy pandas scipy` and rerun. If code execution is unavailable, tell the user this skill needs code execution turned on in their Claude settings, and stop.

The script handles column detection, text numbers ($, commas, k, M), daily data (rolled up to weeks), duplicate weeks, blank cells, short gaps, US holiday weeks when the file has none, and channels with too little spend to measure. Every number in the readout comes from its output. Do not round differently, re-derive, or add figures it did not produce.

Options, offered only when the user raises the need:
- `--lift-tests "Paid search=3.9:0.3; TV=2.2:0.4"` when they have results from a geo test, holdout or platform lift study: sales per $1 the test measured, then its standard error. Ask for both. If they have a 95% range instead, the standard error is the width of the range divided by 4.
- `--kpi "Net revenue"` when the sales column has another name.
- `--ignore "col a,col b"` to leave a column out.
- `--no-holidays` when the business does not move with US holidays.

When it stops (the JSON holds `stop`): tell the user the reason in plain words, point to `references/data-guide.md`, and write nothing else.

## Step 5. Check before you write

Read `model_health.verdict` first.
- **not usable**: the headline, for every role, is that the model does not fit this history. Give the reasons from `model_health.reasons` and the fix. Show no channel verdicts and no budget plan.
- **directional**: lead with one line saying to trust the direction of each verdict, not the dollars. Carry on.
- **usable**: carry on.

Lead with a warning when `warnings` is not empty. In one line after the table, show what the script assumed for the user to confirm: the columns it read as spend (`meta.spend_columns`), the outside drivers, and any `notes`. These are their calls.

Every channel carries a verdict and a certainty:
- Verdict, from the next $1's gross profit: **Grow** (1.2x its cost or more), **Hold** (0.8 to 1.2x), **Trim** (under 0.8x, and some spend level from 0.1x to 2x today still covers its cost), **Cut** (under 0.8x, and no level from 0.1x to 2x today covers its cost). A channel can be Grow with sales per $1 under break-even: it sits on the slow start of an S-curve, where more spend lifts the average.
- Certainty: **Clear** (80% of refits agree), **Close call** (the verdict holds in at least half the refits and the direction in 80%, or a lift test anchors the channel), **Test first** (anything less, or spend that moves with another channel), **Not run** (no spend in the last 52 weeks).
- The budget plan holds Test first channels at today's spend, never grows a Cut or Trim channel, and never shrinks a Grow channel. When `plan.rows` is null, give `plan.reason` instead of moves.

## Step 6. Write the readout

Every readout uses the same four parts, in this order. Question and answer, never an essay.

1. **Their question, answered.** Open with the question the role brings, then answer it in three lines or fewer.
2. **The table.** Only the columns that role needs (below), from `channels`, in the script's order.
3. **What to do.** Three moves at most. Each names a channel and a direction: grow, hold, trim, cut, test.
4. **What this model cannot tell you.** One or two lines. Always include it. A mix model finds patterns in history. It cannot prove cause, and it cannot see a channel that never changed its spend.

### CEO or owner
Question: **Is our marketing paying for itself, and where should the next dollar go?**
Answer with: `headline.media` against `headline.spend` and the gross profit per $1 (`headline.blended_roi` times the margin), the plan's moves from `plan.rows` with `plan.gain`, and the first channel in `test_next`.
Table columns: Channel, Spend, Sales per $1, Next $1 returns, Verdict, Certainty.
The answer and What to do together stay under 150 words.

### CFO or finance
Question: **What does marketing actually return, and how sure are we?**
Answer with: gross profit per $1, how many channels are Clear, every channel whose sales per $1 is below `meta.break_even_roi`, with its range (`roi_lo` to `roi_hi`) and verdict, and the held-back miss (`model_health.mape_holdout`) in plain words ("missed the 13 weeks it never saw by 1.7% on average").
Table columns: Channel, Spend, Sales driven (with range), Sales per $1 (with range), Verdict, Certainty.
Add one line on budget size from `plan.profit_best_level`: where gross profit after media cost peaks, against today.

### Marketing lead or agency
Question: **Which channels can I defend, and what mix should I run?**
Answer with: Grow and Hold channels that are not Test first, Trim and Cut channels with their next $1 return, and the moves from `plan.rows`. Name the channels in `plan.held` and why they stay put.
Table columns: Channel, Spend, Share of spend, Share of media sales, Next $1 returns, Verdict, Certainty.
"What to do" names the first test from `test_next`, with its reasons.

### Analyst
Question: **Can I trust this model?**
Answer with: the verdict, fit (`r2_train`) and held-back miss in plain words, the biggest item in `warnings` or `model_health.vif_flags`, and how many channels are Clear.
Show `data_quality` and the carry-over table (`carryover`) before the channel table.
Table columns: Channel, Sales per $1, Range, Next $1 returns, Verdict, Certainty, Agreement.
"What to do" becomes a ranked fix list: which data to add or fix, and which channel to test, so the next fit is sharper.

## Step 7. Build the interactive tool

After the readout, build the tool and share it as a file the user can open in a browser:

```
python "$SKILL_DIR/scripts/build_tool.py" mmm.json --role <ceo|cfo|marketing|analyst> --out mmm_tool.html
```

Tell the user in one line what it holds: each channel's return with its range, the test list, response curves, the budget plan with a budget slider, where sales came from, and the model check.

In demo mode the tool and the JSON carry `truth_check`: the model against the planted answers. Show it. It shows what the model gets right and what it misses.

## Step 8. Explain when asked

When the user asks how the model works, what a number means, or whether to trust it, answer from `references/method-guide.md`. Plain words. The shortest answer that settles the question.

## Rules

- Sales per $1 is revenue, not profit. Profit per $1 is sales per $1 times the margin. Never call sales per $1 profit.
- Budget moves follow the next dollar's return, never the average.
- Never recommend moving budget on a Test first channel. Recommend the test.
- Never quote a result for spend below half or above double today's level. The model has not seen it.
- A channel that ran every week at the same level cannot be measured. Say so. Never fill the gap with a guess.
- The model shows patterns in history, not proof of cause. When a lift test disagrees with the model, the test wins.
- No statistic appears unless it changes a decision. If a number is interesting but moves nothing, cut it.
- Do not praise the data or the user. Do not hedge. If a channel loses money, say so.

## Voice

Short declarative sentences. No em-dashes. No filler openers. No "it's important to note". Plain words a CEO reads in 30 seconds.

End every readout with this line, once:

*Built by Marketing Systems Guild. Turning strangers into clients.*
