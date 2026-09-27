#!/usr/bin/env python3
"""Prove It or Fail It: size a growth test, seal its numbers, and call the verdict.

Usage:
  python verdict.py design idea.json [--rubric rubric.json] [--plan plan.json] [--json design.json] [--card card.json]
  python verdict.py read card.json results.json [--previous read_day30.json] [--json read.json]

design  reads the idea Claude mapped from the user's words. It parses every number, stops with questions when an
        input is missing or unclear, sizes the test, sets the success, kill and day-15 harm lines, runs the two
        script checks, reads Claude's four rubric checks, and seals the test card when the verdict allows it.
read    checks the card's seal, reads the results, and calls Stop early, Scale, Kill or Extend against the
        numbers locked on the card.

Standard library only. Claude never computes a number this script can produce.
"""
import hashlib, json, math, re, sys
from datetime import date, timedelta
from statistics import NormalDist

VERSION = "1.0.0"
Z_A = NormalDist().inv_cdf(0.975)   # 95% sure, two-sided
Z_B = NormalDist().inv_cdf(0.80)    # sized to catch a real lift of the success size 8 times in 10
EPS = 1e-12
RUBRIC = {"one_change": "One change", "right_metric": "Right metric", "clean_split": "Clean split", "measurable": "Measurable today"}
SCRIPT = {"readable": "Readable in 30 days", "pays_back": "Pays back at the expected lift"}
ACTIONS = {"scale": "On Scale", "kill": "On Kill", "extend": "On Extend", "stop": "On Stop early"}
LOCKED = ("idea", "metric", "design", "test_share", "launch", "baseline", "planned", "sizing", "lines", "dates", "actions", "extend_days")


# ---------------------------------------------------------------- formatting (same rules as the tool)
def fmt_money(v):
    if v is None:
        return "None set"
    v = float(v)
    if v >= 1_000_000:
        return "$" + f"{math.floor(v / 1e6 * 100 + 0.5) / 100:.2f}".rstrip("0").rstrip(".") + "M"
    if v >= 10_000:
        return f"${int(math.floor(v / 1000 + 0.5))}K"
    return f"${int(math.floor(v + 0.5)):,}"


def fmt_exact(v):
    return f"${v:,.2f}".replace(".00", "") if v != int(v) else f"${int(v):,}"


def fmt_pct(x, signed=False):
    """A lift or a rate as a percentage, one decimal, trailing .0 dropped. 0.3301 -> 33%, 0.031 -> 3.1%."""
    v = math.floor(abs(x) * 1000 + 0.5) / 10
    s = f"{int(v)}" if v == int(v) else f"{v:.1f}"
    sign = ("+" if x > 0 else "-" if x < 0 else "") if signed else ("-" if x < 0 and v else "")
    return f"{sign}{s}%"


def fmt_count(v):
    r = math.floor(v * 10 + 0.5) / 10
    return f"{int(r):,}" if r == int(r) else f"{r:,.1f}"


def fmt_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}" if hasattr(d, "strftime") else str(d)


def fmt_value(metric, v):
    """A value of the metric itself: a rate as a percentage, a count as a number a week."""
    return fmt_pct(v) if metric["type"] == "rate" else f"{fmt_count(v)} a week"


# ---------------------------------------------------------------- parsing the user's words
class Unclear(Exception):
    pass


HEDGE = re.compile(r"^(?:\s*(?:about|around|approx\.?|approximately|roughly|nearly|close to|est\.?|estimated|usually|typically|in|~))+\s*", re.I)


def unhedge(s):
    return HEDGE.sub("", str(s)).strip()


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def parse_money(v):
    if isinstance(v, bool) or blank(v):
        raise Unclear("blank")
    if isinstance(v, (int, float)):
        if v < 0:
            raise Unclear("negative")
        return float(v), None
    s = unhedge(v)
    if re.search(r"[€£¥]|\b(eur|gbp|cad|aud)\b", s, re.I):
        raise Unclear("currency")
    t = re.sub(r"\s*(?:a|per|each|/)\s*\w+.*$", "", s.lower()).replace("usd", "").replace("$", "").replace(",", "").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|m|mm|million|thousand)?", t)
    if not m:
        raise Unclear("unreadable")
    mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6}.get(m.group(2), 1)
    val = float(m.group(1)) * mult
    return val, (f"'{v}' read as {fmt_exact(val)}" if mult != 1 or s != str(v).strip() else None)


