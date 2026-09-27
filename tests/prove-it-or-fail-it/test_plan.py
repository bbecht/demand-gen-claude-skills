"""Regression tests for prove-it-or-fail-it.

Run from the repo root:  python tests/prove-it-or-fail-it/test_plan.py
Standard library only. The skill uses no third-party library, so no library version can move a number.
Checked on Python 3.10, 3.11, 3.12 and 3.13.

Six layers:
  1. The answer key (answer_key.py): every lift, line, date and verdict is recomputed from the planted values
     with separate code and day-by-day dates, and must match the skill.
  2. The hand-set verdicts (expected_verdicts.json): the six check states and the verdict for every case,
     written before the build.
  3. Parsing: the user's own words, hedges, shares, dates, and the questions a blank or unreadable field raises.
  4. The card and the reads: the seal, tampering, read days, Extend rules and the fields every read carries.
  5. The linter: it passes clean text and catches invented numbers, dates, em-dashes, hedges and forecasts.
  6. Snapshots in expected/ stop the output drifting. Rebuild them with --update after a deliberate change.
"""
import copy, json, os, re, subprocess, sys, tempfile, unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL = os.path.join(ROOT, "skills", "prove-it-or-fail-it")
SCRIPTS = os.path.join(SKILL, "scripts")
EX = os.path.join(ROOT, "examples", "prove-it-or-fail-it")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import verdict  # noqa: E402
import lint_plan  # noqa: E402
import build_tool  # noqa: E402
import answer_key as key  # noqa: E402

C = lambda *p: os.path.join(HERE, "cases", *p)


def L(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def write_json(obj, p):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)


DESIGNS = {
    "sample": (os.path.join(EX, "sample_idea.json"), os.path.join(EX, "sample_rubric.json"), os.path.join(EX, "sample_plan.json")),
    **{n: (C(n, "idea.json"), C(n, "rubric.json"), None)
       for n in ("d1_rate_split", "d2_count_split", "d3_before_after", "d4_too_small", "d5_weak_idea")},
}
EXPECTED = L(os.path.join(HERE, "expected_verdicts.json"))
READS = [k for k in EXPECTED if k.startswith("r")]
EPS = 1e-6
_cache = {}


def design(name):
    if name not in _cache:
        i, r, p = DESIGNS[name]
        _cache[name] = verdict.design(L(i), L(r), L(p) if p else None)
    return _cache[name]


def do_read(name):
    k = "read:" + name
    if k not in _cache:
        e = EXPECTED[name]
        card = copy.deepcopy(design(e["card"])["card"])
        if e.get("tamper"):
            a, b = e["tamper"].split(".")
            card["body"][a][b] += 0.01
        prev = do_read(e["previous"]) if e.get("previous") else None
        _cache[k] = verdict.read(card, L(C(name, "results.json")), prev)
    return _cache[k]


def iso(d):
    return d.isoformat()


