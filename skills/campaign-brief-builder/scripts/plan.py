#!/usr/bin/env python3
"""Campaign Brief Builder: the math, the four script checks, the verdict and the brief.

Usage:
  python plan.py check strategy.json [--rubric rubric.json] [--previous last_result.json] [--json result.json]
  python plan.py brief result.json brief.json [--lead-times lead_times.json] [--json brief_result.json]

check  reads the strategy Claude mapped from the user's input. It parses every number and date the way the
       user wrote them, stops with questions when an input is missing or unclear, runs the reverse funnel and
       checks 1 to 4, reads Claude's rubric results for checks 5 to 10, and assembles the verdict.
brief  runs after the user approves. It takes the requirements Claude wrote, assigns IDs, due dates, budgets
       and UTMs, adds the tracking and assumption tasks, and checks the trace both ways.

Standard library only. Claude never computes a number this script can produce.
"""
import json, math, re, sys
from datetime import date, datetime, timedelta

VERSION = "1.0.0"

FUNCTIONS = ["ads", "pr", "content", "operations", "sales", "creative"]
FUNCTION_NAMES = {"ads": "Ads", "pr": "PR", "content": "Content", "operations": "Operations",
                  "sales": "Sales enablement", "creative": "Creative"}
PREFIX = {"ads": "ADS", "pr": "PR", "content": "CON", "operations": "OPS", "sales": "SAL", "creative": "CRE"}

# Channel type: the functions it calls on, and its default utm_medium.
CHANNEL_TYPES = {
    "paid_social": (("ads", "creative"), "paid_social"),
    "paid_search": (("ads", "creative"), "cpc"),
    "display": (("ads", "creative"), "display"),
    "syndication": (("ads", "content"), "syndication"),
    "webinar": (("content", "creative"), "webinar"),
    "event": (("content", "creative"), "event"),
    "email": (("content", "creative"), "email"),
    "organic_social": (("content", "creative"), "social"),
    "content": (("content",), "organic"),
    "direct_mail": (("content", "creative"), "direct_mail"),
    "partner": (("content",), "partner"),
    "pr": (("pr",), "pr"),
    "outbound": ((), "outbound"),
}

# Starter lead times: days before launch each function's pre-launch work is due.
# A starting point, not a benchmark. The user confirms or edits every line. Mirrors references/lead-times.md.
DEFAULT_LEAD_DAYS = {"creative": 21, "content": 21, "pr": 14, "operations": 10, "ads": 7, "sales": 5}

REQUIRED_ASSUMABLE = ("funnel.avg_deal", "funnel.lead_to_opp_rate", "funnel.lead_to_opp_days")
RUBRIC_CHECKS = {5: "Audience specific enough to target", 6: "Offer fits the audience",
                 7: "One provable message", 8: "Channels reach the named buying roles",
                 9: "Tracking to pipeline defined", 10: "Risks named"}
SCRIPT_CHECKS = {1: "Target reachable on budget", 2: "Opportunities land before the due date",
                 3: "Every channel can buy at least one opportunity", 4: "Sales capacity"}
STATES = ("pass", "flag", "fail")
MONTH_WEEKS = 52 / 12
EPS = 1e-9


# ---------------------------------------------------------------- formatting (same rules as the tool)
def fmt_money(v):
    if v is None:
        return "None set"
    neg = v < 0
    v = abs(v)
    if v >= 1_000_000:
        s = f"{math.floor(v / 1_000_000 * 100 + 0.5) / 100:.2f}".rstrip("0").rstrip(".")
        out = f"${s}M"
    elif v >= 10_000:
        out = f"${int(math.floor(v / 1000 + 0.5))}K"
    else:
        out = f"${int(math.floor(v + 0.5)):,}"
    return "-" + out if neg else out


def fmt_exact(v):
    """Dollars in full, for questions back to the user: $72,500, not $73K."""
    return f"${v:,.2f}".replace(".00", "") if v != int(v) else f"${int(v):,}"


def fmt_rate(r):
    return f"{int(math.floor(r * 100 + 0.5))}%"


def fmt_count(v):
    """Whole counts as whole numbers. Expected counts (opportunities) to one decimal, trailing .0 dropped."""
    if v is None:
        return ""
    r = math.floor(v * 10 + 0.5) / 10
    return f"{int(r):,}" if r == int(r) else f"{r:,.1f}"


def fmt_days(d):
    return f"{int(d)}" if float(d) == int(d) else f"{d}"


def fmt_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}" if hasattr(d, "strftime") else str(d)


def iso(d):
    return d.isoformat() if d else None


# ---------------------------------------------------------------- parsing the user's own words
class Unclear(Exception):
    pass


HEDGE = re.compile(r"^(?:\s*(?:about|around|approx\.?|approximately|roughly|nearly|close to|est\.?|estimated|usually|typically|in|~))+\s*", re.I)


def unhedge(s):
    """'about $300' -> '$300'. A hedge word does not make a number an assumption. The user says when it is a guess."""
    return HEDGE.sub("", str(s)).strip()


CURRENCY_OTHER = re.compile(r"[€£¥]|\b(eur|gbp|cad|aud|jpy|inr)\b", re.I)


def parse_money(v):
    """'$90k', '90,000', '1.2M', 90000 -> (90000.0, note or None)."""
    if isinstance(v, bool) or v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    if isinstance(v, (int, float)):
        if v < 0:
            raise Unclear("negative")
        return float(v), None
    s = unhedge(v)
    if CURRENCY_OTHER.search(s):
        raise Unclear("currency")
    t = re.sub(r"\s*(?:a|per|each|/)\s*(?:lead|deal|month|mo)\b.*$", "", s.lower())
    t = t.replace("usd", "").replace("$", "").replace(",", "").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(k|m|mm|mn|million|thousand)?", t)
    if not m:
        raise Unclear("unreadable")
    num = float(m.group(1))
    mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "mn": 1e6, "million": 1e6}.get(m.group(2), 1)
    val = num * mult
    shown = fmt_exact(val)
    return val, (f"'{v}' read as {shown}" if (mult != 1 or s != str(v).strip()) else None)


def parse_rate(v):
    """'8%', 0.08, 8 -> (0.08, note or None)."""
    if isinstance(v, bool) or v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    note = None
    if isinstance(v, (int, float)):
        x = float(v)
        if 1 < x <= 100:
            note = f"{v} read as {x:g}%"
            x /= 100
    else:
        s = unhedge(v)
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%.*", s)
        if m:
            x = float(m.group(1)) / 100
        else:
            try:
                x = float(s)
            except ValueError:
                raise Unclear("unreadable")
            if 1 < x <= 100:
                note = f"'{s}' read as {x:g}%"
                x /= 100
    if not (0 < x <= 1):
        raise Unclear("range")
    return x, note


def parse_days(v):
    """21, '21 days', '3 weeks' -> (21, note or None)."""
    if isinstance(v, bool) or v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    if isinstance(v, (int, float)):
        if v < 0:
            raise Unclear("negative")
        return float(v), None
    s = unhedge(v).lower()
    m = re.match(r"(\d+(?:\.\d+)?)\s*(d|day|days|w|wk|wks|week|weeks)?\b", s)
    if not m:
        raise Unclear("unreadable")
    n = float(m.group(1))
    if m.group(2) and m.group(2).startswith("w"):
        return n * 7, f"'{v}' read as {fmt_days(n * 7)} days"
    return n, (f"'{v}' read as {fmt_days(n)} days" if s != str(v).strip().lower() else None)


