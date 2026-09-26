"""Regression tests for campaign-brief-builder.

Run from the repo root:  python tests/campaign-brief-builder/test_plan.py
Standard library only. The skill uses no third-party library, so no library version can move a number.
Checked on Python 3.10, 3.11, 3.12 and 3.13.

Six layers:
  1. The answer key (answer_key.py): every funnel, timing and capacity number is recomputed from the planted
     values with separate code, exact fractions and day-by-day dates, and must match the skill.
  2. The hand-set states (expected_checks.json): all ten checks and the verdict for every case, written before the build.
  3. Parsing: the user's own words, hedges, units, ambiguous dates, currency, the messy file's questions.
  4. The brief: IDs, dates, budgets, UTMs, the trace both ways, and every way a brief can be refused.
  5. The linter: it passes clean text and catches invented numbers, dates, em-dashes, hedges, forecasts and unlabeled assumptions.
  6. Snapshots in expected/ stop the output drifting. Rebuild them with --update after a deliberate change.
"""
import copy, json, os, re, subprocess, sys, tempfile, unittest
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SKILL = os.path.join(ROOT, "skills", "campaign-brief-builder")
SCRIPTS = os.path.join(SKILL, "scripts")
EX = os.path.join(ROOT, "examples", "campaign-brief-builder")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import plan  # noqa: E402
import lint_brief  # noqa: E402
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
RUNS = {
    "sample": (os.path.join(EX, "sample_strategy.json"), os.path.join(EX, "sample_rubric.json")),
    "case1_strong": (C("case1_strong", "strategy.json"), C("case1_strong", "rubric.json")),
    "case2_weak": (C("case2_weak", "strategy.json"), C("case2_weak", "rubric.json")),
    "case3_messy_resolved": (C("case3_messy", "strategy_resolved.json"), C("case3_messy", "rubric.json")),
    "case4_assumptions": (C("case4_assumptions", "strategy.json"), C("case4_assumptions", "rubric.json")),
    "case5_cycle_trap": (C("case5_cycle_trap", "strategy.json"), C("case5_cycle_trap", "rubric.json")),
    "case6_round1": (C("case6_two_rounds", "strategy_round1.json"), C("case6_two_rounds", "rubric_round1.json")),
    "case6_round2": (C("case6_two_rounds", "strategy_round2.json"), C("case6_two_rounds", "rubric_round2.json")),
}
EXPECTED = L(os.path.join(HERE, "expected_checks.json"))
_cache = {}


def run(name):
    if name not in _cache:
        s, r = RUNS[name]
        _cache[name] = plan.check(L(s), L(r))
    return _cache[name]


def sample_brief(lead=None):
    return plan.brief(run("sample"), L(os.path.join(EX, "sample_brief.json")), lead)


class AnswerKey(unittest.TestCase):
    def test_every_number_matches_the_independent_key(self):
        for name in RUNS:
            with self.subTest(case=name):
                res, k = run(name), key.key(key.PLANTED[name])
                f, t = res["funnel"], res["timing"]
                self.assertEqual(f["planned_leads"], k["planned_leads"])
                self.assertEqual(f["opps_needed"], k["opps_needed"])
                self.assertEqual(f["leads_needed"], k["leads_needed"])
                self.assertEqual(f["extra_budget"], k["extra_budget"])
                for mine, theirs in [(f["planned_opps"], k["planned_opps"]), (f["planned_pipeline"], k["planned_pipeline"]),
                                     (f["gap"], k["gap"]), (f["blended_cpl"], k["blended_cpl"]), (f["cpl_ceiling"], k["cpl_ceiling"]),
                                     (t["pipeline_in_time"], k["pipeline_in_time"]), (res["monthly_opps"], k["monthly_opps"])]:
                    self.assertAlmostEqual(mine, theirs, places=4)
                self.assertEqual(t["weeks_late"], k["weeks_late"])
                self.assertEqual(date.fromisoformat(t["last_land"]), k["last_land"])
                for c in res["channels"]:
                    self.assertEqual(c["leads"], k["channel_leads"][c["name"]])
                    self.assertAlmostEqual(c["opps"], k["channel_opps"][c["name"]], places=6)
                if "projected_revenue" in k:
                    self.assertAlmostEqual(res["revenue"]["projected"], k["projected_revenue"], places=4)

    def test_script_check_states_match_the_key(self):
        for name in RUNS:
            with self.subTest(case=name):
                self.assertEqual([c["state"] for c in run(name)["checks"][:4]], key.key(key.PLANTED[name])["states"])

    def test_pacing_adds_up(self):
        for name in RUNS:
            with self.subTest(case=name):
                res = run(name)
                self.assertEqual(sum(p["leads"] for p in res["pacing"]), res["funnel"]["planned_leads"])
                self.assertAlmostEqual(res["pacing"][-1]["pipeline_cum"], res["funnel"]["planned_pipeline"], places=4)
                self.assertAlmostEqual(sum(p["spend"] for p in res["pacing"]), res["funnel"]["budget"], places=4)
                self.assertAlmostEqual(sum(l["opps"] for l in res["landings"] if l["in_time"]), res["timing"]["opps_in_time"], places=6)
                self.assertEqual(len(res["landings"]), res["inputs"]["weeks"])


