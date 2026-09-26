# Answer key: test3, the messy HubSpot file

Built by `make_test_data.py` from the generator's deals (seed 13, 1,200 deals), then broken on purpose. Counts come from the build script's own `MESSY` table, not from the skill.

| Planted problem | Count | What the skill must do |
|---|---|---|
| Rows exported twice | 6 | Count each deal once |
| Deals from a second pipeline (Renewals Pipeline) with their own stage columns | 25 | Leave them out, list the pipeline and its count |
| Closed deals with every stage date wiped | 5 (3 lost, 2 won) | Leave them out of the stage math, report them |
| Lost deals with Demo dated the day before Qualified | 4 | Report 4 deals out of order and 4 negative times in stage. Keep their conversion |
| Won deals with the amount typed as text ("$45,300", "45.3k") | 8 | Read them as numbers |
| Won deals with no amount | 3 | Count toward win rate, leave out of the average won deal |
| Deals with stage dates written 3/4/2025 instead of 2025-03-04 | 40 | Read both |
| Lost deals with a closed-lost date in 2031 | 2 | Ignore the date, keep the deal as lost |
| Lost deals with a closed-lost date of "TBD" | 3 | Ignore the date, keep the deal as lost |
| Won deals with the stage typed "closed won " | 10 | Read them as won |

After the problems, every stage count must equal the generator's truth for the 1,195 deals that still carry history. The trust verdict must read "usable with caveats".
