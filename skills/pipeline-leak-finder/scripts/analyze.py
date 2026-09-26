#!/usr/bin/env python3
"""Pipeline Leak Finder: which stage kills your deals, and which fix is worth the most.

Usage:
  python analyze.py <export.csv> [--json result.json] [--stages "A,B,C"]
                    [--won "Stage A"] [--lost "Stage B,Stage C"] [--pipeline "Name"] [--as-of YYYY-MM-DD]

Reads three layouts, found automatically:
  1. HubSpot deal export with "Date entered" stage columns. One row per deal.
  2. Salesforce Opportunity History report (From Stage, To Stage, Last Modified), or the
     Opportunity Field History report (Old Value, New Value, Edit Date). One row per change.
  3. Any stage log: a deal ID, a stage and the date the deal entered it. One row per change.

Returns, for every stage: conversion to the next stage, time in stage, where lost deals die,
and the closed revenue a fix is worth. The fix target is the stage's own best quarter.
Standard library only. Deterministic: same file, same numbers.
"""
import argparse, csv, io, json, math, re, statistics, sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

VERSION = "1.0.0"
MIN = {"closed": 40, "won": 10, "lost": 10}   # below this: stop
WARN_CLOSED = 150                              # below this: warn
SMALL = 20              # under this many deals behind a rate: show the count, not a percentage
Q_MIN = 20              # resolved deals a quarter needs to count
Q_MATURE = 0.8          # share of a quarter's deals that must have left the stage
Q_COUNT = 3             # qualifying quarters needed for the best-quarter target
FALLBACK_LIFT = 0.10    # equal lift when a stage has too few quarters: 10% on its own rate
EVIDENCE_Z = 3.0        # best quarter against the rest. 3, not 2: the best was picked from many quarters
STALL_Q = 0.75          # stall line: 3 in 4 deals that move on have left by then
MIN_ADVANCERS = 10      # deals that moved on, needed to draw a stall line

# ---------- reading ----------
ID_COLS = ["record id", "deal id", "opportunity id", "opportunity_id", "id", "deal_id", "hs_object_id"]
NAME_COLS = ["deal name", "opportunity name", "deal_name", "name", "dealname"]
AMOUNT_COLS = ["amount", "deal amount", "amount (company currency)", "value", "deal value", "close_value", "acv"]
CREATED_COLS = ["create date", "created date", "createdate", "created", "date created"]
CLOSE_COLS = ["close date", "closedate", "closed date", "close_date"]
CURRENT_COLS = ["deal stage", "stage", "dealstage", "current stage", "stage name"]
PIPELINE_COLS = ["pipeline", "deal pipeline"]
LONG_STAGE = ["to stage", "new stage", "stage", "stage name", "deal stage", "new value"]
LONG_DATE = ["date entered", "entered", "entered date", "changed at", "change date", "edit date",
             "last modified", "last modified date", "date", "timestamp"]
QUOTES = "\"'“”‘’"
ENTERED = re.compile(r"^(?:date entered|hs_v2_date_entered_|hs_date_entered_)\s*(.+)$", re.I)
SUFFIX = re.compile(r"^(.*\S)\s*\(([^()]*)\)$")
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%m/%d/%Y, %I:%M %p",
                "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y",
                "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y", "%d-%b-%Y"]


def read_rows(path):
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16" and "\x00" in text: continue
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    lines = text.splitlines()
    sample = "\n".join(lines[:20])
    delim = max([",", "\t", ";"], key=sample.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    # find the header: the first row with 3 or more non-blank cells
    start = next((i for i, r in enumerate(rows) if sum(1 for c in r if c.strip()) >= 3), 0)
    header = [h.strip() for h in rows[start]]
    out = []
    for r in rows[start + 1:]:
        if not any(c.strip() for c in r): continue
        out.append({h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header) if h})
    return header, out


def norm(h):
    return re.sub(r"\s+", " ", h.strip().lower().replace("_", " "))


def find(headers, names):
    low = {}
    for h in headers:
        low.setdefault(norm(h), h)
    for n in names:
        if norm(n) in low: return low[norm(n)]
    return None


def to_number(v):
    """'$45,000' -> 45000. '45k' -> 45000. '1.2M' -> 1200000. Blank -> None."""
    s = str(v).strip().lower().replace(",", "").replace("$", "").replace("usd", "").strip()
    if not s: return None
    mult = 1
    if s.endswith("k"): mult, s = 1000, s[:-1]
    elif s.endswith("m"): mult, s = 1000000, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def to_date(v):
    s = str(v).strip()
    if not s: return None
    s = re.sub(r"(\d:\d\d(?::\d\d(?:\.\d+)?)?)\s*(Z|[+-]\d\d:?\d\d)$", r"\1", s)   # time zone, only after a time
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    if re.fullmatch(r"\d{12,13}", s):          # HubSpot API epoch milliseconds
        return datetime.fromtimestamp(int(s) / 1000, timezone.utc).date()
    return None


