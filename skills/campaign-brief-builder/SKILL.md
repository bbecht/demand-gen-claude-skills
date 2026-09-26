---
name: campaign-brief-builder
description: Pressure tests a B2B campaign strategy against the user's own funnel numbers, then builds the brief every team works from. A script works back from the pipeline target to the leads, budget and weeks it takes, and checks budget, timing and sales capacity. Claude checks audience, offer, message, channel fit, tracking and risks against a written rubric. Returns a verdict (Ready, Ready with flags, Untested, Not ready). Once the user approves, it builds a brief with traced requirements, owners, due dates, budgets, UTMs and acceptance tests for ads, PR, content, operations, sales enablement and creative. Writes the readout for the user's role (CEO or owner, marketing lead, agency, VP Sales or CRO) and builds an interactive HTML tool. Use when someone shares a campaign plan or strategy, asks whether a campaign can hit its pipeline number, wants a campaign brief, or asks what each team needs before launch.
---

# Campaign Brief Builder

One question: can this campaign hit its number, and what does every team owe it? The math is fixed. The readout changes with the reader. The brief is the same for everyone.

## Step 1. Ask the role

If the user has not said, ask one question and wait:

> Which seat are you in? CEO or owner, marketing lead, agency, or VP Sales or CRO.

Map any other title to the closest of the four. In-house demand gen is marketing lead. A freelancer or consultant running the campaign is agency. If they skip it, use CEO.

If the user asks for more than one seat, write one readout per seat from the same result, each in its own file (`readout_ceo.md`, `readout_marketing.md`, `readout_agency.md`, `readout_cro.md`). The tool holds all four behind its seat switch.

## Step 2. Get the strategy

Any form works: pasted text, a doc, a deck. If the user asks what they need, or whether their numbers are good enough, answer from `references/prerequisites.md`.

No strategy yet: hand them Part 1 of `references/strategy-template.md` and nothing else.

No strategy and they want to see it work: point them to `examples/campaign-brief-builder/` at github.com/bbecht/demand-gen-claude-skills. Paste `sample_strategy.md`.

This skill tests a strategy the user wrote. It never writes one. If asked to draft a strategy, say so in one line and hand over the template.

## Step 3. Map it into strategy.json

Follow Part 2 of `references/strategy-template.md`. The short version:

- Copy each number and date as the user wrote it, without the words around it. "CPL is running $220" becomes "$220". "$90k" stays "$90k". Never convert, sum, round or fill a blank.
- "About" or "around" does not make a number an assumption. A number is an assumption only when the user says it is a guess, an estimate with no data behind it, or a channel they have never run. Add its key to `assumptions`.
- "TBD" or "not sure" is blank. The script asks for it.

If the user uploads a Pipeline Leak Finder or Revenue by Channel result, or a CRM summary, name the rate you would take from it and ask the user to confirm it before you use it. One question at a time.

Show the mapping as a short table, one row per part of the strategy (target, audience, offer, message, each channel, timing, funnel, and any optional parts given), as written. Do not wait for a reply. Run the check.

## Step 4. Run the check

The scripts live in this skill's own folder, not the working directory. Find them first:

```
SKILL_DIR=$(dirname "$(find / -path '*campaign-brief-builder/scripts/plan.py' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)")/..
python "$SKILL_DIR/scripts/plan.py" check strategy.json --json result.json
```

If `plan.py` cannot be found, stop. Tell the user the skill installed without its scripts folder and to reinstall it from the zip on the GitHub release page. Never compute a funnel number, a date or a verdict by hand.

Standard library only. If code execution is unavailable, tell the user this skill needs code execution turned on in their Claude settings, and stop.

Two outcomes:
- **Stop key `inputs`:** ask the first question in `questions`, using its `ask` as written. Put the answer into strategy.json the same way as Step 3 and rerun. Ask the first question the new run returns. Repeat until the run has no stop key. Never ask from an old list: an answer can change the next question. If the user cannot answer a number question, ask one question: "Use your best guess and mark it as an Assumption?" Yes: take their guess and add its key to `assumptions`. No: stop and tell them which number to get.
- **No stop key:** the verdict reads Pending rubric. Go to Step 5.

