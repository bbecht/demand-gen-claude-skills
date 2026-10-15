# How the Marketing Mix Model works

Plain words first. The math is at the end for anyone who wants it.

## What does it do?

It takes weekly sales and splits each week into the parts that drove it: a base you would sell anyway, a trend, seasons, holidays, events, outside forces like price and the economy, and each media channel. From each channel's part it works out sales per dollar, what the next dollar would return, and the best split of the budget.

## How does it know what a channel drove?

It watches how sales moved when that channel's spend moved, while holding the other drivers still. A week TV went dark and sales dipped, after allowing for the season, is evidence about TV. Every week of two or three years adds one more comparison.

## Why do ads keep working after they run?

Carry-over. Part of each week's spend keeps working in the weeks after: people remember the TV spot, the mailer sits on the counter. The model finds each channel's carry-over rate. A rate of 60% means 60% of a week's effect is still there the next week. Half-life is the weeks until half of it has faded.

## Why does the return fall as spend rises?

Saturation. The first dollars reach the easiest buyers. Each extra dollar reaches fewer new ones. The response curve bends to show it. Some channels have an S-curve: too little spend does almost nothing, then it climbs, then it flattens.

## What is the difference between sales per $1 and the next $1?

Sales per $1 is the average: everything the channel drove divided by everything spent. The next $1 is the return on one more dollar at today's level. Past the steep part of the curve, the next dollar returns less than the average. On an S-curve's slow start it can return more, which is why a channel can look weak on average and still earn on the next dollar. Budget moves follow the next dollar.

## How are the verdicts set?

Break-even is 1 divided by your gross margin. At 50%, $2 of sales per $1.

Every verdict starts from the next $1's gross profit.

- **Grow:** the next $1 brings back at least $1.20 in gross profit.
- **Hold:** $0.80 to $1.20.
- **Trim:** under $0.80, but some spend level from a tenth of today to double today still covers the channel's cost. Spend less, not nothing.
- **Cut:** under $0.80, and no level from a tenth of today to double today covers the channel's cost. It loses money at every level the model has seen.

A channel can be Grow while its sales per $1 sit under break-even. That is the slow start of an S-curve: more spend lifts the average.

## How sure is it?

The model refits itself 40 times. Each time it resamples its own weekly misses in 4-week blocks, adds them back to its fitted sales, and runs the whole search again, carry-over and saturation included. A channel whose verdict holds in 80% of the refits is **Clear**. One whose verdict holds in at least half the refits, and with a neighbouring verdict like Hold and Trim in 80%, is a **Close call**: the direction is known, the size is not. A channel anchored by a lift test is at least a Close call. Anything else is **Test first**, and so is any channel whose spend moves with another channel's, since no amount of refitting can split the two. The ranges shown are the middle 90% of the refits.

## What does the budget plan do?

It finds the split of today's budget that drives the most sales, by moving money until the next dollar returns about the same in every channel. Each channel stays between half and double today's spend, the range the model has seen. Test first channels stay at today's spend. Cut and Trim channels can only shrink, and Grow channels can only grow, so the plan never argues with the verdicts. The budget slider repeats this from 60% to 160% of today, and shows where gross profit after media cost peaks.

## How do lift tests change it?

A lift test measures one channel directly: hold spend back in some markets, compare with markets that kept it. Give the skill the result as sales per $1 with its standard error. The model treats the test as one more piece of evidence, weighted by how precise the test was. A tight test pulls the channel's estimate close to the test result. When the model and a test disagree, the test wins.

## When should I not trust it?

- The held-back weeks miss by more than 10%.
- Two channels always ran together. The model cannot split them.
- Spend chases demand, like search bids that rise in peak season. The model can confuse demand with effect.
- Something that moves sales is missing: a price change, a big promotion, a store opening.
- The market changed. A model fit on last year describes last year.

A mix model finds patterns in history. A lift test proves cause. Use the model to decide what to test, and the tests to anchor the model.

## How was it checked?

The skill ships with an invented home-improvement brand: four years of weekly data with every effect planted at a known size. Run the demo and the tool shows the model against the planted answers. On clean data it recovers every channel. On the realistic sample, with noise, flighted channels that overlap, and search that follows demand, it gets most verdicts right and misses some sizes. That is what mix models do, and why the test list exists.

## The math

Weekly sales = intercept + trend + Fourier seasonality (2 pairs) + holiday flags + event signals + outside drivers, centred on their average (promotions on 0) + the sum over channels of beta x Hill(Adstock(spend)) + noise.

- Adstock: a_t = x_t + decay x a_(t-1)
- Hill: h(a) = a^s / (a^s + K^s), with K set relative to the channel's typical adstocked level

Differential evolution searches decay, K and s for every channel at once, inside channel-type ranges (search 0 to 0.4 carry-over, TV 0.3 to 0.85). For each candidate, the base columns are projected out and a non-negative least squares solve finds the media coefficients. The winner is polished with L-BFGS-B, then a ridge regression with non-negative media coefficients solves every coefficient exactly. Lift tests enter as extra weighted rows: ROI is linear in beta, so the solve stays a bounded least squares problem. The last 13 weeks (8 under two years of data) are held out to test the forecast. Ranges come from a moving-block bootstrap with full refits.

Built from a prototype by Bill Becht, Marketing Systems Guild.