def classify_stage(s, won=None, lost=None):
    """--won and --lost add to what the script reads on its own. A stage the user names always wins."""
    t = re.sub(r"\s+", " ", s.strip().lower())
    if won and t in won: return "won"
    if lost and t in lost: return "lost"
    if t in ("closedwon", "closed_won") or re.search(r"\bwon\b", t): return "won"
    if t in ("closedlost", "closed_lost") or re.search(r"\blost\b", t) or "disqualif" in t: return "lost"
    return "open"


def clean_stage(s):
    s = s.strip().strip(QUOTES).strip()
    return re.sub(r"\s+", " ", s)


# ---------- the three layouts, one shape out ----------
# Every parser returns deals: id -> {id, name, amount_raw, created, close, current, pipeline, events[(stage, date_raw)]}

def parse_hubspot(headers, rows, dq, want_pipeline=None):
    cols = []  # (header, stage, pipeline)
    for h in headers:
        m = ENTERED.match(h.strip())
        if not m: continue
        label = clean_stage(m.group(1))
        pm = SUFFIX.match(label)
        stage, pipe = (clean_stage(pm.group(1)), pm.group(2).strip()) if pm else (label, "")
        cols.append((h, stage, pipe))
    pcol = find(headers, PIPELINE_COLS)
    pipes = Counter(r.get(pcol, "") for r in rows) if pcol else Counter()
    col_pipes = Counter()   # pipeline -> deals with at least one date in its columns
    for r in rows:
        for p in {p for h, _, p in cols if p and r.get(h, "").strip()}:
            col_pipes[p] += 1
    main = want_pipeline or (pipes.most_common(1)[0][0] if pipes and pipes.most_common(1)[0][0] else
                             (col_pipes.most_common(1)[0][0] if col_pipes else ""))
    use = [(h, s) for h, s, p in cols if not p or not main or p.lower() == main.lower()]
    idc, namec = find(headers, ID_COLS), find(headers, NAME_COLS)
    amtc, crc, clc, curc = (find(headers, AMOUNT_COLS), find(headers, CREATED_COLS),
                            find(headers, CLOSE_COLS), find(headers, CURRENT_COLS))
    deals, other = {}, Counter()
    for i, r in enumerate(rows):
        key = r.get(idc, "") if idc else ""
        key = key or r.get(namec, "") or f"row {i + 2}"
        if pcol and main and r.get(pcol, "") and r.get(pcol, "").lower() != main.lower():
            other[r.get(pcol)] += 1
            continue
        if key in deals:
            dq["duplicate_rows"] += 1
            dq.setdefault("_dup_ids", []).append(key)
            continue
        deals[key] = {"id": key, "name": r.get(namec, "") if namec else "", "amount_raw": r.get(amtc, "") if amtc else "",
                      "created": r.get(crc, "") if crc else "", "close": r.get(clc, "") if clc else "",
                      "current": r.get(curc, "") if curc else "",
                      "events": [(s, r.get(h, "")) for h, s in use if r.get(h, "")]}
    dq["other_pipelines"] = dict(other)
    return deals, main


def parse_history(headers, rows, dq, kind):
    """Salesforce Opportunity History, Field History, or any stage log."""
    idc = find(headers, ["opportunity id", "opportunity_id", "deal id", "record id", "deal_id", "id"])
    namec = find(headers, NAME_COLS)
    amtc, crc, clc = find(headers, AMOUNT_COLS), find(headers, CREATED_COLS), find(headers, CLOSE_COLS)
    curc = find(headers, ["stage", "current stage", "deal stage"]) if kind != "long" else find(headers, ["current stage"])
    if kind == "sf_history":
        toc, fromc = find(headers, ["to stage"]), find(headers, ["from stage"])
        datec = find(headers, ["last modified", "edit date", "last modified date", "date"])
    elif kind == "sf_field":
        toc, fromc = find(headers, ["new value"]), find(headers, ["old value"])
        datec = find(headers, ["edit date", "last modified", "date"])
        fieldc = find(headers, ["field / event", "field/event", "field", "event"])
    else:
        toc, fromc = find(headers, LONG_STAGE), None
        datec = find(headers, LONG_DATE)
    by_id = bool(idc and any(r.get(idc, "") for r in rows))
    deals, starts = {}, Counter()
    for r in rows:
        name = r.get(namec, "") if namec else ""
        key = (r.get(idc, "") if idc else "") or name
        if not key: continue
        if key.lower().startswith(("total", "grand total", "confidential", "copyright")): continue
        f = (r.get(fieldc, "") if kind == "sf_field" and fieldc else "stage").lower()
        # With no ID column, two deals can share a name. A second start splits them.
        start = (kind == "sf_history" and not r.get(fromc, "").strip()) or (kind == "sf_field" and "created" in f)
        if not by_id:
            if start:
                starts[key] += 1
                if starts[key] > 1: dq["same_name_deals"] += 1
            if starts[key] > 1: key = f"{key} ({starts[key]})"
        d = deals.setdefault(key, {"id": key, "name": name, "amount_raw": "", "created": "", "created_evt": "",
                                   "close": "", "current": "", "events": [], "firsts": []})
        if amtc and r.get(amtc, ""): d["amount_raw"] = r[amtc]
        if crc and r.get(crc, ""): d["created"] = r[crc]
        if clc and r.get(clc, ""): d["close"] = r[clc]
        if curc and r.get(curc, "") and kind != "long": d["current"] = r[curc]
        when = r.get(datec, "") if datec else ""
        if kind == "sf_field":
            if "created" in f:
                d["created_evt"] = when
                continue
            if "stage" not in f:
                dq["history_rows_not_stage"] += 1
                continue
            if r.get(fromc, ""):
                d["firsts"].append((clean_stage(r[fromc]), when))   # the stage it left, to find its first stage
        to = clean_stage(r.get(toc, "")) if toc else ""
        if not to: continue
        if fromc and kind == "sf_history" and clean_stage(r.get(fromc, "")) == to:
            dq["history_rows_not_stage"] += 1
            continue
        d["events"].append((to, when))
    for d in deals.values():
        born = d["created_evt"] or d["created"]
        if kind == "sf_field" and d["firsts"]:
            first = min(d["firsts"], key=lambda x: (to_date(x[1]) or date.max))
            d["events"].insert(0, (first[0], born))              # the first stage was entered at creation
        if not d["events"] and d["current"] and born:
            d["events"] = [(clean_stage(d["current"]), born)]    # never moved: still in its first stage
        if not d["created"]: d["created"] = born
        d["current_from_events"] = not d["current"]
    dq["keyed_by_name"] = 0 if by_id else 1
    return deals