def parse_count(v):
    if isinstance(v, bool) or v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    m = re.match(r"(\d+(?:\.\d+)?)", unhedge(v).replace(",", ""))
    if not m:
        raise Unclear("unreadable")
    x = float(m.group(1))
    if x <= 0:
        raise Unclear("range")
    return x


MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_date(v):
    """ISO, US slash dates, 'Jan 11, 2027', '11 January 2027' -> (date, note or None).
    A slash date where both parts could be the month raises Unclear('ambiguous')."""
    if v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    s = unhedge(v)
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        if a > 12 and b <= 12:
            d = date(y, b, a)
        elif b > 12 and a <= 12:
            d = date(y, a, b)
        elif a == b:
            d = date(y, a, b)
        else:
            raise Unclear("ambiguous")
        return d, f"'{s}' read as {fmt_date(d)}"
    t = re.sub(r"[,]", " ", s.lower()).split()
    try:
        if len(t) == 3 and t[0][:3] in MONTHS:
            d = date(int(t[2]), MONTHS[t[0][:3]], int(re.sub(r"\D", "", t[1])))
        elif len(t) == 3 and t[1][:3] in MONTHS:
            d = date(int(t[2]), MONTHS[t[1][:3]], int(re.sub(r"\D", "", t[0])))
        else:
            raise Unclear("unreadable")
    except ValueError:
        raise Unclear("unreadable")
    return d, (f"'{v}' read as {fmt_date(d)}" if s != str(v).strip() else None)


