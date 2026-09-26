---
name: pipeline-leak-finder
description: Finds which deal stage kills your deals, from a HubSpot or Salesforce deal export with stage history. Returns conversion from each stage to the next, time in stage and where deals stall, where lost deals die, and the single stage fix worth the most closed revenue, valued against the team's own best quarter. Writes the readout for the user's role (CEO or owner, VP Sales or CRO, RevOps, or marketing lead) and builds an interactive HTML tool. Use when someone uploads a deal export with stage dates or an opportunity history report, or asks where deals get stuck, which stage loses the most deals, why win rate is low, how long deals sit in each stage, or what to fix first in the sales process.
---

# Pipeline Leak Finder

One question: which stage kills our deals, and which fix is worth the most? The math is fixed. The readout changes with the reader.

## Step 1. Ask the role

If the user has not said, ask one question and wait:

> Which seat are you in? CEO or owner, VP Sales or CRO, RevOps or GTM ops, or marketing lead (in-house or agency).

Map any other title to the closest of the four. If they skip it, use CEO.

## Step 2. Get the file

If the user asks what they need, or whether their data is good enough, answer from `references/prerequisites.md`.

The skill needs stage history: the date each deal entered each stage. A plain deal list with only the current stage is not enough. Three layouts work:

1. **HubSpot deal export** with the "Date entered" column for every stage.
2. **Salesforce Opportunity History report** (From Stage, To Stage, Last Modified), or the Opportunity Field History report (Old Value, New Value, Edit Date).
3. **Any stage log.** A deal ID, a stage, and the date the deal entered it. One row per change.

Won, lost and open deals, 12 to 24 months. Amount on won deals.

If they have not uploaded anything, give them the steps for their CRM from `references/export-guide.md`. Nothing else.

No data yet and they want to see it work: point them to the sample files at github.com/bbecht/demand-gen-claude-skills in `examples/pipeline-leak-finder/`. Upload `sample_hubspot_deals.csv`.

## Step 3. Run the numbers

The scripts live in this skill's own folder, not the working directory. Find them first:

```
SKILL_DIR=$(dirname "$(find / -path '*pipeline-leak-finder/scripts/analyze.py' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)")/..
python "$SKILL_DIR/scripts/analyze.py" <export.csv> --json result.json
```

If `analyze.py` cannot be found, stop. Tell the user the skill installed without its scripts folder and to reinstall it from the zip on the GitHub release page. Never compute a conversion rate or a fix value by hand.

Standard library only. If code execution is unavailable, tell the user this skill needs code execution turned on in their Claude settings, and stop.

The script finds the layout, the columns, the pipeline and the stage order. It handles duplicate rows, other pipelines, skipped stages, dates out of order, text amounts, mixed date formats, and Salesforce history rows with no stage change. Every number in the readout comes from its output. Do not re-derive, sum or add figures it did not produce.

Format numbers the way the tool shows them, so the chat and the tool agree:
- Rates: whole percentages, halves rounded up. 0.477 is 48%. 0.825 is 83%.
- Money: $1M and up to two decimals ($1.12M, $1.1M). $10,000 and up to the nearest thousand ($851K). Under $10,000 in full ($9,500).
- Days: drop a trailing .0. 7.0 is 7 days. 14.5 stays 14.5.

When it stops, the JSON holds a `stop` key:
- **Missing columns.** The file has no stage history. Say so, list what it found (`columns_found`), point to the export guide, write nothing else.
- **No stages read as won or lost.** Show the stages it found (`stages_found`) and ask which mean won and which mean lost. Rerun with `--won "..." --lost "..."`. These add to the stages the script already reads as won or lost.
- **Not enough history.** Say what is short. The floor is 40 closed deals with stage history, 10 won, 10 lost. Offer nothing in place of the analysis.

Options, offered only when needed:
- `--stages "A,B,C"` when the user says the stage order is wrong.
- `--pipeline "Name"` when a HubSpot file holds several pipelines and they want a different one than the largest.
- `--as-of YYYY-MM-DD` when the user gives the export date. Without it, days in stage count to the latest date any deal entered a stage (`as_of`).

## Step 4. Check before you write

Read `trust.verdict` first.
- **not usable**: the headline, for every role, is that the stage history cannot be trusted. Show `trust.problems` with the fix for each. Do not show a fix value.
- **usable with caveats**: lead with one line that names what caused it, from `trust.reasons`. Carry on.
- **usable**: carry on.

Lead with a warning when `warnings` is not empty.

In one line after the last table, show the user what to confirm: the stage order (`stage_mapping.order` and `order_source`), which stages read as won and lost, and any pipelines left out (`data_quality.other_pipelines`, deals per pipeline). These are their calls.