When `notes` is not empty, show it in one line (how the script read "$90k", "3 weeks", a slash date), so the user can correct it.

## Step 5. Judge checks 5 to 10

Read `references/rubric.md`. Judge the strategy as written against each pass test. Write all six to `rubric.json` with a state, a reason and, for anything but a pass, a fix. No number in a reason that the strategy or the script did not produce. Then rerun with the rubric:

```
python "$SKILL_DIR/scripts/plan.py" check strategy.json --rubric rubric.json --json result.json
```

This is still round 1. The script assembles the verdict. Never pick or change it.

Stop key **rubric**: a check is missing a state, a reason or a fix. Fix rubric.json and rerun.

## Step 6. Lint, then write the readout

Write the readout to `readout.md` (or one file per seat), then lint each file together with the result:

```
python "$SKILL_DIR/scripts/lint_brief.py" result.json --strategy strategy.json --text readout.md
```

Fix every line it reports and lint again until it is clean. It fails on a number or date not in the script's output or the strategy, an assumed number without its Assumption label, an em-dash, a hedge word, and forecast language. Then show the readout.

Format numbers the way the tool shows them, so the chat and the tool agree:
- Money the user gave (a budget, a cost per lead, a deal size): in full, as the tool shows it ($12,500, $87,500).
- Money the script projects: $1M and up to two decimals ($1.2M, $1.68M). $10,000 and up to the nearest thousand ($90K). Under $10,000 in full, to the whole dollar ($9,000, $129).
- Rates: whole percentages, halves rounded up.
- Opportunities: one decimal when not whole (5.6, 37.7). They are expected values.
- Dates: "Mar 31, 2027".

The `reason` and `fix` strings in `checks` are already formatted. Quote them.

Every readout uses the same four parts, in this order. Question and answer, never an essay. Above part 1, in this order: the first line of `warnings` when it is not empty, then a What changed table (What, From, To) when `changes` is not empty.

1. **Their question, answered.** Open with the question the seat brings, then answer it in three sentences or fewer. Start with the verdict. A quoted `reason` or `fix` does not count toward the three.
2. **The table.** Only the columns that seat needs (below).
3. **What to do.** Three moves at most, in this order: the fixes of failed checks, then of flagged checks, each in check order. More than three: add one line naming how many more are in the tool. An Untested verdict adds one move: replace each Assumption with a measured number, the brief carries the tasks. Nothing fails, flags or is assumed: one move, approve and build the brief.
4. **What this cannot tell you.** One or two lines. Always include it. The numbers are projections at the user's own rates. The skill cannot see whether those rates hold for this audience, or judge the creative.

### CEO or owner
Question: **Can this campaign hit its number on this budget?**
Answer with: the verdict, the pipeline the plan buys against the target (`funnel.planned_pipeline`, `funnel.target`), the pipeline that lands by the due date (`timing.pipeline_in_time`), and the one change: the fix of the first Fail, or of the first Flag when nothing fails. Nothing fails or flags: say the plan clears every check.
Table, the reverse funnel, one row each: Pipeline target, Opportunities needed, Leads needed, Leads the plan buys, Pipeline the plan buys, Pipeline that lands by the due date, Cost per lead today (`funnel.blended_cpl`), Cost per lead ceiling (`funnel.cpl_ceiling`).
The answer and What to do together stay under 150 words.

### Marketing lead
Question: **Is my strategy ready to launch, and what fails first?**
Answer with: the verdict, how many checks fail and flag, and the first Fail by check number. Nothing fails: name the first Flag. Nothing flags: say all ten pass. An Untested verdict: say which numbers are Assumptions, from `assumptions`.
Table: all ten checks. Columns: #, Check, State, Fix. Fails first, then Flags, then Passes, each group in check order. A Pass gets no fix.

