# Pipeline Leak Finder sample

Synthetic B2B deals to try the skill on, and the tool it produces.

| File | What it is |
|---|---|
| `sample_hubspot_deals.csv` | 1,600 deals as a HubSpot deal export with "Date entered" columns: 175 won, 1,384 lost, 41 open |
| `sample_salesforce_history.csv` | The same 1,600 deals as a Salesforce Opportunity History report, one row per change |
| `sample_tool.html` | The interactive tool built from these deals, CEO view. Download it and open it in a browser |
| `generate_sample.py` | The generator. Same seed, same files |

## Where does it come from?

Every company and deal is invented by `generate_sample.py`. Published under MIT with the rest of the repo.

## What leaks are planted?

The skill has to find these. They are the answer key.

| Leak | What was planted |
|---|---|
| Demo to Proposal | The weakest step. 45% of demos reach a proposal. In 2025 Q2 a new demo format ran and 70% did. Then it was dropped |
| Proposal stall | One proposal in three stalls for a month or more. Stalled proposals rarely come back |
| Big deals die late | Deals of $75,000 or more close half as often from Negotiation |
| Early losses | Most lost deals die in Discovery, and most of those never got an amount |
| Skipped stage | 6% of deals jump from Discovery straight to Demo |
| Noise | Every stage swings a few points from quarter to quarter. Only one best quarter is real |

## How do I try it?

Upload `sample_hubspot_deals.csv` to Claude with the skill installed and say: "Where are we losing deals? I'm the CEO." Swap in your own seat.

Salesforce user? Upload `sample_salesforce_history.csv` instead. Same deals, same answer.

To rebuild the files: `python examples/pipeline-leak-finder/generate_sample.py`
