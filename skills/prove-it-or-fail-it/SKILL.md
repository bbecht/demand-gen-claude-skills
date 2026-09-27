---
name: prove-it-or-fail-it
description: Turns a growth idea into a 30-day test with a success number and a kill number, locked before launch, then calls the verdict. The user gives the idea, the one metric it should move, today's baseline, 30 days of volume, the budget and the lift they expect. A script sizes the test, sets the success, kill and day-15 harm lines, checks that 30 days can read the result and that the budget pays back, and seals the numbers and the agreed actions on a test card. Claude checks the idea against a written rubric: one change, the right metric, a clean split, measurable today. At day 15 and day 30 the script reads the results and calls Stop early, Scale, Kill or Extend against the sealed card. Writes the readout for the user's role (CEO or owner, marketing lead, RevOps, agency) and builds an interactive HTML tool. Use when someone wants to test a growth idea, asks how to know whether an idea worked, needs a success or kill line, or brings day-30 test results.
---

# Prove It or Fail It

One question: will this idea work, and how will we know in 30 days? The numbers are locked before launch. The verdict is called against them. Nobody moves the goalposts.

## Step 1. Ask the role

If the user has not said, ask one question and wait:

> Which seat are you in? CEO or owner, marketing lead, RevOps, or agency.

Map any other title to the closest of the four. Growth or demand gen is marketing lead. Marketing ops is RevOps. A freelancer running the test is agency. If they skip it, use CEO. If the user asks for more than one seat, write one readout per seat from the same result, each in its own file.

## Step 2. Design or read?

- **Design:** the user has an idea to test. Go to Step 3.
- **Read:** the user has results and a test card. Go to Step 8.
- Results with no card: say a verdict needs the sealed card from the design, and stop. Offer to design a new test.

If the user asks what they need, answer from `references/prerequisites.md`. No idea written down yet: hand them Part 1 of `references/idea-template.md`.

This skill tests one idea the user brings. It never generates or ranks ideas. If asked to, say so in one line.

## Step 3. Map the idea into idea.json

Follow Part 2 of `references/idea-template.md`. The short version:

- Copy each number and date as the user wrote it. Keep a qualifier such as "about" and drop the rest of the sentence. Never convert, sum, round or fill a blank.
- Before you map a before-and-after test, ask once whether the audience can be split with a control group, unless the user already said. Recommend the split when it is possible.
- Test share: "50/50" reads as is. Blank reads as half. Owners are optional: never invent one.
- The expected lift comes from the user. Never suggest one.
- All four verdict actions are required. Ask for each one the user has not given, one question at a time.

Show the mapping as a short table, one row per part, as written. Do not wait for a reply. Run the design.

## Step 4. Run the design

The scripts live in this skill's own folder, not the working directory. Find them first:

```
SKILL_DIR=$(dirname "$(find / -path '*prove-it-or-fail-it/scripts/verdict.py' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)")/..
python "$SKILL_DIR/scripts/verdict.py" design idea.json --json design.json
```

If `verdict.py` cannot be found, stop. Tell the user the skill installed without its scripts folder and to reinstall it from the zip on the GitHub release page. Never compute a lift, a line, a date or a verdict by hand.

Standard library only. If code execution is unavailable, tell the user this skill needs code execution turned on in their Claude settings, and stop.

- **Stop key `inputs`:** ask the first question in `questions`, using its `ask` as written. Put the answer into idea.json and rerun. Ask the first question the new run returns. Repeat until there is no stop key.
- **No stop key:** the verdict reads Pending rubric, or Too small to read. Go to Step 5 either way. Too small to read still gets the rubric, so the user sees every problem at once.

When `notes` is not empty, show it in one line, so the user can correct how the script read their words.

## Step 5. Judge the four idea checks

Read `references/rubric.md`. Judge the idea as written. Write all four to `rubric.json` with a state, a reason and, for anything but a pass, a fix. Then write the test plan to `plan.json` (the format is at the end of `references/idea-template.md`). Skip the plan when the first run said Too small to read or a check you judged is a Fail: there is no test to plan yet. Rerun:

```
python "$SKILL_DIR/scripts/verdict.py" design idea.json --rubric rubric.json --plan plan.json --json design.json --card card.json
```

