# Demand Gen Claude Skills by Bill Becht

Free Claude skills for B2B demand generation. New skills added as they ship. Built by Bill Becht, founder of [Marketing Systems Guild](https://www.marketingsystemsguild.com).

Each skill does one job with your own data and gives a straight answer. Nothing is sent to us. Everything runs inside your Claude session.

## The skills

| Skill | The question it answers | Released | Download |
|---|---|---|---|
| [Revenue by Channel](docs/revenue-by-channel.md) | Which channels actually turn into closed revenue, and where should the next dollar go? | October 2026 | [revenue-by-channel.zip](../../releases/tag/revenue-by-channel-v1.1.1) |
| [Archie](docs/archie.md) | Is this new account worth working, and where did it come from? | October 2026 | [archie.zip](../../releases/tag/archie-v1.0.1) |
| [Customer Segmentation](docs/customer-segmentation.md) | Which accounts are worth the effort, and how exposed is our revenue? | October 2026 | [customer-segmentation.zip](../../releases/tag/customer-segmentation-v1.0.0) |
| [Pipeline Leak Finder](docs/pipeline-leak-finder.md) | Which stage kills our deals, and which fix is worth the most? | September 2026 | [pipeline-leak-finder.zip](../../releases/tag/pipeline-leak-finder-v1.0.0) |

## How do I install a skill?

1. Download the skill's zip from the Download column above.
2. In Claude, go to **Customize > Skills**, click **+**, choose **Create skill**, then **Upload a skill**.
3. Turn on code execution in your Claude settings. Skills need it.

Skills work on every Claude plan, Free included. Skills that write to your CRM, like Archie, also need their connectors turned on. In Claude Code, unzip into `~/.claude/skills/` instead.

## What is in this repo?

```
skills/       the skills themselves, one folder each, exactly what gets zipped
docs/         a guide per skill, with screenshots
examples/     sample data to try each skill on, plus a sample output
tests/        test data, independent answer keys and regression tests
tools/        build_zips.py packages every skill into dist/
```

## For contributors

```
python tests/revenue-by-channel/test_analyze.py   # regression tests, standard library only
python tests/customer-segmentation/test_segment.py  # regression tests, needs numpy, pandas, scikit-learn
python tests/pipeline-leak-finder/test_analyze.py   # regression tests, standard library only
python tools/build_zips.py                        # builds dist/<skill>.zip and checks each SKILL.md
```

Found a bug or a CRM export the skill cannot read? Open an issue with the column headers (no customer data).

## License

MIT. Use it, change it, share it.

---
Built by Bill Becht, Marketing Systems Guild. Turning strangers into clients.
