"""Budget allocation and what-if scenarios on top of a fitted model.

Every plan scales each channel's actual weekly pattern in the chosen window, so flighting and
timing stay as they were; only the level changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from mmm.analysis import contribution_with_multiplier, window_mask


def _total(fr, mults: np.ndarray, mask: np.ndarray) -> float:
    return sum(contribution_with_multiplier(fr, k, m, mask) for k, m in zip(fr.spec.channels, mults))


def optimize_budget(fr, budget: float, window: str = "Last 52 weeks", lo: float = 0.5, hi: float = 2.0,
                    locked: dict[str, float] | None = None, seed: int = 0,
                    limits: dict[str, tuple[float, float]] | None = None) -> pd.DataFrame:
    """Best split of `budget` across channels. Each channel stays within lo..hi times its actual spend.

    locked: channel key -> fixed multiplier (kept out of the search).
    limits: channel key -> its own (lo, hi), overriding the shared range.
    """
    limits = limits or {}
    mask = window_mask(fr, window)
    keys = list(fr.spec.channels)
    spend = np.array([fr.spend.loc[mask, k].sum() for k in keys])
    locked = locked or {}
    free = [i for i, k in enumerate(keys) if k not in locked and spend[i] > 0]
    fixed_mult = np.ones(len(keys))
    for i, k in enumerate(keys):
        if k in locked:
            fixed_mult[i] = locked[k]
        elif spend[i] <= 0:
            fixed_mult[i] = 0.0
    fixed_spend = sum(spend[i] * fixed_mult[i] for i in range(len(keys)) if i not in free)
    remaining = budget - fixed_spend
    scale = max(_total(fr, np.ones(len(keys)), mask), 1.0)

    def full(z):
        m = fixed_mult.copy()
        m[free] = z
        return m

    def obj(z):
        return -_total(fr, full(z), mask) / scale

    cons = [dict(type="eq", fun=lambda z: (spend[free] @ z - remaining) / max(budget, 1.0))]
    bounds = [limits.get(keys[i], (lo, hi)) for i in free]
    blo = np.array([b[0] for b in bounds])
    bhi = np.array([b[1] for b in bounds])
    if not free or spend[free] @ blo > remaining + 1e-6 * budget or spend[free] @ bhi < remaining - 1e-6 * budget:
        raise ValueError("No plan fits that budget inside the channel limits.")
    rng = np.random.default_rng(seed)
    starts = [np.full(len(free), remaining / spend[free].sum()), np.ones(len(free))]
    starts += [rng.uniform(blo, bhi) for _ in range(2)]
    best = None
    for z0 in starts:
        z0 = np.clip(z0, blo, bhi)
        res = minimize(obj, z0, method="SLSQP", bounds=bounds, constraints=cons,
                       options=dict(maxiter=300, ftol=1e-10))
        feasible = abs(spend[free] @ res.x - remaining) < 1e-3 * max(budget, 1.0)
        if feasible and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        raise ValueError("No plan fits that budget inside the channel limits. Widen the limits or change the budget.")
    m = full(best.x)
    rows = []
    for i, (k, name) in enumerate(zip(keys, fr.spec.channel_names)):
        cur = contribution_with_multiplier(fr, k, 1.0, mask)
        new = contribution_with_multiplier(fr, k, m[i], mask)
        up = contribution_with_multiplier(fr, k, m[i] * 1.01, mask)
        mroi_new = (up - new) / (0.01 * spend[i] * m[i]) if spend[i] * m[i] > 0 else np.nan
        rows.append(dict(key=k, channel=name, current_spend=spend[i], optimal_spend=spend[i] * m[i], multiplier=m[i],
                         current_contribution=cur, optimal_contribution=new,
                         current_roi=cur / spend[i] if spend[i] else np.nan,
                         optimal_roi=new / (spend[i] * m[i]) if spend[i] * m[i] else np.nan,
                         optimal_mroi=mroi_new, locked=k in locked))
    return pd.DataFrame(rows)


def budget_frontier(fr, window: str = "Last 52 weeks", levels=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0),
                    lo: float = 0.0, hi: float = 3.0) -> pd.DataFrame:
    """Media-driven sales at each total budget: today's mix scaled vs the best mix."""
    mask = window_mask(fr, window)
    total_spend = fr.spend[mask].sum().sum()
    rows = []
    for lv in levels:
        b = total_spend * lv
        same_mix = _total(fr, np.full(len(fr.spec.channels), lv), mask)
        try:
            opt = optimize_budget(fr, b, window, lo=lo, hi=hi)["optimal_contribution"].sum()
        except ValueError:
            opt = np.nan
        rows.append(dict(level=lv, budget=b, current_mix=same_mix, optimal_mix=opt))
    return pd.DataFrame(rows)


def scenario(fr, media_mult: dict[str, float], control_shift: dict[str, float],
             window: str = "Last 52 weeks") -> dict:
    """What-if on the window: change channel spend (multipliers) and shift drivers (units added each week)."""
    mask = window_mask(fr, window)
    base = fr.yhat.copy()
    new = base.copy()
    media_rows = []
    for k, name in zip(fr.spec.channels, fr.spec.channel_names):
        m = media_mult.get(k, 1.0)
        x0 = fr.spend[k].values
        x1 = x0.copy()
        x1[mask] = x1[mask] * m
        r0 = fr.channel_response(k, x0)
        r1 = fr.channel_response(k, x1)
        new += (r1 - r0) * mask   # only count weeks inside the window
        media_rows.append(dict(driver=name, kind="Media", change=float(((r1 - r0) * mask).sum()),
                               spend_change=float((x1 - x0)[mask].sum())))
    for c, shift in control_shift.items():
        if c in fr.coef.index and shift:
            delta = fr.coef[c] * shift * mask
            new += delta
            media_rows.append(dict(driver=c, kind="Driver", change=float(delta.sum()), spend_change=0.0))
    return dict(
        weeks=fr.weeks[mask], baseline=base[mask], scenario=new[mask],
        baseline_total=float(base[mask].sum()), scenario_total=float(new[mask].sum()),
        breakdown=pd.DataFrame(media_rows),
    )
