"""Independent answer key for Campaign Brief Builder.

Every number here is recomputed from the planted values, typed in by hand from each case's strategy.md.
No code is shared with the skill: no import of plan.py, no parsing of the strategy JSON. Exact fractions,
and timing walked one calendar day at a time, so a shortcut in the skill cannot hide behind the same shortcut here.
"""
from datetime import date, timedelta
from fractions import Fraction as Fr
import math

# Planted values, as the user stated them. Money in dollars, rates as fractions, lag in days.
PLANTED = {
    "sample": dict(target=1_200_000, due=date(2027, 3, 31), launch=date(2027, 1, 11), weeks=10, deal=30_000, rate=Fr(8, 100), lag=21,
                   channels=[("LinkedIn ads", 40_000, 200), ("Webinar", 15_000, 100), ("Content syndication", 20_000, 80), ("SDR outbound", 15_000, 150)],
                   reps=3, per_rep=10, win=Fr(25, 100)),
    "case1_strong": dict(target=900_000, due=date(2027, 6, 30), launch=date(2027, 3, 1), weeks=12, deal=45_000, rate=Fr(10, 100), lag=14,
                         channels=[("LinkedIn ads", 36_000, 180), ("CISO roundtables", 24_000, 400), ("House email", 6_000, 50), ("Breach report PR", 9_000, 300)],
                         reps=2, per_rep=10, win=Fr(30, 100)),
    "case2_weak": dict(target=2_000_000, due=date(2027, 5, 31), launch=date(2027, 4, 5), weeks=8, deal=25_000, rate=Fr(10, 100), lag=10,
                       channels=[("LinkedIn ads", 30_000, 300), ("Google search ads", 10_000, 150)], reps=None, per_rep=None, win=None),
    # the messy file after the user's answers: launch April 5, trade show $15k, direct mail $250 a lead, total $87.5K.
    # "3 months" = 91 days = 13 weeks.
    "case3_messy_resolved": dict(target=1_200_000, due=date(2027, 7, 31), launch=date(2027, 4, 5), weeks=13, deal=35_000, rate=Fr(8, 100), lag=14,
                                 channels=[("LinkedIn ads", 40_000, 220), ("Partner webinar", 20_000, 95), ("Trade show", 15_000, 500), ("Direct mail", 12_500, 250)],
                                 reps=None, per_rep=None, win=None),
    "case4_assumptions": dict(target=600_000, due=date(2027, 9, 30), launch=date(2027, 7, 12), weeks=8, deal=20_000, rate=Fr(10, 100), lag=21,
                              channels=[("Google search ads", 24_000, 120), ("LinkedIn ads", 16_000, 160)], reps=2, per_rep=12, win=None),
    "case5_cycle_trap": dict(target=500_000, due=date(2027, 4, 30), launch=date(2027, 2, 1), weeks=6, deal=50_000, rate=Fr(5, 100), lag=70,
                             channels=[("LinkedIn ads", 30_000, 150), ("Partner webinar", 10_000, 100)], reps=1, per_rep=12, win=None),
    "case6_round1": dict(target=800_000, due=date(2027, 6, 30), launch=date(2027, 3, 15), weeks=10, deal=40_000, rate=Fr(10, 100), lag=14,
                         channels=[("LinkedIn ads", 20_000, 250), ("Content syndication", 10_000, 100)], reps=2, per_rep=8, win=None),
    "case6_round2": dict(target=800_000, due=date(2027, 6, 30), launch=date(2027, 3, 15), weeks=10, deal=40_000, rate=Fr(10, 100), lag=14,
                         channels=[("LinkedIn ads", 20_000, 250), ("Content syndication", 15_000, 100)], reps=2, per_rep=8, win=None),
}

# What the messy file must produce before anyone answers a question.
MESSY_RAW = {
    "stop": "inputs",
    "question_fields": ["launch.date", "channels.Trade show.budget", "channels.Direct mail.cost_per_lead", "budget_total"],
    "notes_contain": ["$1.2 million", "07/31/2027", "35k", "'8' read as 8%", "2 weeks"],
}


def key(p):
    rate, deal, target = p["rate"], p["deal"], p["target"]
    leads_by = {}
    for name, budget, cpl in p["channels"]:
        n = 0
        while (n + 1) * cpl <= budget:  # whole leads the budget buys, counted up one at a time
            n += 1
        leads_by[name] = n
    leads = sum(leads_by.values())
    budget = sum(b for _, b, _ in p["channels"])
    opps = Fr(leads) * rate
    pipe = opps * deal
    opps_needed = -(-Fr(target) // deal)
    leads_needed = -(-Fr(opps_needed) // rate)
    blended = Fr(budget, leads)
    extra_leads = max(0, int(leads_needed) - leads)
    k = {
        "planned_leads": leads, "planned_opps": float(opps), "planned_pipeline": float(pipe),
        "opps_needed": int(opps_needed), "leads_needed": int(leads_needed),
        "gap": float(max(Fr(0), target - pipe)), "blended_cpl": float(blended), "cpl_ceiling": float(Fr(budget) / leads_needed),
        "extra_leads": extra_leads, "extra_budget": math.ceil(extra_leads * blended) if extra_leads else 0,
        "channel_leads": leads_by,
        "channel_opps": {n: float(v * rate) for n, v in leads_by.items()},
    }
    # timing, one week at a time: whole leads spread evenly, remainder to the earliest weeks
    w = p["weeks"]
    per = [leads // w + (1 if i < leads % w else 0) for i in range(w)]
    in_time_leads, late = 0, 0
    last_land = None
    for i in range(w):
        day = p["launch"]
        for _ in range(7 * i + 6):  # the week's last day
            day += timedelta(days=1)
        land = day
        for _ in range(p["lag"]):
            land += timedelta(days=1)
        last_land = land
        if land <= p["due"]:
            in_time_leads += per[i]
        else:
            late += 1
    k["weeks_late"] = late
    k["pipeline_in_time"] = float(in_time_leads * rate * deal)
    k["last_land"] = last_land
    k["monthly_opps"] = float(opps / w * Fr(52, 12))
    # states for checks 1 to 4
    s1 = "pass" if pipe >= target else "fail"
    if late == 0:
        s2 = "pass"
    else:
        s2 = "flag" if in_time_leads * rate * deal >= target else "fail"
    s3 = "pass" if all(v * rate >= 1 for v in leads_by.values()) else "flag"
    if p["reps"] is None:
        s4 = "flag"
    else:
        s4 = "fail" if opps / w * Fr(52, 12) > p["reps"] * p["per_rep"] else "pass"
    k["states"] = [s1, s2, s3, s4]
    if p["win"] is not None:
        k["projected_revenue"] = float(pipe * p["win"])
    return k


if __name__ == "__main__":
    for name, p in PLANTED.items():
        k = key(p)
        print(name, k["states"], k["planned_leads"], k["planned_pipeline"], k["pipeline_in_time"], k["weeks_late"])
