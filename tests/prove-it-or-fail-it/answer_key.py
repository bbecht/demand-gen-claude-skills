"""Independent answer key for Prove It or Fail It.

Every number is recomputed from the planted values, typed in by hand from each case. No code is shared with the
skill: no import of verdict.py, no parsing of the idea JSON. Dates are walked one day at a time.
"""
import math
from datetime import date, timedelta
from statistics import NormalDist

ZA = NormalDist().inv_cdf(1 - 0.05 / 2)
ZB = NormalDist().inv_cdf(0.80)

# Planted values. Rates as fractions, counts a week, money in dollars.
PLANTED = {
    "sample": dict(kind="rate", design="split", p=0.031, vol=9000, share=0.5, budget=6000, value=400, expected=0.35,
                   launch=date(2027, 2, 1), extend=30),
    "d1_rate_split": dict(kind="rate", design="split", p=0.04, vol=20000, share=0.5, budget=5000, value=250, expected=0.25,
                          launch=date(2027, 3, 1), extend=30),
    "d2_count_split": dict(kind="count", design="split", weekly=120, share=0.5, budget=2000, value=None, expected=0.30,
                           launch=date(2027, 3, 1), extend=30),
    "d3_before_after": dict(kind="count", design="before_after", history=[50, 48, 52, 47, 51, 49, 72, 75, 70, 78, 50, 48],
                            budget=3000, value=300, expected=0.40, launch=date(2027, 4, 5), extend=30),
    "d4_too_small": dict(kind="rate", design="split", p=0.02, vol=3000, share=0.5, budget=1500, value=400, expected=0.20,
                         launch=date(2027, 3, 1), extend=30),
    "d5_weak_idea": dict(kind="rate", design="split", p=0.06, vol=40000, share=0.5, budget=8000, value=None, expected=0.20,
                         launch=date(2027, 3, 1), extend=30),
}


def add_days(d, n):
    for _ in range(n):
        d += timedelta(days=1)
    return d


def design_key(c):
    k = {}
    if c["kind"] == "rate":
        p = c["p"]
        nt, nc = c["vol"] * c["share"], c["vol"] * (1 - c["share"])
        var = lambda n: p * (1 - p) / n
        se = math.sqrt(var(nt) + var(nc)) / p
        se15 = math.sqrt(var(nt / 2) + var(nc / 2)) / p
        det = (ZA + ZB) * se
        units = p * nt
        base = p
    else:
        if c["design"] == "split":
            per_day = c["weekly"] / 7
            lt, lc = per_day * 30 * c["share"], per_day * 30 * (1 - c["share"])
            lt15, lc15 = lt / 2, lc / 2
            base = c["weekly"]
        else:
            h = c["history"]
            base = sum(h) / len(h)
            lt, lc = base / 7 * 30, float(sum(h))
            lt15, lc15 = lt / 2, lc
        se = math.sqrt(1 / lt + 1 / lc)
        se15 = math.sqrt(1 / lt15 + 1 / lc15)
        det = math.exp((ZA + ZB) * se) - 1
        units = lt
    pay = (c["budget"] / c["value"]) / units if c["value"] else None
    sw = None
    if c["design"] == "before_after":
        h = c["history"]
        avg = sum(h) / len(h)
        sw = 0.0
        for i in range(len(h) - 3):
            win = (h[i] + h[i + 1] + h[i + 2] + h[i + 3]) / 4
            sw = max(sw, abs(win / avg - 1))
    cands = [det] + ([pay] if pay is not None else []) + ([sw] if sw is not None else [])
    success = max(cands)
    readable = max(det, sw or 0) <= c["expected"] + 1e-12
    if c["kind"] == "rate":
        kill = success - ZA * se
        harm = -ZA * se15
    else:
        kill = (1 + success) / math.exp(ZA * se) - 1
        harm = 1 / math.exp(ZA * se15) - 1
    k.update(detectable=det, payback=pay, swing=sw, success=success, kill=kill, harm=harm, readable=readable, base=base,
             checkpoint=add_days(c["launch"], 14), day30=add_days(c["launch"], 29), extend_end=add_days(c["launch"], 29 + c["extend"]))
    if not readable and det > c["expected"]:
        # smallest volume multiple that brings the detectable lift down to the expected lift, found by stepping
        m, step = 1.0, 1.0
        while step > 1e-9:
            while True:
                if c["kind"] == "rate":
                    d = (ZA + ZB) * math.sqrt(p * (1 - p) / (nt * (m + step)) + p * (1 - p) / (nc * (m + step))) / p
                else:
                    d = math.exp((ZA + ZB) * math.sqrt(1 / (lt * (m + step)) + 1 / (lc * (m + step)))) - 1
                if d > c["expected"]:
                    m += step
                else:
                    break
            step /= 2
        k["multiple"] = m
        k["days_needed"] = math.ceil(30 * m - 1e-9)
    return k


def read_rate(ct, nt, cc, nc):
    a, b = ct / nt, cc / nc
    lift = a / b - 1
    half = ZA * math.sqrt(a * (1 - a) / nt + b * (1 - b) / nc) / b
    return lift, lift - half, lift + half


def read_count(ct, et, cc, ec):
    r = (ct / et) / (cc / ec)
    half = ZA * math.sqrt(1 / ct + 1 / cc)
    return r - 1, r / math.exp(half) - 1, r * math.exp(half) - 1


def call(day, lift, lo, hi, success):
    if day == 15:
        return "Stop early" if hi < 0 else "Keep running"
    if lo > 0 and lift >= success:
        return "Scale"
    if day == 30:
        return "Kill" if hi < success else "Extend"
    return "Kill"


if __name__ == "__main__":
    for n, c in PLANTED.items():
        k = design_key(c)
        print(n, {x: (round(v, 4) if isinstance(v, float) else v) for x, v in k.items()})