def parse_run(v, launch):
    """'10 weeks', 10, '3 months', or an end date -> (weeks, end_date, note or None)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        raise Unclear("blank")
    note = None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        weeks = int(math.ceil(v))
    else:
        s = unhedge(v).lower()
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(w|wk|wks|week|weeks|m|mo|mos|month|months)", s)
        if m:
            n = float(m.group(1))
            if m.group(2).startswith("w"):
                weeks = int(math.ceil(n))
            else:
                days = int(math.floor(n * 365 / 12 + 0.5))
                weeks = int(math.ceil(days / 7))
                note = f"'{v}' read as {weeks} weeks"
        elif re.fullmatch(r"\d+", s):
            weeks = int(s)
        else:
            end, n2 = parse_date(v)
            days = (end - launch).days + 1
            if days <= 0:
                raise Unclear("range")
            weeks = int(math.ceil(days / 7))
            note = f"End date {fmt_date(end)} read as {weeks} weeks"
    if weeks <= 0:
        raise Unclear("range")
    return weeks, launch + timedelta(days=weeks * 7 - 1), note


def slug(s, n=24):
    """Lowercase, hyphens, at most n characters, cut at a word boundary."""
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    if len(s) > n:
        cut = s[:n + 1]
        s = cut[:cut.rfind("-")] if "-" in cut else s[:n]
    s = re.sub(r"(?:-(?:and|or|of|the|to|for|with|on|at|in|a))+$", "", s.strip("-"))
    return s or "x"


# ---------------------------------------------------------------- reading the strategy
ASK = {
    "target.pipeline": "What is the pipeline target in dollars?",
    "target.due_date": "By what date does the pipeline have to exist?",
    "audience.accounts": "Which accounts is this campaign for? Industry, size, region, or a named list.",
    "audience.roles": "Which buying roles does it have to reach?",
    "offer.offer": "What does the buyer get?",
    "offer.cta": "What is the one action you want the buyer to take?",
    "message.claim": "What is the core message, in one sentence?",
    "channels": "Which channels will run this campaign?",
    "launch.date": "What is the launch date?",
    "launch.run": "How long does the campaign run? Weeks, months, or an end date.",
    "funnel.avg_deal": "What is your average deal size?",
    "funnel.lead_to_opp_rate": "What share of leads become opportunities?",
    "funnel.lead_to_opp_days": "How many days does a lead take to become an opportunity?",
}
WHY = {"blank": "is missing", "unreadable": "could not be read", "ambiguous": "could be read two ways",
       "range": "is out of range", "currency": "is not in US dollars", "negative": "is negative"}


def get(d, path):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not [x for x in v if str(x).strip()])


def read_strategy(raw):
    """Parse and validate. Returns (inputs, notes, questions)."""
    q, notes = [], []

    def ask(field, why, value=None, extra=""):
        base = ASK.get(field, "")
        if why == "blank":
            text = base
        elif why == "ambiguous":
            a, b, y = [int(x) for x in re.split(r"[/.-]", str(value).strip())]
            y = y + 2000 if y < 100 else y
            text = (f"{field_label(field)} '{value}' could be {fmt_date(date(y, a, b))} or {fmt_date(date(y, b, a))}. Which is it?")
        elif why == "currency":
            text = f"{field_label(field)} is '{value}'. This skill reads US dollars only. What is it in dollars?"
        else:
            text = f"{field_label(field)} is '{value}', which {WHY.get(why, why)}. {base}"
        q.append({"field": field, "problem": why, "ask": (text + (" " + extra if extra else "")).strip()})

    def take(field, parser, *args):
        v = get(raw, field)
        try:
            val, note = parser(v, *args) if args else parser(v)
        except Unclear as e:
            ask(field, str(e), v)
            return None
        if note:
            notes.append(note)
        return val

    inp = {}
    inp["target"] = take("target.pipeline", parse_money)
    inp["due"] = take("target.due_date", parse_date)
    for f in ("audience.accounts", "offer.offer", "offer.cta", "message.claim"):
        if blank(get(raw, f)):
            ask(f, "blank")
    roles = get(raw, "audience.roles")
    if isinstance(roles, str):
        roles = [r.strip() for r in re.split(r",|;| and ", roles) if r.strip()]
    if blank(roles):
        ask("audience.roles", "blank")
        roles = []
    inp["roles"] = roles
    inp["launch"] = take("launch.date", parse_date)
    inp["weeks"] = inp["end"] = None
    if inp["launch"]:
        try:
            inp["weeks"], inp["end"], note = parse_run(get(raw, "launch.run"), inp["launch"])
            if note:
                notes.append(note)
        except Unclear as e:
            ask("launch.run", str(e), get(raw, "launch.run"))
    inp["avg_deal"] = take("funnel.avg_deal", parse_money)
    if inp["avg_deal"] == 0:
        ask("funnel.avg_deal", "range", 0); inp["avg_deal"] = None
    inp["rate"] = take("funnel.lead_to_opp_rate", parse_rate)
    inp["lag"] = take("funnel.lead_to_opp_days", parse_days)

    chans = raw.get("channels") or []
    if not chans:
        ask("channels", "blank")
    names = set()
    inp["channels"] = []
    for i, c in enumerate(chans):
        name = str(c.get("name") or "").strip() or f"Channel {i + 1}"
        if name.lower() in names:
            q.append({"field": f"channels.{name}", "problem": "duplicate",
                      "ask": f"Two channels are both called {name}. Are they one channel or two? Give each its own name."})
        names.add(name.lower())
        ctype = str(c.get("type") or "").strip().lower()
        if ctype not in CHANNEL_TYPES:
            q.append({"field": f"channels.{name}.type", "problem": "unreadable" if ctype else "blank",
                      "ask": f"What kind of channel is {name}? One of: " + ", ".join(CHANNEL_TYPES) + "."})
        ch = {"id": f"C{i + 1}", "name": name, "type": ctype, "platform": str(c.get("platform") or "").strip(),
              "reach": str(c.get("reach") or "").strip(), "budget": None, "cpl": None}
        bv = c.get("budget")
        try:
            ch["budget"], note = parse_money(bv)
            if note:
                notes.append(f"{name} budget: {note}")
        except Unclear as e:
            q.append({"field": f"channels.{name}.budget", "problem": str(e),
                      "ask": f"What is the budget for {name}? Write $0 if it runs on no budget." if str(e) == "blank"
                      else f"The budget for {name} is '{bv}', which {WHY.get(str(e), str(e))}. What is it in US dollars?"})
        cv = c.get("cost_per_lead")
        if ch["budget"] == 0 and blank(cv):
            pass  # a channel with no budget buys no leads; check 3 flags it
        else:
            try:
                ch["cpl"], note = parse_money(cv)
                if ch["cpl"] == 0:
                    raise Unclear("range")
                if note:
                    notes.append(f"{name} cost per lead: {note}")
            except Unclear as e:
                q.append({"field": f"channels.{name}.cost_per_lead", "problem": str(e),
                          "ask": f"What does a lead from {name} cost you today?" if str(e) == "blank"
                          else f"The cost per lead for {name} is '{cv}', which {WHY.get(str(e), str(e))}. What does a lead from {name} cost in US dollars?"})
        inp["channels"].append(ch)

    # budget total vs the sum of the channels
    bt = raw.get("budget_total")
    csum = sum(c["budget"] for c in inp["channels"] if c["budget"] is not None)
    inp["budget_total"] = None
    if not blank(bt):
        try:
            inp["budget_total"], note = parse_money(bt)
            if note:
                notes.append(f"Budget total: {note}")
        except Unclear as e:
            q.append({"field": "budget_total", "problem": str(e),
                      "ask": f"The total budget is '{bt}', which {WHY.get(str(e), str(e))}. What is it in US dollars?"})
    all_budgets = all(c["budget"] is not None for c in inp["channels"])
    if inp["budget_total"] is not None and inp["channels"] and (
            (all_budgets and abs(inp["budget_total"] - csum) > 0.5) or (not all_budgets and csum > inp["budget_total"] + 0.5)):
        q.append({"field": "budget_total", "problem": "mismatch",
                  "ask": f"The channel budgets {'add up to' if all_budgets else 'you gave already add up to'} {fmt_exact(csum)}, but the total is {fmt_exact(inp['budget_total'])}. Which is right, and which channel changes?"})
    if inp["budget_total"] is None and all_budgets:
        inp["budget_total"] = csum

    if inp["due"] and inp["launch"] and inp["due"] < inp["launch"]:
        q.append({"field": "target.due_date", "problem": "range",
                  "ask": f"The due date, {fmt_date(inp['due'])}, is before the launch, {fmt_date(inp['launch'])}. Which date is wrong?"})

    # optional inputs: read if present and clear, ignore silently if blank, ask if unreadable
    def opt(field, parser):
        v = get(raw, field)
        if blank(v):
            return None
        try:
            out = parser(v)
            return out[0] if isinstance(out, tuple) else out
        except Unclear as e:
            q.append({"field": field, "problem": str(e), "ask": f"{field_label(field)} is '{v}', which {WHY.get(str(e), str(e))}. Give the number, or leave it out."})
            return None

    inp["reps"] = opt("sales.reps", parse_count)
    inp["per_rep"] = opt("sales.opps_per_rep_month", parse_count)
    inp["win_rate"] = opt("revenue.win_rate", parse_rate)
    inp["cycle"] = opt("revenue.sales_cycle_days", parse_days)

    # assumptions: only the required funnel numbers and channel costs per lead can be assumed
    valid = set(REQUIRED_ASSUMABLE) | {f"channels.{c['name']}.cost_per_lead" for c in inp["channels"]}
    assumed = []
    for a in raw.get("assumptions") or []:
        a = str(a).strip()
        if a in valid:
            assumed.append(a)
        else:
            q.append({"field": "assumptions", "problem": "unreadable",
                      "ask": f"'{a}' is marked as an assumption, but only the funnel numbers and each channel's cost per lead can be. Which number did you mean?"})
    inp["assumptions"] = assumed
    return inp, notes, q


def field_label(field):
    labels = {"target.pipeline": "The pipeline target", "target.due_date": "The due date", "launch.date": "The launch date",
              "launch.run": "The run length", "funnel.avg_deal": "The average deal size",
              "funnel.lead_to_opp_rate": "The lead-to-opportunity rate", "funnel.lead_to_opp_days": "Days from lead to opportunity",
              "sales.reps": "The number of reps", "sales.opps_per_rep_month": "Opportunities per rep a month",
              "revenue.win_rate": "The win rate", "revenue.sales_cycle_days": "The sales cycle", "budget_total": "The total budget"}
    return labels.get(field, field)


# ---------------------------------------------------------------- the math
def spread(total, weeks):
    """Whole leads per week, even, remainder to the earliest weeks."""
    base, extra = divmod(int(total), weeks)
    return [base + (1 if i < extra else 0) for i in range(weeks)]


def compute(inp):
    rate, deal, target, lag = inp["rate"], inp["avg_deal"], inp["target"], inp["lag"]
    weeks, launch, due = inp["weeks"], inp["launch"], inp["due"]
    chans = []
    for c in inp["channels"]:
        leads = int(math.floor(c["budget"] / c["cpl"] + EPS)) if c["budget"] and c["cpl"] else 0
        opps = leads * rate
        chans.append({**c, "leads": leads, "opps": opps, "pipeline": opps * deal,
                      "weekly_spend": c["budget"] / weeks,
                      "min_budget_one_opp": int(math.ceil(1 / rate - EPS)) * c["cpl"] if c["cpl"] else None})
    budget = sum(c["budget"] for c in inp["channels"])
    planned_leads = sum(c["leads"] for c in chans)
    planned_opps = planned_leads * rate
    planned_pipe = planned_opps * deal
    opps_needed = int(math.ceil(target / deal - EPS))
    leads_needed = int(math.ceil(opps_needed / rate - EPS))
    blended = budget / planned_leads if planned_leads else None
    extra_leads = max(0, leads_needed - planned_leads)
    funnel = {
        "target": target, "avg_deal": deal, "rate": rate, "budget": budget,
        "opps_needed": opps_needed, "leads_needed": leads_needed,
        "planned_leads": planned_leads, "planned_opps": planned_opps, "planned_pipeline": planned_pipe,
        "gap": max(0.0, target - planned_pipe),
        "blended_cpl": blended,
        "cpl_ceiling": budget / leads_needed if leads_needed else None,
        "extra_leads": extra_leads,
        "extra_budget": (int(math.ceil(extra_leads * blended - EPS)) if blended else None) if extra_leads else 0,
        "reaches_target": planned_pipe + EPS >= target,
    }

    # timing: each week's leads are counted on the week's last day and become opportunities lag days later
    per_week = spread(planned_leads, weeks)
    rows, landings = [], []
    for i in range(weeks):
        start = launch + timedelta(days=7 * i)
        end = start + timedelta(days=6)
        land = end + timedelta(days=int(math.ceil(lag)))
        landings.append((i, per_week[i], land, land <= due))
    cum_l, landing_rows = 0.0, []
    for i, n, land, ok in landings:
        cum_l += n * rate * deal
        landing_rows.append({"lead_week": i + 1, "leads": n, "lands_on": land, "opps": n * rate, "pipeline_cum": cum_l, "in_time": ok})
    in_time = [x for x in landings if x[3]]
    late = [x for x in landings if not x[3]]
    pipe_in_time = sum(x[1] for x in in_time) * rate * deal
    last_land = landings[-1][2]
    shift_weeks = int(math.ceil((last_land - due).days / 7)) if late else 0
    timing = {"launch": launch, "end": inp["end"], "due": due, "weeks": weeks, "lag_days": lag,
              "weeks_in_time": len(in_time), "weeks_late": len(late),
              "pipeline_in_time": pipe_in_time, "opps_in_time": sum(x[1] for x in in_time) * rate,
              "first_land": landings[0][2], "last_land": last_land, "shift_weeks": shift_weeks,
              "meets_target_in_time": pipe_in_time + EPS >= target, "landings": landing_rows}

    # weekly pacing: launch week to the week the last opportunities land
    horizon = max(weeks, (last_land - launch).days // 7 + 1)
    land_by_week = {}
    for i, n, land, ok in landings:
        wk = (land - launch).days // 7
        land_by_week[wk] = land_by_week.get(wk, 0) + n * rate
    cum = 0.0
    for w in range(horizon):
        start = launch + timedelta(days=7 * w)
        o = land_by_week.get(w, 0.0)
        cum += o * deal
        rows.append({"week": w + 1, "start": start, "end": start + timedelta(days=6),
                     "spend": budget / weeks if w < weeks else 0.0,
                     "leads": per_week[w] if w < weeks else 0,
                     "opps_landing": o, "pipeline_cum": cum,
                     "after_due": start > due, "contains_due": start <= due <= start + timedelta(days=6)})
    # capacity
    monthly = planned_opps / weeks * MONTH_WEEKS
    cap = None
    if inp["reps"] and inp["per_rep"]:
        capv = inp["reps"] * inp["per_rep"]
        cap = {"reps": inp["reps"], "per_rep": inp["per_rep"], "capacity": capv, "monthly_opps": monthly,
               "over": monthly > capv + EPS, "reps_needed": int(math.ceil(monthly / inp["per_rep"] - EPS))}
    revenue = None
    if inp["win_rate"]:
        revenue = {"win_rate": inp["win_rate"], "projected": planned_pipe * inp["win_rate"],
                   "cycle_days": inp["cycle"],
                   "lands_by": (last_land + timedelta(days=int(math.ceil(inp["cycle"])))) if inp["cycle"] else None}
    return chans, funnel, timing, rows, cap, monthly, revenue


# ---------------------------------------------------------------- checks 1 to 4
def script_checks(inp, chans, f, t, cap, monthly):
    out = []
    # 1
    if f["reaches_target"]:
        out.append(chk(1, "pass", f"The plan buys {fmt_count(f['planned_leads'])} leads, {fmt_count(f['planned_opps'])} opportunities "
                       f"and {fmt_money(f['planned_pipeline'])} in pipeline against a {fmt_money(f['target'])} target.", ""))
    else:
        fix = (f"Add {fmt_money(f['extra_budget'])} at today's blended cost per lead of {fmt_money(f['blended_cpl'])}, "
               f"bring the blended cost per lead down to {fmt_money(f['cpl_ceiling'])}, or cut the target to {fmt_money(f['planned_pipeline'])}."
               if f["blended_cpl"] else "Fund at least one channel with a cost per lead, or cut the target.")
        out.append(chk(1, "fail", f"The plan buys {fmt_money(f['planned_pipeline'])} in pipeline against a {fmt_money(f['target'])} target, "
                       f"{fmt_money(f['gap'])} short. It needs {fmt_count(f['leads_needed'])} leads and buys {fmt_count(f['planned_leads'])}.", fix))
    # 2
    due = fmt_date(t["due"])
    if t["weeks_late"] == 0:
        out.append(chk(2, "pass", f"Every week's leads become opportunities by {due}. The last land on {fmt_date(t['last_land'])}.", ""))
    else:
        n = t["weeks_late"]
        wk = "week" if n == 1 else "weeks"
        fix = (f"Launch {t['shift_weeks']} {'week' if t['shift_weeks'] == 1 else 'weeks'} earlier, "
               f"or move the due date to {fmt_date(t['last_land'])}.")
        if t["meets_target_in_time"]:
            out.append(chk(2, "flag", f"Leads from the last {n} {wk} land after {due}. The pipeline that lands in time, "
                           f"{fmt_money(t['pipeline_in_time'])}, still meets the target.", fix))
        else:
            out.append(chk(2, "fail", f"Leads from the last {n} {wk} land after {due}. Only {fmt_money(t['pipeline_in_time'])} "
                           f"of pipeline lands in time against a {fmt_money(f['target'])} target.", fix))
    # 3
    thin = [c for c in chans if c["opps"] < 1 - EPS]
    if not thin:
        out.append(chk(3, "pass", "Every channel buys at least one opportunity in the window.", ""))
    else:
        parts, fixes = [], []
        for c in thin:
            if not c["budget"]:
                parts.append(f"{c['name']} has no budget")
                fixes.append(f"give {c['name']} a budget or cut it")
            else:
                parts.append(f"{c['name']} buys {fmt_count(c['opps'])} expected opportunities")
                fixes.append(f"fund {c['name']} to at least {fmt_money(c['min_budget_one_opp'])} or cut it and move its budget")
        out.append(chk(3, "flag", "; ".join(parts) + ". A channel below one opportunity is too thin to read.",
                       (" ".join(x[0].upper() + x[1:] + "." for x in fixes))))
    # 4
    if cap is None:
        out.append(chk(4, "flag", f"Not run. Sales capacity was not given. The plan sends {fmt_count(monthly)} opportunities a month.",
                       "Get the number of reps who will work these opportunities, and how many new opportunities each can take a month.",
                       not_run=True))
    elif cap["over"]:
        extra = cap["reps_needed"] - cap["reps"]
        out.append(chk(4, "fail", f"The plan sends {fmt_count(monthly)} opportunities a month to a team that can work {fmt_count(cap['capacity'])}.",
                       f"Add {fmt_count(extra)} {'rep' if extra == 1 else 'reps'}, or slow the pacing so the monthly flow stays at {fmt_count(cap['capacity'])} or under."))
    else:
        out.append(chk(4, "pass", f"The plan sends {fmt_count(monthly)} opportunities a month. The team can work {fmt_count(cap['capacity'])}.", ""))
    return out


def chk(n, state, reason, fix, not_run=False):
    return {"n": n, "name": SCRIPT_CHECKS.get(n) or RUBRIC_CHECKS.get(n), "by": "script" if n <= 4 else "claude",
            "state": state, "reason": reason, "fix": fix, "not_run": not_run}


def read_rubric(rub):
    """Claude's results for checks 5 to 10. Returns (checks, problems)."""
    probs, out = [], []
    src = (rub or {}).get("checks", rub or {})
    for n, name in RUBRIC_CHECKS.items():
        r = src.get(str(n)) or src.get(n)
        if not r:
            probs.append(f"Check {n} ({name}) has no result.")
            continue
        st = str(r.get("state", "")).strip().lower()
        if st not in STATES:
            probs.append(f"Check {n} state must be pass, flag or fail, not '{r.get('state')}'.")
            continue
        if not str(r.get("reason", "")).strip():
            probs.append(f"Check {n} needs a reason.")
        if st != "pass" and not str(r.get("fix", "")).strip():
            probs.append(f"Check {n} is {st} and needs a fix.")
        out.append(chk(n, st, str(r.get("reason", "")).strip(), str(r.get("fix", "")).strip()))
    return out, probs


