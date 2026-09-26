"""Regression tests for pipeline-leak-finder.

Run from the repo root:  python tests/pipeline-leak-finder/test_analyze.py
Standard library only. The skill uses no third-party library, so no library version can move a number.
Checked on Python 3.10, 3.11, 3.12 and 3.13.

Four layers:
  1. The answer key: every count, rate, median and fix value is recomputed here from the generator's
     own deal records, never from the CSV the skill reads, and must match the skill exactly.
  2. The planted leaks (answer_keys/planted_leaks.md) must be found on every full-size file.
  3. The same deals in HubSpot and Salesforce layouts must give the same answer.
  4. Snapshots in expected/ stop the numbers drifting.
"""
import csv, io, json, math, os, re, subprocess, sys, tempfile, unittest
from collections import defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPTS = os.path.join(ROOT, "skills", "pipeline-leak-finder", "scripts")
EXAMPLES = os.path.join(ROOT, "examples", "pipeline-leak-finder")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, EXAMPLES)
sys.path.insert(0, HERE)
import analyze  # noqa: E402
import generate_sample as g  # noqa: E402
import make_test_data as mk  # noqa: E402

D = lambda f: os.path.join(HERE, "data", f)
CASES = {  # name: (file, kwargs, truth deals, stage names)
    "sample_hubspot": (os.path.join(EXAMPLES, "sample_hubspot_deals.csv"), {}, lambda: g.generate(), None),
    "test1_hubspot_clean": (D("test1_hubspot_clean.csv"), {}, lambda: g.generate(seed=11), None),
    "test2_salesforce_history": (D("test2_salesforce_history.csv"), {}, lambda: g.generate(seed=12), mk.SF_NAMES),
    "test3_hubspot_messy": (D("test3_hubspot_messy.csv"), {}, None, None),
    "test4_salesforce_field_history": (D("test4_salesforce_field_history.csv"), {}, lambda: g.generate(seed=14, n=600), mk.SF_NAMES),
    "test6_stage_log": (D("test6_stage_log.csv"), {"won": "Signed", "lost": "Dead"}, mk.test6_deals, None),
}
_cache = {}


def run(name):
    if name not in _cache:
        f, kw, _, _ = CASES[name]
        _cache[name] = json.loads(json.dumps(analyze.analyze(f, **kw), default=str))
    return _cache[name]


def messy_truth():
    """test3's deals, minus the five closed deals whose stage dates were wiped (see make_test_data.test3)."""
    deals = mk.test3_deals()
    lost = [x for x in deals if x["outcome"] == "lost"]
    won = [x for x in deals if x["outcome"] == "won"]
    wiped = {x["id"] for x in lost[:3] + won[:2]}
    for x in won[10:13]:          # the three won deals whose amount was blanked
        x["amount"] = None
    return [x for x in deals if x["id"] not in wiped]


