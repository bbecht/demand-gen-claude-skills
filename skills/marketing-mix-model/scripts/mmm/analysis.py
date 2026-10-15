"""Turn a fitted model into business answers: ROI, response curves, driver effects."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mmm.transforms import adstock, decay_weights, half_life, hill

Q_LO, Q_HI = 5, 95   # 90% intervals throughout

WINDOWS = {"Last 52 weeks": 52, "Last 26 weeks": 26, "Last 13 weeks": 13, "All weeks": None}


def window_mask(fr, window: str) -> np.ndarray:
    n = len(fr.weeks)
    w = WINDOWS.get(window)
    mask = np.zeros(n, dtype=bool)
    if w is None:
        mask[:] = True
    else:
        mask[-w:] = True
    return mask


VERDICTS = ("Grow", "Hold", "Trim", "Cut")
AGREE = 0.8   # share of bootstrap refits that must reach the same verdict for it to count as clear
ADJACENT = [("Grow", "Hold"), ("Hold", "Trim"), ("Trim", "Cut")]


def certainty(verdict: str, split: dict, calibrated: bool = False) -> str:
    """Clear: 80% of refits agree. Close call: the verdict holds in at least half the refits and it plus a
    neighbouring verdict hold 80%, or a lift test already anchors the channel. Test first: anything else."""
    if verdict == "Not run":
        return "Not run"
    if split.get(verdict, 0.0) >= AGREE:
        return "Clear"
    if calibrated:
        return "Close call"
    if split.get(verdict, 0.0) >= 0.5 and any(
            verdict in pair and split.get(pair[0], 0) + split.get(pair[1], 0) >= AGREE for pair in ADJACENT):
        return "Close call"
    return "Test first"


LEVELS = np.round(np.arange(0.1, 2.01, 0.1), 2)   # spend levels checked for "pays at any level", x today


def channel_verdict(mroi: float, pays: bool, margin: float) -> str:
    """By the next dollar's gross profit: Grow at 1.2x its cost or more, Hold 0.8 to 1.2x, below that Trim.
    Cut instead of Trim when the channel's gross profit covers its spend at no level from 0.1x to 2x today."""
    p = mroi * margin
    if p >= 1.2:
        return "Grow"
    if p >= 0.8:
        return "Hold"
    return "Trim" if pays else "Cut"


def pays_at(contrib_by_level: np.ndarray, spend: float, margin: float) -> np.ndarray:
    """contrib_by_level: levels x draws (or levels). True where some level's gross profit beats its spend."""
    c = np.asarray(contrib_by_level, dtype=float)
    cost = (LEVELS * spend).reshape((-1,) + (1,) * (c.ndim - 1))
    return (c * margin - cost > 0).any(axis=0)


def draw_contributions(fr, key: str, mult: float, mask: np.ndarray) -> np.ndarray:
    """The channel's contribution over the window under every bootstrap draw."""
    x = fr.spend[key].values.copy()
    x[mask] = x[mask] * mult
    return fr.draw_response(key, x)[:, mask].sum(axis=1)


def contribution_with_multiplier(fr, key: str, mult: float, mask: np.ndarray) -> float:
    x = fr.spend[key].values.copy()
    x[mask] = x[mask] * mult
    return float(fr.channel_response(key, x)[mask].sum())