class HandSetStates(unittest.TestCase):
    def test_all_ten_checks_and_the_verdict(self):
        for name in RUNS:
            with self.subTest(case=name):
                res, exp = run(name), EXPECTED[name]
                self.assertEqual([c["state"] for c in res["checks"]], [exp["checks"][str(i)] for i in range(1, 11)])
                self.assertEqual(res["verdict"], exp["verdict"])

    def test_verdict_precedence(self):
        mk = lambda *s: [{"state": x} for x in s]
        self.assertEqual(plan.verdict_for(mk("pass", "fail", "flag"), ["funnel.avg_deal"]), "Not ready")
        self.assertEqual(plan.verdict_for(mk("pass", "flag"), ["funnel.avg_deal"]), "Untested")
        self.assertEqual(plan.verdict_for(mk("pass", "flag"), []), "Ready with flags")
        self.assertEqual(plan.verdict_for(mk("pass", "pass"), []), "Ready")

    def test_without_a_rubric_the_verdict_waits(self):
        res = plan.check(L(RUNS["sample"][0]))
        self.assertEqual(res["verdict"], "Pending rubric")
        self.assertEqual(len(res["checks"]), 4)

    def test_rubric_problems_stop_the_check(self):
        rub = L(RUNS["sample"][1])
        del rub["checks"]["7"]
        rub["checks"]["8"] = {"state": "flag", "reason": "Silent on reach.", "fix": ""}
        res = plan.check(L(RUNS["sample"][0]), rub)
        self.assertEqual(res["stop"], "rubric")
        self.assertTrue(any("Check 7" in p for p in res["problems"]))
        self.assertTrue(any("Check 8" in p and "fix" in p for p in res["problems"]))

    def test_round_two_reports_what_changed(self):
        r1 = run("case6_round1")
        r2 = plan.check(L(RUNS["case6_round2"][0]), L(RUNS["case6_round2"][1]), r1)
        self.assertEqual(r2["round"], 2)
        what = {c["what"]: (c["from"], c["to"]) for c in r2["changes"]}
        self.assertEqual(what["Check 1: Target reachable on budget"], ("Fail", "Pass"))
        self.assertEqual(what["Check 9: Tracking to pipeline defined"], ("Fail", "Pass"))
        self.assertEqual(what["Budget"], ("$30K", "$35K"))
        self.assertEqual(what["Content syndication budget"], ("$10K", "$15K"))
        self.assertEqual(what["Verdict"], ("Not ready", "Ready"))
        self.assertEqual(what["Pipeline the plan buys"], ("$720K", "$920K"))
        self.assertIn("Tracking", what)

    def test_small_plans_warn(self):
        self.assertTrue(run("case2_weak")["small_sample"])
        self.assertTrue(any("fewer than 20" in w for w in run("case2_weak")["warnings"]))
        self.assertFalse(run("sample")["small_sample"])

    def test_sections_follow_channels_and_the_offer(self):
        f = run("sample")["functions"]
        self.assertFalse(f["pr"]["active"])
        self.assertIn("Not in this campaign", f["pr"]["because"])
        self.assertTrue(all(f[x]["active"] for x in ("ads", "content", "operations", "sales", "creative")))
        self.assertTrue(all(v["active"] for v in run("case1_strong")["functions"].values()))
        self.assertFalse(run("case2_weak")["functions"]["content"]["active"])
        self.assertTrue(run("case4_assumptions")["functions"]["content"]["active"])  # the calculator is an asset