def verdict_for(checks, assumptions):
    states = [c["state"] for c in checks]
    if "fail" in states:
        return "Not ready"
    if assumptions:
        return "Untested"
    if "flag" in states:
        return "Ready with flags"
    return "Ready"


def functions_for(chans, offer_asset=False):
    out = {}
    for fn in FUNCTIONS:
        if fn in ("operations", "sales"):
            out[fn] = {"active": True, "because": "Every campaign needs tracking and follow-up."}
            continue
        using = [c["id"] for c in chans if fn in CHANNEL_TYPES.get(c["type"], ((), ""))[0]]
        if fn == "content" and offer_asset:
            using = ["O1"] + using
        if using:
            out[fn] = {"active": True, "because": "Called for by " + ", ".join(using) + "."}
        else:
            ids = [c["id"] for c in chans]
            span = ids[0] if len(ids) == 1 else f"{ids[0]} to {ids[-1]}"
            extra = " and the offer needs no asset built" if fn == "content" else ""
            out[fn] = {"active": False, "because": f"Not in this campaign. Channels {span} include no channel that uses {FUNCTION_NAMES[fn]}{extra}."}
    return out


def sent(x):
    """One clean sentence: trimmed, one closing period."""
    x = str(x or "").strip().rstrip(".").strip()
    return x + "." if x else ""