def parse_share(v, allow_over_100=False):
    """'3.1%', 0.031, '35%' -> fraction. A bare number over 1 reads as a percentage."""
    if isinstance(v, bool) or blank(v):
        raise Unclear("blank")
    note = None
    if isinstance(v, (int, float)):
        x = float(v)
        if x > 1:
            x, note = x / 100, f"{v} read as {v:g}%"
    else:
        s = unhedge(v)
        m = re.match(r"(\d+(?:\.\d+)?)\s*%", s)
        if m:
            x = float(m.group(1)) / 100
        else:
            try:
                x = float(s)
            except ValueError:
                raise Unclear("unreadable")
            if x > 1:
                note = f"'{v}' read as {x:g}%"
                x = x / 100
        if s != str(v).strip() and not note:
            note = f"'{v}' read as {fmt_pct(x)}"
    if x <= 0 or (x > 1 and not allow_over_100):
        raise Unclear("range")
    return x, note


def parse_test_share(v):
    """'50/50', '60/40' (test first), '50%', 0.5 -> fraction of the audience that sees the change."""
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%?\s*/\s*(\d+(?:\.\d+)?)\s*%?\s*", v)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if a <= 0 or b <= 0:
                raise Unclear("range")
            return a / (a + b), f"'{v}' read as {fmt_pct(a / (a + b))} in the test group"
    return parse_share(v)


def parse_number(v):
    """'9,000 visitors', 9000, '9k' -> 9000."""
    if isinstance(v, bool) or blank(v):
        raise Unclear("blank")
    if isinstance(v, (int, float)):
        if v <= 0:
            raise Unclear("range")
        return float(v), None
    s = unhedge(v).lower().replace(",", "")
    m = re.match(r"(\d+(?:\.\d+)?)\s*(k|m)?\b", s)
    if not m:
        raise Unclear("unreadable")
    x = float(m.group(1)) * {"k": 1e3, "m": 1e6}.get(m.group(2), 1)
    if x <= 0:
        raise Unclear("range")
    return x, (f"'{v}' read as {fmt_count(x)}" if m.group(2) or s != str(v).strip().lower().replace(",", "") else None)


def parse_weekly(v):
    """'40 a week', '40', '170 a month' -> a count per week."""
    x, note = parse_number(v)
    s = str(v).lower()
    if re.search(r"\b(month|mo|monthly)\b", s):
        return x * 12 / 52, f"'{v}' read as {fmt_count(x * 12 / 52)} a week"
    if re.search(r"\b(day|daily)\b", s):
        return x * 7, f"'{v}' read as {fmt_count(x * 7)} a week"
    return x, (f"'{v}' read as {fmt_count(x)} a week" if note else None)


MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def parse_date(v):
    if blank(v):
        raise Unclear("blank")
    s = unhedge(v)
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        if a > 12 >= b:
            d = date(y, b, a)
        elif b > 12 >= a or a == b:
            d = date(y, a, b)
        else:
            raise Unclear("ambiguous")
        return d, f"'{v}' read as {fmt_date(d)}"
    t = s.lower().replace(",", " ").split()
    try:
        if len(t) == 3 and t[0][:3] in MONTHS:
            return date(int(t[2]), MONTHS[t[0][:3]], int(re.sub(r"\D", "", t[1]))), None
        if len(t) == 3 and t[1][:3] in MONTHS:
            return date(int(t[2]), MONTHS[t[1][:3]], int(re.sub(r"\D", "", t[0]))), None
    except ValueError:
        pass
    raise Unclear("unreadable")


# ---------------------------------------------------------------- the statistics
def rate_se_rel(p, n_t, n_c):
    """Standard error of the relative lift of a rate, both arms at the baseline rate."""
    return math.sqrt(p * (1 - p) * (1 / n_t + 1 / n_c)) / p


def count_se_log(l_t, l_c):
    """Standard error of the log ratio of two counts."""
    return math.sqrt(1 / l_t + 1 / l_c)


def detectable(kind, se):
    return (Z_A + Z_B) * se if kind == "rate" else math.exp((Z_A + Z_B) * se) - 1


