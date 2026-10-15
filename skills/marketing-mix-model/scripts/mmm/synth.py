"""Synthetic weekly data for a home-improvement brand, with the true answer kept.

Every number here is invented. The generator plants known effects (media carry-over and
saturation, economy, competitor pressure, price, promotions, holidays, one-off events) so the
model's estimates can be checked against the truth.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from mmm.transforms import adstock, hill, reference_level

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

CHANNELS: list[dict] = [
    # roi = revenue per $1 over the whole history; half_sat is relative to the typical adstocked level
    dict(key="tv", name="TV", roi=2.4, decay=0.60, half_sat=1.0, shape=1.6, weekly_spend=70_000, style="flight"),
    dict(key="radio", name="Radio", roi=1.6, decay=0.40, half_sat=0.9, shape=1.3, weekly_spend=22_000, style="flight_paired"),
    dict(key="direct_mail", name="Direct mail", roi=3.0, decay=0.30, half_sat=1.2, shape=1.0, weekly_spend=16_000, style="drops"),
    dict(key="search", name="Paid search", roi=4.2, decay=0.10, half_sat=1.1, shape=1.2, weekly_spend=45_000, style="demand"),
    dict(key="social", name="Paid social", roi=2.1, decay=0.30, half_sat=0.8, shape=1.0, weekly_spend=35_000, style="always_on"),
    dict(key="video", name="Online video", roi=1.2, decay=0.50, half_sat=1.0, shape=1.5, weekly_spend=28_000, style="flight_late"),
]

# effect = change in weekly sales as a share of base sales, per unit of the indicator
MACRO: list[dict] = [
    dict(key="consumer_confidence", name="Consumer confidence", unit="index points", effect=0.004, noise=1.2,
         anchors=[("2022-10-01", 102), ("2023-03-01", 104), ("2023-07-01", 96), ("2023-12-01", 101),
                  ("2024-06-01", 108), ("2024-12-01", 110), ("2025-04-01", 92), ("2025-08-01", 97),
                  ("2026-02-01", 99), ("2026-10-01", 101)]),
    dict(key="unemployment", name="Unemployment rate", unit="% points", effect=-0.05, noise=0.04,
         anchors=[("2022-10-01", 3.6), ("2023-04-01", 3.5), ("2023-10-01", 3.8), ("2024-03-01", 3.9),
                  ("2024-08-01", 4.2), ("2025-01-01", 4.1), ("2025-08-01", 4.3), ("2026-03-01", 4.5),
                  ("2026-10-01", 4.4)]),
    dict(key="inflation", name="Inflation (CPI, year on year)", unit="% points", effect=-0.015, noise=0.06,
         anchors=[("2022-10-01", 7.7), ("2023-06-01", 3.0), ("2023-09-01", 3.7), ("2024-06-01", 3.0),
                  ("2024-09-01", 2.4), ("2025-04-01", 2.3), ("2025-09-01", 3.0), ("2026-03-01", 3.1),
                  ("2026-10-01", 2.8)]),
    dict(key="mortgage_rate", name="30-year mortgage rate", unit="% points", effect=-0.04, noise=0.05,
         anchors=[("2022-10-01", 6.9), ("2023-02-01", 6.1), ("2023-10-01", 7.8), ("2024-01-01", 6.6),
                  ("2024-09-01", 6.1), ("2025-01-01", 7.0), ("2025-09-01", 6.3), ("2026-10-01", 6.2)]),
    dict(key="gas_price", name="Gas price", unit="$ per gallon", effect=0.0, noise=0.04,
         anchors=[("2022-10-01", 3.8), ("2023-01-01", 3.3), ("2023-09-01", 3.9), ("2024-04-01", 3.6),
                  ("2024-12-01", 3.0), ("2025-06-01", 3.15), ("2026-10-01", 3.1)]),
    dict(key="temp_anomaly", name="Temperature vs normal", unit="degrees F", effect=0.004, noise=0.0, anchors=[]),
]

COMPETITOR = dict(key="competitor_sov", name="Competitor share of voice", unit="share (0-1)", effect=-0.25)
PRICE = dict(key="price_index", name="Price index", unit="index (avg = 100)", elasticity=-1.0)
PROMO = dict(key="promo_depth", name="Promotion depth", unit="% off", effect=0.008)

HOLIDAYS: list[dict] = [
    dict(key="hol_memorial_day", name="Memorial Day", effect=0.06),
    dict(key="hol_july_4", name="July 4th", effect=0.02),
    dict(key="hol_labor_day", name="Labor Day", effect=0.05),
    dict(key="hol_black_friday", name="Black Friday", effect=0.10),
    dict(key="hol_christmas", name="Christmas", effect=-0.10),
]

# shape: pulse (constant for `weeks`), decay (1, rate, rate^2 ...), step (on from start), context (marker only)
EVENTS: list[dict] = [
    dict(name="Website outage", start="2023-06-12", shape="pulse", weeks=1, rate=0.0, effect=-0.15),
    dict(name="Competitor launch", start="2024-02-05", shape="context", weeks=0, rate=0.0, effect=0.0),
    dict(name="Viral TV feature", start="2024-04-15", shape="decay", weeks=0, rate=0.55, effect=0.14),
    dict(name="Hurricane", start="2024-10-07", shape="pulse", weeks=2, rate=0.0, effect=-0.11),
    dict(name="Post-storm rebound", start="2024-10-21", shape="pulse", weeks=4, rate=0.0, effect=0.06),
    dict(name="Tariff pull-forward buying", start="2025-03-31", shape="pulse", weeks=3, rate=0.0, effect=0.07),
    dict(name="Price increase (tariffs)", start="2025-05-05", shape="context", weeks=0, rate=0.0, effect=0.0),
    dict(name="Website relaunch", start="2025-09-08", shape="step", weeks=0, rate=0.0, effect=0.03),
    dict(name="Product recall news", start="2026-02-09", shape="decay", weeks=0, rate=0.75, effect=-0.09),
]


@dataclass
class SynthSettings:
    seed: int = 7
    n_weeks: int = 208
    end_week: str = "2026-09-28"
    base_weekly_sales: float = 1_500_000.0
    trend_per_year: float = 0.04
    season_strength: float = 0.13
    noise_pct: float = 0.025
    noise_autocorr: float = 0.3
    search_follows_demand: float = 0.5
    radio_tv_overlap: float = 0.3
    macro_strength: float = 1.0
    include_events: bool = True
    channels: list[dict] = field(default_factory=lambda: copy.deepcopy(CHANNELS))

    def to_dict(self) -> dict:
        return {k: copy.deepcopy(v) for k, v in self.__dict__.items()}


@dataclass
class SynthData:
    df: pd.DataFrame          # one row per week: sales, spend, indicators, holiday flags
    events: pd.DataFrame      # event list with dates and shapes
    truth: dict               # planted answers


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def event_signal(weeks: pd.DatetimeIndex, start: str, shape: str, n_weeks: int = 0, rate: float = 0.0) -> np.ndarray:
    """Weekly regressor for an event: 0 outside it, 1 at its peak."""
    k = np.asarray((weeks - pd.Timestamp(start)).days // 7)
    out = np.zeros(len(weeks))
    if shape == "pulse":
        out[(k >= 0) & (k < max(n_weeks, 1))] = 1.0
    elif shape == "step":
        out[k >= 0] = 1.0
    elif shape == "decay":
        on = k >= 0
        out[on] = rate ** k[on]
        out[out < 0.01] = 0.0
    return out


def week_of(d: pd.Timestamp) -> pd.Timestamp:
    return d - pd.Timedelta(days=d.weekday())


def holiday_weeks(year: int) -> dict[str, pd.Timestamp]:
    may31 = pd.Timestamp(year, 5, 31)
    memorial = may31 - pd.Timedelta(days=may31.weekday())
    sep1 = pd.Timestamp(year, 9, 1)
    labor = sep1 + pd.Timedelta(days=(7 - sep1.weekday()) % 7)
    nov1 = pd.Timestamp(year, 11, 1)
    thanksgiving = nov1 + pd.Timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    return {
        "hol_memorial_day": week_of(memorial),
        "hol_july_4": week_of(pd.Timestamp(year, 7, 4)),
        "hol_labor_day": week_of(labor),
        "hol_black_friday": week_of(thanksgiving + pd.Timedelta(days=1)),
        "hol_christmas": week_of(pd.Timestamp(year, 12, 25)),
    }


def _ar1(rng: np.random.Generator, n: int, rho: float, sd: float) -> np.ndarray:
    e = rng.normal(0, sd * np.sqrt(max(1 - rho**2, 1e-6)), n)
    out = np.empty(n)
    out[0] = rng.normal(0, sd)
    for i in range(1, n):
        out[i] = rho * out[i - 1] + e[i]
    return out


def _anchored_series(weeks: pd.DatetimeIndex, anchors: list, noise: float, rng: np.random.Generator) -> np.ndarray:
    t = weeks.values.astype("datetime64[D]").astype(float)
    at = np.array([np.datetime64(d).astype("datetime64[D]").astype(float) for d, _ in anchors])
    av = np.array([v for _, v in anchors], dtype=float)
    return np.interp(t, at, av) + _ar1(rng, len(weeks), 0.8, noise)


def _flights(rng: np.random.Generator, n: int, on=(3, 6), off=(2, 5), start_on=True) -> np.ndarray:
    out = np.zeros(n)
    i, state = 0, start_on
    while i < n:
        length = rng.integers(on[0], on[1] + 1) if state else rng.integers(off[0], off[1] + 1)
        if state:
            out[i:i + length] = 1.0
        i += length
        state = not state
    return out


def _spend_series(ch: dict, rng: np.random.Generator, weeks: pd.DatetimeIndex, season: np.ndarray,
                  tv_on: np.ndarray, s: SynthSettings) -> tuple[np.ndarray, np.ndarray | None]:
    n = len(weeks)
    noise = rng.lognormal(0, 0.15, n)
    style = ch["style"]
    on_flags = None
    if style == "flight":
        on_flags = _flights(rng, n)
        x = on_flags * (1 + 0.6 * season) * noise
    elif style == "flight_paired":
        own = _flights(rng, n)
        on_flags = np.where(rng.random(n) < s.radio_tv_overlap, tv_on, own)
        x = on_flags * noise
    elif style == "flight_late":
        on_flags = _flights(rng, n, on=(2, 4), off=(3, 6))
        on_flags[weeks < pd.Timestamp("2023-06-05")] = 0.0
        x = on_flags * noise
    elif style == "drops":
        offset = int(rng.integers(0, 4))
        drop = (np.arange(n) % 4 == offset).astype(float)
        drop[weeks.month == 12] = 0.0
        x = drop * rng.uniform(0.8, 1.2, n)
    elif style == "demand":
        # bids follow seasonal demand; monthly budget resets add independent movement
        month = (weeks.year.values - weeks.year.values[0]) * 12 + (weeks.month.values - 1)
        levels = rng.uniform(0.6, 1.4, month.max() + 1)
        x = np.clip(1 + s.search_follows_demand * season, 0.2, None) * levels[month] * rng.lognormal(0, 0.15, n)
    else:  # always_on, budget reset each month, slow growth
        month = (weeks.year.values - weeks.year.values[0]) * 12 + (weeks.month.values - 1)
        levels = rng.uniform(0.4, 1.6, month.max() + 1)
        x = levels[month] * np.linspace(0.85, 1.15, n) * rng.lognormal(0, 0.15, n)
    x = np.asarray(x, dtype=float)
    if x.mean() > 0:
        x = x / x.mean() * ch["weekly_spend"]
    return np.round(x, 0), on_flags


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(settings: SynthSettings | None = None) -> SynthData:
    s = settings or SynthSettings()
    rng = np.random.default_rng(s.seed)
    end = pd.Timestamp(s.end_week)
    weeks = pd.date_range(end=end, periods=s.n_weeks, freq="W-MON")
    n = len(weeks)
    base = s.base_weekly_sales
    years = np.arange(n) / 52.18

    df = pd.DataFrame({"week": weeks})
    comp: dict[str, np.ndarray] = {}

    # Base and trend
    comp["Base"] = base * (1 + s.trend_per_year * years)

    # Seasonality: home improvement peaks in late spring and summer
    doy = weeks.dayofyear.values.astype(float)
    season = np.sin(2 * np.pi * (doy - 80) / 365.25) + 0.3 * np.cos(4 * np.pi * doy / 365.25)
    season = season / np.abs(season).max()
    comp["Seasonality"] = base * s.season_strength * season

    # Holidays
    hol = {h["key"]: np.zeros(n) for h in HOLIDAYS}
    for y in range(weeks.year.min(), weeks.year.max() + 1):
        for k, wk in holiday_weeks(y).items():
            hol[k][weeks == wk] = 1.0
    hol_effect = np.zeros(n)
    hol_truth = {}
    for h in HOLIDAYS:
        df[h["key"]] = hol[h["key"]]
        hol_effect += base * h["effect"] * hol[h["key"]]
        hol_truth[h["key"]] = base * h["effect"]
    comp["Holidays"] = hol_effect

    # Promotions: most big holiday weekends plus a few extra sales each year
    promo = np.zeros(n)
    for k in ("hol_memorial_day", "hol_labor_day", "hol_black_friday"):
        idx = np.flatnonzero(hol[k])
        for i in idx:
            if rng.random() < 0.8:
                promo[i] = rng.choice([10, 15, 20])
    for _ in range(int(3 * n / 52)):
        i = int(rng.integers(0, n - 1))
        promo[i:i + 2] = np.maximum(promo[i:i + 2], 10)
    df["promo_depth"] = promo
    comp["Promotions"] = base * PROMO["effect"] * promo

    # Economy
    macro_truth = {}
    econ = np.zeros(n)
    for m in MACRO:
        if m["anchors"]:
            x = _anchored_series(weeks, m["anchors"], m["noise"], rng)
        else:
            x = _ar1(rng, n, 0.6, 2.5)
        x = np.round(x, 2)
        df[m["key"]] = x
        coef = base * m["effect"] * s.macro_strength
        macro_truth[m["key"]] = coef
        econ += coef * (x - x.mean())
    comp["Economy"] = econ

    # Competitor pressure: a rival launches and lifts its share of voice
    sov = 0.30 + _ar1(rng, n, 0.9, 0.02)
    launch = pd.Timestamp("2024-02-05")
    k = np.asarray((weeks - launch).days // 7)
    sov += np.where(k >= 0, 0.05 + 0.05 * np.exp(-np.clip(k, 0, None) / 12), 0.0)
    sov = np.round(np.clip(sov, 0.05, 0.9), 3)
    df["competitor_sov"] = sov
    comp_coef = base * COMPETITOR["effect"] * s.macro_strength
    comp["Competition"] = comp_coef * (sov - sov.mean())

    # Price: drifts with inflation, steps up after tariffs
    infl = df["inflation"].values
    price = 100 * np.cumprod(1 + infl / 100 / 52 * 0.4)
    price = price * np.where(weeks >= pd.Timestamp("2025-05-05"), 1.06, 1.0)
    price = price / price.mean() * 100
    df["price_index"] = np.round(price, 2)
    price_coef = base * PRICE["elasticity"] / 100
    comp["Price"] = price_coef * (df["price_index"].values - df["price_index"].values.mean())

    # Events
    events = pd.DataFrame(EVENTS)
    events = events[(pd.to_datetime(events["start"]) >= weeks[0]) & (pd.to_datetime(events["start"]) <= weeks[-1])]
    events = events.reset_index(drop=True)
    events["modeled"] = events["shape"] != "context"
    ev_effect = np.zeros(n)
    event_truth = {}
    if s.include_events:
        for _, e in events[events["modeled"]].iterrows():
            sig = event_signal(weeks, e["start"], e["shape"], int(e["weeks"]), float(e["rate"]))
            ev_effect += base * e["effect"] * sig
            event_truth[e["name"]] = dict(per_unit=base * e["effect"], total=float((base * e["effect"] * sig).sum()))
    else:
        events = events.iloc[0:0]
    comp["Events"] = ev_effect

    # Media
    season01 = season
    tv_on = np.zeros(n)
    channel_rows = []
    for ch in s.channels:
        x, flags = _spend_series(ch, rng, weeks, season01, tv_on, s)
        if ch["style"] == "flight" and flags is not None:
            tv_on = flags
        df[f"spend_{ch['key']}"] = x
        a = adstock(x, ch["decay"])
        k_abs = ch["half_sat"] * reference_level(a)
        r = hill(a, k_abs, ch["shape"])
        beta = ch["roi"] * x.sum() / r.sum() if r.sum() > 0 else 0.0
        comp[ch["name"]] = beta * r
        channel_rows.append(dict(key=ch["key"], channel=ch["name"], roi=ch["roi"], decay=ch["decay"],
                                 half_sat_rel=ch["half_sat"], half_sat=k_abs, shape=ch["shape"], beta=beta,
                                 spend=x.sum(), contribution=(beta * r).sum()))

    # Noise
    comp["Noise"] = _ar1(rng, n, s.noise_autocorr, s.noise_pct * base)

    sales = sum(comp.values())
    df.insert(1, "sales", np.round(sales, 0))

    contrib = pd.DataFrame(comp)
    contrib.insert(0, "week", weeks)

    truth = dict(
        contributions=contrib,
        channels=pd.DataFrame(channel_rows),
        macro=macro_truth,
        competitor=comp_coef,
        price=price_coef,
        promo=base * PROMO["effect"],
        holidays=hol_truth,
        events=event_truth,
        settings=s.to_dict(),
    )
    return SynthData(df=df, events=events, truth=truth)


def channel_names(settings: SynthSettings) -> dict[str, str]:
    return {c["key"]: c["name"] for c in settings.channels}


def control_labels() -> dict[str, tuple[str, str]]:
    """key -> (label, unit) for every non-media driver column."""
    out = {m["key"]: (m["name"], m["unit"]) for m in MACRO}
    out[COMPETITOR["key"]] = (COMPETITOR["name"], COMPETITOR["unit"])
    out[PRICE["key"]] = (PRICE["name"], PRICE["unit"])
    out[PROMO["key"]] = (PROMO["name"], PROMO["unit"])
    for h in HOLIDAYS:
        out[h["key"]] = (h["name"], "week flag")
    return out


# ---------------------------------------------------------------------------
# Export as a plain weekly file, the same layout a user would upload
# ---------------------------------------------------------------------------

SPEND_COLUMNS = {
    "tv": "spend_tv",
    "radio": "spend_radio",
    "direct_mail": "spend_direct_mail",
    "search": "spend_paid_search",
    "social": "spend_paid_social",
    "video": "spend_online_video",
}


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")


def export_frame(d: SynthData) -> pd.DataFrame:
    """One row per week: week, sales, spend_*, outside drivers, hol_* flags, event_* signals."""
    df = d.df.copy()
    weeks = pd.DatetimeIndex(df["week"])
    df = df.rename(columns={f"spend_{k}": v for k, v in SPEND_COLUMNS.items()})
    for _, e in d.events[d.events["modeled"]].iterrows():
        df["event_" + _slug(e["name"])] = np.round(
            event_signal(weeks, e["start"], e["shape"], int(e["weeks"]), float(e["rate"])), 4)
    df["week"] = weeks.strftime("%Y-%m-%d")
    return df


def truth_by_name(d: SynthData) -> dict:
    """Planted ROI and carry-over per channel display name, plus weekly true contributions."""
    ch = d.truth["channels"].set_index("channel")
    return dict(channels=ch, contributions=d.truth["contributions"])
