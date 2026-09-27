# The idea template

Part 1 is the blank template to hand a user who is starting from zero. Part 2 is how Claude maps any idea, in any form, into `idea.json` for the script.

## Part 1. The blank template

Copy this, fill it in, and paste it back. Seven parts are required.

```
THE IDEA (one sentence, one change):

1. THE ONE METRIC IT SHOULD MOVE:
   Is it a rate (a share of people who act, such as form conversion)
   or a count (things per week, such as demos booked)?

2. TODAY'S BASELINE (last 90 days):

3. VOLUME IN 30 DAYS (rates only): how many people will the test see?

4. DESIGN: can you split the audience, with a control group that does not
   see the change? If not, it is before and after, and you need the metric
   for each of the last 12 weeks.

5. BUDGET FOR THE TEST:

6. THE LIFT YOU EXPECT (for example 20%):

7. LAUNCH DATE:

WHAT HAPPENS ON EACH VERDICT (agreed now, locked on the card)
   On Scale, what gets funded and by how much:
   On Kill, where the budget goes:
   On Extend, how many more days (up to 30) and how much more budget:
   On Stop early, who shuts it off:

OPTIONAL
   Value of one unit of the metric (one demo, one lead), to tie the test to money
   Share of the audience in the test (default half)
   Owners
```

## Part 2. Mapping into idea.json

Claude writes this file. Rules:

- **Copy each number and date as the user wrote it. Keep a qualifier such as "about" and drop the rest of the sentence.** "Our form converts at about 3.1%" becomes "about 3.1%". The script parses it and notes how it read it. Claude never converts, sums or rounds.
- **Blank stays blank.** "TBD" and "not sure" are blank. The script asks for them.
- **One idea per card.** Three changes at once is three ideas. The rubric fails it.
- **Ask about the split first.** Before mapping before and after, ask once whether a control group is possible, unless the user already said. Recommend it when it is.
- **Test share.** "50/50" or "60/40" (test first) reads as is. Blank reads as half. Say so in the mapping table.
- **Owners are optional.** When the user has not named one, leave it blank and write setup steps without an owner. Never invent a name.
- **Show the user the mapping** before the first run: a short table, one row per part, as written.

```json
{
 "idea": "",
 "metric": {"name": "", "type": "rate", "unit": ""},
 "baseline": "",
 "volume_30d": "",
 "design": "split",
 "test_share": "",
 "budget": "",
 "expected_lift": "",
 "value_per_unit": "",
 "launch": "",
 "extend_days": "",
 "history": [],
 "actions": {"scale": "", "kill": "", "extend": "", "stop": ""},
 "owners": {}
}
```

### Field notes

| Field | Note |
|---|---|
| `metric.type` | `rate` or `count`. A rate is a share of people who act. A count is things per week. Revenue and deal size are not testable in this version: pick the rate or count that drives them |
| `metric.unit` | One of what the metric counts: "demo request", "trial start", "demo". Used in the readout |
| `baseline` | A rate as a percentage ("3.1%"). A count per week ("40 a week"; "170 a month" also reads) |
| `volume_30d` | Rates only. The people the whole test will see in 30 days, both arms together |
| `design` | `split` or `before_after` |
| `test_share` | Split only. The share of the audience that sees the change. Default half |
| `expected_lift` | The lift the user expects, as a percentage. It sets the Too small to read line. It comes from the user, never from Claude |
| `value_per_unit` | Optional. The dollar value of one unit. Without it, the success number is not tied to money |
| `extend_days` | The extra days in the Extend action, 1 to 30. Default 30 |
| `history` | Before and after only. The last 12 weeks, oldest first. Rates: `{"week": "", "conversions": "", "volume": ""}`. Counts: `{"week": "", "count": ""}` |
| `actions` | One sentence each, in the user's words. All four are required before the card is sealed |

## plan.json

After the checks, Claude writes the test plan. Words only. Every number in it comes from the design result or the idea. The linter checks it.

```json
{
 "change": "What the test changes, in one sentence.",
 "who_sees_it": "Who sees the change, and who does not.",
 "split": "How people are assigned: at random by the page tool, by a fixed rule, or before and after.",
 "metric_definition": "Exactly what counts as one unit, and what does not.",
 "counted_in": "The system and report where the metric is counted.",
 "setup": ["One setup step per line, each with who does it."],
 "risks": ["What could spoil the result. For before and after, the first risk is what else changes in those 30 days."]
}
```