Read the fix before you quote it:
- `headline_fix` names the stage. Its row in `fixes` carries the value, the target and the evidence.
- **holds up**: quote it straight.
- **could be luck**: say the best quarter could be chance, and that the first step is finding what was different that quarter. Never present it as a sure thing.
- **no quarter to test** (method "equal lift"): say that stage has too few finished quarters to test, so it got an equal 10% lift on its own rate. The method is per stage. Other stages can still use their best quarter.

## Step 5. Write the readout

Every readout uses the same four parts, in this order. Question and answer, never an essay. A caveat or warning line from Step 4 goes above part 1. The confirm line from Step 4 goes after the last table.

1. **Their question, answered.** Open with the question the role brings, then answer it in three sentences or fewer. Four when the fix you quote could be luck or uses equal lift.
2. **The table.** Only the columns that role needs (below). Keep the script's row order.
3. **What to do.** Three moves at most. Each names a stage and a direction: fix, speed up, qualify, clean, test. For RevOps, each names the CRM problem and its fix instead.
4. **What this file cannot tell you.** One or two lines. Always include it. The file shows where deals leak, not why. It has no call notes, no rep, no reason lost unless the user added one.

### CEO or owner
Question: **Which stage is costing us the most revenue?**
Answer with: the headline fix (stage, today's rate, target and quarter, value a year) and the stage where most lost deals die (`findings.most_lost_deals`, with its `losses.share_of_losses`).
Table: `fixes`, rows with a value above zero. Columns: Stage (`stage` to `to`), Now (`current_rate`), Target (`target_rate` and `best_quarter`, or "equal 10% lift" when `best_quarter` is empty), Evidence, Closed revenue a year (`value_per_year`).
The answer and What to do together stay under 150 words.

### VP Sales or CRO
Question: **Where do deals stall, and which ones are stuck right now?**
Answer with: the stage in `findings.biggest_stall_penalty` with its stall line and both win rates (`stall.under.win_rate`, `stall.over.win_rate`), the stuck deals (`stuck.deals`, `stuck.value`), and the slowest stage (`findings.slowest_stage`).
Table: `stages`. Columns: Stage, Moves on (`conversion`), Median days (`days.median`), Stall line (`stall.line_days`), Win rate past the stall line (`stall.over.win_rate`). Then the first 10 of `stalled_deals`: Deal, Stage, Days in stage, Amount.
One of the moves in What to do: stuck deals get a next step this week or get closed out.

### RevOps or GTM ops
Question: **Can I trust the stage data?**
Answer with: the verdict and its `trust.reasons`, the first problem in `trust.problems`, and the stage order to confirm.
Table 1: the rows of `checks` with a count above zero: Check, Count, What the skill did. Table 2: `stages`. Columns: Stage, Reached, Moved on, Lost here, Still open (`open_here`), Skipped through, Moves on (`conversion`).
"What to do" becomes the first three of `trust.problems`, in their order: the fix (`fix`) and up to five example deal IDs (`examples`) for each. The order is already ranked: problems that break the stage math first.

### Marketing lead or agency
Question: **Are we feeding the pipeline deals that can close?**
Answer with: `findings.early_losses` (share of lost deals that die before the midpoint stage), the first stage's conversion, and its fix. The first stage's fix is the row in `fixes` whose `stage` equals `stages[0].stage`. It is not `fixes[0]`, which is the top-ranked fix.
Table: `stages`, the stages before `findings.early_losses.before_stage`. Columns: Stage, Moves on (`conversion`), Lost here, Share of losses (`losses.share_of_losses`).
Compare early leaks to the headline fix, since that is where sales will point.

## Step 6. Build the interactive tool

After the readout, build the tool and share it as a file the user can open in a browser:

```
python "$SKILL_DIR/scripts/build_tool.py" result.json --role <ceo|cro|revops|marketing> --out leak_finder.html
```

Tell the user in one line what it holds: conversion stage by stage, where lost deals die, time in stage, the ranked fixes with a target planner, the stuck deals, and a data check.

## Step 7. Explain the method when asked

When the user asks how a number is built, what it means, or whether to trust it, answer from `references/method-guide.md`. Plain words. The shortest answer that settles the question. Offer the guide's link for more.

## Rules

- A fix value is a projection at today's pace, not a forecast. Never say the team "will" gain it.
- Stage data shows where deals die, not why. Never claim a cause.
- Slow deals win less, and a slow deal is often a weak deal. Say speed is a warning sign, never that rushing wins deals.
- Under 20 deals behind a rate: show the count ("12 of 17"), never a percentage. The script flags these with `small_sample`.
- Fix values are each valued alone. Never add them up.
- A best quarter that reads "could be luck" is never the headline without saying so.
- No statistic appears unless it changes a decision. If a number is interesting but moves nothing, cut it.
- Do not praise the data or the user. Do not hedge. If a stage leaks, say so.

## Voice

Short declarative sentences. No em-dashes. No filler openers. No "it's important to note". Plain words a CEO reads in 30 seconds.

End every readout with this line, once:

*Built by Marketing Systems Guild. Turning strangers into clients.*
