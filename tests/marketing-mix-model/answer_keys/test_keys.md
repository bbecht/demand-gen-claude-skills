# Answer keys

Built from how each test file was made (`make_test_data.py`), not from the skill's own code.

## Test 1: clean weekly file

208 weeks, 2022-10-10 to 2026-09-28. Noise at 0.2% of base sales, so the model should recover the planted answers.

Planted sales per $1 come from the generator's own record of what each channel added (`truth["contributions"]`), divided by spend. Planted verdicts come from the planted curves at a 50% margin, on the last 52 weeks. The test recomputes both from the generator, so the key cannot drift from the data.

| Check | Pass line |
|---|---|
| Fit (R squared) | above 0.99 |
| Held-back miss | under 2% |
| Median error in sales per $1, all weeks | under 3% |
| Verdicts that match the planted verdict | 6 of 6 |

## Test 2: messy weekly file

The realistic sample with export problems planted in it. Counts by construction:

| Planted problem | Count | Expected handling |
|---|---|---|
| Rows in the file | 210 (208 weeks, 1 duplicate, 1 bad date) | |
| Unreadable date ("not a date") | 1 | Row dropped |
| Duplicate week (row 100 repeated) | 1 | First row kept |
| Blank sales (row 50) | 1 | Row dropped |
| Weeks left | 207 | |
| Missing week left by the blank sales row | 1 | Flagged, kept back to back |
| Text numbers: Revenue as "$1,234,567" on 208 readable-date rows minus 1 blank, plus TV as "70.2k" on 10 rows | 218 | Read as numbers |
| Blank Paid search spend (rows 30 to 32) | 3 | Read as $0 |
| Negative Radio spend (row 40) | 1 | Set to $0 |
| Blank consumer confidence (rows 60 and 61) | 2 | Filled from the week before |
| Text column "Notes" | 1 column | Left out |
| Column names | "Week Starting", "Revenue ($)", "TV Spend", "Paid Search Spend ($)" | Read as week, sales, TV, Paid search |

Sales total after cleaning: the sample's total minus row 50's sales. TV spend total: within $500 of the sample's total minus nothing dropped beyond rows 50 and the bad date, since 70.2k rounds to the nearest $100.

## Test 3: 40 weeks

Stops: "40 weeks of data. A mix model needs at least 52 weeks".

## Test 4: monthly rows

Stops: "The file looks monthly".

## Test 5: daily rows

The clean file spread evenly over 7 days. Rolls up to the same 208 weeks with the same sales and spend totals as test 1, to the dollar.
