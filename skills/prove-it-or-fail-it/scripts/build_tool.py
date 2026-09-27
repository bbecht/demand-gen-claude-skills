#!/usr/bin/env python3
"""Build the interactive Prove It or Fail It tool and the Markdown test plan.

Usage:
  python build_tool.py design.json|read.json --role ceo|marketing|revops|agency --out prove_it.html [--markdown test_plan.md]

The Markdown is built here once and embedded in the tool, so the tool's export hands back exactly the same file.
Standard library only.
"""
import json, os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict import fmt_money, fmt_pct, fmt_count, fmt_date, fmt_value, ACTIONS  # noqa: E402

ROLES = ("ceo", "marketing", "revops", "agency")
SIGN = "*Built by Marketing Systems Guild. Turning strangers into clients.*"


def d(s):
    return fmt_date(date.fromisoformat(s)) if s else ""


def cell(s):
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ")


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return "\n".join(out + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows])


def card_rows(b):
    m, L, D = b["metric"], b["lines"], b["dates"]
    return [["Baseline", fmt_value(m, L["baseline"])],
            ["Success number", f"{fmt_value(m, L['success'])} ({fmt_pct(L['success_lift'], True)})"],
            ["Kill number, day 30", f"{fmt_value(m, L['kill'])} ({fmt_pct(L['kill_lift'], True)})"],
            ["Harm line at day 15", f"{fmt_value(m, L['harm'])} ({fmt_pct(L['harm_lift'], True)})"],
            ["Launch", d(D["launch"])], ["Day-15 check", d(D["checkpoint"])], ["Day-30 verdict", d(D["day30"])],
            ["Extend ends", d(D["extend_end"])]]