def kill_line(kind, success, se):
    """The observed lift at day 30 at or below which the top of the range sits below the success number."""
    return success - Z_A * se if kind == "rate" else (1 + success) * math.exp(-Z_A * se) - 1


def harm_line(kind, se15):
    """The observed lift at day 15 at or below which the whole range sits below zero."""
    return -Z_A * se15 if kind == "rate" else math.exp(-Z_A * se15) - 1


def arms(kind, design, share, base, vol30, hist, scale=1.0, days=30):
    """Planned sizes. Split: both arms grow with the volume. Before and after: the history is fixed."""
    f = scale * days / 30
    if kind == "rate":
        if design == "split":
            return vol30 * f * share, vol30 * f * (1 - share)
        return vol30 * f, hist["volume"]
    lam30 = base * 30 / 7
    if design == "split":
        return lam30 * f * share, lam30 * f * (1 - share)
    return lam30 * f, hist["count"]


def se_for(kind, p, a):
    return rate_se_rel(p, a[0], a[1]) if kind == "rate" else count_se_log(a[0], a[1])


def swing(kind, weeks):
    """Largest relative gap between any 4-week window and the 12-week average."""
    if kind == "rate":
        tot = sum(w["conversions"] for w in weeks) / sum(w["volume"] for w in weeks)
        vals = [sum(w["conversions"] for w in weeks[i:i + 4]) / sum(w["volume"] for w in weeks[i:i + 4]) for i in range(len(weeks) - 3)]
    else:
        tot = sum(w["count"] for w in weeks) / len(weeks)
        vals = [sum(w["count"] for w in weeks[i:i + 4]) / 4 for i in range(len(weeks) - 3)]
    return max(abs(v / tot - 1) for v in vals), tot


# ---------------------------------------------------------------- reading the idea
ASK = {"idea": "What is the idea, in one sentence?",
       "metric.name": "What is the one metric this idea should move?",
       "metric.type": "Is the metric a rate (a share of people who act, such as form conversion) or a count (things per week, such as demos booked)?",
       "baseline": "What is that metric today, over the last 90 days?",
       "volume_30d": "How many people will the test see in 30 days? Visitors, sends or leads.",
       "design": "Can you split the audience, with a control group that does not see the change? Or is it before and after?",
       "test_share": "What share of the audience sees the change? For example 50%.",
       "budget": "What will the test cost?",
       "expected_lift": "How much do you expect the idea to lift the metric? For example 20%.",
       "launch": "What is the launch date?",
       "history": "Before-and-after tests need the metric for each of the last 12 weeks. Can you share them, or can you split the audience instead?",
       "actions.scale": "If the idea wins, what gets funded and by how much?",
       "actions.kill": "If the idea loses, where does the budget go?",
       "actions.extend": "If the result is in between, how many more days (up to 30) and how much more budget?",
       "actions.stop": "If the idea is doing harm at day 15, who shuts it off?"}
WHY = {"blank": "is missing", "unreadable": "could not be read", "ambiguous": "could be read two ways", "range": "is out of range",
       "currency": "is not in US dollars", "negative": "is negative"}


def get(d, path):
    for p in path.split("."):
        d = d.get(p) if isinstance(d, dict) else None
    return d


