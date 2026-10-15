"""Rebuild the test and example files. Every number in them is invented.

Usage (repo root): python tests/marketing-mix-model/make_test_data.py
"""
import os, sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "marketing-mix-model", "scripts"))
from mmm.synth import SynthSettings, export_frame, generate  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
EX = os.path.join(ROOT, "examples", "marketing-mix-model")


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(EX, exist_ok=True)

    # 1. Clean: almost no noise, so the model should recover the planted answers
    clean = export_frame(generate(SynthSettings(noise_pct=0.002)))
    clean.to_csv(os.path.join(DATA, "test1_clean.csv"), index=False)

    # 2. Realistic sample: default noise, overlap and search that follows demand
    sample = export_frame(generate(SynthSettings()))
    sample.to_csv(os.path.join(EX, "sample_weekly.csv"), index=False)

    # 3. Messy: the sample with export problems planted in it
    m = sample.copy().astype(object)
    m = m.rename(columns={"week": "Week Starting", "sales": "Revenue ($)", "spend_tv": "TV Spend",
                          "spend_paid_search": "Paid Search Spend ($)"})
    m["Revenue ($)"] = ["${:,.0f}".format(float(v)) for v in m["Revenue ($)"]]       # text money, 208 cells
    m.loc[10:19, "TV Spend"] = ["{:.1f}k".format(float(v) / 1000) for v in m.loc[10:19, "TV Spend"]]  # 10 cells as 70.2k
    m.loc[[30, 31, 32], "Paid Search Spend ($)"] = ""                                  # 3 blank spend cells
    m.loc[40, "spend_radio"] = -500                                                     # 1 negative spend
    m.loc[50, "Revenue ($)"] = ""                                                       # 1 blank sales row
    m.loc[60:61, "consumer_confidence"] = ""                                            # 2 blank driver cells
    m["Week Starting"] = pd.to_datetime(m["Week Starting"]).dt.strftime("%m/%d/%Y")     # US date format
    dup = m.iloc[[100]].copy()                                                          # 1 duplicate week
    bad = m.iloc[[0]].copy()
    bad["Week Starting"] = "not a date"                                                 # 1 unreadable date
    m = pd.concat([m.iloc[:101], dup, m.iloc[101:], bad], ignore_index=True)
    m["Notes"] = ""                                                                     # a text column to ignore
    m.loc[5, "Notes"] = "TV flight starts"
    m.to_csv(os.path.join(DATA, "test2_messy.csv"), index=False)
    m.to_csv(os.path.join(EX, "sample_messy_weekly.csv"), index=False)

    # 4. Too short: 40 weeks
    sample.iloc[:40].to_csv(os.path.join(DATA, "test3_short.csv"), index=False)

    # 5. Monthly rows
    s = sample.copy()
    s["month"] = pd.to_datetime(s["week"]).dt.to_period("M").dt.to_timestamp()
    num = [c for c in s.columns if c not in ("week", "month")]
    mo = s.groupby("month")[num].sum().reset_index().rename(columns={"month": "week"})
    mo.to_csv(os.path.join(DATA, "test4_monthly.csv"), index=False)

    # 6. Daily rows: the clean file spread evenly over 7 days
    rows = []
    for _, r in clean.iterrows():
        for dd in range(7):
            row = r.copy()
            row["week"] = (pd.Timestamp(r["week"]) + pd.Timedelta(days=dd)).strftime("%Y-%m-%d")
            for c in clean.columns:
                if c == "sales" or c.startswith("spend_"):
                    row[c] = float(r[c]) / 7
            rows.append(row)
    pd.DataFrame(rows).to_csv(os.path.join(DATA, "test5_daily.csv"), index=False)
    print("written")


if __name__ == "__main__":
    main()