# ---------- 1. the answer key
class AnswerKey(unittest.TestCase):
    def test_design_numbers_match_the_key(self):
        for name, planted in key.PLANTED.items():
            with self.subTest(case=name):
                k, res = key.design_key(planted), design(name)
                s, ln, d = res["sizing"], res["lines"], res["dates"]
                self.assertAlmostEqual(s["detectable"], k["detectable"], delta=EPS)
                if k["payback"] is None:
                    self.assertIsNone(s["payback"])
                else:
                    self.assertAlmostEqual(s["payback"], k["payback"], delta=EPS)
                if k["swing"] is None:
                    self.assertIsNone(s["swing"])
                else:
                    self.assertAlmostEqual(s["swing"], k["swing"], delta=EPS)
                self.assertAlmostEqual(ln["success_lift"], k["success"], delta=EPS)
                self.assertAlmostEqual(ln["kill_lift"], k["kill"], delta=EPS)
                self.assertAlmostEqual(ln["harm_lift"], k["harm"], delta=EPS)
                self.assertAlmostEqual(ln["baseline"], k["base"], delta=EPS)
                self.assertEqual((d["checkpoint"], d["day30"], d["extend_end"]), (iso(k["checkpoint"]), iso(k["day30"]), iso(k["extend_end"])))
                self.assertEqual(res["verdict"] != "Too small to read", k["readable"])
                if "multiple" in k:
                    self.assertAlmostEqual(res["too_small"]["multiple"], k["multiple"], delta=1e-4)
                    self.assertEqual(res["too_small"]["days_needed"], k["days_needed"])

    def test_read_numbers_match_the_key(self):
        for name in READS:
            e = EXPECTED[name]
            if e.get("stop"):
                continue
            with self.subTest(case=name):
                r, body = do_read(name), design(e["card"])["card"]["body"]
                res, p = L(C(name, "results.json")), key.PLANTED[e["card"]]
                if p["kind"] == "rate":
                    lift, lo, hi = key.read_rate(res["test"]["conversions"], res["test"]["volume"],
                                                 res["control"]["conversions"], res["control"]["volume"])
                elif p["design"] == "split":
                    lift, lo, hi = key.read_count(res["test"]["count"], p["share"], res["control"]["count"], 1 - p["share"])
                else:
                    h = p["history"]
                    lift, lo, hi = key.read_count(res["test"]["count"], res["day"], float(sum(h)), 7.0 * len(h))
                o = r["observed"]
                self.assertAlmostEqual(o["lift"], lift, delta=EPS)
                self.assertAlmostEqual(o["low"], lo, delta=EPS)
                self.assertAlmostEqual(o["high"], hi, delta=EPS)
                self.assertEqual(r["verdict"], key.call(res["day"], lift, lo, hi, body["lines"]["success_lift"]))


# ---------- 2. the hand-set verdicts
class HandSetVerdicts(unittest.TestCase):
    def test_design_verdicts_and_checks(self):
        for name, e in EXPECTED.items():
            if not name.startswith("d"):
                continue
            with self.subTest(case=name):
                res = design(name)
                self.assertEqual(res["verdict"], e["verdict"])
                self.assertEqual({c["key"]: c["state"] for c in res["checks"]}, e["checks"])
                if e.get("driver"):
                    self.assertEqual(res["sizing"]["driver"], e["driver"])
                self.assertEqual(bool(res.get("card")), e["verdict"] in ("Ready", "Ready with flags"))

    def test_read_verdicts(self):
        for name in READS:
            e = EXPECTED[name]
            with self.subTest(case=name):
                r = do_read(name)
                if e.get("stop"):
                    self.assertEqual(r["stop"], e["stop"])
                    continue
                self.assertEqual(r["verdict"], e["verdict"])
                if e.get("detail"):
                    self.assertTrue(r["detail"].startswith(e["detail"]), r["detail"])

    def test_sample_numbers_quoted_in_the_docs(self):
        res = design("sample")
        self.assertEqual(res["card"]["seal"], "d50f634de49d0cd6")
        self.assertEqual(verdict.fmt_pct(res["sizing"]["detectable"], True), "+33%")
        self.assertEqual(verdict.fmt_pct(res["lines"]["success"]), "4.1%")
        self.assertEqual(verdict.fmt_pct(res["lines"]["kill"]), "3.4%")
        self.assertEqual(verdict.fmt_pct(res["lines"]["harm"]), "2.1%")
        self.assertEqual(verdict.fmt_pct(res["sizing"]["payback"], True), "+10.8%")
        self.assertEqual(do_read("r3_extend")["verdict"], "Extend")


