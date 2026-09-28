# Changelog

## Prove It or Fail It

### 1.0.0 (September 2026)

- Turns one growth idea into a 30-day test with a success number, a kill number and a day-15 harm line, locked before launch
- Sizes the test from the user's own numbers: the smallest lift 30 days can detect, the lift that pays back the budget, and for before-and-after tests the business's own swing over 12 weeks. The largest sets the success number
- Rates and counts, split tests and before-and-after tests. One standard for every test: 95% sure, sized to catch a real lift 8 times in 10
- Too small to read when 30 days cannot see the lift the user expects, with three fixes at the user's own numbers: the volume, the days, or a bolder idea
- Six checks, each Pass, Flag or Fail with the fix. Two are arithmetic: readable in 30 days, pays back. Four are Claude's calls against a written rubric: one change, the right metric, a clean split, measurable today
- A sealed test card holding the numbers, the dates and the four agreed actions. Any edit breaks the seal, and the read refuses and names what changed
- Reads at day 15 (Stop early or Keep running), day 30 (Scale, Kill or Extend) and once at the end of an Extend (Scale or Kill, unproven or disproven). Every read quotes the action the team agreed to
- Reads the user's own words: "about 3.1%", "$6K", "9,000 visitors", "50/50", and asks for anything blank or unreadable, one question at a time
- A linter that fails any number or date Claude writes that the script or the idea did not produce, em-dashes, hedges and forecast language
- Readouts for four seats: CEO or owner, marketing lead, RevOps, agency
- Interactive tool with the locked lines, the result against them, the test card, the six checks, a volume planner and exports to Markdown and PDF
- Plain-language method guide, rubric, idea template and prerequisites
- Synthetic MIT sample test with its design and day-30 read

## Campaign Brief Builder

### 1.0.0 (September 2026)

- Takes a campaign strategy in any form: pasted text, a doc or a deck. Claude maps it to a fixed template and asks for each missing part, one question at a time
- Reads the user's own words: "$90k", "1.2 million", "about $300 a lead", "3 weeks", "3 months", slash dates, and asks when a date could be read two ways
- The reverse funnel: opportunities and leads the target needs, against the leads each channel's budget buys at its own cost per lead
- Ten checks, each Pass, Flag or Fail with the fix. Four are arithmetic: target on budget, timing to the due date, channel minimum, sales capacity. Six are Claude's calls against a written rubric: audience, offer, message, channel reach, tracking, risks
- Verdict assembled by the script: Ready, Ready with flags, Untested (built on guessed numbers), Not ready. A Fail blocks the brief with no override
- Revision rounds with a report of what changed, then a typed approval with the approver's name and title
- The brief: six sections for ads, PR, content, operations, sales enablement and creative. Every requirement carries an ID, the strategy line it traces to, an owner, a due date from lead times the user confirms, a budget line, dependencies and a yes-or-no acceptance test
- UTMs for every link, from a default convention or the user's own, and one CRM campaign ID on every opportunity
- Measured on pipeline: the primary KPI is pipeline and opportunities by the due date, with weekly leads, opportunities and spend as leading indicators
- A linter that fails any number or date Claude writes that the script or the strategy did not produce, any assumed number without its label, em-dashes, hedges and forecast language
- Readouts for four seats: CEO or owner, marketing lead, agency, VP Sales or CRO
- Interactive tool with the ten checks, the reverse funnel, a what-if planner, weekly pacing, the brief by owner, and exports to Markdown and CSV
- Plain-language method guide, rubric, lead-time table and strategy template
- Synthetic MIT sample campaign with its full output

## Pipeline Leak Finder

### 1.0.0 (September 2026)

- Conversion from each stage to the next, from a HubSpot deal export with "Date entered" columns, a Salesforce Opportunity History or Field History report, or any stage log
- Open deals wait until they move. Skipped stages count as passed through
- Time in stage, and a stall line per stage: the day by which three in four deals that moved on had left
- Win rate for deals that left each stage in time against those that sat past the stall line
- Where lost deals die: by count, by value and by typical lost deal
- The fix worth the most: every stage valued against its own best quarter, as closed revenue a year at last year's volume
- A luck test on every best quarter: Holds up or Could be luck. Equal 10% lift when a stage has too few finished quarters
- Stuck right now: open deals past their stage's stall line, biggest first
- Data check: duplicate rows, other pipelines, deals with no history, dates out of order, skipped stages, text amounts, mixed and unreadable dates
- Readouts for four seats: CEO or owner, VP Sales or CRO, RevOps, marketing lead
- Interactive tool with a target planner and each stage's rate by quarter
- Plain-language method guide: what each number means, how to read it, when not to trust it
- Synthetic MIT sample data with planted leaks, as a HubSpot export and a Salesforce history report

## Customer Segmentation

### 1.0.0 (September 2026)

- Logistic regression and random forest on account firmographics, trained on won and lost deals
- Grouped cross-validation by account: every account with history is scored by models that never saw it
- The model that ranks held-out accounts better sets the win probability. The other is the second opinion, and gaps of 25 points or more get flagged
- Four segments from win probability and typical deal value: Core, Volume, Stretch, Deprioritize
- Concentration risk: top account and top 10 share, accounts to half and 80% of revenue, and revenue from off-fit accounts
- Pipeline opportunity: open deals weighted by fit, untouched accounts valued by fit, and a ranked work list
- Key fit attributes labeled Both agree, Curved, Straight line, Weak or No signal, with win rate by value
- Model check: check score, calibration and a plain verdict. Stops below 100 closed deals
- Readouts for four seats: CEO or owner, VP Sales or CRO, RevOps, marketing lead
- Interactive tool with a movable value map, sector and status filters, and account search
- Plain-language guide to both models: what they do, how they work, how to read them, when not to trust them
- Synthetic MIT sample data with planted patterns, laid out like Maven Analytics' CRM Sales Opportunities dataset

## Archie

### 1.0.1

- The ICP now comes from a Notion page or doc you name at run time. Claude.ai cannot edit an installed skill, so the old copy-to-icp.md step only worked in Claude Code

### 1.0.0 (September 2026)

- Binary In or Out ICP gate on every new account, from an Apollo run or new inbound
- Evaluates each account once and never revisits it
- Writes passing accounts to HubSpot and Notion with `lead_source_detail` on every contact
- Reads every field back after writing
- One digest per run, with the failing clause for every Out

## Revenue by Channel

### 1.1.1

- Zip now carries explicit folder entries so the scripts, assets and references folders survive every upload path
- SKILL.md finds its scripts from the skill's own folder, and stops with a reinstall message if they are missing instead of counting by hand

### 1.1.0

- Renamed from Where Revenue Came From to Revenue by Channel. The skill folder, zip and install name are now revenue-by-channel
- Solver result reads "2 fewer opportunities, worth more each" instead of "-2 new opportunities" when a shift trades volume for value
- Solver demo GIF added to the guide

### 1.0.0 (September 2026)

- Revenue, win rate and sales cycle by source from any CRM deal export
- Readouts for four seats: CEO or owner, VP Sales or CRO, RevOps, marketing lead
- Data trust check: duplicates, open deals, blank sources, label variants, text amounts, mixed dates, bad close dates
- Channel detail from campaign names: paid search, paid social and events buckets
- Reads HubSpot drill-down fields where HubSpot actually stores the campaign: drill-down 1 for paid search and other campaigns, drill-down 2 for paid social and offline imports
- Interactive report with a budget optimizer: linear program with diminishing returns, worst, base and best cases, and a plain-language recommendation
- Organic search, branded search and unclassified campaigns held fixed by default
