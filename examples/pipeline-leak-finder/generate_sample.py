#!/usr/bin/env python3
"""Generate the synthetic B2B deal data for Pipeline Leak Finder.

Usage (repo root):  python examples/pipeline-leak-finder/generate_sample.py

Every company and deal here is invented. MIT licensed with the repo.

One set of deals, written three ways: a HubSpot deal export with "Date entered" columns,
a Salesforce Opportunity History report, and a Salesforce Opportunity Field History report.
Same deals, same answers, whichever format the skill reads.

The pipeline:  Discovery > Qualified > Demo > Proposal > Negotiation > Closed Won or Closed Lost

The leaks below are planted on purpose. They are the answer key.

  Demo to Proposal     The biggest leak. 45% of demos reach a proposal. In one quarter,
                       2025 Q2, a new demo format ran and 70% did. Then it was dropped.
                       The fix worth the most closed revenue is getting that quarter back.
  Proposal stall       One proposal in three stalls: the buyer goes quiet and the deal sits
                       for a month or more. A stalled proposal reaches Negotiation 25% of the
                       time. The rest move fast and reach it 80% of the time.
  Big deals die late   Deals of $75,000 or more close 45% of the time from Negotiation.
                       Smaller deals close 90%. The biggest lost deals die in Negotiation.
  Early losses         Most lost deals die in Discovery. They are cheap losses: most never
                       got an amount.
  Noise                Every stage swings a few points quarter to quarter, at random. Only
                       Demo to Proposal has a real best quarter. Every other best quarter
                       is luck, and the skill must say so.
  Skipped stages       About 6% of deals jump from Discovery straight to Demo.

Standard library only. Same seed, same files.
"""
import csv, math, os, random
from datetime import date, datetime, timedelta

STAGES = ["Discovery", "Qualified", "Demo", "Proposal", "Negotiation"]
PIPELINE = "Sales Pipeline"
EXPORT_DATE = date(2026, 9, 15)
BIG_DEAL = 75000
STALL_SHARE = 0.35                     # share of proposals that stall
PLAYBOOK_QUARTER = (2025, 2)          # the quarter the demo format ran
BASE = {"Discovery": 0.65, "Qualified": 0.72, "Demo": 0.45}
PLAYBOOK_RATE = 0.70
PROPOSAL_FAST, PROPOSAL_SLOW = 0.80, 0.25
NEGOTIATION_SMALL, NEGOTIATION_BIG = 0.90, 0.45
NOISE = 0.03                           # random quarter-to-quarter swing, plus or minus
SKIP_QUALIFIED = 0.06
DAYS = {  # (median days, spread) per stage, lognormal
    "Discovery": (7, 0.5), "Qualified": (9, 0.5), "Demo": (10, 0.5),
    "Proposal": (10, 0.45), "Stalled": (32, 0.4), "Negotiation": (12, 0.5),
}
NAMES_A = ["Harbor", "Summit", "Cedar", "Northwind", "Bluestone", "Ironvale", "Lumen", "Copperline",
           "Redfield", "Silverbrook", "Oakmont", "Clearpath", "Brightline", "Granite", "Kestrel",
           "Westmark", "Halcyon", "Pinecrest", "Riverton", "Stonebridge", "Aldercroft", "Beacon",
           "Driftwood", "Fairhaven", "Glenmore", "Highpoint", "Juniper", "Larkspur", "Marlowe",
           "Nettle", "Orchard", "Quarry", "Ravenna", "Saltmarsh", "Thornbury", "Upland", "Vantage"]
NAMES_B = ["Software", "Health", "Capital", "Industries", "Partners", "Networks", "Logistics",
           "Labs", "Systems", "Foods", "Energy", "Analytics", "Freight", "Clinics", "Advisory"]
PRODUCTS = ["Platform", "Platform + Services", "Team plan", "Enterprise rollout", "Pilot"]