class Parsing(unittest.TestCase):
    def test_money(self):
        for raw, want in [("$90k", 90000), ("90,000", 90000), ("$1.2M", 1.2e6), ("$1.2 million", 1.2e6), ("about $300", 300),
                          ("around $500", 500), ("$220 a lead", 220), ("~$40k", 40000), (35000, 35000), ("$87.5K", 87500)]:
            self.assertAlmostEqual(plan.parse_money(raw)[0], want, msg=raw)
        for raw in ("€40,000", "TBD", "", None, "40 GBP"):
            with self.assertRaises(plan.Unclear, msg=raw):
                plan.parse_money(raw)

    def test_rates_days_counts(self):
        self.assertAlmostEqual(plan.parse_rate("8%")[0], 0.08)
        self.assertAlmostEqual(plan.parse_rate("8")[0], 0.08)
        self.assertAlmostEqual(plan.parse_rate(0.08)[0], 0.08)
        self.assertAlmostEqual(plan.parse_rate("about 8% of leads")[0], 0.08)
        with self.assertRaises(plan.Unclear):
            plan.parse_rate("140%")
        self.assertEqual(plan.parse_days("3 weeks")[0], 21)
        self.assertEqual(plan.parse_days("about 10 weeks")[0], 70)
        self.assertEqual(plan.parse_days("usually in about 10 days")[0], 10)
        self.assertEqual(plan.parse_count("2 AEs"), 2)
        self.assertEqual(plan.parse_count("8 new opportunities each a month"), 8)

    def test_dates(self):
        self.assertEqual(plan.parse_date("2027-03-31")[0], date(2027, 3, 31))
        self.assertEqual(plan.parse_date("June 30, 2027")[0], date(2027, 6, 30))
        self.assertEqual(plan.parse_date("30 June 2027")[0], date(2027, 6, 30))
        self.assertEqual(plan.parse_date("07/31/2027")[0], date(2027, 7, 31))
        self.assertEqual(plan.parse_date("31/07/2027")[0], date(2027, 7, 31))
        with self.assertRaises(plan.Unclear) as e:
            plan.parse_date("04/05/2027")
        self.assertEqual(str(e.exception), "ambiguous")

    def test_run_length(self):
        launch = date(2027, 4, 5)
        self.assertEqual(plan.parse_run("10 weeks", launch)[0], 10)
        self.assertEqual(plan.parse_run("3 months", launch)[0], 13)
        self.assertEqual(plan.parse_run("2027-06-13", launch)[0], 10)

    def test_messy_file_asks_the_right_questions(self):
        res = plan.check(L(C("case3_messy", "strategy.json")))
        self.assertEqual(res["stop"], key.MESSY_RAW["stop"])
        self.assertEqual([q["field"] for q in res["questions"]], key.MESSY_RAW["question_fields"])
        notes = " ".join(res["notes"])
        for frag in key.MESSY_RAW["notes_contain"]:
            self.assertIn(frag, notes)
        asks = " ".join(q["ask"] for q in res["questions"])
        self.assertIn("Apr 5, 2027 or May 4, 2027", asks)
        self.assertIn("$72,500", asks)  # exact dollars in a question, never rounded

    def test_blank_and_bad_fields_become_questions(self):
        raw = L(RUNS["sample"][0])
        raw["funnel"]["avg_deal"] = ""
        raw["channels"][0]["type"] = "tiktok"
        raw["assumptions"] = ["sales.reps"]
        raw["target"]["due_date"] = "2026-12-01"
        fields = [q["field"] for q in plan.check(raw)["questions"]]
        for f in ("funnel.avg_deal", "channels.LinkedIn ads.type", "assumptions", "target.due_date"):
            self.assertIn(f, fields)

    def test_zero_budget_channel_is_flagged_not_asked(self):
        raw = L(RUNS["sample"][0])
        raw["channels"].append({"name": "House email", "type": "email", "budget": "$0", "cost_per_lead": ""})
        raw["budget_total"] = ""
        res = plan.check(raw)
        self.assertNotIn("stop", res)
        c3 = res["checks"][2]
        self.assertEqual(c3["state"], "flag")
        self.assertIn("House email has no budget", c3["reason"])

    def test_text_is_clean(self):
        res = run("case1_strong")
        for l in res["strategy_lines"]:
            self.assertNotIn("..", l["text"])
        slug_ok = re.compile(r"^[a-z0-9-]+$")
        self.assertTrue(slug_ok.match(res["campaign"]["audience_tag"]))
        self.assertEqual(plan.slug("Pillarmint spring push", 20), "pillarmint-spring")
        self.assertEqual(plan.slug("ops and logistics directors", 16), "ops")