# ---------- 3. parsing
class Parsing(unittest.TestCase):
    def test_shares(self):
        self.assertEqual(verdict.parse_share("3.1%")[0], 0.031)
        self.assertEqual(verdict.parse_share(0.031)[0], 0.031)
        self.assertEqual(verdict.parse_share("50"), (0.5, "'50' read as 50%"))
        self.assertAlmostEqual(verdict.parse_share("about 3.1%")[0], 0.031)
        self.assertIn("about 3.1%", verdict.parse_share("about 3.1%")[1])
        with self.assertRaises(verdict.Unclear):
            verdict.parse_share("150%")
        self.assertEqual(verdict.parse_share("150%", allow_over_100=True)[0], 1.5)

    def test_test_share_forms(self):
        for raw, want in (("50/50", 0.5), ("60/40", 0.6), ("30 / 70", 0.3), ("50%", 0.5), (0.5, 0.5), ("50", 0.5)):
            self.assertAlmostEqual(verdict.parse_test_share(raw)[0], want, msg=raw)

    def test_unreadable_share_asks_a_question(self):
        raw = L(DESIGNS["sample"][0])
        raw["test_share"] = "half-ish"
        res = verdict.design(raw)
        self.assertEqual(res["stop"], "inputs")
        q = next(x for x in res["questions"] if x["field"] == "test_share")
        self.assertIn("What share of the audience sees the change?", q["ask"])

    def test_share_out_of_range(self):
        raw = L(DESIGNS["sample"][0])
        raw["test_share"] = "99/1"
        self.assertEqual(verdict.design(raw)["stop"], "inputs")

    def test_money_and_numbers(self):
        self.assertEqual(verdict.parse_money("$6K")[0], 6000)
        self.assertEqual(verdict.parse_money("$1.2 million")[0], 1_200_000)
        self.assertEqual(verdict.parse_number("9,000 visitors")[0], 9000)
        self.assertEqual(verdict.parse_number("9k")[0], 9000)

    def test_every_blank_asks_a_question(self):
        res = verdict.design({})
        self.assertEqual(res["stop"], "inputs")
        fields = {q["field"] for q in res["questions"]}
        for f in ("idea", "metric.name", "metric.type", "design"):
            self.assertIn(f, fields)
        for q in res["questions"]:
            self.assertTrue(q["ask"].endswith("?") or q["ask"].endswith("."), q)

    def test_missing_action_stops(self):
        raw = L(DESIGNS["sample"][0])
        raw["actions"]["stop"] = ""
        res = verdict.design(raw)
        self.assertEqual(res["stop"], "inputs")
        self.assertIn("actions.stop", [q["field"] for q in res["questions"]])

    def test_before_after_needs_twelve_weeks(self):
        raw = L(DESIGNS["d3_before_after"][0])
        raw["history"] = raw["history"][:6]
        res = verdict.design(raw)
        self.assertEqual(res["stop"], "inputs")
        self.assertIn("history", [q["field"] for q in res["questions"]])

    def test_dates(self):
        self.assertEqual(verdict.parse_date("2027-02-01")[0], date(2027, 2, 1))
        self.assertEqual(verdict.parse_date("Feb 1, 2027")[0], date(2027, 2, 1))