def markdown(res):
    L = []
    if res["mode"] == "design":
        L += [f"# Test plan: {res['idea']}", "", f"**Verdict: {res['verdict']}.** Metric: {res['metric']['name']} ({res['metric']['type']}). "
              + ("Split test, " + fmt_pct(res["test_share"]) + " of the audience sees the change." if res["design"] == "split"
                 else "Before and after. No control.")]
        if res.get("card"):
            L.append(f"Sealed. Seal `{res['card']['seal']}`. Keep card.json: every read needs it.")
        for w in res.get("warnings") or []:
            L += ["", f"> {w}"]
        if res.get("too_small"):
            L += ["", "## Too small to read", "", "No card was sealed. Three fixes:", ""] + [f"- {x}." for x in res["too_small"]["fixes"]]
        sealed = bool(res.get("card"))
        if not sealed and not res.get("too_small"):
            L += ["", f"No card was sealed. The verdict is {res['verdict']}. Fix what the checks below name and run the design again."]
        rows = card_rows(res) if sealed else [r for r in card_rows(res) if r[0] in ("Baseline", "Success number", "Kill number, day 30", "Harm line at day 15")]
        L += ["", "## The numbers, locked before launch" if sealed else "## The numbers at these inputs, not locked", "", table(["Line", "Value"], rows)]
        s = res["sizing"]
        L += ["", table(["What sets the bar", "Lift"], [["Smallest lift 30 days can detect", fmt_pct(s["detectable"], True)],
                                                        ["Lift that pays back the budget", fmt_pct(s["payback"], True) if s["payback"] is not None else "Not run: no value per unit"],
                                                        ["The business's own swing", fmt_pct(s["swing"], True) if s["swing"] is not None else "Split test: not needed"],
                                                        ["The lift you expect", fmt_pct(res["inputs"]["expected_lift"], True)]])]
        L += ["", f"The success number is set by the {({'detectable': 'smallest detectable lift', 'payback': 'payback lift', 'swing': 'business swing'})[s['driver']]}."]
        L += ["", "## What happens on each verdict", "", table(["Verdict", "Agreed action"], [[ACTIONS[k].replace("On ", ""), res["actions"].get(k, "")] for k in ACTIONS])]
        L += ["", "## The checks", "", table(["Check", "State", "Reason", "Fix"],
                                              [[c["name"], c["state"].capitalize() + (", not run" if c.get("not_run") else ""), c["reason"], c["fix"]] for c in res["checks"]])]
        p = res.get("plan") or {}
        if p:
            L += ["", "## The plan", ""]
            for k, label in (("change", "The change"), ("who_sees_it", "Who sees it"), ("split", "How people are assigned"),
                             ("metric_definition", "What counts"), ("counted_in", "Where it is counted")):
                if p.get(k):
                    L.append(f"- **{label}:** {p[k]}")
            if p.get("setup"):
                L += ["", "**Setup**", ""] + [f"{i + 1}. {x}" for i, x in enumerate(p["setup"])]
            if p.get("risks"):
                L += ["", "**Risks**", ""] + [f"- {x}" for x in p["risks"]]
        pl = res["planned"]
        if not sealed:
            pl = None
    if res["mode"] == "design" and pl:
        unit = "people" if res["metric"]["type"] == "rate" else res["metric"]["unit"] + "s"
        L += ["", "## Reads", "", table(["Read", "Date", "Expected " + unit + " so far"],
                                          [["Day 15", d(res["dates"]["checkpoint"]), f"test {fmt_count(pl['test_day15'])}, control {fmt_count(pl['control_day15'])}"],
                                           ["Day 30", d(res["dates"]["day30"]), f"test {fmt_count(pl['test'])}, control {fmt_count(pl['control'])}"]])]
    if res["mode"] != "design":
        b = res["card"]["body"]
        o = res["observed"]
        L += [f"# Day {res['day']} read: {res['idea']}", "", f"**Verdict: {res['verdict']}.** {res['reason']}"]
        if res.get("detail"):
            L.append(res["detail"])
        if res.get("action"):
            L += ["", f"**Agreed action:** {res['action']}"]
        if res.get("no_control"):
            L += ["", "> No control. This verdict cannot rule out what else changed in the test period."]
        if res.get("small_sample"):
            L += ["", "> An arm has fewer than 20 " + res["metric"]["unit"] + "s. Read counts, not rates."]
        m, ln = res["metric"], b["lines"]
        other = "Control" if res["design"] == "split" else "Before"
        rows = [["Success number", fmt_pct(ln["success_lift"], True), fmt_value(m, ln["success"])]]
        if res["day"] == 30:
            rows.append(["Kill number, day 30 only", fmt_pct(ln["kill_lift"], True), fmt_value(m, ln["kill"])])
        if res["day"] == 15:
            rows.append(["Harm line, day 15 only", fmt_pct(ln["harm_lift"], True), fmt_value(m, ln["harm"])])
        result = f"Test {fmt_value(m, o['test_value'])} against {other.lower()} {fmt_value(m, o['control_value'])}"
        if m["type"] == "count":
            rt, rc = (res.get("results") or {}).get("test") or {}, (res.get("results") or {}).get("control") or {}
            counted = f"{rt.get('count')} in the test group" + (f", {rc.get('count')} in the control group" if rc.get("count") is not None else "")
            result += f", scaled to the whole audience. Counted: {counted}"
        rows += [["Result", fmt_pct(o["lift"], True), result],
                 ["Range, 95% sure", f"{fmt_pct(o['low'], True)} to {fmt_pct(o['high'], True)}", ""]]
        L += ["", table(["Line", "Lift", "Value"], rows)]
        L += ["", res.get("compare", ""), "", res.get("rule", "")]
        L += ["", f"Card seal `{res['seal']}` intact."]
    L += ["", "A verdict is about this test in this period, not a forecast.", "", SIGN, ""]
    return "\n".join(L)


def main():
    if len(sys.argv) < 2 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 else 1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("stop"):
        sys.exit("Stopped (" + data["stop"] + "). Resolve it before building the tool.")
    arg = lambda k, dflt=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else dflt
    role = arg("--role", "ceo")
    role = role if role in ROLES else "ceo"
    out = arg("--out", "prove_it.html")
    md = markdown(data)
    if arg("--markdown"):
        with open(arg("--markdown"), "w", encoding="utf-8") as fh:
            fh.write(md)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "tool_template.html"), encoding="utf-8") as fh:
        tpl = fh.read()
    esc = lambda o: json.dumps(o, default=str, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", esc(data)).replace('/*__ROLE__*/"ceo"', json.dumps(role)).replace('/*__MD__*/""', esc(md))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Tool written to " + out + (", Markdown to " + arg("--markdown") if arg("--markdown") else ""))


if __name__ == "__main__":
    main()