def detect_layout(headers):
    low = [norm(h) for h in headers]
    if sum(1 for h in headers if ENTERED.match(h.strip())) >= 2: return "hubspot"
    if "to stage" in low: return "sf_history"
    if "new value" in low and "old value" in low: return "sf_field"
    if find(headers, LONG_STAGE) and find(headers, LONG_DATE) and (find(headers, ID_COLS) or find(headers, NAME_COLS)):
        return "long"
    return None


# ---------- helpers ----------
def pct(q, xs):
    """Linear-interpolated percentile of a sorted list."""
    if not xs: return None
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def r1(x): return None if x is None else round(x, 1)
def r3(x): return None if x is None else round(x, 3)
def money(x): return None if x is None else int(round(x))


def qlabel(q): return f"{q[0]} Q{q[1]}"


def quarter_end(q):
    y, n = q
    return date(y + 1, 1, 1) - timedelta(days=1) if n == 4 else date(y, 3 * n + 1, 1) - timedelta(days=1)


def order_stages(deals, stages):
    """Pipeline order from the data: stage A comes before B when most deals entered A first."""
    before = Counter()
    for d in deals.values():
        seq = sorted((dt, i, s) for i, (s, dt) in enumerate(d["entries_list"]))
        names = [s for _, _, s in seq]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if a != b: before[(a, b)] += 1
    score = {s: sum(1 for t in stages if t != s and before[(s, t)] > before[(t, s)]) for s in stages}
    first_seen = {}
    for d in deals.values():
        for s, dt in d["entries_list"]:
            first_seen.setdefault(s, len(first_seen))
    return sorted(stages, key=lambda s: (-score[s], first_seen.get(s, 99)))