def read_idea(raw):
    q, notes = [], []

    def ask(field, why, value=None):
        text = ASK.get(field, "") if why == "blank" else f"'{value}' for {field.replace('_', ' ')} {WHY.get(why, why)}. {ASK.get(field, '')}"
        q.append({"field": field, "problem": why, "ask": text.strip()})

    def take(field, fn):
        v = get(raw, field)
        try:
            out, note = fn(v)
        except Unclear as e:
            ask(field, str(e), v)
            return None
        if note:
            notes.append(note)
        return out

    x = {}
    for f in ("idea", "metric.name"):
        if blank(get(raw, f)):
            ask(f, "blank")
    kind = str(get(raw, "metric.type") or "").strip().lower()
    if kind not in ("rate", "count"):
        ask("metric.type", "blank" if not kind else "unreadable", get(raw, "metric.type"))
        kind = None
    x["kind"] = kind
    design = str(raw.get("design") or "").strip().lower().replace("-", "_").replace(" ", "_")
    design = {"before_and_after": "before_after", "a/b": "split", "ab": "split"}.get(design, design)
    if design not in ("split", "before_after"):
        ask("design", "blank" if not design else "unreadable", raw.get("design"))
        design = None
    x["design"] = design
    x["share"] = 0.5
    if design == "split" and not blank(raw.get("test_share")):
        x["share"] = take("test_share", parse_test_share)
        if x["share"] is not None and not 0.05 <= x["share"] <= 0.95:
            ask("test_share", "range", raw.get("test_share"))
    if kind == "rate":
        x["base"] = take("baseline", parse_share)
        x["vol30"] = take("volume_30d", parse_number)
    elif kind == "count":
        x["base"] = take("baseline", parse_weekly)
        x["vol30"] = None
    x["budget"] = take("budget", parse_money)
    x["expected"] = take("expected_lift", lambda v: parse_share(v, allow_over_100=True))
    x["value"] = None
    if not blank(raw.get("value_per_unit")):
        x["value"] = take("value_per_unit", parse_money)
    x["launch"] = take("launch", parse_date)
    ext = raw.get("extend_days")
    x["extend_days"] = 30
    if not blank(ext):
        try:
            d = int(parse_number(ext)[0])
            if not 1 <= d <= 30:
                raise Unclear("range")
            x["extend_days"] = d
        except Unclear as e:
            q.append({"field": "extend_days", "problem": str(e), "ask": "An Extend can add 1 to 30 days. How many?"})
    x["hist"] = None
    if design == "before_after" and kind:
        weeks = raw.get("history") or []
        if len(weeks) < 12:
            ask("history", "blank")
        else:
            try:
                weeks = weeks[-12:]
                if kind == "rate":
                    wk = [{"conversions": parse_number(w["conversions"])[0] if not blank(w.get("conversions")) and float(str(w["conversions"]).replace(",", "") or 0) != 0 else 0.0,
                           "volume": parse_number(w["volume"])[0]} for w in weeks]
                else:
                    wk = [{"count": float(str(w["count"]).replace(",", ""))} for w in weeks]
                    if any(w["count"] < 0 for w in wk):
                        raise Unclear("range")
                sw, avg = swing(kind, wk)
                x["hist"] = {"weeks": wk, "swing": sw, "average": avg,
                             "volume": sum(w["volume"] for w in wk) if kind == "rate" else None,
                             "conversions": sum(w["conversions"] for w in wk) if kind == "rate" else None,
                             "count": sum(w["count"] for w in wk) if kind == "count" else None}
                if x.get("base") is not None and abs(avg / x["base"] - 1) > 0.02:
                    notes.append(f"The 12-week history averages {fmt_value({'type': kind}, avg)}, not the stated {fmt_value({'type': kind}, x['base'])}. The test uses the history.")
                x["base"] = avg
            except (Unclear, KeyError, ValueError, TypeError, ZeroDivisionError):
                q.append({"field": "history", "problem": "unreadable",
                          "ask": "The weekly history could not be read. Each week needs " + ("conversions and volume." if kind == "rate" else "a count.")})
    acts = raw.get("actions") or {}
    x["actions"] = {}
    for k in ACTIONS:
        if blank(acts.get(k)):
            ask("actions." + k, "blank")
        else:
            x["actions"][k] = str(acts[k]).strip()
    return x, notes, q


# ---------------------------------------------------------------- design
def size(x, scale=1.0):
    a = arms(x["kind"], x["design"], x["share"], x["base"], x["vol30"], x["hist"], scale)
    return detectable(x["kind"], se_for(x["kind"], x["base"], a)), a


def fixes(x, bar):
    """The smallest volume multiple at which the test can detect the lift the user expects."""
    lo, hi = 1.0, 1.0
    while size(x, hi)[0] > bar + EPS:
        hi *= 2
        if hi > 1024:
            return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if size(x, mid)[0] > bar + EPS:
            lo = mid
        else:
            hi = mid
    return hi


def check(n, state, reason, fix="", not_run=False):
    return {"key": n, "name": SCRIPT.get(n) or RUBRIC.get(n), "by": "script" if n in SCRIPT else "claude",
            "state": state, "reason": reason, "fix": fix, "not_run": not_run}


