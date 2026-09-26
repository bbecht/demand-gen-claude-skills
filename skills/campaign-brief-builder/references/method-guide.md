# How Campaign Brief Builder works, in plain words

Most campaigns launch on a strategy nobody tested, and each team gets a partial brief. This guide explains every number and every call the skill makes: what it means, how it is built, how to read it, and when not to trust it.

## What does the skill test?

Two things. Can the budget and the timeline reach the pipeline target, at your own rates? And is the strategy specific enough to reach its buyers and be measured? A script answers the first with arithmetic. Claude answers the second against a written rubric. Neither judges whether the idea is clever.

## What is the reverse funnel?

It starts at the target and works backward.

1. **Opportunities needed** = pipeline target ÷ average deal size, rounded up.
2. **Leads needed** = opportunities needed ÷ the share of leads that become opportunities, rounded up.

Then it works forward from what the budget buys.

3. **Leads per channel** = channel budget ÷ that channel's cost per lead, in whole leads. A budget buys whole leads, so $40,000 at $220 a lead is 181 leads, not 181.8.
4. **Planned opportunities** = all planned leads × the lead-to-opportunity rate.
5. **Planned pipeline** = planned opportunities × average deal size.

Every input is your own number. The skill never supplies a rate.

## Why are opportunities shown with a decimal?

Because they are expected values. 700 leads at 8% is 56 opportunities on average. 471 leads at 8% is 37.7. Rounding hides how close to the line a plan sits.

## Check 1. Target reachable on budget

Passes when planned pipeline meets or beats the target. A plan that lands exactly on the target passes.

When it fails, the fix gives three levers, each at your own numbers:

- **Budget to add** = the leads still needed × today's blended cost per lead (total budget ÷ planned leads).
- **Cost per lead ceiling** = total budget ÷ leads needed. The most a lead can cost, across the mix, for this budget to reach the target.
- **Target the plan supports** = planned pipeline.

## Hedged numbers

"About $300 a lead" is read as $300, and the script says so in its notes. A hedge is not an assumption. A number is an assumption only when you call it a guess.

## Check 2. Opportunities land before the due date

A lead is not pipeline. It becomes an opportunity some days later. The skill spreads the planned leads evenly across the run weeks, in whole leads, with any remainder in the earliest weeks. It counts each week's leads on the week's last day, adds your days from lead to opportunity, and asks whether that date falls on or before the due date.

- **Pass:** every week's leads land in time.
- **Flag:** the last weeks land late, but the pipeline that lands in time still meets the target.
- **Fail:** the late weeks leave the in-time pipeline short of the target.

The fix says how many weeks earlier to launch, or which due date the plan actually supports.

**Why even pacing?** It is the plainest assumption, and it is stated. Front-load the spend and more lands in time. Back-load it and less does. If your plan is not even, say so and read check 2 with that in mind.

## Check 3. Every channel can buy at least one opportunity

A channel that buys under one expected opportunity in the whole run cannot tell you anything. It is a Flag, never a Fail. The fix gives the budget that buys one: the leads it takes to expect one opportunity, rounded up, × that channel's cost per lead. Or cut the channel and move its money.

A channel with a $0 budget buys no leads and is flagged the same way.

## Check 4. Sales capacity

Planned opportunities ÷ run weeks × 52 ÷ 12 gives opportunities a month. Capacity is reps × the new opportunities each can take a month.

- **Pass:** the flow fits.
- **Fail:** the plan sends more than the team can work. Opportunities nobody works are pipeline on paper only.
- **Flag, not run:** you did not give capacity. The skill names the number to get.

## Checks 5 to 10

Claude judges these against `rubric.md`, one pass test per check. Audience specific enough to target. Offer fits the audience. One provable message, with the swap test. Channels reach the named roles. Tracking to pipeline defined. Risks named.

The swap test: put a competitor's name in place of yours. If the message still reads true, it is not a message. It is a category description.

## How is the verdict built?

The script assembles it from the ten states. Claude does not pick it.

| Verdict | When |
|---|---|
| Not ready | Any check fails. The brief is blocked. No override |
| Untested | Nothing fails, and at least one required number is your assumption |
| Ready with flags | Nothing fails, no assumptions, at least one Flag |
| Ready | All ten pass |

Untested builds the brief, stamped Untested, with a task to replace each assumption and rerun the check. An assumed cost per lead is due at the end of week one. An assumed deal size, rate or lag is due the day the first opportunities land, because none of them can be measured sooner. A Fail cannot be overridden. Change the strategy, the budget or the target.

## What does "agreed" mean?

No Fail, and you type an explicit approval. Every revision reruns all ten checks and shows what changed since the last round. The brief records the approver's name, seat and date.

## How are due dates set?

Each function's pre-launch work is due a set number of days before launch, from `lead-times.md`. That table is a starting point. You confirm or edit every line before dates are set, and the brief prints which ones you changed. Launch-day items are due on launch day. Ongoing items run from launch to the end date.

## How do budgets reach the brief?

Each funded channel's budget sits on exactly one requirement: the one that spends it. Ad media, an event's venue, an email send, a PR agency fee. Every other requirement reads "No separate budget". The script checks that the channels add up to the total, and that the requirements add up to the channels.

## How are UTMs built?

The script writes them. Default: source = the platform, medium = the channel type, campaign = campaign ID, objective, audience tag and launch month joined by underscores, content = the requirement ID. So every link in the brief points back to the requirement that owns it. Give your own convention and the script applies it instead.

## How does the brief tie the campaign to pipeline?

One CRM campaign ID. The script adds an Operations requirement that every opportunity from the campaign carries it, with a test lead from each channel as the acceptance check. The primary KPI is pipeline dollars and opportunities by the due date. Leads, opportunities and spend per week are the leading indicators. Clicks, impressions and MQL counts are Ads diagnostics, never KPIs.

## What is the closed revenue line?

Shown only when you give a win rate: planned pipeline × win rate. With a sales cycle, it also shows when the last of it would close. It is a projection at your own rates, not a forecast.

## When should I not trust it?

- **Assumed numbers.** A guessed rate or cost per lead drives everything downstream. The verdict says Untested until week one replaces it.
- **Rates from a different motion.** A cost per lead from last year's search campaigns does not carry to a new channel or a new audience.
- **Fewer than 20 opportunities.** One deal swings the result. The readout shows counts, not rates.
- **Uneven pacing.** Check 2 assumes even weekly leads. A launch-week spike or a late event changes it.
- **Average deal size across segments.** A campaign aimed at larger or smaller accounts than your average will not land at your average deal.

## What does it not do?

- Write the strategy. You write it. The skill tests it.
- Write the ads, the press release or the content. The brief sets the requirements. Each function produces the work.
- Use benchmarks. Every rate is yours.
- Forecast. Every number is a projection at your own rates.
- Track the campaign after launch.
- Set anything up in an ad platform or a CRM.
- Judge creative taste.