# ---------- the analysis ----------
def analyze(path, stages=None, won=None, lost=None, pipeline=None, as_of=None):
    headers, rows = read_rows(path)
    dq = Counter()
    layout = detect_layout(headers)
    if not layout:
        return {"stop": "Missing columns. The file needs stage history: HubSpot 'Date entered' columns, a Salesforce "
                        "Opportunity History report (From Stage, To Stage), or a deal ID with a stage and a date.",
                "columns_found": headers, "version": VERSION}
    if layout == "hubspot":
        deals, main = parse_hubspot(headers, rows, dq, pipeline)
    else:
        deals, main = parse_history(headers, rows, dq, layout), None
    won_set = {s.strip().lower() for s in won.split(",")} if won else None
    lost_set = {s.strip().lower() for s in lost.split(",")} if lost else None
    cls = lambda s: classify_stage(s, won_set, lost_set)

    today = date.today()
    ex = defaultdict(list)   # example deal IDs behind each data problem
    ref = to_date(as_of) if as_of else today
    if as_of and ref is None:
        return {"stop": f"Could not read the as-of date '{as_of}'. Use YYYY-MM-DD.", "version": VERSION}
    # parse dates and amounts
    all_stage_names = Counter()
    for d in deals.values():
        d["created_d"], d["close_d"] = to_date(d["created"]), to_date(d["close"])
        d.setdefault("current_from_events", False)
        ents = []
        for s, v in d["events"]:
            dt = to_date(v)
            if v and dt is None:
                dq["unreadable_dates"] += 1
                ex["unreadable_dates"].append(d["id"])
                continue
            if dt and dt > ref:
                dq["future_dates"] += 1
                ex["future_dates"].append(d["id"])
                continue
            if dt: ents.append((s, dt))
        ents = [e for _, e in sorted(((dt, i), (s, dt)) for i, (s, dt) in enumerate(ents))]   # oldest first
        d["entries_list"] = ents
        if d.get("current_from_events") and ents:
            d["current"] = ents[-1][0]
        for s, _ in ents: all_stage_names[s] += 1
        amt = to_number(d["amount_raw"])
        if d["amount_raw"] and amt is not None and not re.fullmatch(r"-?\d+(\.\d+)?", d["amount_raw"].strip()):
            dq["text_amounts_parsed"] += 1
        d["amount"] = amt if amt and amt > 0 else None

    stage_kind = {s: cls(s) for s in all_stage_names}
    for d in deals.values():
        if d["current"]: stage_kind.setdefault(clean_stage(d["current"]), cls(d["current"]))
    won_names = sorted(s for s, k in stage_kind.items() if k == "won")
    lost_names = sorted(s for s, k in stage_kind.items() if k == "lost")
    if not won_names or not lost_names:
        return {"stop": "No stages read as won or lost. Say which stages mean won and which mean lost.",
                "stages_found": sorted(stage_kind), "layout": layout, "version": VERSION}

    open_found = [s for s, k in stage_kind.items() if k == "open" and all_stage_names[s]]
    if stages:
        order = [clean_stage(s) for s in stages.split(",") if s.strip()]
        order_source = "Set by the user"
        unknown = [s for s in open_found if s.lower() not in {o.lower() for o in order}]
        dq_unmapped = unknown
    else:
        order = order_stages(deals, open_found)
        order_source = "Read from the data: the order most deals moved through"
        dq_unmapped = []
    idx = {s.lower(): i for i, s in enumerate(order)}

    # per deal: outcome, path through the pipeline, time in each stage
    used, no_history = [], 0
    for d in deals.values():
        cur = clean_stage(d["current"]) if d["current"] else ""
        outcome = cls(cur) if cur else "open"
        term = [(s, dt) for s, dt in d["entries_list"] if stage_kind.get(s) in ("won", "lost")]
        if not cur and term:
            outcome = stage_kind[term[-1][0]]
        first = {}
        for s, dt in d["entries_list"]:
            if s.lower() in idx:
                k = idx[s.lower()]
                if k not in first or dt < first[k]: first[k] = dt
        close_date = (min(dt for s, dt in term if stage_kind[s] == outcome) if any(stage_kind[s] == outcome for s, _ in term)
                      else d["close_d"]) if outcome != "open" else None
        d.update(outcome=outcome, first=first, closed_on=close_date)
        if not first:
            if outcome != "open":
                no_history += 1
                ex["closed_without_history"].append(d["id"])
            else: dq["open_without_history"] += 1
            continue
        ks = sorted(first)
        d["start"], d["furthest"] = ks[0], ks[-1]
        if d["created_d"] is None: d["created_d"] = min(first.values())
        # dates against pipeline order
        seq = [first[k] for k in ks]
        if any(b < a for a, b in zip(seq, seq[1:])):
            dq["deals_out_of_order"] += 1
            ex["deals_out_of_order"].append(d["id"])
        for k in range(ks[0], ks[-1]):
            if k not in first:
                dq["skipped"] += 1
                d.setdefault("skipped", []).append(k)
                ex["skipped"].append(d["id"])
        # time in each entered stage: until the next stage entered, or until close
        d["days"] = {}
        for k in ks:
            later = [first[j] for j in ks if j > k]
            end = min(later) if later else (close_date if outcome != "open" else None)
            if end is None: continue
            n = (end - first[k]).days
            if n < 0: dq["negative_durations"] += 1
            else: d["days"][k] = n
        d["age"] = None
        used.append(d)

    closed = [d for d in used if d["outcome"] != "open"]
    n_won = sum(d["outcome"] == "won" for d in closed)
    n_lost = len(closed) - n_won
    dates = [dt for d in used for dt in d["first"].values()]
    asof = to_date(as_of) if as_of else (max(dates) if dates else today)

    counts = {"rows": len(rows), "deals": len(deals), "deals_with_history": len(used), "closed": len(closed),
              "won": n_won, "lost": n_lost, "open": len(used) - len(closed),
              "closed_without_history": no_history}
    data_quality = {
        "layout": {"hubspot": "HubSpot deal export", "sf_history": "Salesforce Opportunity History",
                   "sf_field": "Salesforce Opportunity Field History", "long": "Stage log"}[layout],
        "pipeline": main,
        "duplicate_rows": dq["duplicate_rows"],
        "other_pipelines": dq["other_pipelines"] or {},
        "closed_without_history": no_history,
        "open_without_history": dq["open_without_history"],
        "deals_out_of_order": dq["deals_out_of_order"],
        "negative_durations": dq["negative_durations"],
        "skipped_stage_entries": dq["skipped"],
        "text_amounts_parsed": dq["text_amounts_parsed"],
        "won_without_amount": sum(1 for d in closed if d["outcome"] == "won" and d["amount"] is None),
        "won_without_close_date": sum(1 for d in closed if d["outcome"] == "won" and d["closed_on"] is None),
        "future_dates": dq["future_dates"],
        "unreadable_dates": dq["unreadable_dates"],
        "history_rows_not_stage": dq["history_rows_not_stage"],
        "stages_not_in_order": dq_unmapped,
        "same_name_deals": dq["same_name_deals"],
        "keyed_by": "deal name" if dq["keyed_by_name"] else "deal ID",
    }
    ex["duplicate_rows"] = dq.get("_dup_ids", [])
    ex["won_without_amount"] = [d["id"] for d in closed if d["outcome"] == "won" and d["amount"] is None]
    ex["won_without_close_date"] = [d["id"] for d in closed if d["outcome"] == "won" and d["closed_on"] is None]
    base = {"version": VERSION, "file": path.replace("\\", "/").split("/")[-1], "as_of": asof.isoformat(),
            "as_of_source": "set by the user" if as_of else "the latest stage date in the file",
            "counts": counts, "data_quality": data_quality,
            "stage_mapping": {"order": order, "order_source": order_source, "won": won_names, "lost": lost_names}}
    short = [k for k in ("closed", "won", "lost") if counts[k] < MIN[k]]
    if short:
        base["stop"] = (f"Not enough history. {counts['closed']} closed deals with stage history, {n_won} won, "
                        f"{n_lost} lost. The floor is {MIN['closed']} closed, {MIN['won']} won, {MIN['lost']} lost.")
        return base

    won_amts = [d["amount"] for d in closed if d["outcome"] == "won" and d["amount"]]
    avg_won = statistics.mean(won_amts) if won_amts else 0
    cycles = sorted((d["closed_on"] - d["created_d"]).days for d in closed
                    if d["outcome"] == "won" and d["closed_on"] and d["created_d"] and d["closed_on"] >= d["created_d"])
    open_deals = [d for d in used if d["outcome"] == "open"]
    overview = {"win_rate": r3(n_won / len(closed)), "won_revenue": money(sum(won_amts)), "avg_won_deal": money(avg_won),
                "median_won_cycle_days": r1(pct(0.5, cycles)), "open_deals": len(open_deals),
                "open_value": money(sum(d["amount"] or 0 for d in open_deals))}

    won_count = Counter()
    for d in deals.values():
        for st, _ in d["entries_list"]:
            if stage_kind.get(st) == "won": won_count[st] += 1
        if d["current"] and stage_kind.get(clean_stage(d["current"])) == "won": won_count[clean_stage(d["current"])] += 1
    won_label = won_count.most_common(1)[0][0] if won_count else "Won"

    # ---------- stage by stage ----------
    last = len(order) - 1
    out_stages, fixes = [], []
    lost_total = n_lost
    for k, s in enumerate(order):
        thru = [d for d in used if d["start"] <= k]
        fwd = [d for d in thru if d["furthest"] > k or d["outcome"] == "won"]
        died = [d for d in thru if d["furthest"] == k and d["outcome"] == "lost"]
        sitting = [d for d in thru if d["furthest"] == k and d["outcome"] == "open"]
        resolved = len(fwd) + len(died)
        conv = len(fwd) / resolved if resolved else None
        # time in stage
        adv_days = sorted(d["days"][k] for d in fwd if k in d["days"])
        died_days = sorted(d["days"][k] for d in died if k in d["days"])
        all_days = sorted(adv_days + died_days)
        line = pct(STALL_Q, adv_days) if len(adv_days) >= MIN_ADVANCERS else None
        stall = None
        if line is not None:
            closed_here = [d for d in thru if d["outcome"] != "open" and k in d["days"]]
            fast = [d for d in closed_here if d["days"][k] <= line]
            slow = [d for d in closed_here if d["days"][k] > line]
            stall = {"line_days": r1(line),
                     "under": {"deals": len(fast), "won": sum(d["outcome"] == "won" for d in fast),
                               "win_rate": r3(sum(d["outcome"] == "won" for d in fast) / len(fast)) if fast else None,
                               "small_sample": len(fast) < SMALL},
                     "over": {"deals": len(slow), "won": sum(d["outcome"] == "won" for d in slow),
                              "win_rate": r3(sum(d["outcome"] == "won" for d in slow) / len(slow)) if slow else None,
                              "small_sample": len(slow) < SMALL}}
            for d in sitting:
                if k in d["first"]:
                    d["age"] = (asof - d["first"][k]).days
        stalled_now = [d for d in sitting if line is not None and d.get("age") is not None and d["age"] > line]
        lost_amts = sorted(d["amount"] for d in died if d["amount"])
        # downstream: of deals that moved on from here and have closed, the share that won
        fwd_closed = [d for d in fwd if d["outcome"] != "open"]
        downstream = sum(d["outcome"] == "won" for d in fwd_closed) / len(fwd_closed) if fwd_closed else 0

        # ---------- the fix: this stage's own best quarter ----------
        def passed_on(d):
            if k in d["first"]: return d["first"][k]
            later = [d["first"][j] for j in d["first"] if j > k]
            if later: return min(later)
            return d["closed_on"] if d["outcome"] == "won" else None   # skipped straight to won
        byq = defaultdict(lambda: {"entered": 0, "fwd": 0, "died": 0})
        fwd_ids, died_ids = {id(d) for d in fwd}, {id(d) for d in died}
        last_year = 0
        for d in thru:
            dt = passed_on(d)
            if dt is None: continue
            if asof - timedelta(days=365) < dt <= asof: last_year += 1
            q = (dt.year, (dt.month - 1) // 3 + 1)
            byq[q]["entered"] += 1
            if id(d) in fwd_ids: byq[q]["fwd"] += 1
            elif id(d) in died_ids: byq[q]["died"] += 1
        quarters = []
        for q in sorted(byq):
            v = byq[q]
            res = v["fwd"] + v["died"]
            done = quarter_end(q) < asof
            ok = done and res >= Q_MIN and res / v["entered"] >= Q_MATURE
            quarters.append({"quarter": qlabel(q), "entered": v["entered"], "resolved": res, "moved_on": v["fwd"],
                             "rate": r3(v["fwd"] / res) if res else None, "complete": done, "counts": ok})
        good = [x for x in quarters if x["counts"]]
        fix = {"stage": s, "to": order[k + 1] if k < last else won_label, "current_rate": r3(conv),
               "deals_per_year": last_year, "downstream_win_rate": r3(downstream), "avg_won_deal": money(avg_won)}
        if conv is not None and len(good) >= Q_COUNT:
            best = sorted(good, key=lambda x: (-x["rate"], x["quarter"]))[0]
            rest_f = len(fwd) - best["moved_on"]
            rest_n = resolved - best["resolved"]
            p1, p2 = best["moved_on"] / best["resolved"], (rest_f / rest_n if rest_n else 0)
            pool = len(fwd) / resolved
            se = math.sqrt(pool * (1 - pool) * (1 / best["resolved"] + (1 / rest_n if rest_n else 0))) if 0 < pool < 1 else 0
            z = (p1 - p2) / se if se else 0
            fix.update(method="best quarter", target_rate=best["rate"], best_quarter=best["quarter"],
                       best_quarter_deals=best["resolved"], quarters_counted=len(good), z=round(z, 2),
                       evidence="holds up" if z >= EVIDENCE_Z else "could be luck")
        elif conv is not None:
            fix.update(method="equal lift", target_rate=r3(min(1.0, conv * (1 + FALLBACK_LIFT))), best_quarter=None,
                       best_quarter_deals=None, quarters_counted=len(good), z=None, evidence="no quarter to test")
        else:
            fix.update(method="none", target_rate=None, best_quarter=None, best_quarter_deals=None,
                       quarters_counted=0, z=None, evidence="no quarter to test")
        if fix["target_rate"] is not None:
            lift = max(0.0, fix["target_rate"] - r3(conv))   # rounded rates, so the tool's planner matches
            extra_wins = last_year * lift * downstream
            fix.update(lift=r3(lift), extra_wins_per_year=r1(extra_wins), value_per_year=money(extra_wins * avg_won))
        else:
            fix.update(lift=None, extra_wins_per_year=None, value_per_year=None)
        fixes.append(fix)

        out_stages.append({
            "stage": s, "to": fix["to"], "reached": resolved + len(sitting), "moved_on": len(fwd), "lost_here": len(died),
            "open_here": len(sitting), "conversion": r3(conv), "small_sample": resolved < SMALL,
            "skipped_through": sum(1 for d in used if k in d.get("skipped", [])),
            "days": {"median": r1(pct(0.5, all_days)), "p75": r1(pct(0.75, all_days)), "p90": r1(pct(0.9, all_days)),
                     "median_moved_on": r1(pct(0.5, adv_days)), "median_lost": r1(pct(0.5, died_days)),
                     "deals_timed": len(all_days)},
            "stall": stall,
            "stalled_now": {"deals": len(stalled_now), "value": money(sum(d["amount"] or 0 for d in stalled_now))},
            "losses": {"deals": len(died), "share_of_losses": r3(len(died) / lost_total) if lost_total else None,
                       "lost_value": money(sum(lost_amts)), "with_amount": len(lost_amts),
                       "median_lost_deal": money(pct(0.5, lost_amts))},
            "quarters": quarters,
        })

    ranked = sorted(fixes, key=lambda f: -(f["value_per_year"] or 0))
    for i, f in enumerate(ranked): f["rank"] = i + 1
    holds = [f for f in ranked if f["evidence"] == "holds up" and (f["value_per_year"] or 0) > 0]
    headline = holds[0] if holds else (ranked[0] if ranked and (ranked[0]["value_per_year"] or 0) > 0 else None)
    convs = [(x["conversion"], x["stage"]) for x in out_stages if x["conversion"] is not None and not x["small_sample"]]
    worst = min(convs)[1] if convs else None
    most_losses = max(out_stages, key=lambda x: x["losses"]["deals"])["stage"]
    most_lost_value = max(out_stages, key=lambda x: x["losses"]["lost_value"] or 0)["stage"]
    slowest = max((x for x in out_stages if x["days"]["median"] is not None), key=lambda x: x["days"]["median"],
                  default=None)
    penalties = [(x["stall"]["under"]["win_rate"] - x["stall"]["over"]["win_rate"], x["stage"]) for x in out_stages
                 if x["stall"] and x["stall"]["over"]["deals"] >= SMALL and x["stall"]["under"]["deals"] >= SMALL]
    stalled_list = []
    for d in used:
        if d["outcome"] != "open" or d.get("age") is None: continue
        st = out_stages[d["furthest"]]["stall"]
        if st and d["age"] > st["line_days"]:
            stalled_list.append({"deal": d["name"] or d["id"], "id": d["id"], "stage": order[d["furthest"]],
                                 "days_in_stage": d["age"], "stall_line_days": st["line_days"],
                                 "amount": money(d["amount"])})
    stalled_list.sort(key=lambda x: (-(x["amount"] or 0), -x["days_in_stage"], x["id"]))

    warnings = []
    if counts["closed"] < WARN_CLOSED:
        warnings.append(f"Only {counts['closed']} closed deals with stage history. Stage rates swing on a file this size.")
    share_nohist = no_history / (no_history + len(closed)) if (no_history + len(closed)) else 0
    if share_nohist >= 0.2:
        warnings.append(f"{no_history} closed deals have no stage history and are left out. The stage math runs on the rest.")
    ooo = data_quality["deals_out_of_order"] / len(used) if used else 0
    n_used = max(1, len(used))
    skip_share = data_quality["skipped_stage_entries"] / n_used
    reasons = []
    if share_nohist >= 0.05:
        reasons.append(f"{r3(share_nohist) * 100:.0f}% of closed deals have no stage history")
    if ooo >= 0.05:
        reasons.append(f"{r3(ooo) * 100:.0f}% of deals have stage dates out of order")
    if counts["closed"] < WARN_CLOSED:
        reasons.append(f"only {counts['closed']} closed deals with stage history")
    if data_quality["same_name_deals"]:
        reasons.append(f"{data_quality['same_name_deals']} deals share a name with another deal and there is no ID column")
    if data_quality["duplicate_rows"]:
        reasons.append(f"{data_quality['duplicate_rows']} rows exported twice")
    if skip_share >= 0.15:
        reasons.append(f"stages skipped {data_quality['skipped_stage_entries']} times")
    if data_quality["future_dates"] or data_quality["unreadable_dates"]:
        reasons.append(f"{data_quality['future_dates'] + data_quality['unreadable_dates']} stage dates in the future or unreadable")
    verdict = ("not usable" if share_nohist >= 0.3 or ooo >= 0.2 else "usable with caveats" if reasons else "usable")
    probs = [  # (check, count, fix, example key, severity: 1 breaks the stage math, 2 breaks a figure, 3 worth a look)
        ("Closed deals with no stage history", no_history,
         "Export stage history for every deal: every 'Date entered' column in HubSpot, the Opportunity History report in Salesforce",
         "closed_without_history", 1),
        ("Deals that share a name, with no ID column", data_quality["same_name_deals"],
         "Add Opportunity ID to the report so each deal is read on its own", "same_name_deals", 1),
        ("Rows exported twice", data_quality["duplicate_rows"], "Export with Record ID or Opportunity ID and dedupe on it",
         "duplicate_rows", 1),
        ("Deals with stage dates out of order", data_quality["deals_out_of_order"],
         "Fix the stage dates on these deals. " + {"hubspot": "HubSpot pipeline rules can block backward moves",
                                                    "long": "Your CRM's stage rules can block backward moves"}.get(
             layout, "Salesforce validation rules can block backward moves"), "deals_out_of_order", 1),
        ("Won deals with no amount", data_quality["won_without_amount"], "Make Amount required when a deal moves to won",
         "won_without_amount", 2),
        ("Won deals with no close date", data_quality["won_without_close_date"],
         "Make Close Date required when a deal moves to won", "won_without_close_date", 2),
        ("Stage dates after the as-of date", data_quality["future_dates"], "Fix the stage dates on these deals",
         "future_dates", 2),
        ("Stage dates the script could not read", data_quality["unreadable_dates"],
         "Store stage dates as dates, not text", "unreadable_dates", 2),
        ("Stages skipped on the way through", data_quality["skipped_stage_entries"],
         "Require every stage, or merge a stage reps routinely skip. " + {"hubspot": "HubSpot pipeline rules can block skipping",
                                                                          "long": "Your CRM's stage rules can block skipping"}.get(
             layout, "A Salesforce validation rule can require each stage in order"), "skipped", 3),
    ]
    problems = sorted(({"check": c, "count": n, "fix": f, "severity": sv, "examples": sorted(set(ex[k]))[:5]}
                       for c, n, f, k, sv in probs if n), key=lambda x: (x["severity"], -x["count"]))
    D = data_quality
    checks = [{"check": c, "count": n, "what_the_skill_did": w} for c, n, w in [
        ("Rows exported twice", D["duplicate_rows"], "Counted once"),
        ("Deals sharing a name, no ID column", D["same_name_deals"], "Split at each new start"),
        ("Deals in other pipelines", sum(D["other_pipelines"].values()),
         "Left out: " + ", ".join(f"{k} ({v})" for k, v in D["other_pipelines"].items()) if D["other_pipelines"] else ""),
        ("Closed deals with no stage history", D["closed_without_history"], "Left out of the stage math"),
        ("Open deals with no stage history", D["open_without_history"], "Left out"),
        ("Deals with stage dates out of order", D["deals_out_of_order"], "Read in pipeline order"),
        ("Negative times in stage", D["negative_durations"], "Left out of time in stage"),
        ("Stages skipped on the way through", D["skipped_stage_entries"], "Counted as passed"),
        ("Text amounts read as numbers", D["text_amounts_parsed"], "Read as numbers"),
        ("Won deals with no amount", D["won_without_amount"], "Count toward win rate, not deal value"),
        ("Won deals with no close date", D["won_without_close_date"], "Left out of the sales cycle"),
        ("Stage dates after the as-of date", D["future_dates"], "Ignored"),
        ("Stage dates the script could not read", D["unreadable_dates"], "Ignored"),
        ("History rows with no stage change", D["history_rows_not_stage"], "Skipped, not a problem"),
    ]]
    base.update({
        "overview": overview,
        "stages": out_stages,
        "fixes": ranked,
        "headline_fix": headline["stage"] if headline else None,
        "findings": {"lowest_conversion": worst, "most_lost_deals": most_losses, "most_lost_value": most_lost_value,
                     "slowest_stage": slowest["stage"] if slowest else None,
                     "biggest_stall_penalty": max(penalties)[1] if penalties else None,
                     "biggest_lost_deals": max(((x["losses"]["median_lost_deal"], x["stage"]) for x in out_stages
                                                if x["losses"]["with_amount"] >= SMALL), default=(None, None))[1],
                     "early_losses": {"before_stage": order[max(1, len(order) // 2)] if len(order) > 1 else None,
                                      "deals": sum(x["losses"]["deals"] for x in out_stages[:max(1, len(order) // 2)]),
                                      "share": r3(sum(x["losses"]["deals"] for x in out_stages[:max(1, len(order) // 2)]) / lost_total)
                                      if lost_total else None}},
        "stalled_deals": stalled_list,
        "checks": checks,
        "trust": {"verdict": verdict, "reasons": reasons, "closed_without_history_share": r3(share_nohist),
                  "out_of_order_share": r3(ooo), "problems": problems},
        "stuck": {"deals": len(stalled_list), "value": money(sum(x["amount"] or 0 for x in stalled_list))},
        "warnings": warnings,
        "rules": {"small_sample": SMALL, "quarter_min_deals": Q_MIN, "quarter_mature": Q_MATURE, "quarters_needed": Q_COUNT,
                  "fallback_lift": FALLBACK_LIFT, "evidence_z": EVIDENCE_Z, "stall_quantile": STALL_Q},
    })
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json", default=None)
    ap.add_argument("--stages", default=None, help="open stages in pipeline order, comma separated")
    ap.add_argument("--won", default=None)
    ap.add_argument("--lost", default=None)
    ap.add_argument("--pipeline", default=None, help="HubSpot pipeline to read when the file holds several")
    ap.add_argument("--as-of", default=None, help="date the export was pulled, YYYY-MM-DD")
    a = ap.parse_args()
    res = analyze(a.file, a.stages, a.won, a.lost, a.pipeline, a.as_of)
    text = json.dumps(res, indent=1, default=str)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Result written to " + a.json)
    if res.get("stop"):
        print("STOP: " + res["stop"])
        sys.exit(0)
    if not a.json:
        print(text)
        return
    o = res["overview"]
    print(f"{res['counts']['closed']} closed deals, win rate {o['win_rate']:.1%}. Trust: {res['trust']['verdict']}.")
    print("Stage order: " + " > ".join(res["stage_mapping"]["order"]))
    for x in res["stages"]:
        c = "n/a" if x["conversion"] is None else f"{x['conversion']:.1%}"
        print(f"  {x['stage']:<24} to {x['to']:<16} {c:>7}  lost here {x['losses']['deals']:>4}  median days {x['days']['median']}")
    if res["headline_fix"]:
        f = next(f for f in res["fixes"] if f["stage"] == res["headline_fix"])
        print(f"Fix worth the most: {f['stage']} ({f['method']}, {f['evidence']}) ${f['value_per_year']:,} a year")


if __name__ == "__main__":
    main()