# ---------- 4. the card and the reads
class CardAndReads(unittest.TestCase):
    def test_untouched_card_verifies(self):
        for name in ("sample", "d1_rate_split", "d2_count_split", "d3_before_after"):
            ok, _ = verdict.verify(copy.deepcopy(design(name)["card"]))
            self.assertTrue(ok, name)

    def test_card_survives_a_json_round_trip(self):
        card = json.loads(json.dumps(design("sample")["card"]))
        self.assertTrue(verdict.verify(card)[0])

    def test_every_locked_field_is_guarded(self):
        for f in verdict.LOCKED:
            card = copy.deepcopy(design("sample")["card"])
            v = card["body"][f]
            card["body"][f] = (v + "x") if isinstance(v, str) else ({**v, "_x": 1} if isinstance(v, dict) else (v or 0) + 1)
            ok, msg = verdict.verify(card)
            self.assertFalse(ok, f)
            self.assertIn(f, msg)

    def test_tampered_card_refuses(self):
        r = do_read("r6_tampered")
        self.assertEqual(r["stop"], "seal")
        self.assertIn("lines", " ".join(r["problems"]))

    def test_no_card_on_unsealed_designs(self):
        for name in ("d4_too_small", "d5_weak_idea"):
            self.assertIsNone(design(name).get("card"))

    def test_read_carries_every_field(self):
        r = do_read("r3_extend")
        for k in ("verdict", "reason", "action", "observed", "seal", "rule", "compare", "small_sample", "no_control", "dates"):
            self.assertIn(k, r)
        self.assertEqual(r["action"], design("sample")["actions"]["extend"])

    def test_day60_needs_the_extend_read(self):
        card, res = design("sample")["card"], L(C("r5_day60", "results.json"))
        self.assertEqual(verdict.read(card, res)["stop"], "results")
        self.assertEqual(verdict.read(card, res, do_read("r1_scale"))["stop"], "results")
        self.assertEqual(verdict.read(card, res, do_read("r3_extend"))["verdict"], "Kill")

    def test_day60_kill_explains_itself(self):
        r = do_read("r5_day60")
        self.assertIn("kill number no longer applies", r["detail"])
        self.assertIn("no second Extend", r["rule"])

    def test_off_day_refuses(self):
        res = L(C("r3_extend", "results.json"))
        res["day"] = 22
        self.assertEqual(verdict.read(design("sample")["card"], res)["stop"], "results")

    def test_missing_control_refuses(self):
        res = L(C("r3_extend", "results.json"))
        del res["control"]
        self.assertEqual(verdict.read(design("sample")["card"], res)["stop"], "results")

    def test_before_after_read_is_labeled(self):
        r = do_read("r2_kill")
        self.assertTrue(r["no_control"])
        self.assertIn("12 weeks", r["compare"])

    def test_small_arm_is_flagged(self):
        res = {"day": 15, "test": {"conversions": 12, "volume": 400}, "control": {"conversions": 15, "volume": 400}}
        self.assertTrue(verdict.read(design("sample")["card"], res)["small_sample"])

    def test_slow_start_never_stops(self):
        res = {"day": 15, "test": {"conversions": 60, "volume": 2250}, "control": {"conversions": 72, "volume": 2250}}
        self.assertEqual(verdict.read(design("sample")["card"], res)["verdict"], "Keep running")


# ---------- 5. the linter
class Lint(unittest.TestCase):
    def test_designs_are_clean(self):
        for name in DESIGNS:
            self.assertEqual(lint_plan.lint(design(name), L(DESIGNS[name][0])), [], name)

    def test_reads_are_clean(self):
        for name in READS:
            if not EXPECTED[name].get("stop"):
                r = do_read(name)
                self.assertEqual(lint_plan.lint(r, None, [("reason", r["reason"]), ("rule", r["rule"]), ("compare", r["compare"])]), [], name)

    def test_clean_readout_passes(self):
        text = ("**Is this idea worth 30 days and this budget, and when do I get an answer?**\n\n"
                "Ready. Scale at 4.1% (+33%), kill at 3.4% or below. The verdict lands Mar 2, 2027.\n"
                "| Success number | 4.1% (+33%) |\n| Harm line at day 15 | 2.1% (-32.7%) |\n| Budget | $6,000 |\n"
                "Every arm is above 20 units. Reads on day 15 and day 30, 95% sure.")
        self.assertEqual(lint_plan.lint(design("sample"), L(DESIGNS["sample"][0]), [("readout", text)]), [])

    def test_catches_every_kind_of_problem(self):
        bad = "The form will produce 5.2% \u2014 a sure thing. It might reach 57 demos by Apr 30, 2027."
        probs = " ".join(lint_plan.lint(design("sample"), None, [("readout", bad)]))
        for frag in ("em-dash", "hedge word 'might'", "forecast language", "'5.2%'", "'57'", "Apr 30, 2027"):
            self.assertIn(frag, probs)

    def test_catches_an_invented_number_in_the_plan(self):
        res = copy.deepcopy(design("sample"))
        res["plan"]["risks"] = ["A 17.3% dip in traffic."]
        self.assertTrue(any("17.3%" in p for p in lint_plan.lint(res)))