def strategy_lines(raw, inp, chans):
    A = set(inp["assumptions"])
    tag = lambda k: " (Assumption)" if k in A else ""
    L = []
    L += [{"id": "T1", "label": "Pipeline target", "text": f"{fmt_exact(inp['target'])} in pipeline by {fmt_date(inp['due'])}", "covered": True},
         {"id": "A1", "label": "Audience", "text": f"{sent(get(raw, 'audience.accounts'))} Roles: {', '.join(inp['roles'])}.", "covered": True},
         {"id": "O1", "label": "Offer", "text": f"{sent(get(raw, 'offer.offer'))} CTA: {sent(get(raw, 'offer.cta'))}", "covered": True},
         {"id": "M1", "label": "Message", "text": sent(get(raw, "message.claim")) +
          (f" Proof: {sent(get(raw, 'message.proof'))}" if not blank(get(raw, "message.proof")) else ""), "covered": True}]
    for c in chans:
        L.append({"id": c["id"], "label": f"Channel: {c['name']}", "covered": True,
                  "text": f"{c['name']} ({c['type'].replace('_', ' ')}), {fmt_exact(c['budget'])}" +
                  (f" at {fmt_exact(c['cpl'])} a lead" + tag(f"channels.{c['name']}.cost_per_lead") if c["cpl"] else "")})
    L.append({"id": "K1", "label": "Tracking", "covered": True,
              "text": str(raw.get("tracking") or "").strip() or "Not stated in the strategy."})
    L.append({"id": "B1", "label": "Budget", "text": f"{fmt_exact(inp['budget_total'])} total", "covered": False})
    L.append({"id": "L1", "label": "Launch", "text": f"{fmt_date(inp['launch'])} for {inp['weeks']} weeks, to {fmt_date(inp['end'])}", "covered": False})
    L.append({"id": "F1", "label": "Funnel", "covered": False,
              "text": f"Average deal {fmt_exact(inp['avg_deal'])}{tag('funnel.avg_deal')}, {fmt_rate(inp['rate'])}{tag('funnel.lead_to_opp_rate')} of leads "
                      f"become opportunities in {fmt_days(inp['lag'])} days{tag('funnel.lead_to_opp_days')}"})
    return L


def assumption_value(a, inp):
    if a == "funnel.avg_deal":
        return "Average deal size", fmt_money(inp["avg_deal"])
    if a == "funnel.lead_to_opp_rate":
        return "Lead-to-opportunity rate", fmt_rate(inp["rate"])
    if a == "funnel.lead_to_opp_days":
        return "Days from lead to opportunity", fmt_days(inp["lag"]) + " days"
    name = a.split(".", 1)[1].rsplit(".", 1)[0]
    c = next(c for c in inp["channels"] if c["name"] == name)
    return f"Cost per lead for {name}", fmt_money(c["cpl"])


def compare(prev, cur):
    if not prev or prev.get("stop"):
        return []
    ch = []
    pc = {c["n"]: c["state"] for c in prev.get("checks", [])}
    for c in cur["checks"]:
        if c["n"] in pc and pc[c["n"]] != c["state"]:
            ch.append({"what": f"Check {c['n']}: {c['name']}", "from": pc[c["n"]].capitalize(), "to": c["state"].capitalize()})
    pi, ci = prev.get("inputs", {}), cur["inputs"]
    pairs = [("target", "Pipeline target", fmt_money), ("budget_total", "Budget", fmt_money), ("avg_deal", "Average deal", fmt_money),
             ("rate", "Lead-to-opportunity rate", fmt_rate), ("lag_days", "Days from lead to opportunity", fmt_days),
             ("launch", "Launch", str), ("due", "Due date", str), ("weeks", "Run length in weeks", str)]
    for k, label, fm in pairs:
        if pi.get(k) != ci.get(k):
            ch.append({"what": label, "from": fm(pi[k]) if pi.get(k) is not None else "None",
                       "to": fm(ci[k]) if ci.get(k) is not None else "None"})
    pch = {c["name"]: c for c in prev.get("channels", [])}
    cch = {c["name"]: c for c in cur["channels"]}
    for n in cch:
        if n not in pch:
            ch.append({"what": f"Channel {n}", "from": "None", "to": fmt_money(cch[n]["budget"])})
        else:
            for k, label in (("budget", "budget"), ("cpl", "cost per lead")):
                if pch[n].get(k) != cch[n].get(k):
                    ch.append({"what": f"{n} {label}", "from": fmt_money(pch[n].get(k)), "to": fmt_money(cch[n].get(k))})
    for n in pch:
        if n not in cch:
            ch.append({"what": f"Channel {n}", "from": fmt_money(pch[n]["budget"]), "to": "Cut"})
    for k, label in (("id", "CRM campaign ID"),):
        if (prev.get("campaign") or {}).get(k) != cur["campaign"].get(k):
            ch.append({"what": label, "from": (prev.get("campaign") or {}).get(k) or "None", "to": cur["campaign"].get(k)})
    pl = {l["id"]: l["text"] for l in prev.get("strategy_lines", [])}
    for l in cur["strategy_lines"]:
        if l["id"] in ("A1", "O1", "M1", "K1") and pl.get(l["id"]) not in (None, l["text"]):
            ch.append({"what": l["label"], "from": pl[l["id"]], "to": l["text"]})
    pf, cf = prev.get("funnel") or {}, cur["funnel"]
    if pf.get("planned_pipeline") is not None and abs(pf["planned_pipeline"] - cf["planned_pipeline"]) > 0.5:
        ch.append({"what": "Pipeline the plan buys", "from": fmt_money(pf["planned_pipeline"]), "to": fmt_money(cf["planned_pipeline"])})
    if prev.get("verdict") != cur["verdict"]:
        ch.append({"what": "Verdict", "from": prev.get("verdict"), "to": cur["verdict"]})
    return ch


