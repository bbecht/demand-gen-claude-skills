"""Compare a fitted model with the answers planted in the synthetic data (demo mode only)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mmm.analysis import LEVELS, Q_HI, Q_LO, channel_verdict, contribution_with_multiplier, draw_contributions, pays_at, window_mask
from mmm.transforms import adstock, hill


def _true_contrib(fr, tch, name, key, mult, mask):
    t = tch.loc[name]
    x = fr.spend[key].values.copy()
    x[mask] = x[mask] * mult
    return float((t["beta"] * hill(adstock(x, t["decay"]), t["half_sat"], t["shape"]))[mask].sum())


def channel_check(fr, truth: dict, window: str = "All weeks", margin: float = 0.5) -> pd.DataFrame:
    """ROI over `window` against the planted truth, plus the Grow/Hold/Trim/Cut verdict on the last 52 weeks."""
    vmask = window_mask(fr, "Last 52 weeks")
    mask = window_mask(fr, window)
    tch = truth["channels"]
    tcon = truth["contributions"]
    rows = []
    for k, name in zip(fr.spec.channels, fr.spec.channel_names):
        if name not in tch.index:
            continue
        col = f"media:{k}"
        spend = fr.spend.loc[mask, k].sum()
        xs = fr.design.loc[mask, col].sum()
        est = fr.coef[col] * xs / spend if spend else np.nan
        d = draw_contributions(fr, k, 1.0, mask) / spend if spend else np.array([np.nan])
        true_roi = tcon.loc[mask, name].sum() / spend if spend else np.nan
        lo, hi = min(np.percentile(d, Q_LO), est), max(np.percentile(d, Q_HI), est)
        vs = fr.spend.loc[vmask, k].sum()
        t1 = _true_contrib(fr, tch, name, k, 1.0, vmask)
        t2 = _true_contrib(fr, tch, name, k, 1.01, vmask)
        e1 = contribution_with_multiplier(fr, k, 1.0, vmask)
        e2 = contribution_with_multiplier(fr, k, 1.01, vmask)
        t_pays = bool(pays_at(np.array([_true_contrib(fr, tch, name, k, m, vmask) for m in LEVELS]), vs, margin)) if vs else False
        e_pays = bool(pays_at(np.array([contribution_with_multiplier(fr, k, m, vmask) for m in LEVELS]), vs, margin)) if vs else False
        true_v = channel_verdict((t2 - t1) / (0.01 * vs), t_pays, margin) if vs else "Not run"
        est_v = channel_verdict((e2 - e1) / (0.01 * vs), e_pays, margin) if vs else "Not run"
        rows.append(dict(channel=name, true_verdict=true_v, est_verdict=est_v, true_roi=float(true_roi), est_roi=float(est), est_lo=float(lo),
                         est_hi=float(hi), error_pct=float((est - true_roi) / true_roi * 100) if true_roi else None,
                         in_range=bool(lo <= true_roi <= hi),
                         true_decay=float(tch.loc[name, "decay"]), est_decay=float(fr.media.loc[k, "decay"])))
    return pd.DataFrame(rows)


def simulate_lift_tests(fr, truth: dict, names: list[str], se: float = 0.25, seed: int = 11):
    """Pretend a geo lift test ran on each named channel: true ROI over the training weeks, plus test noise."""
    rng = np.random.default_rng(seed)
    tcon = truth["contributions"]
    by_name = dict(zip(fr.spec.channel_names, fr.spec.channels))
    out = []
    for name in names:
        k = by_name[name]
        spend = fr.spend.loc[fr.train, k].sum()
        true = tcon.loc[fr.train, name].sum() / spend if spend else 0.0
        out.append((k, round(float(true + rng.normal(0, se)), 2), se))
    return out
