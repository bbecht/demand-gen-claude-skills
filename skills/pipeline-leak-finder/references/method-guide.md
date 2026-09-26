# How Pipeline Leak Finder works, in plain words

Your team knows its win rate. It does not know which stage costs it the most deals. This guide explains every number the skill shows: what it means, how it is built, how to read it, and when not to trust it.

## What is a leak?

A stage where deals go in and too few come out. Every pipeline loses deals. A leak is a stage that loses more than it has to, measured against what your own team has already done.

## What does "conversion" mean here?

Of the deals that left a stage, the share that moved forward.

- **Moved on:** the deal reached any later stage, or closed won.
- **Lost here:** the deal closed lost and this was the last stage it reached.
- **Still open:** the deal is sitting in this stage today. It is left out until it moves.

Conversion = moved on ÷ (moved on + lost here).

Open deals wait on purpose. Count them as failures and a young pipeline looks like a leaky one. Count them as wins and you flatter the stage. Neither is true yet.

**Skipped stages.** A deal that jumps from Discovery straight to Demo passed Qualified. It counts as moving on from Qualified. The data check reports how often it happens, because a stage reps routinely skip is a stage worth questioning.

**Deals that start midway.** A deal created straight into Demo never sat in Discovery. It does not count toward Discovery at all.

## How do I read the stage chart?

Each bar is one step: Discovery to Qualified, Qualified to Demo, and so on. The bar is today's conversion. The amber marker is the stage's best quarter. The distance between them is the room to improve.

The lowest bar is not always the biggest leak in money. A late stage with a small gap can be worth more than an early stage with a big one, because every deal saved late is close to a win. That is why the fix ranking exists.

## What is "time in stage"?

Days from entering a stage to entering the next one, or to closing. Measured on deals that have left the stage.

- **Median:** half the deals leave faster, half slower.
- **Slowest quarter:** the striped bar runs to the day by which three in four deals had left.

## What is the stall line?

The day by which three in four deals that moved on had already left the stage. Past it, a deal is behind its own pipeline's pace.

It comes from your data, not a rule of thumb. If your Proposal deals that go on to Negotiation usually leave within 17 days, a proposal at day 25 is stalled.

## Does waiting really cost deals?

The skill compares closed deals that left each stage before the stall line with those that sat past it, and shows the final win rate of each group. A big gap means waiting in that stage goes with losing.

Read it as a warning sign, not a cause. A slow deal is often slow because the buyer was never serious. Pushing it faster will not make it serious. The useful move: treat the stall line as the day a manager asks what the next step is.

## What is "where lost deals die"?

Every lost deal is counted once, at the last stage it reached.

- **Lost deals** shows where the volume leaks.
- **Lost value** shows where the money leaks. Early deals often have no amount yet, so early lost value reads low.
- **Typical lost deal** is the median amount of deals lost at that stage. A stage where big deals die needs a different fix than a stage where small deals die. The skill names the stage with the biggest typical lost deal only among stages with 20 or more lost deals that carry an amount.

Most pipelines lose the most deals in the first stage. That is normal. It is also cheap. The question is whether the right deals leave early.

## How is the fix value built?

For each stage:

1. **Target.** The stage's own best quarter, grouped by the quarter deals entered the stage. A quarter counts when it has finished, at least 20 of the deals that entered that quarter have left the stage, and those are at least 80% of the deals that entered.
2. **Gap.** Target minus today's conversion.
3. **Volume.** Deals that passed through the stage in the last 12 months.
4. **Downstream.** Of deals that moved on from the stage and have closed, the share that won.
5. **Average won deal.** Mean amount of won deals.

Value a year = volume × gap × downstream × average won deal.

In words: if this stage hit its best quarter again, this many more deals would move on, this many of them would win, and this is what they would be worth.

**Why the team's own best quarter?** It is a rate this team, with this product and this market, already hit. An industry benchmark comes from companies you know nothing about. An equal lift on every stage is simple but arbitrary.

**Each fix is valued alone.** Later stages convert as they do today. Two fixes together are worth a little more than the two added up, because deals saved early also pass through the fixed later stage. The skill never adds them.

## What do "holds up" and "could be luck" mean?

Pick the best of ten quarters and one will look good by chance. Every stage has a best quarter. Most of them are noise.

The skill tests the best quarter against all the other quarters combined. It asks how far apart the two rates are, measured in units of normal random swing for that many deals. The bar is 3 units, not the usual 2, because the best quarter was picked from many and quarters swing for ordinary reasons: a holiday, a big rep out, a lumpy month.

- **Holds up:** the best quarter is too far ahead to be a lucky draw. Something was different. Find it and bring it back.
- **Could be luck:** the gap is within normal swing. The target is still a rate the team hit, but do not fund a change on it until you know what drove it.
- **Equal lift:** this stage had fewer than three finished quarters with enough deals, so it gets a 10% lift on its own rate instead of a best quarter. The method is set stage by stage. Other stages in the same file can still use their best quarter.

## How do I use the target planner?

Pick a stage. Drag the target. The planner shows how many more deals reach the next stage, how many more wins, and the closed revenue a year, with the same math as the fix table. Below it, the stage's rate by quarter: blue quarters count, hollow ones do not, amber is the best.

## When should I not trust it?

- **Under 20 deals behind a rate.** You see counts, not percentages. A rate on 12 deals moves 8 points when one deal flips.
- **Stage dates entered in bulk.** If reps update stages on Friday afternoon, or a cleanup moved 200 deals on one day, time in stage is fiction. Conversion still holds.
- **Deals moved backward.** The data check counts deals with stage dates out of order. The skill reads them in pipeline order, which is right for conversion and wrong for time.
- **Stages that changed.** A stage renamed or split halfway through the file breaks the quarter comparison. Export only the period after the change.
- **A best quarter from a different world.** A big launch, a new rep, a price change or one huge customer can make a quarter. Holds up means it was not chance. It does not tell you why.
- **Deals with no stage history.** Closed deals from before history tracking was on are left out. The data check says how many. Over 20%, what is left is not a fair picture of your whole business.
- **Renewals mixed in.** A renewal pipeline has different stages and a different win rate. The skill reads the main pipeline and lists the others it left out.

## What does it not do?

- Tell you why a deal was lost. Add a reason-lost field and a separate analysis can.
- Score individual deals. The stuck list is a list of deals past a line, not a forecast.
- Compare you to other companies.
- Add fix values together.