def check(raw, rubric=None, previous=None):
    inp, notes, questions = read_strategy(raw)
    base = {"tool": "campaign-brief-builder", "version": VERSION, "mode": "check",
            "campaign": {"name": str(get(raw, "campaign.name") or "").strip() or "Untitled campaign"}}
    if questions:
        return {**base, "stop": "inputs", "questions": questions, "notes": notes}
    chans, f, t, rows, cap, monthly, rev = compute(inp)
    checks = script_checks(inp, chans, f, t, cap, monthly)
    rubric_problems = []
    if rubric is not None:
        rc, rubric_problems = read_rubric(rubric)
        if rubric_problems:
            return {**base, "stop": "rubric", "problems": rubric_problems}
        checks += rc
        verdict = verdict_for(checks, inp["assumptions"])
    else:
        verdict = "Pending rubric"
    cid = str(get(raw, "campaign.id") or "").strip() or slug(base["campaign"]["name"], 20)
    audience_tag = str(get(raw, "audience.tag") or "").strip() or slug(inp["roles"][0] if inp["roles"] else "audience", 24)
    warnings = []
    if f["planned_opps"] < 20:
        warnings.append(f"The plan rests on {fmt_count(f['planned_opps'])} expected opportunities, fewer than 20. One deal swings the result, so read counts, not rates.")
    if inp["assumptions"]:
        warnings.append("Built on assumed numbers: " + ", ".join(assumption_value(a, inp)[0] for a in inp["assumptions"]) + ". The verdict can be no better than Untested.")
    res = {
        **base,
        "round": (previous or {}).get("round", 0) + 1 if previous and not previous.get("stop") else 1,
        "campaign": {**base["campaign"], "id": cid, "objective": str(get(raw, "campaign.objective") or "pipeline").strip() or "pipeline",
                     "audience_tag": slug(audience_tag, 24)},
        "inputs": {"target": inp["target"], "due": iso(inp["due"]), "launch": iso(inp["launch"]), "end": iso(inp["end"]),
                   "weeks": inp["weeks"], "avg_deal": inp["avg_deal"], "rate": inp["rate"], "lag_days": inp["lag"],
                   "budget_total": inp["budget_total"], "roles": inp["roles"],
                   "reps": inp["reps"], "per_rep": inp["per_rep"], "win_rate": inp["win_rate"], "cycle_days": inp["cycle"],
                   "owners": {k: v for k, v in (raw.get("owners") or {}).items() if k in FUNCTIONS and not blank(v)},
                   "utm_convention": raw.get("utm_convention") or None},
        "notes": notes,
        "assumptions": [{"field": a, "label": assumption_value(a, inp)[0], "value": assumption_value(a, inp)[1]} for a in inp["assumptions"]],
        "strategy_lines": strategy_lines(raw, inp, chans),
        "channels": [{"id": c["id"], "name": c["name"], "type": c["type"], "platform": c["platform"], "reach": c["reach"],
                      "budget": c["budget"], "cpl": c["cpl"], "leads": c["leads"], "opps": c["opps"], "pipeline": c["pipeline"],
                      "weekly_spend": c["weekly_spend"], "min_budget_one_opp": c["min_budget_one_opp"],
                      "cpl_assumed": f"channels.{c['name']}.cost_per_lead" in inp["assumptions"]} for c in chans],
        "funnel": f,
        "timing": {k: (iso(v) if isinstance(v, date) else v) for k, v in t.items() if k != "landings"},
        "landings": [{k: (iso(v) if isinstance(v, date) else v) for k, v in r.items()} for r in t["landings"]],
        "pacing": [{k: (iso(v) if isinstance(v, date) else v) for k, v in r.items()} for r in rows],
        "capacity": cap, "monthly_opps": monthly,
        "revenue": {k: (iso(v) if isinstance(v, date) else v) for k, v in rev.items()} if rev else None,
        "checks": checks,
        "verdict": verdict,
        "functions": functions_for(chans, str(get(raw, "offer.asset")).strip().lower() in ("true", "yes", "1")),
        "risks_named": [{"id": f"R{i + 1}", "risk": str(r.get("risk", "")).strip(), "owner": str(r.get("owner", "")).strip() or "Unassigned"}
                        for i, r in enumerate(x for x in (raw.get("risks") or []) if isinstance(x, dict) and str(x.get("risk", "")).strip())],
        "warnings": warnings,
        "small_sample": f["planned_opps"] < 20,
    }
    res["changes"] = compare(previous, res) if previous else []
    return clean(res)


# ---------------------------------------------------------------- the brief
def utm_for(conv, ctx):
    conv = conv or {}
    d = {"source": "{platform}", "medium": "{medium}", "campaign": "{campaign_id}_{objective}_{audience}_{yyyymm}", "content": "{req_id}"}
    out = {}
    for k in ("source", "medium", "campaign", "content"):
        tpl = str(conv.get(k) or d[k])
        v = re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), tpl)
        out[k] = re.sub(r"[^A-Za-z0-9_\-.]+", "-", v).strip("-").lower()
    out["query"] = "?" + "&".join(f"utm_{k}={out[k]}" for k in ("source", "medium", "campaign", "content"))
    return out