def quarter(d):
    return (d.year, (d.month - 1) // 3 + 1)


def days_in(rng, stage):
    med, sd = DAYS[stage]
    return max(1, round(med * math.exp(rng.gauss(0, sd))))


def generate(seed=7, n=1600, start=date(2024, 1, 1), end=date(2026, 9, 10), export_date=EXPORT_DATE):
    """Return a list of deals. Each deal: id, name, amount, created, entries {stage: date},
    outcome won|lost|open, closed (date or None), expected_close (open deals)."""
    rng = random.Random(seed)
    span = (end - start).days
    q_noise = {}  # (stage, quarter) -> random swing

    def rate(stage, d):
        key = (stage, quarter(d))
        if key not in q_noise:
            q_noise[key] = rng.uniform(-NOISE, NOISE)
        if stage == "Demo" and quarter(d) == PLAYBOOK_QUARTER:
            return PLAYBOOK_RATE
        return BASE[stage] + q_noise[key]

    deals, used = [], set()
    for i in range(n):
        created = start + timedelta(days=rng.randrange(span + 1))
        amount = int(round(min(260000, max(6000, 30000 * math.exp(rng.gauss(0, 0.75)))), -2))
        while True:
            name = f"{rng.choice(NAMES_A)} {rng.choice(NAMES_B)}"
            if name not in used or len(used) > 500:
                break
        used.add(name)
        deal = {"id": str(40100000 + i * 7), "name": f"{name} - {rng.choice(PRODUCTS)}", "amount": amount,
                "created": created, "entries": {}, "outcome": "open", "closed": None}
        d, idx = created, 0
        skip = rng.random() < SKIP_QUALIFIED
        while True:
            stage = STAGES[idx]
            if d > export_date:
                break
            deal["entries"][stage] = d
            stay = days_in(rng, stage)
            if stage == "Proposal":
                stalled = rng.random() < STALL_SHARE
                stay = days_in(rng, "Stalled") if stalled else stay
                p = PROPOSAL_SLOW if stalled else PROPOSAL_FAST
            elif stage == "Negotiation":
                p = NEGOTIATION_BIG if amount >= BIG_DEAL else NEGOTIATION_SMALL
            else:
                p = rate(stage, d)
            leave = d + timedelta(days=stay)
            if leave > export_date:
                break                                   # still sitting in this stage
            if rng.random() >= p:
                deal["outcome"], deal["closed"] = "lost", leave
                break
            if stage == "Negotiation":
                deal["outcome"], deal["closed"] = "won", leave
                break
            idx += 1
            if stage == "Discovery" and skip:
                idx += 1                                # jump straight to Demo
            d = leave
        if deal["outcome"] == "open":
            deal["expected_close"] = export_date + timedelta(days=rng.randrange(20, 120))
        deals.append(deal)
    # Most deals lost early never got an amount.
    for x in deals:
        if x["outcome"] == "lost" and max(x["entries"], key=STAGES.index) in ("Discovery", "Qualified"):
            if rng.random() < 0.6:
                x["amount"] = None
    return deals


def last_stage(deal):
    return max(deal["entries"], key=STAGES.index)


def stamp(d, rng):
    return datetime(d.year, d.month, d.day, rng.randrange(8, 18), rng.randrange(60)).strftime("%Y-%m-%d %H:%M")


def hubspot_rows(deals, seed=1, stages=STAGES, pipeline=PIPELINE):
    """One row per deal, HubSpot deal export layout."""
    rng = random.Random(seed)
    label = {"won": "Closed Won", "lost": "Closed Lost"}
    rows = []
    for x in deals:
        r = {"Record ID": x["id"], "Deal Name": x["name"], "Pipeline": pipeline,
             "Deal Stage": label.get(x["outcome"], last_stage(x) if x["entries"] else stages[0]),
             "Amount": "" if x["amount"] is None else x["amount"],
             "Create Date": stamp(x["created"], rng),
             "Close Date": stamp(x["closed"] or x["expected_close"], rng)}
        for s in stages + ["Closed Won", "Closed Lost"]:
            r[f'Date entered "{s} ({pipeline})"'] = ""
        for s, d in x["entries"].items():
            r[f'Date entered "{s} ({pipeline})"'] = stamp(d, rng)
        if x["outcome"] != "open":
            r[f'Date entered "{label[x["outcome"]]} ({pipeline})"'] = stamp(x["closed"], rng)
        rows.append(r)
    return rows


def us(d):
    return f"{d.month}/{d.day}/{d.year}"


def salesforce_rows(deals, seed=2, rename=None):
    """Salesforce Opportunity History report: one row per change, stage and amount changes."""
    rng = random.Random(seed)
    rename = rename or {}
    nm = lambda s: rename.get(s, s)
    rows = []
    for x in deals:
        events = sorted(x["entries"].items(), key=lambda kv: STAGES.index(kv[0]))
        if x["outcome"] != "open":
            events.append(("Closed Won" if x["outcome"] == "won" else "Closed Lost", x["closed"]))
        current = nm(events[-1][0])
        close = x["closed"] or x["expected_close"]
        prev = ""
        oid = "006" + format(int(x["id"]), "X").rjust(12, "0")
        for j, (s, d) in enumerate(events):
            nxt = events[j + 1][1] if j + 1 < len(events) else None
            rows.append({"Opportunity ID": oid, "Opportunity Name": x["name"], "From Stage": prev, "To Stage": nm(s),
                         "Stage Duration": (nxt - d).days if nxt else "", "Last Modified": us(d),
                         "Amount": "" if x["amount"] is None else x["amount"],
                         "Close Date": us(close), "Stage": current, "Created Date": us(x["created"])})
            prev = nm(s)
            # an amount edit partway through: a history row with no stage change
            if nxt and x["amount"] and rng.random() < 0.15:
                mid = d + timedelta(days=max(0, (nxt - d).days // 2))
                rows.append({"Opportunity ID": oid, "Opportunity Name": x["name"], "From Stage": nm(s), "To Stage": nm(s),
                             "Stage Duration": "", "Last Modified": us(mid), "Amount": x["amount"],
                             "Close Date": us(close), "Stage": current, "Created Date": us(x["created"])})
    return rows


def field_history_rows(deals, rename=None):
    """Salesforce Opportunity Field History report: Stage changes as Old Value and New Value."""
    rename = rename or {}
    nm = lambda s: rename.get(s, s)
    rows = []
    for x in deals:
        events = sorted(x["entries"].items(), key=lambda kv: STAGES.index(kv[0]))
        if x["outcome"] != "open":
            events.append(("Closed Won" if x["outcome"] == "won" else "Closed Lost", x["closed"]))
        current = nm(events[-1][0])
        base = {"Opportunity ID": "006" + format(int(x["id"]), "X").rjust(12, "0"), "Opportunity Name": x["name"], "Stage": current,
                "Amount": "" if x["amount"] is None else x["amount"], "Created Date": us(x["created"]),
                "Close Date": us(x["closed"] or x["expected_close"])}
        rows.append({**base, "Field / Event": "Created.", "Old Value": "", "New Value": "", "Edit Date": us(x["created"])})
        for j in range(1, len(events)):
            rows.append({**base, "Field / Event": "Stage", "Old Value": nm(events[j - 1][0]),
                         "New Value": nm(events[j][0]), "Edit Date": us(events[j][1])})
    return rows


def write(path, rows, encoding="utf-8"):
    with open(path, "w", newline="", encoding=encoding) as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    deals = generate()
    write(os.path.join(here, "sample_hubspot_deals.csv"), hubspot_rows(deals))
    write(os.path.join(here, "sample_salesforce_history.csv"), salesforce_rows(deals))
    won = sum(x["outcome"] == "won" for x in deals)
    lost = sum(x["outcome"] == "lost" for x in deals)
    print(f"{len(deals)} deals: {won} won, {lost} lost, {len(deals) - won - lost} open")
