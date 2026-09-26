#!/usr/bin/env python3
"""Check what Claude wrote before the user sees it.

Usage:
  python lint_brief.py result.json [--strategy strategy.json] [--text readout.md ...]

result.json is the output of plan.py, check or brief mode. The linter reads every field Claude wrote in it
(the reasons and fixes for checks 5 to 10, and each requirement and its acceptance test) plus any text files
passed with --text, such as the readout. It fails on:

  - a number or date that does not come from the script's output or the user's own strategy
  - a requirement with no strategy line or no acceptance test
  - an em-dash
  - a hedge word
  - forecast language: "will produce", "will generate" and the like

Standard library only. Exit code 0 when clean, 1 when it finds a problem.
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import fmt_money, fmt_rate, fmt_count, fmt_days, fmt_date  # noqa: E402
from datetime import date  # noqa: E402

HEDGES = ["might", "perhaps", "possibly", "maybe", "arguably", "it seems", "seems to", "we think", "i think",
          "hopefully", "somewhat", "fairly", "potentially", "could potentially", "in theory", "sort of", "kind of"]
FORECAST = re.compile(r"\bwill\s+(produce|generate|deliver|drive|create|hit|reach|bring|return|yield|make)\b", re.I)
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
MNUM = {m: i + 1 for i, m in enumerate(MONTHS.split("|"))}
DATE_RE = re.compile(rf"\b(?:({MONTHS})[a-z]*\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?|(\d{{4}})-(\d{{2}})-(\d{{2}}))\b", re.I)
ID_RE = re.compile(r"\b(?:[A-Z]{2,4}-\d{2}|[TAOMCKBLF]\d{1,2}|Check\s+\d{1,2}|Week\s+\d{1,2}|utm_\w+|Q[1-4])\b", re.I)
URLISH = re.compile(r"\?utm_\S+|\b[\w.-]+_[\w.-]+_\d{6}\b")
NUM_RE = re.compile(r"(?<![\w.])(\$?)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|[kKmM](?![a-zA-Z]))?")


def canon(sign, digits, suffix):
    v = float(digits.replace(",", ""))
    if suffix in ("k", "K"):
        v *= 1e3
    elif suffix in ("m", "M"):
        v *= 1e6
    return round(v, 4), suffix == "%"


def tokens(text):
    text = URLISH.sub(" ", text)
    text = ID_RE.sub(" ", text)
    text = DATE_RE.sub(" ", text)
    return [(m.group(0).strip(), canon(*m.groups())) for m in NUM_RE.finditer(text)]


def dates_in(text):
    out = []
    for m in DATE_RE.finditer(URLISH.sub(" ", text)):
        if m.group(4):
            out.append((m.group(0), (int(m.group(4)), int(m.group(5)), int(m.group(6)))))
        else:
            out.append((m.group(0), (int(m.group(3)) if m.group(3) else None, MNUM[m.group(1)[:3].lower()], int(m.group(2)))))
    return out


def walk(x, skip, path=""):
    """Yield (path, value) for every leaf, except Claude-written fields."""
    if isinstance(x, dict):
        for k, v in x.items():
            p = f"{path}.{k}" if path else k
            if p in skip:
                continue
            yield from walk(v, skip, p)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk(v, skip, f"{path}[{i}]")
    else:
        yield path, x


def claude_fields(res):
    """(path, label, text) for every field Claude wrote in the result."""
    out = []
    for i, c in enumerate(res.get("checks", [])):
        if c.get("by") == "claude":
            out.append((f"checks[{i}].reason", f"Check {c['n']} reason", c.get("reason", "")))
            out.append((f"checks[{i}].fix", f"Check {c['n']} fix", c.get("fix", "")))
    for i, r in enumerate((res.get("brief") or {}).get("requirements", [])):
        if not r.get("auto"):
            out.append((f"brief.requirements[{i}].requirement", f"{r['id']} requirement", r.get("requirement", "")))
            out.append((f"brief.requirements[{i}].acceptance", f"{r['id']} acceptance", r.get("acceptance", "")))
    return out


def allowed_sets(res, strategy=None):
    skip = {p for p, _, _ in claude_fields(res)}
    nums, dts = set(), set()

    def add_text(s):
        for _, c in tokens(s):
            nums.add(c)
        for _, d in dates_in(s):
            dts.add(d)

    def add_value(v):
        forms = [fmt_money(v), fmt_count(v), fmt_days(v) if float(v) == int(v) else str(v), str(v)]
        if 0 < v <= 1:
            forms.append(fmt_rate(v))
        if v >= 1:
            forms.append(f"{math.ceil(v)}")
            forms.append(f"{math.floor(v)}")
        for f in forms:
            for _, c in tokens(f):
                nums.add(c)
                nums.add((c[0], False))
        if 0 < v <= 1:
            nums.add((round(v * 100, 4), True))
            nums.add((round(math.floor(v * 100 + 0.5), 4), True))

    for p, v in walk(res, skip):
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, float)):
            add_value(float(v))
        elif isinstance(v, str):
            add_text(v)
            m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
            if m:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                dts.add((d.year, d.month, d.day))
                for _, c in tokens(str(d.day)):
                    nums.add(c)
    if strategy:
        for _, v in walk(strategy, set()):
            if isinstance(v, str):
                add_text(v)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                add_value(float(v))
    return nums, dts


def num_ok(c, nums):
    v, pct = c
    if not pct and v <= 10 and v == int(v):
        return True  # small counts: "three moves", "two weeks", "Step 1"
    if not pct and 1900 <= v <= 2100 and v == int(v):
        return True  # years
    return (v, pct) in nums or (not pct and (v, False) in nums)


def lint_text(label, text, nums, dts):
    probs = []
    if "\u2014" in text:
        probs.append(f"{label}: em-dash.")
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    for h in HEDGES:
        if re.search(rf"(?<![a-z]){re.escape(h)}(?![a-z])", low):
            probs.append(f"{label}: hedge word '{h}'.")
    m = FORECAST.search(text)
    if m:
        probs.append(f"{label}: forecast language '{m.group(0)}'. Pipeline is a projection, never a promise.")
    for raw, d in dates_in(text):
        y, mo, dy = d
        if (y is None and not any(x[1:] == (mo, dy) for x in dts)) or (y is not None and d not in dts):
            probs.append(f"{label}: date '{raw}' is not in the script's output.")
    for raw, c in tokens(text):
        if not num_ok(c, nums):
            probs.append(f"{label}: '{raw}' is not in the script's output or the strategy.")
    return probs


def assumed_values(res):
    """Canonical values of every assumed number, so a bare mention without its label is caught."""
    out = set()
    for a in res.get("assumptions") or []:
        for _, c in tokens(str(a.get("value", ""))):
            out.add(c)
    return out


def unlabeled_assumptions(label, text, assumed):
    probs = []
    if not assumed:
        return probs
    for sentence in re.split(r"(?<=[.!?])\s+|\n|\|", text):
        if "assum" in sentence.lower():
            continue
        for raw, c in tokens(sentence):
            if c in assumed and not (c[0] <= 10 and not c[1]):
                probs.append(f"{label}: '{raw}' is an assumed number. Label it Assumption in the same sentence.")
    return probs


def lint(res, strategy=None, texts=None):
    nums, dts = allowed_sets(res, strategy)
    assumed = assumed_values(res)
    probs = []
    for _, label, text in claude_fields(res):
        probs += lint_text(label, str(text or ""), nums, dts)
        probs += unlabeled_assumptions(label, str(text or ""), assumed)
    br = res.get("brief")
    if br:
        lines = {l["id"] for l in res.get("strategy_lines", [])}
        for r in br.get("requirements", []):
            if r.get("traces_to") not in lines:
                probs.append(f"{r['id']}: no strategy line.")
            if not str(r.get("acceptance") or "").strip():
                probs.append(f"{r['id']}: no acceptance test.")
    for label, text in (texts or []):
        probs += lint_text(label, text, nums, dts)
        probs += unlabeled_assumptions(label, text, assumed)
    return probs


def main():
    if len(sys.argv) < 2 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 else 1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        res = json.load(fh)
    strategy = None
    texts = []
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--strategy":
            with open(args[i + 1], encoding="utf-8") as fh:
                strategy = json.load(fh)
            i += 2
        elif args[i] == "--text":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                with open(args[i], encoding="utf-8") as fh:
                    texts.append((os.path.basename(args[i]), fh.read()))
                i += 1
        else:
            i += 1
    probs = lint(res, strategy, texts)
    if probs:
        print("Lint found problems. Fix each one and lint again:")
        for p in probs:
            print("- " + p)
        sys.exit(1)
    print("Lint clean.")


if __name__ == "__main__":
    main()
