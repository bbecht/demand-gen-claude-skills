"""Regression tests for the Marketing Mix Model skill. Needs numpy, pandas and scipy.

Usage (repo root): python tests/marketing-mix-model/test_mmm.py
Takes about two minutes: it fits the model five times.
"""
import json, os, subprocess, sys, tempfile

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "skills", "marketing-mix-model", "scripts")
DATA = os.path.join(os.path.dirname(__file__), "data")
sys.path.insert(0, SCRIPTS)

import run_mmm as R  # noqa: E402
from mmm.analysis import LEVELS, channel_verdict, pays_at  # noqa: E402
from mmm.synth import SynthSettings, export_frame, generate  # noqa: E402
from mmm.transforms import adstock, hill  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILS.append(name)


def run(args):
    out = os.path.join(TMP, "out.json")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "run_mmm.py")] + args + ["--json", out],
                       capture_output=True, text=True)
    with open(out, encoding="utf-8") as fh:
        return p.returncode, json.load(fh)


def planted(settings, window_weeks=52, margin=0.5):
    """Planted ROI (all weeks) and verdict (last 52 weeks) per channel, from the generator alone."""
    d = generate(settings)
    tc, ch = d.truth["contributions"], d.truth["channels"]
    names = {"tv": "TV", "radio": "Radio", "direct_mail": "Direct mail", "search": "Paid search",
             "social": "Paid social", "video": "Online video"}
    out = {}
    for _, c in ch.iterrows():
        x = d.df[f"spend_{c['key']}"].values.astype(float)
        mask = np.zeros(len(x), bool)
        mask[-window_weeks:] = True

        def contrib(mult):
            x1 = x.copy()
            x1[mask] *= mult
            return (c["beta"] * hill(adstock(x1, c["decay"]), c["half_sat"], c["shape"]))[mask].sum()
        sp = x[mask].sum()
        pays = bool(pays_at(np.array([contrib(m) for m in LEVELS]), sp, margin))
        v = channel_verdict((contrib(1.01) - contrib(1.0)) / (0.01 * sp), pays, margin)
        out[names[c["key"]]] = dict(roi=tc[c["channel"]].sum() / x.sum(), verdict=v)
    return out


def test_transforms():
    check("adstock is geometric", np.allclose(adstock(np.array([1.0, 0, 0]), 0.5), [1, 0.5, 0.25]))
    check("hill is half at the half-saturation point", abs(hill(np.array([2.0]), 2.0, 1.7)[0] - 0.5) < 1e-12)
    d = generate(SynthSettings())
    parts = d.truth["contributions"].drop(columns="week").sum(axis=1)
    check("planted parts add up to sales", np.allclose(parts.round(0), d.df["sales"], atol=1))


def test_loader():
    (df, info), err = R.load(os.path.join(DATA, "test2_messy.csv"), None, [], True)
    check("messy file loads", err is None, err or "")
    q = {x["check"]: x["rows"] for x in info["quality"]}
    exp = {"Unreadable dates": 1, "Duplicate weeks": 1, "Weeks with blank sales": 1,
           "Missing weeks inside the date range": 1, "Numbers stored as text ($, commas, %, k)": 218,
           "Blank spend cells: Paid search": 3, "Negative spend: Radio": 1, "Blank values: Consumer confidence": 2}
    for k, v in exp.items():
        check(f"messy: {k} = {v}", q.get(k) == v, f"got {q.get(k)}")
    check("messy: 207 weeks left", len(df) == 207, str(len(df)))
    check("messy: column names read", info["kpi_col"] == "Revenue ($)" and info["week_col"] == "Week Starting"
          and [n for _, n, _ in info["spend_map"]] == ["TV", "Radio", "Direct mail", "Paid search", "Paid social",
                                                       "Online video"])
    check("messy: Notes left out", any("Notes" in n for n in info["notes"]))
    sample = pd.read_csv(os.path.join(ROOT, "examples", "marketing-mix-model", "sample_weekly.csv"))
    check("messy: sales total is the sample less row 50",
          abs(df["sales"].sum() - (sample["sales"].sum() - sample.loc[50, "sales"])) < 1)
    tv_exp = sample["spend_tv"].sum() - sample.loc[50, "spend_tv"]
    check("messy: TV total within $500 after 70.2k rounding", abs(df["spend_tv"].sum() - tv_exp) <= 500,
          f"diff {df['spend_tv'].sum() - tv_exp:.0f}")

    (dd, di), err = R.load(os.path.join(DATA, "test5_daily.csv"), None, [], True)
    (dc, _), _ = R.load(os.path.join(DATA, "test1_clean.csv"), None, [], True)
    check("daily rolls up to 208 weeks", err is None and len(dd) == 208)
    same = all(abs(dd[c].sum() - dc[c].sum()) < 1 for c in dc.columns if c == "sales" or c.startswith("spend_"))
    check("daily totals match the weekly file", same)

    code, out = run([os.path.join(DATA, "test3_short.csv")])
    check("40 weeks stops", code == 2 and out["stop"].startswith("40 weeks of data"), out.get("stop", ""))
    code, out = run([os.path.join(DATA, "test4_monthly.csv")])
    check("monthly stops", code == 2 and "looks monthly" in out["stop"], out.get("stop", ""))
    nospend = os.path.join(TMP, "nospend.csv")
    pd.read_csv(os.path.join(DATA, "test1_clean.csv"))[["week", "sales", "price_index"]].to_csv(nospend, index=False)
    code, out = run([nospend])
    check("no spend columns stops", code == 2 and "No spend columns" in out["stop"])