def design(raw, rubric=None, plan=None):
    x, notes, q = read_idea(raw)
    base = {"tool": "prove-it-or-fail-it", "version": VERSION, "mode": "design"}
    if q:
        return {**base, "stop": "inputs", "questions": q, "notes": notes}
    kind, metric = x["kind"], {"name": str(get(raw, "metric.name")).strip(), "type": x["kind"],
                               "unit": str(get(raw, "metric.unit") or "").strip() or ("conversion" if x["kind"] == "rate" else "unit")}
    det, a = size(x)
    se30 = se_for(kind, x["base"], a)
    a15 = arms(kind, x["design"], x["share"], x["base"], x["vol30"], x["hist"], days=15)
    se15 = se_for(kind, x["base"], a15)
    exp_units = x["base"] * a[0] if kind == "rate" else a[0]
    pay = (x["budget"] / x["value"]) / exp_units if x["value"] else None
    sw = x["hist"]["swing"] if x["hist"] else None
    parts = [("detectable", det), ("payback", pay), ("swing", sw)]
    driver, success = max(((k, v) for k, v in parts if v is not None), key=lambda t: t[1])
    bar_needed = max(det, sw or 0)
    readable = bar_needed <= x["expected"] + EPS
    kill = kill_line(kind, success, se30)
    harm = harm_line(kind, se15)
    launch = x["launch"]
    dates = {"launch": launch.isoformat(), "checkpoint": (launch + timedelta(days=14)).isoformat(),
             "day30": (launch + timedelta(days=29)).isoformat(), "extend_end": (launch + timedelta(days=29 + x["extend_days"])).isoformat()}
    val = lambda lift: x["base"] * (1 + lift)
    lines = {"baseline": x["base"], "success": val(success), "kill": val(kill), "harm": val(harm),
             "success_lift": success, "kill_lift": kill, "harm_lift": harm}

    checks = []
    if readable:
        checks.append(check("readable", "pass", f"30 days can detect a lift of {fmt_pct(det)}. You expect {fmt_pct(x['expected'])}."
                            + (f" The business's own swing is {fmt_pct(sw)}." if sw is not None else "")))
        too_small = None
    else:
        s = fixes(x, x["expected"]) if det > x["expected"] + EPS else None
        why = (f"30 days can only detect a lift of {fmt_pct(det)}. You expect {fmt_pct(x['expected'])}." if det > x["expected"] + EPS
               else f"The business's own swing is {fmt_pct(sw)}, bigger than the {fmt_pct(x['expected'])} you expect. Before and after cannot tell the idea from a normal month.")
        too_small = {"detectable": det, "expected": x["expected"], "swing": sw, "multiple": s}
        fx = []
        if s is not None:
            vol_needed = (x["vol30"] if kind == "rate" else x["base"] * 30 / 7) * s
            too_small.update({"volume_needed": vol_needed, "days_needed": int(math.ceil(30 * s - EPS))})
            if kind == "rate":
                fx.append(f"Send {fmt_count(math.ceil(vol_needed))} people through the test in 30 days")
            else:
                fx.append(f"Run it where the metric reaches {fmt_count(math.ceil(vol_needed))} {metric['unit']}s in 30 days")
            fx.append(f"Run it for {too_small['days_needed']} days at today's volume")
        elif det > x["expected"] + EPS:
            fx.append("No volume fixes it: the 12-week history is too short and too noisy to compare against. Split the audience instead")
        if sw is not None and sw > x["expected"] + EPS:
            fx.append("Split the audience, so a normal month cannot pass for a win")
        fx.append(f"Aim for a bolder idea, one you expect to lift the metric at least {fmt_pct(bar_needed)}")
        too_small["fixes"] = fx
        checks.append(check("readable", "fail", why, ". ".join(fx) + "."))
    if x["value"] is None:
        checks.append(check("pays_back", "flag", "Not run. No value was given for one " + metric["unit"] + ", so the success number is not tied to money.",
                            f"Give the value of one {metric['unit']} to test payback.", not_run=True))
    elif x["expected"] + EPS >= pay:
        checks.append(check("pays_back", "pass", f"The budget pays back at a lift of {fmt_pct(pay)}. You expect {fmt_pct(x['expected'])}."))
    else:
        checks.append(check("pays_back", "flag", f"The budget pays back only at a lift of {fmt_pct(pay)}. You expect {fmt_pct(x['expected'])}, so even a win does not earn back the test.",
                            f"Cut the budget to {fmt_money(x['expected'] * exp_units * x['value'])}, or test an idea you expect to lift the metric {fmt_pct(pay)} or more."))

    rub_probs = []
    if rubric is not None:
        src = rubric.get("checks", rubric)
        for k, name in RUBRIC.items():
            r = src.get(k)
            if not r:
                rub_probs.append(f"Check '{k}' ({name}) has no result.")
                continue
            st = str(r.get("state", "")).lower().strip()
            if st not in ("pass", "flag", "fail"):
                rub_probs.append(f"Check '{k}' state must be pass, flag or fail.")
                continue
            if blank(r.get("reason")):
                rub_probs.append(f"Check '{k}' needs a reason.")
            if st != "pass" and blank(r.get("fix")):
                rub_probs.append(f"Check '{k}' is {st} and needs a fix.")
            checks.append(check(k, st, str(r.get("reason", "")).strip(), str(r.get("fix", "")).strip()))
        if rub_probs:
            return {**base, "stop": "rubric", "problems": rub_probs}
    states = [c["state"] for c in checks]
    if not readable:
        verdict = "Too small to read"
    elif rubric is None:
        verdict = "Pending rubric"
    elif "fail" in states:
        verdict = "Not ready"
    elif "flag" in states:
        verdict = "Ready with flags"
    else:
        verdict = "Ready"

    warnings = []
    small = (x["base"] * a[1] if kind == "rate" else a[1]) < 20 or (x["base"] * a[0] if kind == "rate" else a[0]) < 20
    if small:
        warnings.append("An arm expects fewer than 20 " + metric["unit"] + "s. Read counts, not rates.")
    if x["design"] == "before_after":
        warnings.append("No control. A before-and-after verdict cannot rule out what else changed in those 30 days.")

    res = {**base, "idea": str(raw.get("idea")).strip(), "metric": metric, "design": x["design"],
           "test_share": x["share"] if x["design"] == "split" else None, "launch": dates["launch"], "notes": notes,
           "baseline": x["base"], "inputs": {"volume_30d": x["vol30"], "budget": x["budget"], "expected_lift": x["expected"],
                                             "value_per_unit": x["value"], "history": x["hist"]},
           "planned": {"test": a[0], "control": a[1], "test_units": exp_units, "control_units": (x["base"] * a[1] if kind == "rate" else a[1]),
                       "test_day15": a15[0], "control_day15": a15[1]},
           "sizing": {"detectable": det, "payback": pay, "swing": sw, "success": success, "driver": driver, "se30": se30, "se15": se15,
                      "z95": Z_A, "z80": Z_B,
                      "history_totals": ({"conversions": x["hist"]["conversions"], "volume": x["hist"]["volume"]} if kind == "rate"
                                         else {"count": x["hist"]["count"], "days": 7 * len(x["hist"]["weeks"])}) if x["hist"] else None},
           "lines": lines, "dates": dates, "extend_days": x["extend_days"], "actions": x["actions"],
           "too_small": too_small, "checks": checks, "verdict": verdict, "warnings": warnings,
           "owners": {k: v for k, v in (raw.get("owners") or {}).items() if not blank(v)}}
    if plan:
        res["plan"] = {k: plan.get(k) for k in ("change", "who_sees_it", "split", "metric_definition", "counted_in", "setup", "risks") if not blank(plan.get(k))}
    res = clean(res)
    if verdict in ("Ready", "Ready with flags"):
        res["card"] = seal(res)  # sealed after rounding, so the card survives a round trip through a file
    return res


