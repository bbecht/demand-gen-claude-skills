# Test plan: Cut the demo request form from nine fields to four.

**Verdict: Ready.** Metric: Demo form conversion (rate). Split test, 50% of the audience sees the change.
Sealed. Seal `d50f634de49d0cd6`. Keep card.json: every read needs it.

## The numbers, locked before launch

| Line | Value |
|---|---|
| Baseline | 3.1% |
| Success number | 4.1% (+33%) |
| Kill number, day 30 | 3.4% (+9.9%) |
| Harm line at day 15 | 2.1% (-32.7%) |
| Launch | Feb 1, 2027 |
| Day-15 check | Feb 15, 2027 |
| Day-30 verdict | Mar 2, 2027 |
| Extend ends | Apr 1, 2027 |

| What sets the bar | Lift |
|---|---|
| Smallest lift 30 days can detect | +33% |
| Lift that pays back the budget | +10.8% |
| The business's own swing | Split test: not needed |
| The lift you expect | +35% |

The success number is set by the smallest detectable lift.

## What happens on each verdict

| Verdict | Agreed action |
|---|---|
| Scale | Roll the four-field form out to every demo page and move the $6K test budget into paid search for the demo page. |
| Kill | Keep the nine-field form and put the $6K into the webinar program. |
| Extend | Run 30 more days on the same split, with $3K more for the page tool. |
| Stop early | Marketing ops switches every visitor back to the nine-field form the same day. |

## The checks

| Check | State | Reason | Fix |
|---|---|---|---|
| Readable in 30 days | Pass | 30 days can detect a lift of 33%. You expect 35%. |  |
| Pays back at the expected lift | Pass | The budget pays back at a lift of 10.8%. You expect 35%. |  |
| One change | Pass | The test changes one thing: the number of form fields. The page, offer and traffic stay the same. |  |
| Right metric | Pass | Demo form conversion is the first number fewer fields can move, and a demo request leads to pipeline. |  |
| Clean split | Pass | The page tool assigns each visitor to a form at random, 50/50. |  |
| Measurable today | Pass | Form submissions and page visitors are tracked today, by form version. |  |

## The plan

- **The change:** The demo request form drops from nine fields to four: name, work email, company and role.
- **Who sees it:** Every visitor to the demo page. Half see the four-field form, half see the current nine-field form.
- **How people are assigned:** The page tool assigns each visitor to a form at random, 50/50, and keeps them on it for the whole test.
- **What counts:** One demo request is one submitted form from a unique visitor. Duplicate submissions from the same email count once.
- **Where it is counted:** The page tool's form report, by form version, matched to demo requests in the CRM.

**Setup**

1. Marketing ops builds the four-field version and the 50/50 split in the page tool.
2. RevOps adds the form version to every demo request in the CRM.
3. Demand gen checks both versions submit a test request before launch.

**Risks**

- Sales asks for the missing fields on the first call, which slows follow-up. The sales director agrees to that before launch.
- A campaign sends new traffic to the page mid-test. Both versions still get it at random, so the split holds.

## Reads

| Read | Date | Expected people so far |
|---|---|---|
| Day 15 | Feb 15, 2027 | test 2,250, control 2,250 |
| Day 30 | Mar 2, 2027 | test 4,500, control 4,500 |

A verdict is about this test in this period, not a forecast.

*Built by Marketing Systems Guild. Turning strangers into clients.*
