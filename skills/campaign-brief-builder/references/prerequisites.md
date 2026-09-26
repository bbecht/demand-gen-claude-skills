# Before you run Campaign Brief Builder

The skill tests a campaign strategy against your own numbers, then builds the brief every team works from. It cannot test numbers you do not have. This page covers what has to be in place, and what happens when it is not.

## What do I need to run it at all?

- **A Claude account on any plan, Free included,** with code execution turned on. Skills do not run without it.
- **The skill uploaded.** In Claude: Customize > Skills > + > Create skill > Upload a skill.
- **A campaign strategy.** Pasted text, a doc or a deck. No strategy yet? Ask for the blank template.

No connectors or MCP servers are needed. The skill works from what you give it, inside your own Claude session. Nothing is sent anywhere else.

## What must the strategy contain?

Nine things. The skill asks for each one that is missing, one at a time.

| Required | Why the skill needs it |
|---|---|
| Pipeline target in dollars, and the due date | The number everything is tested against |
| Audience: accounts and buying roles | Check 5, and the targeting in the brief |
| Offer and call to action | Check 6, and the Content section |
| Core message | Check 7, and the Creative section |
| Channels | Which brief sections fill |
| Budget by channel | The leads each channel buys |
| Launch date and run length | Check 2, and every due date |
| Average deal size, lead-to-opportunity rate, days from lead to opportunity | The reverse funnel |
| Cost per lead by channel | Check 1 cannot run without it |

Optional, and each one sharpens the result:

| Optional | What it unlocks |
|---|---|
| Sales capacity: reps, and new opportunities each can take a month | Check 4. Without it, check 4 is a Flag, not run |
| Win rate and sales cycle | The closed revenue projection and when it lands |
| Owners for each function | Names in the brief. Blank reads Unassigned and is flagged |
| How an opportunity gets credited in the CRM | Check 9 |
| Risks, each with an owner | Check 10 |
| Your UTM convention | Replaces the default |

## Where do the funnel numbers come from?

Your CRM, from the last four quarters of the same kind of campaign. Pipeline Leak Finder gives you conversion stage by stage. Revenue by Channel gives you win rates by source. Upload either result and Claude reads the rates from it, after you confirm each one.

No real number? Type your best guess and say it is a guess. The skill labels it Assumption everywhere, the verdict reads Untested, and the brief carries a week-one task to replace it.

The skill never fills a gap with a benchmark.

## What makes the answer trustworthy?

| What has to be true | Why it matters | What you see if it is not |
|---|---|---|
| Rates come from the same kind of campaign | A webinar rate does not predict paid social | Nothing. The skill cannot tell. Check your source |
| Cost per lead is what you pay today | Leads per channel runs on it | Check 1 passes or fails on the wrong number |
| Average deal fits this audience | Enterprise-aimed campaigns land above average | Pipeline reads low or high |
| Days from lead to opportunity is measured, not hoped | Check 2 runs on it | Timing passes that should fail |
| Spend runs roughly even across the weeks | Check 2 assumes even pacing | A back-loaded plan lands later than shown |

## Readiness checklist

- [ ] Code execution is on in Claude
- [ ] The skill is uploaded
- [ ] A strategy with an audience, offer, message, channels, launch date and run length
- [ ] A pipeline target and due date
- [ ] Budget and cost per lead for every channel
- [ ] Average deal size, lead-to-opportunity rate, days from lead to opportunity
- [ ] Sales capacity
- [ ] How an opportunity gets credited in the CRM

The first six are required. The last two turn Flags into Passes.
