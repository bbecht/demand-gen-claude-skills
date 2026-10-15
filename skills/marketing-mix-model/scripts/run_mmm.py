#!/usr/bin/env python3
"""Fit a marketing mix model to a weekly file and write every number the readout needs.

Usage:
  python run_mmm.py <weekly.csv> --json mmm.json [--kpi COLUMN] [--margin 0.5] [--effort Quick|Standard|Thorough]
                    [--lift-tests "Paid search=3.9:0.3; TV=2.2:0.4"] [--no-holidays] [--ignore "col a,col b"]
  python run_mmm.py --demo --json mmm.json      # invented sample with the true answers planted

The file needs one row per week: a week date, sales or revenue in dollars, and one spend column per
channel. Outside drivers (price, promotions, economy, competitor), holiday flags (hol_*) and event
signals (event_*) are optional. Every number in the readout comes from this script's output.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mmm.analysis import (control_effects, dummy_effects, group_summary, headline, media_params_table,  # noqa: E402
                          response_curve, roi_table, window_mask)
from mmm.diagnostics import vif  # noqa: E402
from mmm.model import ModelSpec, fit, suggested_bounds  # noqa: E402
from mmm.optimize import optimize_budget  # noqa: E402

VERSION = "1.0.0"
WINDOW = "Last 52 weeks"
MIN_WEEKS = 52
GOOD_WEEKS = 104
MIN_SPEND_WEEKS = 8
OPT_LO, OPT_HI = 0.5, 2.0
FRONTIER = [round(x, 1) for x in np.arange(0.6, 1.61, 0.1)]

OUTCOME_WORDS = ("order", "unit", "lead", "conversion", "transaction", "customer", "revenue", "sales", "profit",
                 "impression", "click", "session", "visit", "traffic", "grp", "reach", "booking", "signup",
                 "sign_up", "install", "margin")
WEEK_NAMES = ["week", "week_start", "week_starting", "week_of", "week_beginning", "date", "period", "week_ending",
              "week_end", "start_date"]
KPI_NAMES = ["sales", "revenue", "net_sales", "gross_sales", "total_sales", "total_revenue", "net_revenue",
             "sales_revenue", "kpi", "bookings", "sales_usd", "revenue_usd"]
UPPER = {"tv": "TV", "ctv": "CTV", "ott": "OTT", "ooh": "OOH", "sem": "SEM", "ppc": "PPC", "seo": "SEO",
         "dm": "DM", "sms": "SMS", "b2b": "B2B", "usd": "", "us": "US"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")


def pretty(col: str, strip=("spend", "cost", "media", "investment", "hol", "holiday", "event")) -> str:
    words = [w for w in norm(col).split("_") if w and w not in strip]
    if not words:
        words = norm(col).split("_")
    out = [UPPER.get(w, w) for w in words]
    out = [w for w in out if w]
    s = " ".join(out)
    return s[:1].upper() + s[1:] if s else col


EURO = r"^-?\d{1,3}(\.\d{3})+,\d+$|^-?\d+,\d{1,2}$"   # 88.675,00 or 12,5: needs the comma


def to_number(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip()
    t = t.str.replace(r"(?i)\b(usd|eur|gbp|cad|aud)\b|[€£¥$]", "", regex=True).str.strip()
    mult = pd.Series(1.0, index=t.index)
    for suf, m in (("k", 1e3), ("K", 1e3), ("m", 1e6), ("M", 1e6)):
        hit = t.str.endswith(suf, na=False)
        mult[hit] = m
        t = t.where(~hit, t.str[:-1].str.strip())
    euro = t.str.match(EURO)
    t = t.where(~euro, t.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    dots = t.str.match(r"^-?\d{1,3}(\.\d{3}){2,}$")          # 1.234.567: dot thousands, no decimals
    t = t.where(~dots, t.str.replace(".", "", regex=False))
    neg = t.str.match(r"^\(.*\)$")
    t = t.str.replace(r"[,\s%()]", "", regex=True).replace({"": np.nan, "nan": np.nan, "None": np.nan,
                                                            "-": np.nan, "NaN": np.nan, "null": np.nan})
    v = pd.to_numeric(t, errors="coerce") * mult
    v[neg.fillna(False)] = -v[neg.fillna(False)]
    return v


def r(x, nd=2):
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, nd)


def money(x):
    return r(x, 0)


def stop(msg: str, out: str | None, extra: dict | None = None):
    payload = {"stop": msg, "version": VERSION}
    if extra:
        payload.update(extra)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
    print("STOP: " + msg)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Load and check the file
# ---------------------------------------------------------------------------

US_HOLIDAYS = [("hol_memorial_day", "Memorial Day"), ("hol_july_4", "July 4th"), ("hol_labor_day", "Labor Day"),
               ("hol_black_friday", "Black Friday"), ("hol_christmas", "Christmas")]


def holiday_dates(year: int) -> dict[str, pd.Timestamp]:
    may31 = pd.Timestamp(year, 5, 31)
    memorial = may31 - pd.Timedelta(days=may31.weekday())
    sep1 = pd.Timestamp(year, 9, 1)
    labor = sep1 + pd.Timedelta(days=(7 - sep1.weekday()) % 7)
    nov1 = pd.Timestamp(year, 11, 1)
    thanksgiving = nov1 + pd.Timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    return {"hol_memorial_day": memorial, "hol_july_4": pd.Timestamp(year, 7, 4), "hol_labor_day": labor,
            "hol_black_friday": thanksgiving + pd.Timedelta(days=1), "hol_christmas": pd.Timestamp(year, 12, 25)}


def add_us_holidays(df: pd.DataFrame, week_ending: bool = False) -> list[str]:
    """Flag the week whose 7 days contain each holiday. Dates mark the first day, or the last when week_ending."""
    weeks = pd.DatetimeIndex(df["week"]) - pd.Timedelta(days=6 if week_ending else 0)
    added = []
    for key, _ in US_HOLIDAYS:
        flag = np.zeros(len(df))
        for y in range(weeks.year.min() - 1, weeks.year.max() + 1):
            d = holiday_dates(y)[key]
            hit = (weeks <= d) & (d < weeks + pd.Timedelta(days=7))
            flag[np.asarray(hit)] = 1.0
        if flag.sum() > 0:
            df[key] = flag
            added.append(key)
    return added


def _parse(s: pd.Series, dayfirst: bool) -> pd.Series:
    try:
        out = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=dayfirst)
    except (ValueError, TypeError):
        out = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=dayfirst, utc=True)
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_convert(None)
    return out


def parse_dates(s: pd.Series) -> pd.Series:
    """Month-first unless day-first gives the regular 7-day rhythm and month-first does not."""
    s = s.astype(str).str.strip()
    a = _parse(s, False)
    if not s.str.match(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}").any():
        return a

    def rhythm(x):
        d = x.dropna().sort_values().diff().dt.days.dropna()
        return float((d == 7).mean()) if len(d) else 0.0
    b = _parse(s, True)
    return b if (b.notna().sum() >= a.notna().sum() and rhythm(b) > rhythm(a) + 0.2) else a


def load(path: str, kpi_arg: str | None, ignore: list[str], use_holidays: bool):
    notes, warns, quality = [], [], []
    if path.lower().endswith((".xlsx", ".xls", ".xlsm")):
        return None, "This is an Excel file. Save the sheet as CSV and upload that."
    try:
        try:
            raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
    except pd.errors.EmptyDataError:
        return None, "The file is empty."
    except (pd.errors.ParserError, ValueError):
        return None, "The file could not be read as a CSV. Save it as CSV, comma separated, and upload that."
    if raw.empty:
        return None, "The file has headers but no rows."
    raw.columns = [str(c).strip() for c in raw.columns]
    raw = raw.loc[:, [c for c in raw.columns if c and not c.lower().startswith("unnamed")]]
    raw = raw[~(raw.apply(lambda row: all(str(v).strip() == "" for v in row), axis=1))]
    cols = {norm(c): c for c in raw.columns}
    ignore_n = {norm(c) for c in ignore}

    # Week column
    week_col = next((cols[n] for n in WEEK_NAMES if n in cols), None)
    if week_col is None:
        for c in raw.columns:
            parsed = parse_dates(raw[c])
            if parsed.notna().mean() >= 0.9:
                week_col = c
                break
    if week_col is None:
        return None, f"No date column found. Columns seen: {', '.join(raw.columns)}. Add a column named week."
    wk = parse_dates(raw[week_col])
    if wk.notna().mean() < 0.5:
        return None, (f"The {week_col} column does not hold readable dates. Give each row the date its week starts, "
                      "for example 2025-01-06.")
    bad = int(wk.isna().sum())
    if bad:
        quality.append(dict(check="Unreadable dates", rows=bad, action="Rows dropped"))
    raw = raw[wk.notna()].copy()
    raw["__week"] = wk[wk.notna()].dt.normalize()

    # KPI column
    kpi_col = None
    if kpi_arg:
        kpi_col = cols.get(norm(kpi_arg))
        if kpi_col is None:
            return None, f"Column '{kpi_arg}' not found. Columns seen: {', '.join(c for c in raw.columns if c != '__week')}."
    else:
        kpi_col = next((cols[n] for n in KPI_NAMES if n in cols), None)
    if kpi_col is None:
        return None, ("No sales or revenue column found. Name the column that holds weekly sales in dollars and "
                      "rerun with --kpi. Columns seen: " + ", ".join(c for c in raw.columns if c != "__week") + ".")

    # Sort columns into roles
    spend_cols, hol_cols, ev_cols, ctrl_cols, skipped, outcome, rate_cols = [], [], [], [], [], [], []
    for c in raw.columns:
        if c in (week_col, kpi_col, "__week"):
            continue
        n = norm(c)
        if n in ignore_n:
            skipped.append(c)
            continue
        words = n.split("_")
        if n.startswith("hol_") or n.startswith("holiday"):
            hol_cols.append(c)
        elif n.startswith("event_") or n.startswith("ev_"):
            ev_cols.append(c)
        elif any(t in n for t in ("competitor", "competition", "share_of_voice")) or "sov" in words:
            ctrl_cols.append(c)
        elif any(t in n for t in ("spend", "cost", "investment")) or n.startswith("media_"):
            if any(w in words for w in ("total", "per", "cpc", "cpm", "cpa", "cpl", "cpv", "roas", "all")):
                rate_cols.append(c)
            else:
                spend_cols.append(c)
        elif "price" not in n and any((w == t + "s") if t in ("lead", "unit") else w.startswith(t)
                                      for w in words for t in OUTCOME_WORDS):
            outcome.append(c)
        else:
            ctrl_cols.append(c)
    if outcome:
        notes.append("Left out because they look like results, not causes: " + ", ".join(outcome) +
                     ". A result used as a driver soaks up the media effect.")
    if rate_cols:
        notes.append("Left out because they look like totals or unit costs, not channel spend: " +
                     ", ".join(rate_cols) + ".")
    if not spend_cols:
        return None, ("No spend columns found. Name each channel's weekly spend column with the word spend, "
                      "for example spend_paid_search or tv_spend.")

    df = pd.DataFrame({"week": raw["__week"].values})
    df["kpi"] = to_number(raw[kpi_col]).values

    # Numbers
    text_fixed = 0
    for c in [kpi_col] + spend_cols + hol_cols + ev_cols + ctrl_cols:
        s = raw[c].astype(str).str.strip()
        text_fixed += int(s.str.contains(r"[\$,%]|^\(.*\)$|[kKmM]$", regex=True).sum())
    if text_fixed:
        quality.append(dict(check="Numbers stored as text ($, commas, %, k)", rows=text_fixed, action="Read as numbers"))

    out_spend, spend_names = [], []
    for c in spend_cols:
        v = to_number(raw[c]).values
        out_spend.append(c)
        spend_names.append(pretty(c))
        df["__s_" + c] = v
    used_ctrl = []
    for c in ctrl_cols:
        v = to_number(raw[c])
        if v.notna().mean() < 0.9:
            skipped.append(c)
            continue
        df["__c_" + c] = v.values
        used_ctrl.append(c)
    for c in hol_cols:
        df["__h_" + c] = to_number(raw[c]).fillna(0).clip(0, 1).values
    for c in ev_cols:
        df["__e_" + c] = to_number(raw[c]).fillna(0).values
    if skipped:
        notes.append("Columns left out (not numbers, or set aside): " + ", ".join(skipped) + ".")

    # Cadence: daily data rolls up to weeks, monthly stops
    df = df.sort_values("week", kind="stable").reset_index(drop=True)
    gaps = df["week"].diff().dt.days.dropna()
    med = float(gaps[gaps > 0].median()) if (gaps > 0).any() else 7.0
    if med <= 2:
        start = df["week"] - pd.to_timedelta(df["week"].dt.weekday, unit="D")
        agg = {c: "sum" for c in df.columns if c.startswith("__s_") or c == "kpi"}
        agg.update({c: "mean" for c in df.columns if c.startswith("__c_") or c.startswith("__e_")})
        agg.update({c: "max" for c in df.columns if c.startswith("__h_")})
        days = df.groupby(start).size()
        df = df.groupby(start).agg(agg).reset_index().rename(columns={"index": "week"})
        df.columns = ["week"] + list(df.columns[1:])
        full = days.values == 7
        if (~full).any():
            quality.append(dict(check="Partial weeks in daily data", rows=int((~full).sum()),
                                action="Dropped"))
            df = df[full].reset_index(drop=True)
        notes.append("Daily rows were summed into Monday-start weeks.")
    elif med >= 25:
        return None, ("The file looks monthly. A mix model needs weekly rows: monthly data gives too few points "
                      "to separate channels. Export by week.")

    # Duplicate weeks
    dup = df["week"].duplicated(keep="first")
    if dup.any():
        quality.append(dict(check="Duplicate weeks", rows=int(dup.sum()), action="Kept the first row of each week"))
        df = df[~dup].reset_index(drop=True)

    # Blank sales
    blank_kpi = df["kpi"].isna()
    if blank_kpi.any():
        quality.append(dict(check="Weeks with blank sales", rows=int(blank_kpi.sum()), action="Rows dropped"))
        df = df[~blank_kpi].reset_index(drop=True)
    if (df["kpi"] < 0).any():
        return None, "Sales are negative in some weeks. Check the sales column for netted returns."

    # Missing weeks
    span = (df["week"].iloc[-1] - df["week"].iloc[0]).days / 7 + 1 if len(df) else 0
    missing = int(round(span - len(df)))
    if missing > 0:
        quality.append(dict(check="Missing weeks inside the date range", rows=missing,
                            action="Left as is. The model reads the rows as back to back"))
        if missing > 0.1 * span:
            return None, (f"{missing} of {int(span)} weeks are missing. Carry-over math needs a continuous weekly "
                          "series. Fill the gaps in the export and rerun.")

    # Spend cleanup
    keep_spend, keep_names = [], []
    for c, name in zip(out_spend, spend_names):
        col = "__s_" + c
        blank = int(df[col].isna().sum())
        if blank:
            quality.append(dict(check=f"Blank spend cells: {name}", rows=blank, action="Read as $0"))
            df[col] = df[col].fillna(0.0)
        negv = int((df[col] < 0).sum())
        if negv:
            quality.append(dict(check=f"Negative spend: {name}", rows=negv, action="Set to $0"))
            df[col] = df[col].clip(lower=0)
        active = int((df[col] > 0).sum())
        if df[col].sum() <= 0:
            warns.append(f"{name} has no spend in the file. Left out.")
            continue
        if active < MIN_SPEND_WEEKS:
            warns.append(f"{name} ran in only {active} weeks. Too few to measure. Left out of the model, "
                         "so its sales sit in base.")
            continue
        if df[col].std() < 0.1 * df[col].mean():
            warns.append(f"{name} ran at the same level every week. A model cannot measure a channel whose spend "
                         "never moved. Left out, so its sales sit in base. A test can measure it.")
            continue
        keep_spend.append(c)
        keep_names.append(name)
    # a column that is the sum of the others is a total, not a channel
    for c, name in list(zip(keep_spend, keep_names)):
        others = [o for o in keep_spend if o != c]
        if len(others) >= 2:
            tot = df[["__s_" + o for o in others]].sum(axis=1)
            x = df["__s_" + c]
            close = (np.abs(x - tot) <= 0.01 * np.maximum(tot, 1)).mean()
            if close >= 0.9:
                notes.append(f"{c} equals the sum of the other spend columns, so it was read as a total and left out.")
                i = keep_spend.index(c)
                keep_spend.pop(i)
                keep_names.pop(i)
    if not keep_spend:
        return None, "No channel has enough weeks of spend to measure."

    # Controls: fill short gaps, drop flat ones
    final_ctrl = []
    for c in used_ctrl:
        col = "__c_" + c
        blank = int(df[col].isna().sum())
        if blank:
            df[col] = df[col].ffill().bfill()
            quality.append(dict(check=f"Blank values: {pretty(c, ())}", rows=blank, action="Filled from the week before"))
        if df[col].std() <= 1e-12:
            notes.append(f"{pretty(c, ())} never changes, so it was left out.")
            continue
        final_ctrl.append(c)

    # Assemble the clean frame
    clean = pd.DataFrame({"week": df["week"], "sales": df["kpi"]})
    labels = {}
    used_names = set()
    spend_map = []
    for c, name in zip(keep_spend, keep_names):
        key = "spend_" + norm(name)
        while key in clean.columns:
            key += "_2"
        if name in used_names:
            name = f"{name} ({c})"
        used_names.add(name)
        clean[key] = df["__s_" + c].values
        labels[key] = name
        spend_map.append((key, name, c))
    ctrl_keys = []
    for c in final_ctrl:
        key = "ctrl_" + norm(c)
        clean[key] = df["__c_" + c].values
        labels[key] = pretty(c, ())
        ctrl_keys.append((key, c))
    hol_keys = []
    for c in hol_cols:
        key = "hol_" + norm(c).replace("hol_", "").replace("holiday_", "")
        if clean.get(key) is not None:
            continue
        clean[key] = df["__h_" + c].values
        labels[key] = pretty(c)
        if clean[key].sum() > 0:
            hol_keys.append(key)
    ev_keys = []
    for c in ev_cols:
        key = "event_" + norm(c).replace("event_", "").replace("ev_", "")
        clean[key] = df["__e_" + c].values
        labels[key] = pretty(c)
        if np.abs(clean[key]).sum() > 0:
            ev_keys.append(key)
    if not hol_keys and use_holidays:
        ending = "end" in norm(week_col)
        added = add_us_holidays(clean, ending)
        hol_keys = added
        for k, name in US_HOLIDAYS:
            labels[k] = name
        if added:
            notes.append("No holiday columns in the file, so US holiday weeks were added: Memorial Day, July 4th, "
                         "Labor Day, Black Friday, Christmas. Dates are read as the " +
                         ("last" if ending else "first") + " day of each week.")

    info = dict(week_col=week_col, kpi_col=kpi_col, spend_map=spend_map, controls=ctrl_keys, holidays=hol_keys,
                events=ev_keys, labels=labels, notes=notes, warnings=warns, quality=quality)
    return (clean, info), None


def control_role(name: str) -> tuple[str, bool]:
    n = norm(name)
    if "price" in n:
        return "Price", False
    if any(t in n for t in ("promo", "discount", "markdown", "coupon")):
        return "Promotions", True
    if any(t in n for t in ("competitor", "competition", "comp_", "sov", "share_of_voice")):
        return "Competition", False
    return "Economy and other", False


# ---------------------------------------------------------------------------
# Build the output
# ---------------------------------------------------------------------------

def parse_lift(text: str, spec_keys: list[str], names: list[str]):
    out, bad = [], []
    if not text:
        return out, bad
    by_name = {n.lower(): k for k, n in zip(spec_keys, names)}
    by_key = {k.lower(): k for k in spec_keys}
    for part in re.split(r"[;\n]+", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.+?)\s*[=:]\s*\$?([0-9.]+)\s*[:/,]\s*([0-9.]+)\s*$", part)
        if not m:
            bad.append(part)
            continue
        who = m.group(1).strip().lower()
        k = by_name.get(who) or by_key.get(who) or by_key.get("spend_" + norm(who))
        if not k:
            bad.append(part)
            continue
        out.append((k, float(m.group(2)), max(float(m.group(3)), 0.01)))
    return out, bad


def list_words(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def health(metrics: dict) -> tuple[str, list[str]]:
    r2 = metrics["r2_train"]
    mape = metrics["mape_holdout"]
    dw = metrics["durbin_watson"]
    reasons = []
    if r2 < 0.70:
        reasons.append(f"The model explains {r2 * 100:.0f}% of the weekly swings in sales. 70% is the floor.")
    if mape is not None and not math.isnan(mape) and mape > 15:
        reasons.append(f"On the {metrics['n_holdout']} weeks it never saw, it missed by {mape:.1f}% on average. "
                       "15% is the ceiling.")
    if reasons:
        return "not usable", reasons
    if r2 < 0.85:
        reasons.append(f"Explains {r2 * 100:.0f}% of weekly swings. 85% is the target.")
    if mape is not None and not math.isnan(mape) and mape > 10:
        reasons.append(f"Missed the weeks it never saw by {mape:.1f}% on average. 10% is the target.")
    if not (1.0 <= dw <= 3.0):
        reasons.append("Misses run in streaks, so something that moves sales week to week is missing from the file.")
    return ("directional" if reasons else "usable"), reasons


def test_next(rt: pd.DataFrame, break_even: float, overlap: dict) -> list[dict]:
    """Channels whose verdict does not hold across the refits. Test first before Close call, then by spend."""
    out = []
    for _, row in rt.iterrows():
        if row["spend"] <= 0 or row["certainty"] in ("Clear", "Not run"):
            continue
        split = {k: v for k, v in sorted(row["verdict_split"].items(), key=lambda kv: -kv[1]) if v >= 0.05}
        parts = [f"{k} in {v * 100:.0f}%" for k, v in split.items()]
        reasons = ["Across the refits the verdict lands on " + ", ".join(parts) + "."]
        crosses = row["roi_lo"] < break_even < row["roi_hi"]
        if row["certainty"] == "Close call" and not crosses:
            reasons.append("The direction holds. The size of the move does not.")
        if crosses:
            reasons.append(f"Its sales per $1 range, {row['roi_lo']:.2f} to {row['roi_hi']:.2f}, runs across "
                           f"break-even ({break_even:.2f}), so the model cannot say whether it pays at all.")
        if row["zero_draws"] >= 0.2:
            reasons.append(f"In {row['zero_draws'] * 100:.0f}% of refits the model credits it with nothing.")
        if row["key"] in overlap:
            reasons.append(overlap[row["key"]])
        out.append(dict(channel=row["channel"], key=row["key"], spend=money(row["spend"]),
                        spend_share=r(row["spend_share"], 3), verdict=row["verdict"], certainty=row["certainty"],
                        agreement=r(row["agreement"], 2), roi_lo=r(row["roi_lo"]), roi_hi=r(row["roi_hi"]),
                        reasons=reasons))
    out.sort(key=lambda d: (d["certainty"] != "Test first", -(d["spend"] or 0)))
    out = out[:3]
    for i, d in enumerate(out, 1):
        d["rank"] = i
    return out


def build(fr, info, margin: float, demo_truth=None, calibration=()):
    rt = roi_table(fr, WINDOW, margin)
    be = 1.0 / margin
    mask = window_mask(fr, WINDOW)
    hd = headline(fr, WINDOW, margin)
    met = fr.metrics
    verdict, reasons = health(met)
    v = vif(fr)

    # Channels whose spend moves with another driver cannot be read apart, whatever the refits say
    overlap = {}
    vmap = {row["column"]: row["vif"] for _, row in v.iterrows()}
    cm = fr.spend.corr()
    for k in fr.spec.channels:
        partners = [fr.spec.label(o) for o in fr.spec.channels
                    if o != k and not math.isnan(cm.loc[k, o]) and cm.loc[k, o] >= 0.8]
        if partners:
            overlap[k] = f"Its spend moves with {list_words(partners)} (correlation 0.8 or more), so the model cannot split credit between them."
        elif vmap.get(f"media:{k}", 0) >= 10:
            overlap[k] = "Its spend moves in step with other drivers, so the model cannot pull its effect apart."
    calibrated = {k for k, _, _ in calibration}
    for i, row in rt.iterrows():
        if row["key"] in overlap and row["key"] not in calibrated and row["certainty"] not in ("Not run",):
            rt.at[i, "certainty"] = "Test first"
    if hd["media"] > 0 and met["r2_train"] > 0.99 and hd["media_share"] < 0.02:
        info["warnings"].append("The model explains almost every week while giving media under 2% of sales. "
                                "A column in the file looks like a result of sales, not a cause. Check the outside drivers.")

    channels = []
    for _, row in rt.iterrows():
        channels.append(dict(
            key=row["key"], channel=row["channel"], spend=money(row["spend"]), contribution=money(row["contribution"]),
            contribution_lo=money(row["contribution_lo"]), contribution_hi=money(row["contribution_hi"]),
            roi=r(row["roi"]), roi_lo=r(row["roi_lo"]), roi_hi=r(row["roi_hi"]), mroi=r(row["mroi"]),
            spend_share=r(row["spend_share"], 3), effect_share=r(row["effect_share"], 3),
            zero_draws=r(row["zero_draws"], 3), verdict=row["verdict"], certainty=row["certainty"],
            agreement=r(row["agreement"], 2), verdict_split={k: r(v, 2) for k, v in row["verdict_split"].items()},
            calibrated=any(k == row["key"] for k, _, _ in calibration)))

    params = media_params_table(fr)
    carry = [dict(channel=p["channel"], decay=r(p["decay"], 3), half_life_weeks=r(p["half_life_weeks"], 1),
                  shape=r(p["shape"], 2), half_sat_rel=r(p["half_sat_rel"], 2)) for _, p in params.iterrows()]

    curves = {}
    for k, name in zip(fr.spec.channels, fr.spec.channel_names):
        rc = response_curve(fr, k, WINDOW, max_mult=2.5, points=51)
        curves[name] = dict(spend=[money(x) for x in rc["spend"]], contribution=[money(x) for x in rc["contribution"]],
                            lo=[money(x) for x in rc["contribution_lo"]], hi=[money(x) for x in rc["contribution_hi"]],
                            mroi=[r(x) for x in rc["mroi"]], current_spend=money(rc["spend"].iloc[20]))

    budget = float(rt["spend"].sum())
    locked = {row["key"]: 1.0 for _, row in rt.iterrows() if row["certainty"] == "Test first" and row["spend"] > 0}
    free = [k for k in fr.spec.channels if k not in locked]
    # the plan never grows a channel the model says to cut or trim, and never shrinks one it says to grow
    caps = {row["key"]: (OPT_LO, 1.0) for _, row in rt.iterrows() if row["verdict"] in ("Cut", "Trim")}
    limits = dict(caps)
    limits.update({row["key"]: (1.0, OPT_HI) for _, row in rt.iterrows() if row["verdict"] == "Grow"})
    opt, plan_reason = None, None
    growable = [k for k in free if limits.get(k, (OPT_LO, OPT_HI))[1] > 1.0 and float(rt.set_index("key").loc[k, "spend"]) > 0]
    if len(free) >= 2 and not growable:
        plan_reason = ("Every channel the model can read says hold back or reduce, so there is nowhere better to move "
                       "money. The question is the budget's size, not its split.")
    elif len(free) >= 2:
        try:
            opt = optimize_budget(fr, budget, WINDOW, lo=OPT_LO, hi=OPT_HI, locked=locked, limits=limits)
        except ValueError:
            plan_reason = ("No channel the model can read is worth more money, so there is nowhere to move it. "
                           "The question is the budget's size, not its split.")
    else:
        plan_reason = ("Fewer than two channels have a readable verdict, so there is nothing safe to move money "
                       "between. Test first.")
    try:
        opt_all = optimize_budget(fr, budget, WINDOW, lo=OPT_LO, hi=OPT_HI)
    except ValueError:
        opt_all = None

    def plan_rows(o):
        return [dict(channel=x["channel"], current_spend=money(x["current_spend"]), best_spend=money(x["optimal_spend"]),
                     change=money(x["optimal_spend"] - x["current_spend"]), multiplier=r(x["multiplier"], 3),
                     current_contribution=money(x["current_contribution"]),
                     best_contribution=money(x["optimal_contribution"]), best_mroi=r(x["optimal_mroi"]),
                     held=bool(x["locked"])) for _, x in o.iterrows()]

    def plan_gain(o):
        return float(o["optimal_contribution"].sum() - o["current_contribution"].sum())
    cert = {row["channel"]: row["certainty"] for _, row in rt.iterrows()}
    plan_main = plan_rows(opt) if opt is not None else None
    if plan_main:
        for p in plan_main:
            p["certainty"] = cert.get(p["channel"])
    gain = plan_gain(opt) if opt is not None else 0.0
    gain_all = plan_gain(opt_all) if opt_all is not None else None

    frontier = []
    for lv in FRONTIER:
        b = budget * lv
        same = sum(float(fr.channel_response(k, np.where(mask, fr.spend[k].values * lv, fr.spend[k].values))[mask].sum())
                   for k in fr.spec.channels)
        try:
            # channels waiting on a test move with the budget; the clear ones are optimised
            lk = {k: lv for k in locked}
            o = optimize_budget(fr, b, WINDOW, lo=OPT_LO, hi=OPT_HI, locked=lk, limits=caps)
            best = float(o["optimal_contribution"].sum())
            alloc = {row["channel"]: money(row["optimal_spend"]) for _, row in o.iterrows()}
        except ValueError:
            if not free or all(k in locked for k in fr.spec.channels):
                # nothing is free to move: the plan at this level is today's mix scaled
                best = same
                alloc = {fr.spec.label(k): money(fr.spend.loc[mask, k].sum() * lv) for k in fr.spec.channels}
            else:
                best, alloc = None, {}
        frontier.append(dict(level=lv, budget=money(b), same_mix=money(same), best_mix=money(best), allocation=alloc))
    for f in frontier:
        f["profit"] = money(f["best_mix"] * margin - f["budget"]) if f["best_mix"] is not None else None
    for i in range(1, len(frontier)):
        a, b2 = frontier[i - 1], frontier[i]
        if a["best_mix"] is not None and b2["best_mix"] is not None:
            b2["next_dollar"] = r((b2["best_mix"] - a["best_mix"]) / (b2["budget"] - a["budget"]))

    gs = group_summary(fr, WINDOW)
    drivers_tbl = [dict(group=g["group"], contribution=money(g["contribution"]), lo=money(g["lo"]), hi=money(g["hi"]),
                        share=r(g["share"], 3), is_media=bool(g["is_media"])) for _, g in gs.iterrows()]

    ce = control_effects(fr, WINDOW)
    outside = [dict(driver=c["driver"], group=c["group"], weekly_effect_1sd=money(c["weekly_effect_1sd"]),
                    pct_effect_1sd=r(c["pct_effect_1sd"]), one_sd_change=r(c["one_sd_change"], 3),
                    p_value=r(c["p_value"], 3), verdict=c["verdict"], elasticity=r(c["elasticity"]),
                    window_contribution=money(c["window_contribution"]))
               for _, c in ce.iterrows()] if len(ce) else []

    def dummies(group):
        t = dummy_effects(fr, group)
        return [dict(name=d["name"], weekly_lift=money(d["weekly_lift"]), weekly_lift_lo=money(d["weekly_lift_lo"]),
                     weekly_lift_hi=money(d["weekly_lift_hi"]), pct_of_avg_week=r(d["pct_of_avg_week"], 1),
                     total_impact=money(d["total_impact"]), weeks_affected=int(d["weeks_affected"]),
                     verdict=d["verdict"]) for _, d in t.iterrows()] if len(t) else []

    vif_media = [dict(column=fr.spec.label(row["column"].split(":", 1)[1]) if row["column"].startswith("media:")
                      else fr.spec.label(row["column"]), vif=r(row["vif"], 1), rating=row["rating"])
                 for _, row in v.iterrows() if row["rating"] != "Pass"
                 and not (row["column"] == "trend" or re.match(r"^(sin|cos)\d+$", row["column"]))]

    corr_warn = []
    sp = fr.spend
    cm = sp.corr()
    for i, a in enumerate(sp.columns):
        for b in sp.columns[i + 1:]:
            c = cm.loc[a, b]
            if c is not None and not math.isnan(c) and c >= 0.8:
                corr_warn.append(f"{fr.spec.label(a)} and {fr.spec.label(b)} spend move together (correlation "
                                 f"{c:.2f}). The model cannot split credit between them.")

    warns = list(info["warnings"])
    n = len(fr.weeks)
    if n < GOOD_WEEKS:
        warns.append(f"{n} weeks of history. Two years (104 weeks) lets the model tell seasons from trend. "
                     "Treat seasonal and trend effects as rough.")
    warns.extend(corr_warn)
    p = met["n_params"]
    if met["n_train"] < 4 * p:
        warns.append(f"{p} things to estimate from {met['n_train']} weeks. Aim for 4 weeks per estimate. "
                     "Drop drivers that do not matter or add history.")

    feas = [f for f in frontier if f["profit"] is not None]
    best_lv = max(feas, key=lambda f: f["profit"]) if feas else None
    out = dict(
        version=VERSION,
        demo=demo_truth is not None,
        meta=dict(weeks=n, start=str(fr.weeks[0].date()), end=str(fr.weeks[-1].date()),
                  window=WINDOW, window_weeks=int(mask.sum()), holdout_weeks=int(fr.spec.holdout_weeks),
                  kpi_column=info["kpi_col"], week_column=info["week_col"], margin=margin, break_even_roi=r(be),
                  effort=fr.spec.effort, fit_seconds=r(fr.fit_seconds, 1), channels=list(fr.spec.channel_names),
                  spend_columns=[dict(column=c, channel=nm) for _, nm, c in info["spend_map"]],
                  outside_drivers=[fr.spec.label(k) for k, _ in info["controls"]],
                  holidays=[fr.spec.label(k) for k in info["holidays"]],
                  events=[fr.spec.label(k) for k in info["events"]],
                  calibration=[dict(channel=fr.spec.label(k), roi=r(roi), se=r(se)) for k, roi, se in calibration],
                  optimizer_limits=[OPT_LO, OPT_HI]),
        notes=info["notes"],
        warnings=warns,
        data_quality=info["quality"],
        model_health=dict(verdict=verdict, reasons=reasons,
                          r2_train=r(met["r2_train"], 3), mape_train=r(met["mape_train"]),
                          mape_holdout=r(met["mape_holdout"]), durbin_watson=r(met["durbin_watson"]),
                          ljung_box_p=r(met["ljung_box_p"], 3), n_train=met["n_train"], n_holdout=met["n_holdout"],
                          n_params=met["n_params"], ratings=met["ratings"], vif_flags=vif_media),
        headline=dict(sales=money(hd["sales"]), media=money(hd["media"]), media_share=r(hd["media_share"], 3),
                      spend=money(hd["spend"]), blended_roi=r(hd["blended_roi"]),
                      best_channel=hd["best_channel"], best_mroi=r(hd["best_mroi"]),
                      worst_channel=hd["worst_channel"], worst_mroi=r(hd["worst_mroi"])),
        channels=channels,
        carryover=carry,
        curves=curves,
        plan=dict(budget=money(budget), gain=money(gain), gain_pct_of_media=r(gain / max(hd["media"], 1), 3),
                  rows=plan_main, held=[fr.spec.label(k) for k in locked], limits=[OPT_LO, OPT_HI],
                  all_rows=plan_rows(opt_all) if opt_all is not None else
                  [dict(channel=row["channel"], current_spend=money(row["spend"])) for _, row in rt.iterrows()],
                  gain_all=money(gain_all),
                  profit_best_level=best_lv["level"] if best_lv else None,
                  profit_at_edge=(None if not best_lv else "low" if best_lv is feas[0] else
                                  "high" if best_lv is feas[-1] else None),
                  profit_best_budget=best_lv["budget"] if best_lv else None,
                  profit_at_best_level=best_lv["profit"] if best_lv else None,
                  profit_at_today=next((f["profit"] for f in frontier if abs(f["level"] - 1) < 1e-9), None),
                  reason=plan_reason),
        frontier=frontier,
        drivers=drivers_tbl,
        outside=outside,
        holidays=dummies("Holidays"),
        events=dummies("Events"),
        test_next=test_next(rt, be, overlap),
        series=dict(weeks=[str(w.date()) for w in fr.weeks], actual=[money(x) for x in fr.y],
                    fitted=[money(x) for x in fr.yhat], train=[bool(x) for x in fr.train],
                    media=[money(x) for x in fr.contributions[[f"media:{k}" for k in fr.spec.channels]].sum(axis=1)]),
    )
    if demo_truth is not None:
        from mmm.truth import channel_check
        cc = channel_check(fr, demo_truth, WINDOW, margin=margin)
        out["truth_check"] = [dict(channel=c["channel"], true_roi=r(c["true_roi"]), est_roi=r(c["est_roi"]),
                                   true_verdict=c["true_verdict"], est_verdict=c["est_verdict"],
                                   est_lo=r(c["est_lo"]), est_hi=r(c["est_hi"]), error_pct=r(c["error_pct"], 1),
                                   in_range=c["in_range"], true_decay=r(c["true_decay"], 2),
                                   est_decay=r(c["est_decay"], 2)) for _, c in cc.iterrows()]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", default="mmm.json")
    ap.add_argument("--kpi")
    ap.add_argument("--margin", type=float, default=0.5)
    ap.add_argument("--effort", default="Standard", choices=["Quick", "Standard", "Thorough"])
    ap.add_argument("--lift-tests", default="")
    ap.add_argument("--no-holidays", action="store_true")
    ap.add_argument("--ignore", default="")
    ap.add_argument("--holdout", type=int)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--demo-csv", default="mmm_demo_weekly.csv")
    ap.add_argument("--demo-tests", default="", help="demo only: simulate lift tests on these channels, comma separated")
    a = ap.parse_args(argv)

    margin = a.margin / 100 if a.margin > 1 else a.margin
    if not 0.02 <= margin <= 1:
        stop("Gross margin must be between 2% and 100%.", a.json)

    truth = None
    path = a.file
    if a.demo:
        from mmm.synth import SynthSettings, export_frame, generate, truth_by_name
        d = generate(SynthSettings())
        export_frame(d).to_csv(a.demo_csv, index=False)
        truth = truth_by_name(d)
        path = a.demo_csv
    if not path:
        stop("No file given.", a.json)
    if not os.path.exists(path):
        stop(f"File not found: {path}", a.json)

    loaded, err = load(path, a.kpi, [c for c in a.ignore.split(",") if c.strip()], not a.no_holidays)
    if err:
        stop(err, a.json)
    df, info = loaded
    n = len(df)
    if n < MIN_WEEKS:
        stop(f"{n} weeks of data. A mix model needs at least 52 weeks, and two years is better.", a.json,
             dict(data_quality=info["quality"]))

    keys = [k for k, _, _ in info["spend_map"]]
    names = [nm for _, nm, _ in info["spend_map"]]
    holdout = a.holdout if a.holdout is not None else (13 if n >= GOOD_WEEKS else 8)
    groups, zeros = [], []
    for k, c in info["controls"]:
        g, z = control_role(c)
        groups.append((k, g))
        if z:
            zeros.append(k)
    lift_text = a.lift_tests
    if a.demo and a.demo_tests:
        rng = np.random.default_rng(11)
        sims = []
        for nm in [x.strip() for x in a.demo_tests.split(",") if x.strip()]:
            if nm not in names:
                stop(f"No channel named {nm} in the demo. Channels: {', '.join(names)}.", a.json)
            k = keys[names.index(nm)]
            tr = np.arange(n) < n - holdout
            true = truth["contributions"].loc[tr, nm].sum() / df.loc[tr, k].sum()
            sims.append(f"{nm}={max(true + rng.normal(0, 0.25), 0.01):.2f}:0.25")
        lift_text = "; ".join([t for t in [lift_text] + sims if t])
    calib, bad = parse_lift(lift_text, keys, names)
    if bad:
        stop("Could not match these lift tests to a channel in the model: " + "; ".join(bad) +
             ". Write each as Channel=sales per $1:standard error, for example Paid search=3.9:0.3. "
             "Channels in the model: " + ", ".join(names) + ".", a.json)
    spec = ModelSpec(channels=tuple(keys), channel_names=tuple(names), controls=tuple(k for k, _ in info["controls"]),
                     zero_controls=tuple(zeros), control_groups=tuple(groups), holidays=tuple(info["holidays"]),
                     events=tuple(info["events"]), labels=tuple(info["labels"].items()), holdout_weeks=holdout,
                     effort=a.effort, bounds=suggested_bounds(keys), calibration=tuple(calib))
    fr = fit(df, spec, kpi="sales")
    out = build(fr, info, margin, truth, calib)
    with open(a.json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    h = out["model_health"]
    print(f"Fitted {n} weeks, {len(keys)} channels in {out['meta']['fit_seconds']}s. Model check: {h['verdict']}.")
    print("Results written to " + a.json)


if __name__ == "__main__":
    main()
