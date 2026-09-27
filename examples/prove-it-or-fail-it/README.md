# Prove It or Fail It sample

A synthetic growth test to try the skill on, and everything it produces.

| File | What it is |
|---|---|
| `sample_idea.md` | The idea as a user would paste it. Start here |
| `sample_idea.json` | The same idea as Claude maps it for the script |
| `sample_rubric.json` | Claude's calls on the four rubric checks |
| `sample_plan.json` | The test plan Claude writes |
| `sample_card.json` | The sealed test card. Every read needs it |
| `sample_tool.html` | The design tool, CEO view. Download it and open it in a browser |
| `sample_test_plan.md` | The plan as Markdown, the same file the tool exports |
| `sample_readout_ceo.md` | The CEO design readout, lint-clean |
| `sample_results_day30.json` | Day-30 results as a user would bring them |
| `sample_tool_day30.html` | The day-30 read tool |
| `sample_read_day30.md` | The day-30 read as Markdown |
| `sample_readout_day30_ceo.md` | The CEO day-30 readout, lint-clean |
| `build_sample.py` | Rebuilds the outputs from the inputs: `python examples/prove-it-or-fail-it/build_sample.py` |

## Where does it come from?

The form, the traffic and the people are invented. Published under MIT with the rest of the repo.

## What should the skill find?

| Step | Result | Why |
|---|---|---|
| Design | Ready | All six checks pass. 30 days can detect +33%, and you expect +35% |
| Success number | 4.1% (+33%) | Set by the smallest lift 30 days can detect, above the +10.8% that pays back $6,000 |
| Kill number, day 30 | 3.4% (+9.9%) | At or below it, even the top of the range sits under the success number |
| Harm line, day 15 | 2.1% (-32.7%) | At or below it, the whole range sits under zero |
| Day-30 read | Extend | +21.4%, range -2.8% to +45.6%. Not proven, not clearly short |

## How do I try it?

Upload nothing. Paste `sample_idea.md` into Claude with the skill installed and say: "Prove it or fail it. I'm the CEO." Swap in your own seat. For a read, bring `sample_card.json` and the numbers in `sample_results_day30.json`.