def roi_table(fr, window: str = "Last 52 weeks", margin: float = 0.5) -> pd.DataFrame:
    mask = window_mask(fr, window)
    calibrated = {k for k, _, _ in fr.spec.calibration}
    rows = []
    total_spend = fr.spend[mask].sum().sum()
    total_eff = sum(fr.contributions.loc[mask, f"media:{k}"].sum() for k in fr.spec.channels)
    for k, name in zip(fr.spec.channels, fr.spec.channel_names):
        col = f"media:{k}"
        spend = float(fr.spend.loc[mask, k].sum())
        xsum = float(fr.design.loc[mask, col].sum())
        contrib = float(fr.coef[col] * xsum)
        draws = draw_contributions(fr, k, 1.0, mask)
        base = contribution_with_multiplier(fr, k, 1.0, mask)
        up = contribution_with_multiplier(fr, k, 1.01, mask)
        mroi = (up - base) / (0.01 * spend) if spend > 0 else np.nan
        roi = contrib / spend if spend > 0 else np.nan
        up_d = draw_contributions(fr, k, 1.01, mask)
        if spend > 0:
            pays = bool(pays_at(np.array([contribution_with_multiplier(fr, k, m, mask) for m in LEVELS]), spend, margin))
            pays_d = pays_at(np.array([draw_contributions(fr, k, m, mask) for m in LEVELS]), spend, margin)
        verdict = channel_verdict(mroi, pays, margin) if spend > 0 else "Not run"
        if spend > 0:
            vd = [channel_verdict(mr, pd_, margin) for mr, pd_ in zip((up_d - draws) / (0.01 * spend), pays_d)]
            split = {v: float(np.mean([x == v for x in vd])) for v in VERDICTS}
        else:
            split = {v: 0.0 for v in VERDICTS}
        agree = split.get(verdict, 0.0)
        rows.append(dict(
            key=k, channel=name, spend=spend, contribution=contrib,
            contribution_lo=min(float(np.percentile(draws, Q_LO)), contrib),
            contribution_hi=max(float(np.percentile(draws, Q_HI)), contrib),
            roi=roi,
            # the range always holds the main estimate, even when the refits settle elsewhere
            roi_lo=min(float(np.percentile(draws, Q_LO)), contrib) / spend if spend > 0 else np.nan,
            roi_hi=max(float(np.percentile(draws, Q_HI)), contrib) / spend if spend > 0 else np.nan,
            mroi=mroi,
            profit_roi=roi * margin - 1 if spend > 0 else np.nan,
            spend_share=spend / total_spend if total_spend > 0 else np.nan,
            effect_share=contrib / total_eff if total_eff > 0 else np.nan,
            zero_draws=float((fr.boot_media[k]["beta"].values <= 1e-9).mean()),
            verdict=verdict, agreement=agree, verdict_split=split,
            certainty=certainty(verdict, split, k in calibrated),
        ))
    return pd.DataFrame(rows)


def response_curve(fr, key: str, window: str = "Last 52 weeks", max_mult: float = 2.5, points: int = 51) -> pd.DataFrame:
    mask = window_mask(fr, window)
    spend = float(fr.spend.loc[mask, key].sum())
    mults = np.linspace(0, max_mult, points)
    contrib = np.array([contribution_with_multiplier(fr, key, m, mask) for m in mults])
    # with zero spend in the window, carry-in from earlier weeks remains; report the increment over that
    floor = contrib[0]
    inc = contrib - floor
    d0 = draw_contributions(fr, key, 0.0, mask)
    dr = np.array([draw_contributions(fr, key, m, mask) - d0 for m in mults])   # points x draws
    band_lo = np.percentile(dr, Q_LO, axis=1)
    band_hi = np.percentile(dr, Q_HI, axis=1)
    total_spend = mults * spend
    mroi = np.gradient(inc, total_spend) if spend > 0 else np.zeros_like(inc)
    return pd.DataFrame(dict(multiplier=mults, spend=total_spend, contribution=inc,
                             contribution_lo=band_lo, contribution_hi=band_hi,
                             roi=np.divide(inc, total_spend, out=np.zeros_like(inc), where=total_spend > 0),
                             mroi=mroi))


def carryover_table(fr, weeks: int = 12) -> pd.DataFrame:
    rows = []
    for k, r in fr.media.iterrows():
        w = decay_weights(r["decay"], weeks)
        for i, v in enumerate(w):
            rows.append(dict(channel=r["channel"], week=i, share=v))
    return pd.DataFrame(rows)


def media_params_table(fr) -> pd.DataFrame:
    t = fr.media.copy()
    t["half_life_weeks"] = [half_life(d) for d in t["decay"]]
    return t.reset_index()


def _sig_word(draws: np.ndarray) -> tuple[float, str]:
    if np.all(draws == 0):
        return 1.0, "Not significant"
    p = 2 * min((draws <= 0).mean(), (draws >= 0).mean())
    p = float(min(p, 1.0))
    return p, ("Significant" if p < 0.10 else "Not significant")


