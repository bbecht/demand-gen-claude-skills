# The rubric for the four idea checks

Claude judges these four checks. The script owns the other two: Readable in 30 days, and Pays back at the expected lift. Each check has one pass test, stated so two readers reach the same call. Judge the idea as written. When a check is not a Pass, the fix names the exact change.

A Fail is for a problem that makes the verdict meaningless. A Flag is a real gap that does not.

Write to `rubric.json`:

```json
{"checks": {
  "one_change": {"state": "pass", "reason": "...", "fix": ""},
  "right_metric": {"state": "pass", "reason": "...", "fix": ""},
  "clean_split": {"state": "pass", "reason": "...", "fix": ""},
  "measurable": {"state": "pass", "reason": "...", "fix": ""}
}}
```

All four, every time. A reason always. A fix whenever the state is not `pass`. No number in a reason that the idea or the script did not produce.

## One change

**Pass test:** the test changes one thing.

- **Pass:** one change. Everything else about the page, offer, audience and budget stays the same.
- **Flag:** one main change with a small side change the user can remove, such as new copy alongside the new form.
- **Fail:** two or more changes that could each move the metric. A result cannot say which one worked.

## Right metric

**Pass test:** the metric is the first number the idea can move, and it leads to pipeline.

- **Pass:** the first step the change touches, and that step leads to pipeline: a form fill, a demo request, a trial start, a reply, a demo booked.
- **Flag:** leads to pipeline, but a step or more past the change, so the test needs more volume than it has to. A new headline measured on demos held, not demo requests.
- **Fail:** clicks, impressions, opens, time on page or followers alone. None of them is pipeline.

## Clean split

**Pass test:** chance or a fixed rule decides who sees the change.

- **Pass:** a split by the page tool, the email platform, or a fixed rule set in advance (odd and even record IDs, alternating weeks). Or a before-and-after design, which has no split to spoil and carries the No control label instead.
- **Flag:** a fixed rule that could line up with something else, such as one region against another.
- **Fail:** people choose who gets the change. Reps pick the accounts, or the best leads go to the new version.

## Measurable today

**Pass test:** the metric is tracked now, in a system the team can pull from at day 15 and day 30.

- **Pass:** tracked today, by version for a split.
- **Flag:** tracked today, but not by version yet. Setup can add it before launch.
- **Fail:** not tracked at all. There is nothing to read at day 30.

## What the rubric does not judge

Whether the idea is clever, on brand, or worth doing. The rubric checks that the test can give a clean answer. The user decides what to test.
