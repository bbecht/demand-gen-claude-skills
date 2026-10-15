# Building the weekly file

One CSV. One row per week. The skill reads the column names, so naming matters more than order.

## The layout

| Column | Required | Name it | What goes in it |
|---|---|---|---|
| Week | Yes | `week` (or `date`, `week_start`) | The first day of the week. Any common date format. |
| Sales | Yes | `sales` or `revenue` (or any name, passed with `--kpi`) | Sales in dollars for that week, every channel included |
| Spend, one per channel | Yes | Any name with spend in it: `spend_tv`, `paid_search_spend` | Dollars spent that week. Blank means $0 |
| Outside drivers | No | Any name: `price_index`, `promo_depth`, `competitor_sov`, `consumer_confidence` | Numbers that move sales and are not media |
| Holidays | No | `hol_` then the name: `hol_black_friday` | 1 in the holiday's week, 0 otherwise |
| Events | No | `event_` then the name: `event_site_outage` | 1 while the event runs, 0 otherwise. A fading effect can step down: 1, 0.5, 0.25 |

Example:

```
week,sales,spend_tv,spend_paid_search,spend_paid_social,price_index,promo_depth,event_site_outage
2024-01-01,1482000,70000,41000,33000,99.8,0,0
2024-01-08,1517000,0,44000,35000,99.8,10,0
```

## How the skill reads columns

- **Competition first:** names with competitor, competition, share_of_voice or sov read as competition, even with spend in the name.
- **Spend:** any other column with spend, cost or investment in its name, or starting with media_. Names with total, per, cpc, cpm, cpa, cpl or roas are left out as totals or unit costs, and so is a column that equals the sum of the others.
- **Holidays:** columns starting with hol_ or holiday. With none, it adds US holiday weeks: Memorial Day, July 4th, Labor Day, Black Friday and Christmas. Turn that off with `--no-holidays`.
- **Events:** columns starting with event_.
- **Outside drivers:** every other number column. Names with price read as price. Names with promo, discount, markdown or coupon read as promotions, where 0 means no promotion. Names with competitor or sov read as competition.
- **Left out:** columns that are not numbers, results of sales (orders, units, leads, conversions, transactions, customers, revenue, profit, impressions, clicks, sessions, visits, traffic), and any you name with `--ignore`. A result used as a driver soaks up the media effect.

## What the skill fixes and what it does not

| In the file | What happens |
|---|---|
| $ signs, commas, %, 12k, 1.2M, USD or € | Read as numbers |
| European decimals: 88.675,00 | Read as 88675.00 |
| Day-first dates: 13/01/2025 | Read day-first when that gives a steady 7-day rhythm |
| Dates marking the end of the week | Read as week ending when the column name has "end" in it, for holiday timing |
| Daily rows | Summed into Monday-start weeks. Partial weeks are dropped |
| Monthly rows | Stops. Monthly data gives too few points. Export by week |
| The same week twice | Keeps the first row |
| Blank sales | Row dropped |
| Blank spend | Read as $0 |
| Negative spend | Set to $0 |
| Blank outside driver | Filled from the week before |
| A few missing weeks | Left as is and flagged |
| More than 10% of weeks missing | Stops |
| A channel with under 8 weeks of spend | Left out and named |
| A channel at the same level every week | Left out and named. Its spend never moved, so it cannot be measured |
| An Excel file or an empty file | Stops. Save the sheet as CSV |
| Fewer than 52 weeks | Stops |

## Where to get each piece

- **Sales:** your ecommerce platform, POS, ERP or finance system, by week.
- **Spend:** each ad platform's reporting by week, or your media agency's flowchart. TV, radio, print and outdoor come from the buy, not the invoice date.
- **Price and promotions:** your pricing history and promo calendar.
- **Economy:** public series such as consumer confidence, unemployment or mortgage rates, if your category moves with them.

## Leads instead of dollars?

The model reads dollars. Multiply weekly leads or orders by the average value of one. Use the same value for every week, so the model still sees the real swings.