def control_effects(fr, window: str = "Last 52 weeks") -> pd.DataFrame:
    """Economy, competition, price and promotion: one row each."""
    mask = window_mask(fr, window)
    ybar = fr.y.mean()
    rows = []
    for c in fr.spec.controls:
        x = fr.design[c].values
        raw = x + fr.control_means[c]
        draws = fr.boot_coef[c].values
        coef = float(fr.coef[c])
        p, word = _sig_word(draws)
        sd = float(raw.std())
        contrib = fr.contributions.loc[mask, c]
        rows.append(dict(
            key=c, driver=fr.spec.label(c), group=fr.groups[c],
            coef=coef, coef_lo=float(np.percentile(draws, Q_LO)), coef_hi=float(np.percentile(draws, Q_HI)),
            p_value=p, verdict=word,
            one_sd_change=sd, weekly_effect_1sd=coef * sd, pct_effect_1sd=coef * sd / ybar * 100,
            elasticity=coef * raw.mean() / ybar if raw.mean() != 0 else np.nan,
            window_contribution=float(contrib.sum()),
            latest_value=float(raw[-1]), average_value=float(raw.mean()),
        ))
    return pd.DataFrame(rows)


def dummy_effects(fr, group: str) -> pd.DataFrame:
    """Holidays (group 'Holidays') or events (group 'Events')."""
    ybar = fr.y.mean()
    rows = []
    cols = [c for c in fr.design.columns if fr.groups.get(c) == group]
    for c in cols:
        draws = fr.boot_coef[c].values
        x = fr.design[c].values
        total = float(fr.coef[c] * x.sum())
        p, word = _sig_word(draws)
        name = fr.spec.label(c)
        rows.append(dict(
            key=c, name=name, weekly_lift=float(fr.coef[c]),
            weekly_lift_lo=float(np.percentile(draws, Q_LO)), weekly_lift_hi=float(np.percentile(draws, Q_HI)),
            pct_of_avg_week=float(fr.coef[c]) / ybar * 100,
            total_impact=total,
            total_lo=float(np.percentile(draws * x.sum(), Q_LO)), total_hi=float(np.percentile(draws * x.sum(), Q_HI)),
            weeks_affected=int((x > 0).sum()), p_value=p, verdict=word,
        ))
    return pd.DataFrame(rows)


def seasonality_profile(fr) -> pd.DataFrame:
    """Seasonal swing by day of year, from the Fourier terms."""
    doy = np.arange(1, 366)
    total = np.zeros(len(doy))
    for k in range(1, fr.spec.fourier_order + 1):
        total += fr.coef.get(f"sin{k}", 0.0) * np.sin(2 * np.pi * k * doy / 365.25)
        total += fr.coef.get(f"cos{k}", 0.0) * np.cos(2 * np.pi * k * doy / 365.25)
    dates = pd.Timestamp("2025-01-01") + pd.to_timedelta(doy - 1, unit="D")
    return pd.DataFrame(dict(date=dates, effect=total, pct=total / fr.y.mean() * 100))


def group_summary(fr, window: str = "Last 52 weeks") -> pd.DataFrame:
    """Total contribution per group over the window, with bootstrap intervals."""
    mask = window_mask(fr, window)
    xs = fr.design.loc[mask].sum()
    draws = fr.boot_coef.values * xs.values
    rows = []
    gser = pd.Series(fr.groups)
    for g in pd.unique(gser.reindex(fr.design.columns).values):
        cols = [c for c in fr.design.columns if fr.groups[c] == g]
        idx = [fr.design.columns.get_loc(c) for c in cols]
        d = draws[:, idx].sum(axis=1)
        media_keys = [c.split(":", 1)[1] for c in cols if c.startswith("media:")]
        if media_keys:
            d = sum(draw_contributions(fr, k, 1.0, mask) for k in media_keys)
        val = float((fr.coef[cols] * xs[cols]).sum())
        rows.append(dict(group=g, contribution=val, lo=float(np.percentile(d, Q_LO)), hi=float(np.percentile(d, Q_HI)),
                         is_media=g in fr.spec.channel_names))
    out = pd.DataFrame(rows)
    out["share"] = out["contribution"] / fr.y[mask].sum()
    return out


def headline(fr, window: str = "Last 52 weeks", margin: float = 0.5) -> dict:
    mask = window_mask(fr, window)
    rt = roi_table(fr, window, margin)
    sales = float(fr.y[mask].sum())
    media = float(rt["contribution"].sum())
    spend = float(rt["spend"].sum())
    best = rt.sort_values("mroi", ascending=False).iloc[0]
    worst = rt.sort_values("mroi", ascending=True).iloc[0]
    return dict(sales=sales, media=media, media_share=media / sales, spend=spend,
                blended_roi=media / spend if spend else np.nan,
                best_channel=best["channel"], best_mroi=best["mroi"],
                worst_channel=worst["channel"], worst_mroi=worst["mroi"])
