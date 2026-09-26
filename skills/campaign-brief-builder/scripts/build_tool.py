#!/usr/bin/env python3
"""Build the interactive Campaign Brief Builder tool, the Markdown brief and the requirements CSV.

Usage:
  python build_tool.py result.json|brief_result.json --role ceo|marketing|agency|cro --out campaign_brief.html [--markdown campaign_brief.md] [--csv requirements.csv]

The Markdown and CSV are built here once and embedded in the tool, so the tool's export buttons hand back
exactly the same files. Standard library only.
"""
import csv, io, json, os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import fmt_money, fmt_exact, fmt_rate, fmt_count, fmt_days, fmt_date, FUNCTION_NAMES  # noqa: E402

ROLES = ("ceo", "marketing", "agency", "cro")
SIGN = "*Built by Marketing Systems Guild. Turning strangers into clients.*"


def d(s):
    return fmt_date(date.fromisoformat(s)) if s else ""


def cell(s):
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ")


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def markdown(res):
    f, t, br = res["funnel"], res["timing"], res.get("brief")
    L = [f"# Campaign brief: {res['campaign']['name']}", ""]
    stamp = br["stamp"] if br else res["verdict"]
    L.append(f"**Verdict: {stamp}.** CRM campaign `{res['campaign']['id']}`. Round {res.get('round', 1)}.")
    if br:
        a = br["approval"]
        L.append(f"Approved by {a['name']}, {a['seat']}, on {a['date_label']}.")
    else:
        L.append("Pressure test only. The brief builds after the strategy is approved.")
    for w in res.get("warnings") or []:
        L += ["", f"> {w}"]
    L += ["", "## The target", ""]
    if br:
        m = br["measurement"]
        L += [f"- **Primary KPI:** {m['primary']}."]
        L += ["- **Leading indicators:** " + ", ".join(m["leading"]) + "."]
        if m.get("revenue"):
            L.append(f"- **Closed revenue:** {m['revenue']}")
        L.append("- **Not KPIs:** clicks, impressions and MQL counts. Ads diagnostics only.")
        L.append("")
    L.append(table(["Reverse funnel", "Value"], [
        ["Pipeline target", fmt_money(f["target"])], ["Due date", d(t["due"])],
        ["Opportunities needed", fmt_count(f["opps_needed"])], ["Leads needed", fmt_count(f["leads_needed"])],
        ["Leads the plan buys", fmt_count(f["planned_leads"])], ["Expected opportunities", fmt_count(f["planned_opps"])],
        ["Pipeline the plan buys", fmt_money(f["planned_pipeline"])], ["Pipeline that lands by the due date", fmt_money(t["pipeline_in_time"])],
        ["Cost per lead today (blended)", fmt_money(f["blended_cpl"])], ["Cost per lead ceiling", fmt_money(f["cpl_ceiling"])]]))
    if res.get("assumptions"):
        L += ["", "**Assumptions:** " + "; ".join(f"{a['label']} {a['value']} (Assumption)" for a in res["assumptions"]) + "."]
    L += ["", "## The ten checks", ""]
    L.append(table(["#", "Check", "State", "Reason", "Fix"],
                   [[c["n"], c["name"], state_word(c), c["reason"], c["fix"]] for c in res["checks"]]))
    L += ["", "## The strategy it traces to", ""]
    L.append(table(["Line", "What", "As stated"], [[l["id"], l["label"], l["text"]] for l in res["strategy_lines"]]))
    L += ["", "## Channels", ""]
    L.append(table(["ID", "Channel", "Budget", "Cost per lead", "Leads", "Expected opportunities", "Pipeline"],
                   [[c["id"], c["name"], fmt_exact(c["budget"]), (fmt_exact(c["cpl"]) + (" (Assumption)" if c["cpl_assumed"] else "")) if c["cpl"] else "None",
                     fmt_count(c["leads"]), fmt_count(c["opps"]), fmt_money(c["pipeline"])] for c in res["channels"]]))
    if br:
        by = {r["id"]: r for r in br["requirements"]}
        for s in br["sections"]:
            L += ["", f"## {s['name']}", ""]
            if not s["active"]:
                L.append(s["because"])
                continue
            L.append(table(["ID", "Requirement", "Traces to", "Owner", "Due", "Budget", "Depends on", "Acceptance"],
                           [[r["id"], r["requirement"], r["trace_label"], r["owner"], r["due_label"], r["budget_label"],
                             ", ".join(r["depends_on_ids"]) or "None", r["acceptance"]] for r in (by[i] for i in s["requirements"])]))
        if br["unassigned"]:
            L += ["", "**Unassigned:** " + ", ".join(br["unassigned"]) + ". Name an owner for each."]
        if br["dependency_conflicts"]:
            L += ["", "**Dependency conflicts:**"] + [f"- {x}" for x in br["dependency_conflicts"]]
        L += ["", "## Risks", ""]
        L.append(table(["From", "Risk", "Fix", "Owner"], [[r["source"], r["risk"], r["fix"] or "None given", r["owner"]] for r in br["risks"]])
                 if br["risks"] else "None named.")
        utm = [r for r in br["requirements"] if r.get("utm")]
        if utm:
            L += ["", "## UTMs", ""]
            L.append(table(["ID", "utm_source", "utm_medium", "utm_campaign", "utm_content"],
                           [[r["id"], r["utm"]["source"], r["utm"]["medium"], r["utm"]["campaign"], r["utm"]["content"]] for r in utm]))
        L += ["", "## Lead times", ""]
        L.append(table(["Function", "Days before launch", "Source"], [[x["name"], fmt_days(x["days"]), x["source"]] for x in br["lead_times"]]))
        rc = br["reconciliation"]
        L += ["", f"**Budget check:** channels {fmt_exact(rc['channels_total'])}, total {fmt_exact(rc['budget_total'])}, "
                  f"requirements {fmt_exact(rc['requirements_total'])}. " + ("They reconcile." if rc["ok"] else "They do not reconcile.")]
    L += ["", "## Weekly pacing", ""]
    L.append(table(["Week", "Starts", "Spend", "Leads", "Opportunities landing", "Pipeline to date"],
                   [[p["week"], d(p["start"]) + (" (due week)" if p.get("contains_due") else ""), fmt_money(p["spend"]),
                     fmt_count(p["leads"]), fmt_count(p["opps_landing"]), fmt_money(p["pipeline_cum"])] for p in res["pacing"]]))
    L += ["", "Every number is a projection at the user's own rates, not a forecast.", "", SIGN, ""]
    return "\n".join(L)