class Brief(unittest.TestCase):
    def test_sample_brief_builds(self):
        b = sample_brief()
        self.assertNotIn("stop", b)
        br = b["brief"]
        ids = [r["id"] for r in br["requirements"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[:3], ["ADS-01", "ADS-02", "ADS-03"])
        self.assertTrue(br["reconciliation"]["ok"])
        self.assertEqual(br["unassigned"], [])
        self.assertEqual(br["dependency_conflicts"], [])
        self.assertEqual(br["stamp"], "Ready with flags")
        self.assertEqual([s["function"] for s in br["sections"]], plan.FUNCTIONS)
        self.assertFalse(next(s for s in br["sections"] if s["function"] == "pr")["active"])

    def test_due_dates_count_back_from_launch(self):
        br = sample_brief()["brief"]
        launch = date(2027, 1, 11)
        for r in br["requirements"]:
            if r["when"] == "pre-launch":
                self.assertEqual(date.fromisoformat(r["due"]), launch - timedelta(days=plan.DEFAULT_LEAD_DAYS[r["function"]]), r["id"])
            if r["when"] == "ongoing":
                self.assertIsNone(r["due"])
        edited = sample_brief({"creative": "4 weeks"})["brief"]
        cre = [r for r in edited["requirements"] if r["function"] == "creative" and r["when"] == "pre-launch"]
        self.assertTrue(all(r["due"] == "2026-12-14" for r in cre))
        src = {x["function"]: x["source"] for x in edited["lead_times"]}
        self.assertEqual(src["creative"], "Edited by the user")
        self.assertEqual(src["ads"], "As shipped")

    def test_budgets_and_utms(self):
        br = sample_brief()["brief"]
        carried = [r for r in br["requirements"] if r["budget"] is not None]
        self.assertEqual(sorted(r["budget"] for r in carried), [15000, 15000, 20000, 40000])
        self.assertTrue(all(r["budget_label"] == "No separate budget" for r in br["requirements"] if r["budget"] is None))
        ads1 = br["requirements"][0]
        self.assertEqual(ads1["utm"]["query"], "?utm_source=linkedin&utm_medium=paid_social&utm_campaign=brasswick-q1_pipeline_cfo-mfg_202701&utm_content=ads-01")
        self.assertTrue(all(r["utm"] is None for r in br["requirements"] if r["function"] == "operations"))

    def test_own_utm_convention(self):
        raw = L(RUNS["sample"][0])
        raw["utm_convention"] = {"campaign": "{yyyymm}-{campaign_id}", "source": "{channel}"}
        res = plan.check(raw, L(RUNS["sample"][1]))
        br = plan.brief(res, L(os.path.join(EX, "sample_brief.json")))["brief"]
        u = br["requirements"][0]["utm"]
        self.assertEqual((u["campaign"], u["source"], u["medium"]), ("202701-brasswick-q1", "linkedin-ads", "paid_social"))

    def test_tracking_task_is_added(self):
        ops1 = sample_brief()["brief"]["requirements"]
        auto = [r for r in ops1 if r["auto"]]
        self.assertEqual(len(auto), 1)
        self.assertEqual(auto[0]["traces_to"], "K1")
        self.assertIn("brasswick-q1", auto[0]["requirement"])

    def test_untested_brief_carries_assumption_tasks(self):
        res = run("case4_assumptions")
        spec = {"approval": {"name": "Nia Brooks", "seat": "Head of Growth", "date": "2026-09-26"}, "requirements": [
            {"key": "a", "function": "ads", "traces_to": "C1", "channel": "C1", "carries_budget": True, "requirement": "Search.", "acceptance": "Live."},
            {"key": "b", "function": "ads", "traces_to": "C2", "channel": "C2", "carries_budget": True, "requirement": "LinkedIn.", "acceptance": "Live."},
            {"key": "c", "function": "content", "traces_to": "O1", "requirement": "Calculator.", "acceptance": "Built."},
            {"key": "d", "function": "creative", "traces_to": "M1", "requirement": "Concepts.", "acceptance": "Approved."},
            {"key": "e", "function": "sales", "traces_to": "A1", "requirement": "Talk track.", "acceptance": "Run."},
            {"key": "f", "function": "ops", "traces_to": "T1", "requirement": "Dashboard.", "acceptance": "Live."}]}
        b = plan.brief(res, spec)
        self.assertNotIn("stop", b)
        br = b["brief"]
        self.assertEqual(br["stamp"], "Untested")
        tasks = [r for r in br["requirements"] if r["auto"] and "Assumption" in r["requirement"]]
        self.assertEqual(len(tasks), 4)
        cpl = next(r for r in tasks if "LinkedIn ads" in r["requirement"])
        self.assertEqual(cpl["due"], "2027-07-18")        # end of week one
        self.assertEqual(cpl["traces_to"], "C2")
        self.assertEqual(cpl["function"], "ads")           # the team that runs the channel measures its cost per lead
        rate = next(r for r in tasks if "lead-to-opportunity" in r["requirement"])
        self.assertEqual(rate["due"], res["timing"]["first_land"])  # cannot be measured before the first opportunities land
        self.assertEqual(len(br["unassigned"]), len(br["requirements"]))

    def test_owners_and_named_risks(self):
        br = sample_brief()["brief"]
        r1 = next(r for r in br["risks"] if "R1" in r["source"])
        con = next(r for r in br["requirements"] if r.get("prevents") == "R1")
        self.assertEqual(r1["fix"], "See " + con["id"])
        spec = L(os.path.join(EX, "sample_brief.json"))
        spec["owners"] = {"Sales enablement": "Jo Park"}
        br2 = plan.brief(run("sample"), spec)["brief"]
        self.assertTrue(all(r["owner"] == "Jo Park" for r in br2["requirements"] if r["function"] == "sales"))
        spec["owners"] = {"marketing": "Jo Park"}
        self.assertIn("not a function", " ".join(plan.brief(run("sample"), spec)["problems"]))
        spec["owners"] = {}
        spec["requirements"][0]["prevents"] = "R9"
        self.assertIn("not a named risk", " ".join(plan.brief(run("sample"), spec)["problems"]))

    def test_refusals(self):
        spec = L(os.path.join(EX, "sample_brief.json"))
        self.assertEqual(plan.brief(run("case2_weak"), spec)["stop"], "blocked")
        self.assertEqual(plan.brief(plan.check(L(RUNS["sample"][0])), spec)["stop"], "brief")

        def problems(mutate):
            s = copy.deepcopy(spec)
            mutate(s)
            out = plan.brief(run("sample"), s)
            self.assertEqual(out.get("stop"), "brief")
            return " ".join(out["problems"])

        self.assertIn("not a strategy line", problems(lambda s: s["requirements"][0].update(traces_to="Z9")))
        self.assertIn("no acceptance test", problems(lambda s: s["requirements"][1].update(acceptance="")))
        self.assertIn("not in this campaign", problems(lambda s: s["requirements"][1].update(function="pr")))
        self.assertIn("Exactly one requirement must carry it; 0 do", problems(lambda s: s["requirements"][0].update(carries_budget=False)))
        self.assertIn("2 do", problems(lambda s: s["requirements"][1].update(carries_budget=True)))
        self.assertIn("does not exist", problems(lambda s: s["requirements"][0].update(depends_on=["nope"])))
        self.assertIn("loop", problems(lambda s: (s["requirements"][0].update(depends_on=["cre-li"]),
                                                   next(r for r in s["requirements"] if r["key"] == "cre-li").update(depends_on=["ads-li"]))))
        self.assertIn("has no requirement", problems(lambda s: s.update(requirements=[r for r in s["requirements"] if r["traces_to"] != "A1"])))
        self.assertIn("approver's name", problems(lambda s: s["approval"].update(name="")))

    def test_dependency_conflict_is_reported(self):
        s = L(os.path.join(EX, "sample_brief.json"))
        next(r for r in s["requirements"] if r["key"] == "cre-li")["depends_on"] = ["ads-li"]
        next(r for r in s["requirements"] if r["key"] == "ads-li")["depends_on"] = ["ops-form"]
        br = plan.brief(run("sample"), s)["brief"]
        self.assertTrue(any(x.startswith("CRE-01") for x in br["dependency_conflicts"]))


class Lint(unittest.TestCase):
    def test_sample_brief_is_clean(self):
        self.assertEqual(lint_brief.lint(sample_brief(), L(RUNS["sample"][0])), [])

    def test_clean_readout_passes(self):
        text = ("**Ready with flags.** The plan buys $1.68M in pipeline against a $1.2M target. $1.34M lands by Mar 31, 2027.\n"
                "| Leads needed | 500 |\n| Leads the plan buys | 700 |\n| Cost per lead ceiling | $180 |\n56 expected opportunities, 24.3 a month.")
        self.assertEqual(lint_brief.lint(run("sample"), L(RUNS["sample"][0]), [("readout", text)]), [])

    def test_catches_every_kind_of_problem(self):
        bad = ("The campaign will produce $2.4M \u2014 a sure thing. It might reach 63 opportunities by Apr 30, 2027.")
        probs = " ".join(lint_brief.lint(run("sample"), None, [("readout", bad)]))
        for frag in ("em-dash", "hedge word 'might'", "forecast language", "'$2.4M'", "'63'", "Apr 30, 2027"):
            self.assertIn(frag, probs)

    def test_catches_an_invented_number_in_a_requirement(self):
        b = sample_brief()
        b["brief"]["requirements"][1]["requirement"] = "Pause any ad set above $215 a lead."
        self.assertTrue(any("$215" in p for p in lint_brief.lint(b)))

    def test_catches_an_unlabeled_assumption(self):
        res = run("case4_assumptions")
        self.assertTrue(any("assumed number" in p for p in lint_brief.lint(res, None, [("r", "LinkedIn costs $160 a lead.")])))
        self.assertEqual(lint_brief.lint(res, None, [("r", "LinkedIn costs $160 a lead (Assumption).")]), [])

    def test_blind_run_fixtures_stay_clean(self):
        for name in ("case1_strong", "case2_weak", "case5_cycle_trap"):
            self.assertEqual(lint_brief.lint(run(name)), [], name)


class ToolAndFiles(unittest.TestCase):
    def test_tool_builds_with_data_markdown_and_csv(self):
        b = sample_brief()
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "b.json")
            write_json(b, src)
            out, md = os.path.join(d, "t.html"), os.path.join(d, "t.md")
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_tool.py"), src, "--role", "cro", "--out", out, "--markdown", md],
                           check=True, capture_output=True)
            html = read(out)
            self.assertNotIn("/*__DATA__*/null", html)
            self.assertIn('let ROLE = "cro"', html)
            text = read(md)
            for r in b["brief"]["requirements"]:
                self.assertIn(r["id"], text)
            self.assertIn("Not in this campaign", text)
            self.assertNotIn("\u2014", text)
        rows = build_tool.requirements_csv(b).strip().split("\n")
        self.assertEqual(len(rows), len(b["brief"]["requirements"]) + 1)

    def test_lead_time_table_matches_the_script(self):
        md = read(os.path.join(SKILL, "references", "lead-times.md"))
        names = {v: k for k, v in plan.FUNCTION_NAMES.items()}
        found = {names[m.group(1)]: int(m.group(2)) for m in re.finditer(r"^\| ([A-Za-z ]+) \| (\d+) \|", md, re.M)}
        self.assertEqual(found, plan.DEFAULT_LEAD_DAYS)

    def test_channel_types_documented(self):
        md = read(os.path.join(SKILL, "references", "strategy-template.md"))
        for t in plan.CHANNEL_TYPES:
            self.assertIn(t, md)

    def test_skill_frontmatter(self):
        md = read(os.path.join(SKILL, "SKILL.md"))
        m = re.search(r"^---\s*\nname:\s*(.+?)\s*\ndescription:\s*(.+?)\s*\n---", md, re.S)
        self.assertEqual(m.group(1), "campaign-brief-builder")
        self.assertLess(len(m.group(2)), 1024)
        for root, _, files in os.walk(SKILL):
            for f in files:
                if f.endswith((".md", ".py", ".html")):
                    self.assertNotIn("\u2014", read(os.path.join(root, f)), f)


# ---------- snapshots
SNAP_KEYS = ("funnel", "timing", "landings", "checks", "verdict", "strategy_lines", "channels", "functions", "notes", "warnings")


def snapshot(res):
    return {k: res.get(k) for k in SNAP_KEYS}


class Snapshots(unittest.TestCase):
    def test_outputs_match_snapshots(self):
        for name in RUNS:
            with self.subTest(case=name):
                p = os.path.join(HERE, "expected", name + ".json")
                self.assertTrue(os.path.exists(p), f"missing snapshot {p}; run with --update")
                self.assertEqual(json.loads(json.dumps(snapshot(run(name)))), L(p))
        p = os.path.join(HERE, "expected", "sample_brief.json")
        self.assertEqual(json.loads(json.dumps(sample_brief()["brief"])), L(p))


def update():
    os.makedirs(os.path.join(HERE, "expected"), exist_ok=True)
    for name in RUNS:
        write_json(snapshot(run(name)), os.path.join(HERE, "expected", name + ".json"))
    write_json(sample_brief()["brief"], os.path.join(HERE, "expected", "sample_brief.json"))
    print("Snapshots written to", os.path.join(HERE, "expected"))


if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main(verbosity=1)