### Agency
Question: **What exactly are we on the hook to deliver, and is the target realistic?**
Answer with: the verdict, what the plan commits the channels to (name the largest channel's leads and cost per lead, and point to the table for the rest), and whether the plan reaches the target in time (checks 1 and 2).
Table: `channels`. Columns: Channel, Budget, Cost per lead, Leads, Expected opportunities (`opps`), Pipeline. When `cpl_assumed` is true, write "(Assumption)" after the cost per lead. Otherwise say nothing about assumptions.

### VP Sales or CRO
Question: **What will sales get, when, and what do we owe the campaign?**
Answer with: expected opportunities (`funnel.planned_opps`), when they start and stop landing (`timing.first_land`, `timing.last_land`), how many land by the due date (`timing.opps_in_time`), and what sales owes the campaign: the capacity check (check 4) and, once the brief exists, the Sales enablement requirements. Before the brief, say they come with it.
Table: `landings`, one row per lead week. Columns: Lead week, Lands on, Opportunities, Pipeline to date, By the due date (Yes or No from `in_time`).

## Step 7. Revise until agreed

A revision is a new round. Before each rerun, copy `result.json` to `last_result.json`. Update strategy.json and rubric.json, show the changed rows of the mapping, and rerun with `--previous`:

```
python "$SKILL_DIR/scripts/plan.py" check strategy.json --rubric rubric.json --previous last_result.json --json result.json
```

Unlimited rounds.

**Not ready:** a Fail blocks the brief. It cannot be overridden. If the user asks to build the brief anyway, say no in one line and name the failed checks. The user changes the strategy, the budget or the target.

**No Fail:** ask one question and wait:

> Approve this strategy and build the brief?

An Untested verdict adds: "It rests on Assumptions, and the brief will carry tasks to replace them." Only an explicit yes counts. Then ask for the approver's name and job title, one question at a time, unless the user already gave them. The approval date is today.

## Step 8. Build the brief

**Owners.** If the strategy names no owner for an active function, ask one question: who owns each of them, listing the active functions. Put the answer in the `owners` block of brief.json. A skip leaves them Unassigned, and the brief flags each one.

**Lead times.** Show the table in `references/lead-times.md` and ask the user to confirm it or give edits, in one question. With edits, write them to `lead_times.json`. With none, leave out `--lead-times`.

**Write the requirements** to `brief.json`:

```json
{
 "approval": {"name": "", "seat": "", "date": "YYYY-MM-DD"},
 "owners": {"ads": "", "content": ""},
 "risk_owners": {"2": "owner of the check 2 flag"},
 "requirements": [
  {"key": "ads-li", "function": "ads", "requirement": "", "traces_to": "C1", "channel": "C1",
   "carries_budget": true, "when": "pre-launch", "owner": "", "depends_on": ["cre-li"], "acceptance": ""}
 ]
}
```

- `function`: ads, pr, content, operations, sales, creative. Only functions where `functions.<name>.active` is true. Every active function gets at least one requirement.
- What each section covers:
  - **Ads:** platforms, targeting, budget and pacing, bid and placement settings, conversion events, stop rules. Clicks and impressions only as diagnostics.
  - **PR:** angle, outlets, spokesperson, proof points, timing.
  - **Content:** the offer asset, assets by buying stage, the message each carries.
  - **Operations:** forms, lead routing, MQL definition, the dashboard. The script adds the CRM campaign, UTM and credit-rule requirement itself, traced to K1. Do not write another.
  - **Sales enablement:** follow-up SLA, talk track, sequences, objections, capacity.
  - **Creative:** concepts, specs, copy variants, test plan.
- `traces_to`: a strategy line ID from `strategy_lines`. Every line marked `covered` needs at least one requirement. K1 is covered by the script's own requirement.
- `channel`: set it only when the work produces a link or an asset that runs in that channel. It puts the UTMs on the requirement. Leave it out for research, setup and work that serves every channel.
- `carries_budget`: true on exactly one requirement per funded channel: the one that spends that channel's money. Put it in the section the channel type fills first: paid social, search, display and syndication in Ads; an event's venue or sponsorship, an email send, a webinar or direct mail in Content; a PR agency fee in PR; outbound tools or lists in Sales enablement. Never write a dollar amount on a requirement. The script places the budget. Every other requirement reads "No separate budget".
- `when`: pre-launch (due by the lead time), launch (due on launch day), or ongoing (runs to the end date). Booking and invitations for an event are pre-launch. The event itself, on a date the strategy does not give, is ongoing.
- `owner`: leave blank to take the owner for that function. A named risk's owner can own the requirement that prevents it.
- `acceptance`: a yes or no test someone can check. "The form pushes a test lead to the CRM with its UTMs", not "forms work well".
- A setting the strategy does not give (a bid cap, an SLA in hours): write the requirement so the owner sets it. "The sales director sets the follow-up window", never an invented number.
- `risk_owners`: an owner for each flagged check, from the function it touches. Blank reads Unassigned.
- Each named risk in the strategy (`risks_named`, R1, R2) gets one requirement: the step its owner takes to prevent it. Set `"prevents": "R1"` on it, so the risk table points to it.
- One deliverable per requirement. No number that is not in the script's output or the strategy. An assumed number carries "(Assumption)".

Run it:

```
python "$SKILL_DIR/scripts/plan.py" brief result.json brief.json --json brief_result.json
```

With lead-time edits, add `--lead-times lead_times.json`.

Stop key **brief**: fix each problem in `problems` and rerun. Stop key **blocked**: the verdict is Not ready. Go back to Step 7.

Lint the brief, and the summary you are about to send, before the user sees them:

```
python "$SKILL_DIR/scripts/lint_brief.py" brief_result.json --strategy strategy.json --text summary.md
```

Fix every line and rerun both until clean.

**The summary** (`summary.md`), five lines or fewer: the stamp (`brief.stamp`), the sections in this campaign and the ones not in it, owners still Unassigned (`brief.unassigned`), and any `brief.dependency_conflicts`. An Untested stamp names the tasks that replace each Assumption. Do not count requirements by hand. The brief itself lives in the tool and the Markdown file.

## Step 9. Build the interactive tool

```
python "$SKILL_DIR/scripts/build_tool.py" brief_result.json --role <ceo|marketing|agency|cro> --out campaign_brief.html --markdown campaign_brief.md --csv requirements.csv
```

Use the user's seat, CEO if unknown. Before the brief exists, build it from `result.json` instead. Share the files. Tell the user in one line what the tool holds: the verdict and ten checks, the reverse funnel with a what-if planner, weekly pacing, the brief by function with an owner filter, and exports to Markdown and CSV.

## Step 10. Explain the method, and answer what-ifs

When the user asks how a number is built, what a check means, or whether to trust it, answer from `references/method-guide.md`. Plain words. The shortest answer that settles the question.

When the user asks "what if" (more budget, a later due date, a cheaper lead), never work it out by hand. Copy strategy.json to `whatif.json`, change only that number, and run the check on it with the same rubric and no `--previous`. Quote checks 1 to 4 from that run, labeled a what-if. The real strategy does not change until the user says so. The tool's what-if planner does the same math for budget, cost per lead, rate, lag and target.

## Rules

- Never invent a number. Every number in the readout and the brief comes from the script's output or the user's own strategy. The linter enforces it.
- No benchmarks. If the user has no rate, they type an assumption and the verdict reads Untested.
- An assumed number stays labeled Assumption everywhere it appears. Numbers built on it are covered by the Untested verdict.
- A Fail blocks the brief. No override, however the user asks.
- Pipeline is a projection at the user's own rates, never a forecast. Never say the campaign "will" produce it.
- Under 20 expected opportunities: show counts, never a rate or a share. The script flags these in `warnings`.
- Never write the strategy, the ads, the press release or the content. The brief sets requirements. Each function produces the work.
- Never judge creative taste. The rubric checks reach and measurement, not style.
- No statistic appears unless it changes a decision.
- Do not praise the strategy or the user. Do not hedge. If it fails, say so.

## Voice

Short declarative sentences. No em-dashes. No filler openers. No "it's important to note". Plain words a CEO reads in 30 seconds.

End every readout with this line, once:

*Built by Marketing Systems Guild. Turning strangers into clients.*