def state_word(c):
    w = {"pass": "Pass", "flag": "Flag", "fail": "Fail"}[c["state"]]
    return w + (", not run" if c.get("not_run") else "")


def requirements_csv(res):
    br = res.get("brief")
    if not br:
        return ""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ID", "Function", "Requirement", "Traces to", "Owner", "Due", "Budget", "Depends on", "Acceptance",
                "utm_source", "utm_medium", "utm_campaign", "utm_content"])
    for r in br["requirements"]:
        u = r.get("utm") or {}
        w.writerow([r["id"], FUNCTION_NAMES[r["function"]], r["requirement"], r["trace_label"], r["owner"], r["due"] or r["due_label"],
                    (f"{r['budget']:g}" if r["budget"] is not None else r["budget_label"]), " ".join(r["depends_on_ids"]), r["acceptance"],
                    u.get("source", ""), u.get("medium", ""), u.get("campaign", ""), u.get("content", "")])
    return buf.getvalue()


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
    out = arg("--out", "campaign_brief.html")
    md, cs = markdown(data), requirements_csv(data)
    if arg("--markdown"):
        with open(arg("--markdown"), "w", encoding="utf-8") as fh:
            fh.write(md)
    if arg("--csv") and cs:
        with open(arg("--csv"), "w", encoding="utf-8", newline="") as fh:
            fh.write(cs)
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "tool_template.html")
    with open(tpl_path, encoding="utf-8") as fh:
        tpl = fh.read()
    esc = lambda o: json.dumps(o, default=str, separators=(",", ":")).replace("</", "<\\/")
    html = (tpl.replace("/*__DATA__*/null", esc(data)).replace('/*__ROLE__*/"ceo"', json.dumps(role))
            .replace('/*__MD__*/""', esc(md)).replace('/*__CSV__*/""', esc(cs)))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Tool written to " + out + (", Markdown to " + arg("--markdown") if arg("--markdown") else ""))


if __name__ == "__main__":
    main()