def test_clean_fit():
    code, out = run([os.path.join(DATA, "test1_clean.csv"), "--effort", "Quick"])
    check("clean: runs", code == 0)
    mh = out["model_health"]
    check("clean: R squared above 0.99", mh["r2_train"] > 0.99, str(mh["r2_train"]))
    check("clean: held-back miss under 2%", mh["mape_holdout"] < 2, str(mh["mape_holdout"]))
    truth = planted(SynthSettings(noise_pct=0.002))
    match = sum(c["verdict"] == truth[c["channel"]]["verdict"] for c in out["channels"])
    # median ROI error over all weeks, from a direct fit (the JSON reports the last 52 weeks)
    errs = []
    from mmm.model import ModelSpec, fit, suggested_bounds
    (d2, info), _ = R.load(os.path.join(DATA, "test1_clean.csv"), None, [], True)
    keys = [k for k, _, _ in info["spend_map"]]
    names = [n for _, n, _ in info["spend_map"]]
    g = [(k, R.control_role(c)[0]) for k, c in info["controls"]]
    z = [k for k, c in info["controls"] if R.control_role(c)[1]]
    spec = ModelSpec(channels=tuple(keys), channel_names=tuple(names), controls=tuple(k for k, _ in info["controls"]),
                     zero_controls=tuple(z), control_groups=tuple(g), holidays=tuple(info["holidays"]),
                     events=tuple(info["events"]), effort="Quick", n_boot=2, bounds=suggested_bounds(keys))
    fr = fit(d2, spec)
    for k, n in zip(keys, names):
        est = fr.contributions[f"media:{k}"].sum() / fr.spend[k].sum()
        errs.append(abs(est - truth[n]["roi"]) / truth[n]["roi"])
    check("clean: median ROI error under 3%", np.median(errs) < 0.03, f"{np.median(errs) * 100:.1f}%")
    check("clean: 6 of 6 verdicts match the planted verdicts", match == 6, f"{match} of 6")
    check("clean: contributions add up to the fit", np.allclose(fr.contributions.sum(axis=1).values, fr.yhat))
    plan = out["plan"]
    if plan["rows"]:
        check("clean: plan keeps the budget", abs(sum(r["best_spend"] for r in plan["rows"]) - plan["budget"])
              <= 0.001 * plan["budget"] + 6)
        check("clean: plan does not lose sales", plan["gain"] >= -1)
        check("clean: held channels do not move", all(r["change"] == 0 for r in plan["rows"] if r["held"]))
        check("clean: every move stays inside half to double",
              all(0.5 - 1e-3 <= r["multiplier"] <= 2.0 + 1e-3 for r in plan["rows"]))
    for c in out["channels"]:
        if not (c["roi_lo"] <= c["roi"] <= c["roi_hi"]):
            check(f"clean: {c['channel']} range holds its estimate", False)
    return out


def test_sample_and_calibration():
    code, out = run(["--demo", "--effort", "Quick", "--demo-csv", os.path.join(TMP, "demo.csv")])
    check("demo: runs", code == 0 and out["demo"] is True)
    tc = out["truth_check"]
    right = sum(t["true_verdict"] == t["est_verdict"] for t in tc)
    check("demo: at least 4 of 6 verdicts right", right >= 4, f"{right} of 6")
    radio0 = next(c for c in out["channels"] if c["channel"] == "Radio")
    true_radio = next(t for t in tc if t["channel"] == "Radio")["true_roi"]
    code, out2 = run(["--demo", "--effort", "Quick", "--demo-csv", os.path.join(TMP, "demo.csv"),
                      "--demo-tests", "Radio"])
    radio1 = next(c for c in out2["channels"] if c["channel"] == "Radio")
    test = out2["meta"]["calibration"][0]["roi"]
    check("calibration: radio moves toward its lift test", abs(radio1["roi"] - test) < abs(radio0["roi"] - test),
          f"{radio0['roi']} -> {radio1['roi']}, test {test}, truth {true_radio}")
    check("calibration: radio flagged as tested", radio1["calibrated"] is True)
    code, out3 = run([os.path.join(DATA, "test1_clean.csv"), "--effort", "Quick", "--lift-tests", "Nonsense"])
    check("unreadable lift test stops", code == 2 and "Could not match" in out3["stop"])
    return out


def test_tool(out):
    p = os.path.join(TMP, "o.json")
    with open(p, "w") as fh:
        json.dump(out, fh)
    html = os.path.join(TMP, "t.html")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_tool.py"), p, "--role", "cfo", "--out", html],
                       capture_output=True, text=True)
    s = open(html, encoding="utf-8").read()
    check("tool builds", r.returncode == 0 and "/*__DATA__*/" not in s and '"cfo"' in s)
    check("tool has no em-dash", chr(0x2014) not in s)


if __name__ == "__main__":
    test_transforms()
    test_loader()
    out = test_clean_fit()
    test_tool(out)
    test_sample_and_calibration()
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + "; ".join(FAILS))
    sys.exit(1 if FAILS else 0)
