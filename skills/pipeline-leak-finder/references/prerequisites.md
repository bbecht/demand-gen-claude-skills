# Before you run Pipeline Leak Finder

The skill reads the path each deal took through your pipeline. If your CRM never recorded when a deal changed stage, no analysis can recover it. This page covers what has to be in place, and what happens when it is not.

## What do I need to run it at all?

- **A Claude account on any plan, Free included,** with code execution turned on. Skills do not run without it.
- **The skill uploaded.** In Claude: Customize > Skills > + > Create skill > Upload a skill.
- **A deal export with stage history,** as a CSV. HubSpot "Date entered" columns, a Salesforce Opportunity History report, or any log of stage changes with dates.
- **Won, lost and open deals** from the last 12 to 24 months.
- **Enough history.** 40 closed deals with stage history, at least 10 won and 10 lost, is the floor. 150 or more is where stage rates get steady. The best-quarter target needs three finished quarters with 20 or more deals through a stage.

No connectors or MCP servers are needed. The skill works from the file you upload, inside your own Claude session. Nothing is sent anywhere else.

## Which columns does it read?

The skill finds these by name, in any order, any capitalization.

| What | Names it recognizes |
|---|---|
| Deal ID | Record ID, Deal ID, Opportunity ID, ID |
| Deal name | Deal Name, Opportunity Name |
| Stage history (HubSpot) | Every `Date entered "Stage (Pipeline)"` column |
| Stage history (Salesforce) | From Stage, To Stage, Last Modified. Or Old Value, New Value, Edit Date |
| Stage history (other) | Stage, plus Date Entered, Changed At or Date |
| Current stage | Deal Stage, Stage |
| Amount | Amount, Deal Amount, Value |
| Dates | Create Date, Close Date |
| Pipeline | Pipeline (HubSpot) |

Stages containing "won" count as won. Stages containing "lost" or "disqualified" count as lost. Custom names work with `--won` and `--lost`, and the skill asks when it cannot tell. The stage order comes from the order most deals moved through. Claude shows it for you to confirm.

## What makes the answer trustworthy?

| What has to be true | Why it matters | What you see if it is not |
|---|---|---|
| Stage history was on for the whole period | Deals closed before it was on have no path | "Closed deals with no stage history" in the data check |
| Reps move deals when they move, not in a Friday batch | Time in stage depends on real dates | Nothing. The skill cannot see a batch update. Ask your team |
| Lost deals are marked lost, not deleted | Every lost deal shows where one died | Conversion looks better than it is |
| Deals move forward, not back and forth | A deal sent back muddles time in stage | "Deals with stage dates out of order" |
| Every stage is used | A stage reps skip is a stage to question | "Stages skipped on the way through" |
| Amount is set on won deals | Fix values run on the average won deal | "Won deals with no amount" |
| The stages did not change partway through | A renamed or split stage breaks the quarter comparison | Nothing. Export only the period after the change |
| Renewals sit in their own pipeline | A renewal is not a new decision to buy | Other pipelines listed as left out |

## Readiness checklist

- [ ] Code execution is on in Claude
- [ ] The skill is uploaded
- [ ] The export has stage dates, not just the current stage
- [ ] Won, lost and open deals, 12 to 24 months
- [ ] At least 40 closed deals with stage history (150 or more is better)
- [ ] Amount on won deals
- [ ] One pipeline, or you know which one to read
- [ ] Reps update stages when deals move

The first five are required. The rest decide how far you can trust the answer.