def seal(res):
    body = {k: res[k] for k in LOCKED}
    body = json.loads(json.dumps(body, default=str))
    fields = {k: hashlib.sha256(json.dumps(body[k], sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12] for k in LOCKED}
    s = hashlib.sha256(json.dumps({"body": body, "fields": fields}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return {"tool": "prove-it-or-fail-it", "version": VERSION, "body": body, "fields": fields, "seal": s}


def verify(card):
    """Returns (ok, message). Names the field that changed when it can."""
    try:
        body, fields, s = card["body"], card["fields"], card["seal"]
    except (KeyError, TypeError):
        return False, "This is not a Prove It or Fail It test card."
    changed = [k for k in LOCKED if k in body and hashlib.sha256(json.dumps(body[k], sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12] != fields.get(k)]
    again = hashlib.sha256(json.dumps({"body": body, "fields": fields}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    if changed:
        return False, "The card was edited after it was sealed. Changed: " + ", ".join(changed) + ". The numbers agreed before launch are the only ones a verdict can use."
    if again != s or any(k not in body for k in LOCKED):
        return False, "The card was edited after it was sealed. The seal does not match. The numbers agreed before launch are the only ones a verdict can use."
    return True, "Seal intact."


# ---------------------------------------------------------------- read
def observed(kind, design, share, res_t, res_c, base_hist, day):
    """Observed relative lift and its 95% range."""
    if kind == "rate":
        ct, nt = res_t
        cc, nc = res_c
        pt, pc = ct / nt, cc / nc
        se = math.sqrt(pt * (1 - pt) / nt + pc * (1 - pc) / nc) / pc
        lift = pt / pc - 1
        return lift, lift - Z_A * se, lift + Z_A * se, pt, pc
    xt, et = res_t
    xc, ec = res_c
    r = math.log((xt / et) / (xc / ec))
    se = math.sqrt(1 / xt + 1 / xc)
    return math.exp(r) - 1, math.exp(r - Z_A * se) - 1, math.exp(r + Z_A * se) - 1, xt / et, xc / ec


def read(card, results, previous=None):
    base = {"tool": "prove-it-or-fail-it", "version": VERSION, "mode": "read"}
    ok, msg = verify(card)
    if not ok:
        return {**base, "stop": "seal", "problems": [msg]}
    b = card["body"]
    kind, design, share = b["metric"]["type"], b["design"], b["test_share"]
    probs = []
    try:
        day = int(results.get("day"))
    except (TypeError, ValueError):
        return {**base, "stop": "results", "problems": ["Say which day these results are for: 15, 30, or the last day of an Extend."]}
    ext_end = 30 + b["extend_days"]
    if day not in (15, 30) and not (30 < day <= ext_end):
        probs.append(f"Day {day} is not a read day. Read at day 15, day 30, or by day {ext_end} after an Extend.")
    if 30 < day and (not previous or previous.get("verdict") != "Extend" or previous.get("seal") != card["seal"]):
        probs.append("A read after day 30 needs the day-30 read that called Extend on this same card.")

    def num(path):
        v = get(results, path)
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            probs.append(f"Results need {path.replace('.', ' ')}.")
            return None

    h = b["sizing"].get("history_totals") or {}
    if kind == "rate":
        ct, nt = num("test.conversions"), num("test.volume")
        if design == "split":
            cc, nc = num("control.conversions"), num("control.volume")
        else:
            cc, nc = h.get("conversions"), h.get("volume")
    else:
        ct = num("test.count")
        if design == "split":
            nt, cc, nc = share, num("control.count"), 1 - share
        else:
            nt, cc, nc = day, h.get("count"), h.get("days")
    if not probs:
        for v, label in ((ct, "test"), (cc, "control")):
            if v is not None and v <= 0:
                probs.append(f"The {label} result is zero. A verdict needs at least one {b['metric']['unit']} in each arm.")
        if kind == "rate" and not probs and (ct > nt or cc > nc):
            probs.append("An arm has more conversions than people. Check the numbers.")
    if probs:
        return {**base, "stop": "results", "problems": probs}
    lift, lo, hi, vt, vc = observed(kind, design, share, (ct, nt), (cc, nc), None, day)
    succ = b["lines"]["success_lift"]
    if day == 15:
        verdict = "Stop early" if hi < 0 else "Keep running"
    elif day == 30:
        verdict = "Scale" if lo > 0 and lift >= succ - EPS else ("Kill" if hi < succ else "Extend")
    else:
        verdict = "Scale" if lo > 0 and lift >= succ - EPS else "Kill"
    detail = None
    if verdict == "Kill" and day > 30 and hi >= succ:
        detail = ("Unproven, not disproven. " + ("The lift is above zero but under the success number, and the final read has no more time."
                                                 if lo > 0 else "The range still reaches both zero and the success number, and the final read has no more time.")
                  + " The day-30 kill number no longer applies: the final read scales only at the success number."
                  + " The idea can come back as a bolder version.")
    elif verdict == "Kill":
        detail = "Disproven. Even the top of the range sits below the success number."
    action = {"Scale": b["actions"]["scale"], "Kill": b["actions"]["kill"], "Extend": b["actions"]["extend"],
              "Stop early": b["actions"]["stop"], "Keep running": None}[verdict]
    arm_units = [ct, cc]
    res = {**base, "seal": card["seal"], "day": day, "idea": b["idea"], "metric": b["metric"], "design": design,
           "verdict": verdict, "detail": detail, "action": action,
           "observed": {"lift": lift, "low": lo, "high": hi, "test_value": vt, "control_value": vc},
           "results": {"test": results.get("test"), "control": results.get("control")},
           "lines": b["lines"], "dates": b["dates"], "baseline": b["baseline"],
           "small_sample": min(arm_units) < 20,
           "no_control": design == "before_after",
           "card": card}
    if kind == "count":  # counts a week, for the whole audience
        if design == "split":
            res["observed"]["test_value"] = ct / share / (day / 7)
            res["observed"]["control_value"] = cc / (1 - share) / (day / 7)
        else:
            res["observed"]["test_value"] = ct / day * 7
            res["observed"]["control_value"] = cc / nc * 7
    res["reason"] = reason_for(res)
    sl = fmt_pct(succ, True)
    res["rule"] = {15: "Day 15 stops the test only when the whole range is below zero. A slow start never stops it.",
                   30: f"Day 30 scales when the whole range is above zero and the lift is at least {sl}. It kills when the top of the range is under {sl}. Anything else extends."
                   }.get(day, f"The final read scales when the whole range is above zero and the lift is at least {sl}. Anything else is Kill. There is no second Extend.")
    res["compare"] = ("The verdict compares the test group with the control group over the same days, as a lift. "
                      "It does not compare either group with the baseline or with the success number as a value."
                      if design == "split" else
                      "The verdict compares the test period with the 12 weeks before, as a lift. No control group rules out other changes.")
    return clean(res)


def reason_for(r):
    o, L, m = r["observed"], r["lines"], r["metric"]
    rng = f"{fmt_pct(o['low'], True)} to {fmt_pct(o['high'], True)}"
    base = f"The lift is {fmt_pct(o['lift'], True)}, with a range of {rng}."
    v = r["verdict"]
    if v == "Stop early":
        return base + " The whole range is below zero. The idea is doing harm."
    if v == "Keep running":
        return base + " Nothing shows harm. A slow start never stops a test."
    if v == "Scale":
        return base + f" The lift is real and at or above the success number of {fmt_pct(L['success_lift'], True)}."
    if v == "Extend":
        return base + f" It is not proven, and it has not fallen clearly short of the success number of {fmt_pct(L['success_lift'], True)}."
    return base + f" The success number was {fmt_pct(L['success_lift'], True)}."


# ---------------------------------------------------------------- CLI
def clean(x):
    if isinstance(x, float):
        return round(x, 9)
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, date):
        return x.isoformat()
    return x


def load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        sys.exit(f"No file at {p}. Check the path.")


def main():
    a = sys.argv
    if len(a) < 3 or a[1] not in ("design", "read") or "--help" in a or "-h" in a:
        print(__doc__)
        sys.exit(0 if ("--help" in a or "-h" in a) else 1)
    arg = lambda k: a[a.index(k) + 1] if k in a else None
    if a[1] == "design":
        res = design(load(a[2]), load(arg("--rubric")) if arg("--rubric") else None, load(arg("--plan")) if arg("--plan") else None)
        out = arg("--json") or "design.json"
        if res.get("card") and arg("--card"):
            with open(arg("--card"), "w", encoding="utf-8") as fh:
                json.dump(res["card"], fh, indent=1)
    else:
        if len(a) < 4:
            sys.exit(__doc__)
        res = read(load(a[2]), load(a[3]), load(arg("--previous")) if arg("--previous") else None)
        out = arg("--json") or "read.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(f"Stopped ({res['stop']}). See {out}." if res.get("stop") else f"{res['verdict']}. Written to {out}.")


if __name__ == "__main__":
    main()
