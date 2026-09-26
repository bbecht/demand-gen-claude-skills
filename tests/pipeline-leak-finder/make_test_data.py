#!/usr/bin/env python3
"""Rebuild the Pipeline Leak Finder test files. Run from the repo root.

  python tests/pipeline-leak-finder/make_test_data.py

test1: HubSpot deal export, clean. A different seed from the sample.
test2: Salesforce Opportunity History report, clean, Salesforce's default stage names.
test3: HubSpot deal export with planted data problems. See answer_keys/test3_messy.md.
test4: Salesforce Opportunity Field History report (Old Value, New Value), smaller.
test5: too small to analyze. The script must stop.
test6: a plain stage log with custom stage names (Signed, Dead). The script must ask, then run.
"""
import csv, os, random, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "examples", "pipeline-leak-finder"))
import generate_sample as g  # noqa: E402

DATA = os.path.join(HERE, "data")
SF_NAMES = {"Discovery": "Prospecting", "Qualified": "Qualification", "Demo": "Needs Analysis",
            "Proposal": "Proposal/Price Quote", "Negotiation": "Negotiation/Review"}
# The planted problems in test3. The answer key reads these, not the skill's output.
MESSY = {"duplicates": 6, "renewals": 25, "no_history": 5, "out_of_order": 4, "text_amounts": 8,
         "won_no_amount": 3, "us_dates": 40, "future": 2, "unreadable": 3, "lowercase_won": 10}


def path(name):
    return os.path.join(DATA, name)


def test1():
    g.write(path("test1_hubspot_clean.csv"), g.hubspot_rows(g.generate(seed=11)))


def test2():
    g.write(path("test2_salesforce_history.csv"), g.salesforce_rows(g.generate(seed=12), rename=SF_NAMES))


def test3_deals():
    """The deals behind test3, before any problem is planted. The tests use these as the truth."""
    return g.generate(seed=13, n=1200)


def test3():
    rng = random.Random(33)
    deals = test3_deals()
    rows = g.hubspot_rows(deals, seed=3)
    by_id = {r["Record ID"]: r for r in rows}
    col = lambda s: f'Date entered "{s} ({g.PIPELINE})"'
    won = [x for x in deals if x["outcome"] == "won"]
    lost = [x for x in deals if x["outcome"] == "lost"]
    taken = set()

    def take(pool, n, cond=lambda x: True):
        out = [x for x in pool if x["id"] not in taken and cond(x)][:n]
        taken.update(x["id"] for x in out)
        return out

    # 1. five closed deals lose every stage date (the export was pulled before history was switched on)
    for x in take(lost, 3) + take(won, 2):
        for s in g.STAGES + ["Closed Won", "Closed Lost"]:
            by_id[x["id"]][col(s)] = ""
    # 2. four lost deals show Demo entered the day before Qualified
    for x in take(lost, MESSY["out_of_order"], lambda x: "Qualified" in x["entries"] and "Demo" in x["entries"]):
        q = x["entries"]["Qualified"] - g.timedelta(days=1)
        by_id[x["id"]][col("Demo")] = q.strftime("%Y-%m-%d") + " 09:00"
    # 3. text amounts on eight won deals
    for i, x in enumerate(take(won, MESSY["text_amounts"])):
        by_id[x["id"]]["Amount"] = f"${x['amount']:,}" if i % 2 == 0 else f"{x['amount'] / 1000:g}k"
    # 4. three won deals with no amount
    for x in take(won, MESSY["won_no_amount"]):
        by_id[x["id"]]["Amount"] = ""
    # 5. forty deals written with US dates
    for x in take(deals, MESSY["us_dates"]):
        r = by_id[x["id"]]
        for k, v in list(r.items()):
            if k.startswith("Date entered") and v:
                y, m, d = v[:10].split("-")
                r[k] = f"{int(m)}/{int(d)}/{y}"
    # 6. two lost deals with a closed-lost date years in the future
    for x in take(lost, MESSY["future"]):
        by_id[x["id"]][col("Closed Lost")] = "2031-01-15 10:00"
    # 7. three lost deals with an unreadable closed-lost date
    for x in take(lost, MESSY["unreadable"]):
        by_id[x["id"]][col("Closed Lost")] = "TBD"
    # 8. ten won deals with the stage typed in lower case with a trailing space
    for x in take(won, MESSY["lowercase_won"]):
        by_id[x["id"]]["Deal Stage"] = "closed won "
    # 9. twenty-five renewal deals from a second pipeline, with their own columns
    out = [by_id[x["id"]] for x in deals]
    renew_cols = ['Date entered "Renewal Review (Renewals Pipeline)"', 'Date entered "Renewed (Renewals Pipeline)"']
    for r in out:
        for c in renew_cols: r[c] = ""
    for i in range(MESSY["renewals"]):
        r = {k: "" for k in out[0]}
        r.update({"Record ID": str(49900000 + i), "Deal Name": f"Renewal {i + 1}", "Pipeline": "Renewals Pipeline",
                  "Deal Stage": "Renewed", "Amount": 20000 + 500 * i, "Create Date": "2025-06-01 09:00",
                  "Close Date": "2025-07-01 09:00", renew_cols[0]: "2025-06-01 09:00", renew_cols[1]: "2025-07-01 09:00"})
        out.insert(rng.randrange(len(out)), r)
    # 10. six rows exported twice
    for x in take(deals, MESSY["duplicates"]):
        out.insert(rng.randrange(len(out)), dict(by_id[x["id"]]))
    g.write(path("test3_hubspot_messy.csv"), out)
    return taken


def test4():
    g.write(path("test4_salesforce_field_history.csv"), g.field_history_rows(g.generate(seed=14, n=600), rename=SF_NAMES))


def test5():
    g.write(path("test5_tiny.csv"), g.hubspot_rows(g.generate(seed=15, n=30)))


def test6_deals():
    return g.generate(seed=16, n=500)


def test6():
    """A plain stage log: one row per stage change, custom closed stages."""
    names = {"Closed Won": "Signed", "Closed Lost": "Dead"}
    rows = []
    for x in test6_deals():
        ev = sorted(x["entries"].items(), key=lambda kv: g.STAGES.index(kv[0]))
        if x["outcome"] != "open":
            ev.append(("Closed Won" if x["outcome"] == "won" else "Closed Lost", x["closed"]))
        for s, d in ev:
            rows.append({"deal_id": "D" + x["id"], "stage": names.get(s, s), "date_entered": d.isoformat(),
                         "amount": "" if x["amount"] is None else x["amount"]})
    g.write(path("test6_stage_log.csv"), rows)


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    test1(); test2(); test3(); test4(); test5(); test6()
    print("test files written to " + DATA)