Leave out `--plan plan.json` when you skipped the plan.

The script assembles the verdict and seals the card when the verdict is Ready or Ready with flags. Never pick or change the verdict.

| Verdict | What happens |
|---|---|
| Ready | The card is sealed. The test can launch |
| Ready with flags | The card is sealed. Each Flag is a named risk |
| Not ready | A rubric check fails. No card. The user changes the idea and reruns |
| Too small to read | 30 days cannot read the lift the user expects. No card. Quote the three fixes in `too_small.fixes` |

Stop key **rubric**: a check is missing a state, a reason or a fix. Fix rubric.json and rerun.

## Step 6. Lint, then write the design readout

Write the readout to `readout.md`, then lint it:

```
python "$SKILL_DIR/scripts/lint_plan.py" design.json --idea idea.json --text readout.md
```

Fix every line and lint again until clean. It fails on a number or date not in the script's output or the idea, an em-dash, a hedge word and forecast language.

Format numbers the way the tool shows them:
- Lifts: a signed percentage, one decimal when needed (+33%, +9.9%, -32.7%).
- Rates: a percentage, one decimal when needed (3.1%, 4.1%).
- Counts: a number a week (120 a week).
- Money: $1M and up to two decimals. $10,000 and up to the nearest thousand. Under $10,000 in full.
- Dates: "Mar 2, 2027".

The `reason` and `fix` strings in `checks`, and the `too_small.fixes`, are already formatted. Quote them.

**Too small to read or Not ready:** every seat uses the same short form. Part 1 opens with the seat's question, then the verdict, the reason as quoted, and "No card is sealed." Part 2 is a table of every Fail and Flag: Check, State, Fix. Part 3 is the fixes, quoted once. Part 4 as below. The seat tables below are for a sealed card.

Every readout uses the same four parts, in this order. Question and answer, never an essay. The first line of `warnings`, when there is one, goes above part 1.

1. **Their question, answered.** Open with the seat's question, then answer it in three sentences or fewer. Start with the verdict. A quoted reason or fix does not count toward the three.
2. **The table.** Only the columns that seat needs (below).
3. **What to do.** Three moves at most. Fails first, then Flags. Ready: one move, launch on the launch date and read on the card's dates. Too small to read: the three fixes.
4. **What this cannot tell you.** One or two lines. Always include it. The test says whether this idea moved this metric in this period. It cannot say why, or whether the lift lasts.

### CEO or owner
Question: **Is this idea worth 30 days and this budget, and when do I get an answer?**
Answer with: the verdict, the success number as a metric value and a lift (`lines.success`, `lines.success_lift`), what set it (`sizing.driver`: detectable, payback or swing), the kill number, and the day-30 date (`dates.day30`). No value per unit: say the success number is not tied to money.
Table, the card: Baseline, Success number, Kill number, Harm line at day 15, Day-15 check (`dates.checkpoint`), Day-30 verdict (`dates.day30`), Extend ends (`dates.extend_end`), Budget.
The answer and What to do together stay under 150 words.

### Marketing lead
Question: **How do I run it so the answer is clean?**
Answer with: the verdict, the first Fail or else the first Flag, and the design (split and its share, or before and after with the No control label).
Table: all six checks. Columns: Check, State, Fix. Fails first, then Flags, then Passes. A Pass gets no fix.

### RevOps
Question: **Can we measure it, and what do I set up?**
Answer with: the Measurable today check, what counts as one unit and where it is counted (from the plan), and how people are assigned.
Table, the reads: Read, Date, What to pull. Rates: conversions and people, per arm. Counts: the count per arm. Before and after: the test period only; the card holds the history.

### Agency
Question: **What are we testing, and what counts as a win?**
Answer with: the change, the success number, the kill number and the budget.
Table, the plan by arm: Arm, Share, Expected people or units (`planned`), Win at (`lines.success`), Kill at (`lines.kill`).

## Step 7. Build the design tool

```
python "$SKILL_DIR/scripts/build_tool.py" design.json --role <ceo|marketing|revops|agency> --out prove_it.html --markdown test_plan.md
```