# ---------- the independent answer key, from the generator's deal records ----------
def median(xs):
    xs = sorted(xs)
    if not xs: return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def quantile(xs, q):
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def key_for(deals, as_of):
    """Recompute every stage number from first principles. No code shared with the skill."""
    stages = g.STAGES
    closed = [x for x in deals if x["outcome"] != "open"]
    won = [x for x in closed if x["outcome"] == "won"]
    won_amts = [x["amount"] for x in won if x["amount"]]
    avg_won = sum(won_amts) / len(won_amts)
    out = {"closed": len(closed), "won": len(won), "lost": len(closed) - len(won), "stages": []}
    for k, s in enumerate(stages):
        moved, died, sitting, days, adv_days = [], [], [], [], []
        for x in deals:
            idx = sorted(stages.index(t) for t in x["entries"])
            top = idx[-1]
            if top < k: continue
            if top > k or x["outcome"] == "won": moved.append(x)
            elif x["outcome"] == "lost": died.append(x)
            else: sitting.append(x)
            if s in x["entries"]:
                later = [x["entries"][t] for t in x["entries"] if stages.index(t) > k]
                end = min(later) if later else x["closed"]
                if end is not None:
                    n = (end - x["entries"][s]).days
                    days.append(n)
                    if x in moved: adv_days.append(n)
        # the fix: quarters by the date a deal passed through the stage
        def passed(x):
            if s in x["entries"]: return x["entries"][s]
            return min(x["entries"][t] for t in x["entries"] if stages.index(t) > k)
        q = defaultdict(lambda: [0, 0, 0])  # entered, moved, resolved
        year = 0
        moved_ids = {x["id"] for x in moved}
        died_ids = {x["id"] for x in died}
        for x in moved + died + sitting:
            d = passed(x)
            if as_of - timedelta(days=365) < d <= as_of: year += 1
            qq = (d.year, (d.month - 1) // 3 + 1)
            q[qq][0] += 1
            if x["id"] in moved_ids: q[qq][1] += 1; q[qq][2] += 1
            elif x["id"] in died_ids: q[qq][2] += 1
        def finished(qq):
            y, n = qq
            nxt = date(y + 1, 1, 1) if n == 4 else date(y, 3 * n + 1, 1)
            return nxt - timedelta(days=1) < as_of
        good = {qq: v for qq, v in q.items() if finished(qq) and v[2] >= 20 and v[2] / v[0] >= 0.8}
        conv = len(moved) / (len(moved) + len(died))
        fwd_closed = [x for x in moved if x["outcome"] != "open"]
        down = sum(x["outcome"] == "won" for x in fwd_closed) / len(fwd_closed)
        if len(good) >= 3:
            best_q = sorted(good, key=lambda qq: (-round(good[qq][1] / good[qq][2], 3), qq))[0]
            target = round(good[best_q][1] / good[best_q][2], 3)
        else:
            best_q, target = None, round(min(1.0, conv * 1.1), 3)
        value = year * max(0, target - round(conv, 3)) * down * avg_won
        out["stages"].append({"stage": s, "moved_on": len(moved), "lost_here": len(died), "open_here": len(sitting),
                              "conversion": round(conv, 3), "median_days": median(days),
                              "stall_line": quantile(adv_days, 0.75), "best_quarter": best_q, "target": target,
                              "deals_per_year": year, "value": round(value)})
    return out


def rename_stage(name, names):
    inv = {v: k for k, v in (names or {}).items()}
    return inv.get(name, name)


class TestAnswerKey(unittest.TestCase):
    """Every number, recomputed from the generator's deal records."""
    def check(self, name, deals):
        res = run(name)
        key = key_for(deals, date.fromisoformat(res["as_of"]))
        self.assertEqual(res["counts"]["closed"], key["closed"])
        self.assertEqual(res["counts"]["won"], key["won"])
        self.assertEqual(res["counts"]["lost"], key["lost"])
        names = CASES[name][3]
        self.assertEqual([rename_stage(s, names) for s in res["stage_mapping"]["order"]], g.STAGES)
        fixes = {rename_stage(f["stage"], names): f for f in res["fixes"]}
        for got, want in zip(res["stages"], key["stages"]):
            with self.subTest(name=name, stage=want["stage"]):
                self.assertEqual(got["moved_on"], want["moved_on"])
                self.assertEqual(got["lost_here"], want["lost_here"])
                self.assertEqual(got["open_here"], want["open_here"])
                self.assertEqual(got["conversion"], want["conversion"])
                if name != "test3_hubspot_messy":   # messy dates shift a few durations on purpose
                    self.assertEqual(got["days"]["median"], round(want["median_days"], 1))
                    self.assertEqual(got["stall"]["line_days"], round(want["stall_line"], 1))
                f = fixes[want["stage"]]
                self.assertEqual(f["deals_per_year"], want["deals_per_year"])
                self.assertEqual(f["target_rate"], want["target"])
                if want["best_quarter"]:
                    self.assertEqual(f["best_quarter"], f"{want['best_quarter'][0]} Q{want['best_quarter'][1]}")
                self.assertLessEqual(abs(f["value_per_year"] - want["value"]), 1, "fix value")

    def test_all(self):
        for name, (_, _, truth, _) in CASES.items():
            if truth: self.check(name, truth())

    def test_messy(self):
        self.check("test3_hubspot_messy", messy_truth())


class TestMessyFile(unittest.TestCase):
    """Every problem planted in test3, counted from make_test_data.MESSY. See answer_keys/test3_messy.md."""
    def test_planted_problems(self):
        dq, M = run("test3_hubspot_messy")["data_quality"], mk.MESSY
        self.assertEqual(dq["duplicate_rows"], M["duplicates"])
        self.assertEqual(dq["other_pipelines"], {"Renewals Pipeline": M["renewals"]})
        self.assertEqual(dq["closed_without_history"], M["no_history"])
        self.assertEqual(dq["deals_out_of_order"], M["out_of_order"])
        self.assertEqual(dq["negative_durations"], M["out_of_order"])
        self.assertEqual(dq["text_amounts_parsed"], M["text_amounts"])
        self.assertEqual(dq["won_without_amount"], M["won_no_amount"])
        self.assertEqual(dq["future_dates"], M["future"])
        self.assertEqual(dq["unreadable_dates"], M["unreadable"])
        self.assertEqual(dq["pipeline"], "Sales Pipeline")

    def test_verdict_and_mapping(self):
        res = run("test3_hubspot_messy")
        self.assertEqual(res["trust"]["verdict"], "usable with caveats")
        self.assertEqual(res["stage_mapping"]["won"], ["Closed Won", "closed won"])
        self.assertEqual(res["counts"]["won"], sum(x["outcome"] == "won" for x in messy_truth()))


class TestPlantedLeaks(unittest.TestCase):
    """The answer key: what the generator planted, and the skill must find. See answer_keys/planted_leaks.md."""
    FULL = ("sample_hubspot", "test1_hubspot_clean", "test2_salesforce_history", "test3_hubspot_messy")

    def stage(self, res, plain):
        names = CASES[self.name][3]
        return next(x for x in res["stages"] if rename_stage(x["stage"], names) == plain)

    def test_leaks(self):
        for self.name in self.FULL:
            res, names = run(self.name), CASES[self.name][3]
            with self.subTest(self.name):
                # the biggest leak: Demo to Proposal, its best quarter is the playbook quarter, and it holds up
                self.assertEqual(rename_stage(res["headline_fix"], names), "Demo")
                demo = next(f for f in res["fixes"] if rename_stage(f["stage"], names) == "Demo")
                self.assertEqual(demo["rank"], 1)
                self.assertEqual(demo["best_quarter"], "2025 Q2")
                self.assertEqual(demo["evidence"], "holds up")
                self.assertEqual(rename_stage(res["findings"]["lowest_conversion"], names), "Demo")
                # every other best quarter is noise and must not pass the luck test
                for f in res["fixes"]:
                    if rename_stage(f["stage"], names) != "Demo":
                        self.assertNotEqual(f["evidence"], "holds up", f["stage"])
                # the proposal stall: past the line, the win rate drops by 40% or more, and 25 points or more
                self.assertEqual(rename_stage(res["findings"]["biggest_stall_penalty"], names), "Proposal")
                st = self.stage(res, "Proposal")["stall"]
                self.assertLess(st["over"]["win_rate"], st["under"]["win_rate"] * 0.6)
                self.assertGreaterEqual(st["under"]["win_rate"] - st["over"]["win_rate"], 0.25)
                # big deals die late, most deals die early
                self.assertEqual(rename_stage(res["findings"]["biggest_lost_deals"], names), "Negotiation")
                self.assertEqual(rename_stage(res["findings"]["most_lost_deals"], names), "Discovery")
                # the Qualified skip is read as passing through
                self.assertGreater(self.stage(res, "Qualified")["skipped_through"], 0)

    def test_small_file_does_not_overclaim(self):
        # 600 deals: the same planted leak is there, but the skill must not call it proven
        res = run("test4_salesforce_field_history")
        f = next(f for f in res["fixes"] if f["stage"] == res["headline_fix"])
        self.assertEqual(f["evidence"], "could be luck")


class TestLayouts(unittest.TestCase):
    def test_same_deals_same_answer(self):
        """The sample in HubSpot and Salesforce layouts must agree on every stage number."""
        h = run("sample_hubspot")
        s = json.loads(json.dumps(analyze.analyze(os.path.join(EXAMPLES, "sample_salesforce_history.csv")), default=str))
        self.assertEqual(h["stages"], s["stages"])
        self.assertEqual(h["fixes"], s["fixes"])
        self.assertEqual(h["overview"], s["overview"])
        self.assertEqual(s["data_quality"]["layout"], "Salesforce Opportunity History")
        self.assertGreater(s["data_quality"]["history_rows_not_stage"], 0)

    def test_utf16_tab_and_footer(self):
        """A UTF-16 tab-delimited HubSpot file, and a Salesforce export with its footer lines."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            src = os.path.join(EXAMPLES, "sample_hubspot_deals.csv")
            rows = list(csv.reader(open(src, encoding="utf-8")))
            p = os.path.join(t, "u16.csv")
            buf = io.StringIO(); csv.writer(buf, delimiter="\t").writerows(rows)
            open(p, "w", encoding="utf-16", newline="").write(buf.getvalue())
            self.assertEqual(analyze.analyze(p)["stages"], run("sample_hubspot")["stages"])
            sf = open(os.path.join(EXAMPLES, "sample_salesforce_history.csv"), encoding="utf-8", newline="").read()
            p2 = os.path.join(t, "sf.csv")
            open(p2, "w", encoding="utf-8", newline="").write(sf + '\n\n"Grand Totals (5700 records)"\n\n"Confidential Information - Do Not Distribute"\n"Copyright (c) 2000-2026 salesforce.com, inc. All rights reserved."\n')
            self.assertEqual(analyze.analyze(p2)["stages"], run("sample_hubspot")["stages"])


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


class TestRealExports(unittest.TestCase):
    """Shapes real exports take, each one a defect found in review and fixed."""
    def test_newest_first_rows(self):
        rows = list(csv.DictReader(open(D("test6_stage_log.csv"), encoding="utf-8")))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = os.path.join(t, "desc.csv")
            write_rows(p, sorted(rows, key=lambda r: r["date_entered"], reverse=True))
            self.assertEqual(analyze.analyze(p, won="Signed", lost="Dead")["stages"], run("test6_stage_log")["stages"])

    def test_skip_straight_to_won_counts_in_quarters(self):
        # a won deal that jumps from Demo to won still has a quarter for Proposal and Negotiation
        res = run("sample_hubspot")
        for x in res["stages"]:
            counted = sum(q["resolved"] for q in x["quarters"])
            self.assertEqual(counted, x["moved_on"] + x["lost_here"], x["stage"])

    def test_won_lost_overrides_add(self):
        res = analyze.analyze(D("test1_hubspot_clean.csv"), lost="Disqualified")
        self.assertEqual(res["stage_mapping"]["lost"], ["Closed Lost"])
        self.assertEqual(res["counts"], run("test1_hubspot_clean")["counts"])
        self.assertEqual(analyze.classify_stage("Follow On Call"), "open")
        self.assertEqual(analyze.classify_stage("Two Next Steps"), "open")
        self.assertEqual(analyze.classify_stage("Closed Won", lost={"closed won"}), "lost")

    def test_field_history_without_created_date(self):
        rows = list(csv.DictReader(open(D("test4_salesforce_field_history.csv"), encoding="utf-8")))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = os.path.join(t, "ff.csv")
            write_rows(p, [{k: v for k, v in r.items() if k != "Created Date"} for r in rows])
            res = analyze.analyze(p)
            self.assertEqual(res["stages"], run("test4_salesforce_field_history")["stages"])

    def test_same_names_without_id(self):
        rows = list(csv.DictReader(open(D("test2_salesforce_history.csv"), encoding="utf-8")))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = os.path.join(t, "noid.csv")
            write_rows(p, [{k: v for k, v in r.items() if k != "Opportunity ID"} for r in rows])
            res = analyze.analyze(p)
            want = run("test2_salesforce_history")
            self.assertEqual(res["counts"]["deals"], want["counts"]["deals"])
            self.assertEqual(res["stages"], want["stages"])
            self.assertGreater(res["data_quality"]["same_name_deals"], 0)
            self.assertEqual(res["data_quality"]["keyed_by"], "deal name")

    def test_hubspot_pipelines_without_pipeline_column(self):
        rows = list(csv.DictReader(open(D("test3_hubspot_messy.csv"), encoding="utf-8")))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = os.path.join(t, "nopipe.csv")
            write_rows(p, [{k: v for k, v in r.items() if k != "Pipeline"} for r in rows])
            self.assertEqual(analyze.analyze(p)["data_quality"]["pipeline"], "Sales Pipeline")

    def test_more_date_shapes(self):
        self.assertEqual(analyze.to_date("03-05-2026"), date(2026, 3, 5))
        self.assertEqual(analyze.to_date("05-Mar-2026"), date(2026, 3, 5))
        self.assertEqual(analyze.to_date("3/5/2026 2:15:33 PM"), date(2026, 3, 5))
        self.assertEqual(analyze.to_date("2026-03-05T14:15:33+01:00"), date(2026, 3, 5))

    def test_bad_as_of_stops(self):
        self.assertIn("as-of", analyze.analyze(D("test1_hubspot_clean.csv"), as_of="2026/13/01")["stop"])

    def test_as_of_drops_later_dates(self):
        res = analyze.analyze(D("test1_hubspot_clean.csv"), as_of="2026-06-30")
        self.assertEqual(res["as_of"], "2026-06-30")
        self.assertGreater(res["data_quality"]["future_dates"], 0)
        self.assertTrue(all(d["days_in_stage"] >= 0 for d in res["stalled_deals"]))


class TestRules(unittest.TestCase):
    def test_stop_when_too_small(self):
        res = analyze.analyze(D("test5_tiny.csv"))
        self.assertIn("Not enough history", res["stop"])

    def test_stop_when_no_won_or_lost(self):
        res = analyze.analyze(D("test6_stage_log.csv"))
        self.assertIn("No stages read as won or lost", res["stop"])
        self.assertEqual(res["stages_found"], ["Dead", "Demo", "Discovery", "Negotiation", "Proposal", "Qualified", "Signed"])

    def test_stop_without_history(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            p = os.path.join(t, "d.csv")
            with open(p, "w", newline="") as fh:
                w = csv.writer(fh); w.writerow(["Deal Name", "Deal Stage", "Amount"])
                for i in range(100): w.writerow([f"D{i}", "Closed Won" if i % 3 else "Closed Lost", 1000])
            self.assertIn("Missing columns", analyze.analyze(p)["stop"])

    def test_stage_order_override(self):
        order = "Discovery,Demo,Qualified,Proposal,Negotiation"
        res = analyze.analyze(D("test1_hubspot_clean.csv"), stages=order)
        self.assertEqual(res["stage_mapping"]["order"], order.split(","))
        self.assertEqual(res["stage_mapping"]["order_source"], "Set by the user")
        self.assertGreater(res["data_quality"]["deals_out_of_order"], 0)

    def test_pipeline_choice(self):
        res = analyze.analyze(D("test3_hubspot_messy.csv"), pipeline="Renewals Pipeline")
        self.assertIn("stop", res)

    def test_small_sample_flag(self):
        for x in run("test4_salesforce_field_history")["stages"]:
            self.assertEqual(x["small_sample"], x["moved_on"] + x["lost_here"] < analyze.SMALL)

    def test_stuck_deals_are_past_the_line(self):
        res = run("sample_hubspot")
        self.assertTrue(res["stalled_deals"])
        for d in res["stalled_deals"]:
            self.assertGreater(d["days_in_stage"], d["stall_line_days"])

    def test_numbers_dates_stages(self):
        self.assertEqual(analyze.to_number("$45,000"), 45000)
        self.assertEqual(analyze.to_number("45k"), 45000)
        self.assertEqual(analyze.to_number("1.2M"), 1200000)
        self.assertIsNone(analyze.to_number(""))
        for s in ("2025-03-04", "2025-03-04 10:22", "3/4/2025", "3/4/2025, 10:22 AM", "2025-03-04T10:22:00Z"):
            self.assertEqual(analyze.to_date(s), date(2025, 3, 4), s)
        self.assertIsNone(analyze.to_date("TBD"))
        self.assertEqual(analyze.classify_stage("Closed Won"), "won")
        self.assertEqual(analyze.classify_stage("closedlost"), "lost")
        self.assertEqual(analyze.classify_stage("Disqualified"), "lost")
        self.assertEqual(analyze.classify_stage("Proposal"), "open")
        self.assertEqual(analyze.classify_stage("Signed", won={"signed"}), "won")

    def test_hubspot_header_variants(self):
        for h in ['Date entered "Demo (Sales Pipeline)"', "Date entered 'Demo (Sales Pipeline)'",
                  "Date entered “Demo (Sales Pipeline)”", "hs_v2_date_entered_Demo"]:
            self.assertTrue(analyze.ENTERED.match(h), h)

    def test_no_em_dash_in_output(self):
        self.assertNotIn(chr(0x2014), json.dumps(run("sample_hubspot")))

    def test_tool_builds(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            j, h = os.path.join(t, "r.json"), os.path.join(t, "r.html")
            with open(j, "w", encoding="utf-8") as fh: json.dump(run("sample_hubspot"), fh)
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_tool.py"), j, "--role", "cro", "--out", h],
                           check=True, capture_output=True)
            html = open(h, encoding="utf-8").read()
            self.assertNotIn("/*__DATA__*/", html)
            self.assertIn('const START_ROLE = "cro"', html)
            self.assertEqual(len(re.findall(r"</script>", html)), 1)


class TestSnapshots(unittest.TestCase):
    pass


SNAP_KEYS = ("counts", "data_quality", "stage_mapping", "overview", "stages", "fixes", "headline_fix", "findings", "trust")


def make(name):
    def test(self):
        got = run(name)
        with open(os.path.join(HERE, "expected", name + ".json")) as fh:
            want = json.load(fh)
        for k in SNAP_KEYS:
            self.assertEqual(got[k], want[k], f"{name}: {k} changed")
    return test


for n in CASES:
    setattr(TestSnapshots, "test_" + n, make(n))


def snapshot():
    """Write expected/ from the current code. Only after the answer key tests pass."""
    os.makedirs(os.path.join(HERE, "expected"), exist_ok=True)
    for n in CASES:
        r = run(n)
        with open(os.path.join(HERE, "expected", n + ".json"), "w") as fh:
            json.dump({k: r[k] for k in SNAP_KEYS}, fh, indent=1)
    print("snapshots written")


if __name__ == "__main__":
    if "--snapshot" in sys.argv:
        snapshot()
    else:
        unittest.main(verbosity=2)