# ---------- tool and files
class ToolAndFiles(unittest.TestCase):
    def build(self, res, role="ceo"):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "r.json")
            write_json(res, src)
            out, md = os.path.join(d, "t.html"), os.path.join(d, "t.md")
            subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS, "build_tool.py"), src, "--role", role, "--out", out, "--markdown", md],
                           check=True, capture_output=True)
            return read(out), read(md)

    def test_design_tool(self):
        html, md = self.build(design("sample"), "agency")
        self.assertNotIn("/*__DATA__*/null", html)
        self.assertIn('"agency"', html)
        self.assertIn("The numbers, locked before launch", md)
        self.assertIn("d50f634de49d0cd6", md)
        self.assertNotIn("\u2014", md)

    def test_unsealed_tools_say_so(self):
        for name in ("d4_too_small", "d5_weak_idea"):
            _, md = self.build(design(name))
            self.assertIn("not locked", md, name)
            self.assertNotIn("locked before launch", md, name)
            self.assertNotIn("## Reads", md, name)

    def test_read_tool_is_lift_first(self):
        _, md = self.build(do_read("r5_day60"))
        self.assertIn("| Line | Lift | Value |", md)
        self.assertNotIn("Kill number", md)
        _, md30 = self.build(do_read("r3_extend"))
        self.assertIn("Kill number, day 30 only", md30)

    def test_count_read_shows_raw_counts(self):
        r = verdict.read(design("d2_count_split")["card"], {"day": 30, "test": {"count": "300"}, "control": {"count": "230"}})
        md = build_tool.markdown(r)
        self.assertIn("Counted: 300 in the test group, 230 in the control group", md)
        self.assertEqual(lint_plan.lint(r, None, [("md", md)]), [])

    def test_lint_passes_on_every_markdown(self):
        for name in DESIGNS:
            self.assertEqual(lint_plan.lint(design(name), L(DESIGNS[name][0]), [("md", build_tool.markdown(design(name)))]), [], name)
        for name in READS:
            if not EXPECTED[name].get("stop"):
                self.assertEqual(lint_plan.lint(do_read(name), None, [("md", build_tool.markdown(do_read(name)))]), [], name)

    def test_skill_frontmatter_and_no_em_dashes(self):
        md = read(os.path.join(SKILL, "SKILL.md"))
        m = re.search(r"^---\s*\nname:\s*(.+?)\s*\ndescription:\s*(.+?)\s*\n---", md, re.S)
        self.assertEqual(m.group(1), "prove-it-or-fail-it")
        self.assertLess(len(m.group(2)), 1024)
        for base in (SKILL, EX, HERE):
            for root, _, files in os.walk(base):
                for f in files:
                    if f.endswith((".md", ".py", ".html")):
                        self.assertNotIn("\u2014", read(os.path.join(root, f)), f)


# ---------- 6. snapshots
SNAP_DESIGN = ("verdict", "sizing", "lines", "dates", "planned", "too_small", "checks", "notes", "warnings", "card")
SNAP_READ = ("verdict", "detail", "action", "observed", "reason", "rule", "compare", "small_sample", "no_control", "seal", "stop", "problems")


def snapshot(res, keys):
    return json.loads(json.dumps({k: res.get(k) for k in keys}))


class Snapshots(unittest.TestCase):
    def test_outputs_match_snapshots(self):
        for name, keys, fn in [(n, SNAP_DESIGN, design) for n in DESIGNS] + [(n, SNAP_READ, do_read) for n in READS]:
            with self.subTest(case=name):
                p = os.path.join(HERE, "expected", name + ".json")
                self.assertTrue(os.path.exists(p), f"missing snapshot {p}; run with --update")
                self.assertEqual(snapshot(fn(name), keys), L(p))


def update():
    os.makedirs(os.path.join(HERE, "expected"), exist_ok=True)
    for name in DESIGNS:
        write_json(snapshot(design(name), SNAP_DESIGN), os.path.join(HERE, "expected", name + ".json"))
    for name in READS:
        write_json(snapshot(do_read(name), SNAP_READ), os.path.join(HERE, "expected", name + ".json"))
    print("Snapshots written to", os.path.join(HERE, "expected"))


if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main(verbosity=1)