Share the tool and the plan. When the card is sealed, share `card.json` too and tell the user in one line: keep the card file. Every read needs it, and any edit to it voids the verdict. No card: say the tool shows the numbers at these inputs, not locked.

### Follow-ups after the design

- **"Run it anyway."** They can launch. There is no card, so there is no verdict. Say so in one line and quote the fixes.
- **"What if we doubled traffic, ran longer, or split 70/30?"** Ask for the new number in the user's words. If the extra volume costs money, ask whether it comes out of the test budget and for the new budget. Copy idea.json to `idea_whatif.json`, change only those fields and rerun the design with `--json design_whatif.json`. Never work out the effect by hand, and never overwrite the original files. The volume planner in the tool shows the what-if for them to explore.

## Step 8. Read the results

The user brings the card and the results. Map the results into `results_day<N>.json`, where N is the read day. Name every read file by its day so the design files are never overwritten: `read_day30.json`, `readout_day30_<seat>.md`, `prove_it_day30.html`, `test_plan_day30.md`. One readout file per seat.

```json
{"day": 30, "test": {"conversions": "", "volume": ""}, "control": {"conversions": "", "volume": ""}}
```

Counts use `{"count": ""}` for each arm. Before and after has no control: the card holds the history. Copy the numbers as the user wrote them, without the words around them.

```
python "$SKILL_DIR/scripts/verdict.py" read card.json results_day30.json --json read_day30.json
```

After an Extend, the final read also needs the day-30 read that called it: add `--previous read_day30.json`.

- **Stop key `seal`:** the card was edited. Quote the problem as written. No verdict is possible. Offer to design a new test.
- **Stop key `results`:** ask for what is missing, one question at a time.

Then write the readout and lint it, same format as Step 6:

```
python "$SKILL_DIR/scripts/lint_plan.py" read_day30.json --text readout_day30_<seat>.md
```

For every seat:

- The seat questions for a read: CEO or owner, **Did it work, and what do we do now?** Marketing lead, **What does the result say, and what runs next?** RevOps, **Is the result clean enough to trust?** Agency, **Did we win?**
- Part 1 answers the seat's question with the verdict, the `reason` as written, and the agreed `action` as written. RevOps also says whether the seal is intact and whether any arm is under 20 units. A Kill after an Extend quotes `detail`: unproven, not disproven.
- The table: Line, Lift, Value. Success number, the kill number at day 30 only, the harm line at day 15 only, the result (the lift, with `observed.test_value` against `observed.control_value`), and the range. The lift decides the verdict. Quote `compare` when the test value sits under the success value, and `rule` on any Kill. Counts are shown a week for the whole audience, so they can be read against the baseline. RevOps also gets the raw counts per arm, as the user gave them, so they match the CRM.
- What to do: the agreed action, first. Extend: the final read date (`dates.extend_end`). Keep running: the day-30 date.
- Before and after: the No control label and the first risk go above part 1.

Build the tool from the read. It plots the result against the locked lines:

```
python "$SKILL_DIR/scripts/build_tool.py" read_day30.json --role <seat> --out prove_it_day30.html --markdown test_plan_day30.md
```

## Step 9. Explain the method when asked

When the user asks how a number is built, what a verdict means, or whether to trust it, answer from `references/method-guide.md`. Plain words. The shortest answer that settles the question.

## Rules

- Never invent a number. Every number comes from the script's output or the user's own words. The linter enforces it.
- The expected lift comes from the user. Never suggest one.
- No benchmarks. Every baseline is the user's.
- The numbers and actions cannot change after launch. No card, no verdict. An edited card, no verdict.
- One standard, 95% sure, for every test.
- A verdict is about this test, in this period. Never say the idea "will" keep producing the lift.
- Under 20 units in an arm: show counts, never a rate. The script flags this in `warnings`.
- A slow start never stops a test. Only harm does.
- No statistic appears unless it changes a decision.
- Do not praise the idea or the user. Do not hedge. If it fails, say so.

## Voice

Short declarative sentences. No em-dashes. No filler openers. Plain words a CEO reads in 30 seconds.

End every readout with this line, once:

*Built by Marketing Systems Guild. Turning strangers into clients.*