def brief(result, spec, lead_edits=None):
    if result.get("stop"):
        return {"stop": "brief", "problems": ["The check stopped. Resolve its questions and rerun the check first."]}
    if result.get("verdict") == "Pending rubric":
        return {"stop": "brief", "problems": ["Checks 5 to 10 have no results. Rerun the check with --rubric."]}
    if result.get("verdict") == "Not ready":
        fails = [f"Check {c['n']}: {c['name']}" for c in result["checks"] if c["state"] == "fail"]
        return {"stop": "blocked", "problems": ["The verdict is Not ready. A Fail blocks the brief and cannot be overridden."] + fails}
    probs = []
    appr = spec.get("approval") or {}
    for k in ("name", "seat", "date"):
        if blank(appr.get(k)):
            probs.append(f"Approval needs the approver's {k}.")
    try:
        appr_date = parse_date(appr.get("date"))[0] if not blank(appr.get("date")) else None
    except Unclear:
        probs.append("The approval date could not be read.")
        appr_date = None

    lead = dict(DEFAULT_LEAD_DAYS)
    edited = set()
    for k, v in (lead_edits or {}).items():
        if k not in lead:
            probs.append(f"Lead time '{k}' is not a function. Use: " + ", ".join(DEFAULT_LEAD_DAYS) + ".")
            continue
        try:
            d = parse_days(v)[0]
        except Unclear:
            probs.append(f"Lead time for {k} could not be read: '{v}'.")
            continue
        if d != lead[k]:
            edited.add(k)
        lead[k] = d

    lines = {l["id"]: l for l in result["strategy_lines"]}
    chans = {c["id"]: c for c in result["channels"]}
    by_name = {c["name"].lower(): c for c in result["channels"]}
    funcs = result["functions"]
    owners = dict(result["inputs"].get("owners") or {})
    for k, v in (spec.get("owners") or {}).items():
        k = {"sales enablement": "sales", "ops": "operations", "sales_enablement": "sales"}.get(str(k).strip().lower(), str(k).strip().lower())
        if k not in FUNCTIONS:
            probs.append(f"Owner given for '{k}', which is not a function. Use: " + ", ".join(FUNCTIONS) + ".")
        elif not blank(v):
            owners[k] = str(v).strip()
    launch = date.fromisoformat(result["inputs"]["launch"])
    end = date.fromisoformat(result["inputs"]["end"])
    camp = result["campaign"]

    reqs = []
    keys = set()
    for i, r in enumerate(spec.get("requirements") or []):
        key = str(r.get("key") or f"r{i + 1}").strip()
        if key in keys:
            probs.append(f"Requirement key '{key}' is used twice.")
        keys.add(key)
        fn = str(r.get("function", "")).strip().lower()
        fn = {"sales enablement": "sales", "ops": "operations", "sales_enablement": "sales"}.get(fn, fn)
        label = f"Requirement '{key}'"
        if fn not in FUNCTIONS:
            probs.append(f"{label} has function '{r.get('function')}'. Use one of: " + ", ".join(FUNCTIONS) + ".")
            continue
        if not funcs[fn]["active"]:
            probs.append(f"{label} is in {FUNCTION_NAMES[fn]}, which is not in this campaign.")
        tr = str(r.get("traces_to", "")).strip().upper()
        if tr not in lines:
            probs.append(f"{label} traces to '{r.get('traces_to')}', which is not a strategy line. Use: " + ", ".join(lines) + ".")
        if blank(r.get("requirement")):
            probs.append(f"{label} has no requirement text.")
        if blank(r.get("acceptance")):
            probs.append(f"{label} has no acceptance test.")
        ch = str(r.get("channel") or "").strip()
        if ch:
            c = chans.get(ch.upper()) or by_name.get(ch.lower())
            if not c:
                probs.append(f"{label} names channel '{ch}', which is not in the strategy.")
                ch = None
            else:
                ch = c["id"]
        else:
            ch = None
        when = str(r.get("when") or "pre-launch").strip().lower()
        if when not in ("pre-launch", "launch", "ongoing"):
            probs.append(f"{label} has when '{r.get('when')}'. Use pre-launch, launch or ongoing.")
            when = "pre-launch"
        if r.get("carries_budget") and not ch:
            probs.append(f"{label} carries a budget but names no channel.")
        prevents = str(r.get("prevents") or "").strip().upper() or None
        if prevents and prevents not in {x["id"] for x in result.get("risks_named") or []}:
            probs.append(f"{label} prevents '{r.get('prevents')}', which is not a named risk. Use: " + (", ".join(x["id"] for x in result.get("risks_named") or []) or "none named") + ".")
            prevents = None
        reqs.append({"key": key, "prevents": prevents, "function": fn, "requirement": str(r.get("requirement", "")).strip(), "traces_to": tr,
                     "channel": ch, "carries_budget": bool(r.get("carries_budget")), "when": when,
                     "owner_given": str(r.get("owner") or "").strip(), "depends_on": [str(x).strip() for x in (r.get("depends_on") or [])],
                     "acceptance": str(r.get("acceptance", "")).strip(), "auto": False})

    for r in reqs:
        for d in r["depends_on"]:
            if d not in keys:
                probs.append(f"Requirement '{r['key']}' depends on '{d}', which does not exist.")

    # every funded channel has exactly one requirement carrying its budget
    for c in result["channels"]:
        n = sum(1 for r in reqs if r["channel"] == c["id"] and r["carries_budget"])
        if c["budget"] and n != 1:
            probs.append(f"{c['id']} {c['name']} has a {fmt_money(c['budget'])} budget. Exactly one requirement must carry it; {n} do.")
    # active functions have work
    for fn in FUNCTIONS:
        if funcs[fn]["active"] and not any(r["function"] == fn for r in reqs):
            probs.append(f"{FUNCTION_NAMES[fn]} is in this campaign and has no requirement.")

    # tracking task and assumption tasks, written by the script
    auto = [{"key": "_ops_campaign", "prevents": None, "function": "operations", "traces_to": "K1", "channel": None, "carries_budget": False,
             "when": "pre-launch", "owner_given": "", "depends_on": [], "auto": True,
             "requirement": f"Set up CRM campaign {camp['id']}, or confirm it exists. Every opportunity from this campaign carries it as its campaign source, "
                            + ("under the credit rule in line K1. " if lines["K1"]["text"] != "Not stated in the strategy." else "under a credit rule Operations writes into line K1 before launch. ")
                            + "Every link uses the UTMs in this brief.",
             "acceptance": f"A test lead from each channel creates a record that shows campaign {camp['id']} and its UTMs in the CRM."}]
    for a in result.get("assumptions") or []:
        is_cpl = a["field"].endswith(".cost_per_lead")
        lab = a["label"][0].lower() + a["label"][1:]
        chan_id = next((c["id"] for c in result["channels"] if is_cpl and a["field"] == f"channels.{c['name']}.cost_per_lead"), None)
        fn_for = "operations"
        if chan_id:
            fns = [x for x in CHANNEL_TYPES[chans[chan_id]["type"]][0] if funcs[x]["active"]] or (["sales"] if chans[chan_id]["type"] == "outbound" else [])
            fn_for = fns[0] if fns else "operations"
        auto.append({"key": "_assume_" + slug(a["field"], 40), "prevents": None, "function": fn_for, "traces_to": chan_id or "F1", "channel": None,
                     "carries_budget": False, "when": "week-one" if is_cpl else "first-opps", "owner_given": "", "depends_on": [], "auto": True,
                     "requirement": f"Replace the Assumption for {lab} ({a['value']}) with the measured number "
                                    + ("from the first week of spend" if is_cpl else "once the first opportunities land") + ", then rerun the check.",
                     "acceptance": f"The strategy shows a measured {lab}, and the check has been rerun on it."})
    reqs = auto[:1] + reqs + auto[1:]

    # coverage both ways
    covered = {r["traces_to"] for r in reqs}
    for l in result["strategy_lines"]:
        if l["covered"] and l["id"] not in covered:
            probs.append(f"Strategy line {l['id']} ({l['label']}) has no requirement.")

    # cycle check in dependencies
    graph = {r["key"]: r["depends_on"] for r in reqs}
    state = {}

    def visit(k, stack):
        if state.get(k) == 1:
            probs.append("Dependencies loop: " + " -> ".join(stack + [k]) + ".")
            return
        if state.get(k) == 2:
            return
        state[k] = 1
        for d in graph.get(k, []):
            if d in graph:
                visit(d, stack + [k])
        state[k] = 2

    for k in graph:
        visit(k, [])

    if probs:
        return {"stop": "brief", "problems": sorted(set(probs), key=probs.index)}

    # IDs, dates, owners, budgets, UTMs
    counters = {fn: 0 for fn in FUNCTIONS}
    ordered = []
    for fn in FUNCTIONS:
        for r in reqs:
            if r["function"] == fn:
                counters[fn] += 1
                r["id"] = f"{PREFIX[fn]}-{counters[fn]:02d}"
                ordered.append(r)
    idmap = {r["key"]: r["id"] for r in ordered}
    unassigned = []
    for r in ordered:
        r["owner"] = r["owner_given"] or owners.get(r["function"]) or "Unassigned"
        if r["owner"] == "Unassigned":
            unassigned.append(r["id"])
        if r["when"] == "pre-launch":
            d = launch - timedelta(days=int(math.ceil(lead[r["function"]])))
            r["due"], r["due_label"] = iso(d), fmt_date(d)
        elif r["when"] == "launch":
            r["due"], r["due_label"] = iso(launch), fmt_date(launch)
        elif r["when"] == "week-one":
            d = launch + timedelta(days=6)
            r["due"], r["due_label"] = iso(d), fmt_date(d)
        elif r["when"] == "first-opps":
            d = date.fromisoformat(result["timing"]["first_land"])
            r["due"], r["due_label"] = iso(d), fmt_date(d)
        else:
            r["due"], r["due_label"] = None, f"Ongoing, {fmt_date(launch)} to {fmt_date(end)}"
        if r["carries_budget"]:
            r["budget"], r["budget_label"] = chans[r["channel"]]["budget"], f"{fmt_exact(chans[r['channel']]['budget'])}, the {r['channel']} budget"
        else:
            r["budget"], r["budget_label"] = None, "No separate budget"
        r["depends_on_ids"] = [idmap[k] for k in r["depends_on"]]
        r["trace_label"] = f"{r['traces_to']}: {lines[r['traces_to']]['label']}"
        if r["channel"]:
            c = chans[r["channel"]]
            ctx = {"platform": slug(c["platform"] or c["name"], 20), "medium": CHANNEL_TYPES[c["type"]][1], "channel": slug(c["name"], 20),
                   "campaign_id": slug(camp["id"], 20), "objective": slug(camp["objective"], 12), "audience": camp["audience_tag"],
                   "yyyymm": launch.strftime("%Y%m"), "req_id": r["id"].lower()}
            r["utm"] = utm_for(result["inputs"].get("utm_convention"), ctx)
        else:
            r["utm"] = None
    by_id = {r["id"]: r for r in ordered}
    conflicts = []
    for r in ordered:
        for d in r["depends_on_ids"]:
            dep = by_id[d]
            if r["due"] and dep["due"] and dep["due"] > r["due"]:
                conflicts.append(f"{r['id']} is due {r['due_label']} but depends on {d}, due {dep['due_label']}.")
            if r["due"] and dep["due"] is None:
                conflicts.append(f"{r['id']} is due {r['due_label']} but depends on {d}, which is ongoing.")

    spent = sum(r["budget"] for r in ordered if r["budget"])
    recon = {"channels_total": sum(c["budget"] for c in result["channels"]), "budget_total": result["inputs"]["budget_total"],
             "requirements_total": spent}
    recon["ok"] = abs(recon["channels_total"] - recon["budget_total"]) < 0.5 and abs(recon["requirements_total"] - recon["channels_total"]) < 0.5

    risk_owner = {str(k): str(v).strip() for k, v in (spec.get("risk_owners") or {}).items()}
    risks = []
    for c in result["checks"]:
        if c["state"] == "flag":
            risks.append({"source": f"Check {c['n']}: {c['name']}", "risk": c["reason"], "fix": c["fix"],
                          "owner": risk_owner.get(str(c["n"])) or "Unassigned"})
    for rn in result.get("risks_named") or []:
        by = [r["id"] for r in ordered if r.get("prevents") == rn["id"]]
        risks.append({"source": f"Named in the strategy ({rn['id']})", "risk": rn["risk"], "fix": ("See " + ", ".join(by)) if by else "", "owner": rn["owner"]})

    f = result["funnel"]
    measurement = {
        "primary": f"{fmt_money(f['target'])} in pipeline and {fmt_count(f['opps_needed'])} opportunities by {fmt_date(date.fromisoformat(result['inputs']['due']))}",
        "leading": [(lambda lo, hi: f"{lo} leads a week" if lo == hi else f"{lo} to {hi} leads a week")(
                        min(p["leads"] for p in result["pacing"][:result["inputs"]["weeks"]]), max(p["leads"] for p in result["pacing"][:result["inputs"]["weeks"]])),
                    f"{fmt_count(f['planned_opps'] / result['inputs']['weeks'])} opportunities a week once leads convert",
                    f"{fmt_money(f['budget'] / result['inputs']['weeks'])} spend a week"],
        "revenue": (f"{fmt_money(result['revenue']['projected'])} closed revenue at a {fmt_rate(result['revenue']['win_rate'])} win rate"
                    + (f", the last of it by {fmt_date(date.fromisoformat(result['revenue']['lands_by']))}" if result["revenue"].get("lands_by") else "")
                    + ". A projection, not a forecast." if result.get("revenue") else None),
        "crm_campaign": camp["id"],
        "diagnostics_only": "Clicks, impressions and MQL counts are Ads diagnostics, never KPIs.",
    }
    sections = []
    for fn in FUNCTIONS:
        sections.append({"function": fn, "name": FUNCTION_NAMES[fn], "active": funcs[fn]["active"], "because": funcs[fn]["because"],
                         "requirements": [r["id"] for r in ordered if r["function"] == fn]})
    out = {**result, "mode": "brief",
           "brief": {"approval": {"name": appr.get("name"), "seat": appr.get("seat"), "date": iso(appr_date), "date_label": fmt_date(appr_date)},
                     "stamp": result["verdict"],
                     "sections": sections,
                     "requirements": [{k: r[k] for k in ("id", "function", "requirement", "traces_to", "trace_label", "owner", "due", "due_label",
                                                           "budget", "budget_label", "depends_on_ids", "acceptance", "channel", "utm", "auto", "when", "prevents")}
                                      for r in ordered],
                     "unassigned": unassigned,
                     "dependency_conflicts": conflicts,
                     "lead_times": [{"function": fn, "name": FUNCTION_NAMES[fn], "days": lead[fn],
                                     "source": "Edited by the user" if fn in edited else "As shipped"} for fn in DEFAULT_LEAD_DAYS],
                     "reconciliation": recon,
                     "risks": risks,
                     "measurement": measurement}}
    return clean(out)


# ---------------------------------------------------------------- CLI
def clean(x):
    """Round away float noise (1344000.0000000002) so the JSON reads as the math."""
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        sys.exit(f"No file at {p}. Check the path. With no lead-time edits, leave out --lead-times.")


def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "brief") or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0 if ("--help" in sys.argv or "-h" in sys.argv) else 1)
    if sys.argv[1] == "check":
        rub = arg("--rubric")
        prev = arg("--previous")
        res = check(load(sys.argv[2]), load(rub) if rub else None, load(prev) if prev else None)
        out = arg("--json") or "result.json"
    else:
        if len(sys.argv) < 4:
            sys.exit(__doc__)
        lt = arg("--lead-times")
        res = brief(load(sys.argv[2]), load(sys.argv[3]), load(lt) if lt else None)
        out = arg("--json") or "brief_result.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(clean(res), fh, indent=1, default=str)
    if res.get("stop"):
        print(f"Stopped ({res['stop']}). See {out}.")
    else:
        print(f"{res.get('verdict')}. Written to {out}.")


if __name__ == "__main__":
    main()
