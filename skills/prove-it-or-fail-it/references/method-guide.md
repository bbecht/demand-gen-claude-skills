# How Prove It or Fail It works, in plain words

Most growth ideas never get a verdict. Nobody agreed what a win looks like, so the idea lives on. This guide explains every number and every call the skill makes: what it means, how it is built, and when not to trust it.

## What does the skill do?

Two things. Before launch, it sizes the test and locks three numbers: the success number, the kill number and the day-15 harm line. At day 30, it reads the results and calls the verdict against those locked numbers. Nobody can move them in between.

## What is a lift?

The change in the metric, as a share of where it started. A form that converts at 3.1% and moves to 4.1% has a lift of 33%. Lifts are what the skill compares, because a 1-point gain means something very different on a 3% rate than on a 30% rate.

## How sure is the skill?

95% sure, for every test. When it calls Scale, the chance that the lift is a fluke is about 1 in 20. The test is also sized so that a real lift of the success size shows up 8 times in 10. The standard is fixed so every verdict means the same thing.

## What is the detectable lift?

The smallest lift 30 days of volume can tell apart from noise, at that standard. More volume, smaller detectable lift. A page with 9,000 visitors a month split in half can detect about a 33% lift on a 3.1% rate. It cannot see a 10% lift at all.

- **Rates** use the standard test for two shares.
- **Counts** use the standard test for two counts over the same period.

## What is the payback lift?

The lift that earns back the test budget within the test. Budget divided by the value of one unit gives the extra units needed. Divided by the units the test arm would get anyway, that is the payback lift. It needs the value of one unit. Without it, the success number is not tied to money, and the readout says so.

## What is the business's own swing?

For before-and-after tests only. With no control group, a good month can look like a win. The skill takes the last 12 weeks, looks at every 4-week stretch, and finds the biggest gap from the 12-week average. That is how far the metric moves on its own. A before-and-after win has to beat it.

## How is the success number set?

The largest of the three: the detectable lift, the payback lift when a value is given, and the business's own swing for before and after. The readout names which one set it.

## What is Too small to read?

The user says what lift they expect. If 30 days can only detect a bigger lift than that, or for before and after if the business's own swing is bigger than that, the test cannot give an answer. No card is sealed and no plan is written. The skill names three fixes at the user's own numbers:

1. The volume 30 days would need.
2. The days today's volume would need.
3. A bolder idea, one the user expects to lift the metric at least as much as the test can detect.

## What are the kill number and the harm line?

- **Kill number:** the result at day 30 at or below which even the top of the range sits under the success number. The lift that matters is ruled out.
- **Harm line:** the result at day 15 at or below which the whole range sits under zero. The idea is making things worse.

Both are set before launch, at the planned volume. The verdict at each read is made on the actual results.

## How is the verdict called?

At each read, the skill computes the lift and its range, 95% sure.

| When | Verdict | Rule |
|---|---|---|
| Day 15 | Stop early | The whole range is below zero |
| Day 15 | Keep running | Anything else. A slow start never stops a test |
| Day 30 | Scale | The range is above zero, and the lift is at or above the success number |
| Day 30 | Kill | The top of the range is below the success number |
| Day 30 | Extend | In between. Once, for the extra days agreed on the card |
| End of Extend | Scale | Same rule as day 30 |
| End of Extend | Kill | Anything else. Still in between reads as unproven, not disproven |

The kill number is the day-30 line only. The final read after an Extend has no kill number: it scales at the success number or it kills. A final Kill can sit on a real lift that is smaller than the success number. That is still a Kill, because the success number is the lift the team agreed is worth scaling.

## Why can the test group sit under the success number and still Scale?

In a split test the verdict compares the test group with the control group over the same days. It never compares the test group with the baseline. If the whole market dips, the control dips too, and a real lift still shows. The success number on the card is the success lift applied to the baseline, a guide for planning. The lift decides.

At every read, the skill quotes the action the team agreed to for that verdict.

## What is the test card?

A file written at design with the idea, metric, design, dates, baseline, all the numbers, and the four agreed actions. A seal is computed from all of it. Read needs the card. If a number or an action changes, the seal breaks, and Read refuses and names what changed. The seal catches edits. It is a check on the team's own discipline, not a lock against a determined forger.

## What does No control mean?

A before-and-after test compares the 30 days to the 12 weeks before. It cannot rule out anything else that changed in those 30 days: a price change, a launch, a holiday, a competitor. Every before-and-after verdict carries the No control label, and the first risk in the plan is what else changed.

## When should I not trust it?

- **Under 20 units in an arm.** Read counts, not rates. One unit swings the result.
- **A split that people chose.** If reps picked who got the change, the verdict measures the reps.
- **A metric that changed definition mid-test.** The day-30 number must be counted the same way as the baseline.
- **Stopping at a good-looking day.** The verdict is only valid on the read days on the card. Peeking and stopping early on a good day turns a 1-in-20 fluke into a much bigger one.

## What does it not do?

- Generate or rank ideas. You bring one.
- Test more than one change at a time.
- Test revenue or deal size in this version.
- Change the numbers after launch.
- Use benchmarks. Every baseline is yours.
- Set anything up in a site, ad platform or CRM.
