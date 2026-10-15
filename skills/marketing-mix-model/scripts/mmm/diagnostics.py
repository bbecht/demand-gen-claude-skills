"""Fit statistics and residual checks, each with a plain-word rating."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _mape(y, f):
    """Total weekly miss as a share of total sales. Safe when some weeks have no sales."""
    tot = float(np.sum(np.abs(y)))
    return float(np.sum(np.abs(y - f)) / tot * 100) if tot > 0 else float("nan")


def acf(x: np.ndarray, lags: int = 12) -> np.ndarray:
    x = np.asarray(x, dtype=float) - np.mean(x)
    d = x @ x
    return np.array([(x[:-k] @ x[k:]) / d for k in range(1, lags + 1)])


def rate(value: float, good: float, ok: float, higher_is_better: bool = False) -> str:
    if higher_is_better:
        return "Pass" if value >= good else "Warning" if value >= ok else "Fail"
    return "Pass" if value <= good else "Warning" if value <= ok else "Fail"


def fit_metrics(fr) -> dict:
    y, f, tr = fr.y, fr.yhat, fr.train
    ho = ~tr
    r = y - f
    rt = r[tr]
    ss_res = rt @ rt
    ss_tot = ((y[tr] - y[tr].mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot
    p = fr.design.shape[1]
    n = tr.sum()
    adj = 1 - (1 - r2) * (n - 1) / max(n - p - 1, 1)
    dw = float(np.sum(np.diff(rt) ** 2) / ss_res)
    jb_p = float(stats.jarque_bera(rt).pvalue)
    a = acf(rt, 12)
    lb_q = n * (n + 2) * np.sum(a**2 / (n - np.arange(1, 13)))
    lb_p = float(1 - stats.chi2.cdf(lb_q, 12))

    # Spend share vs effect share distance (lower = the model's split looks like the spend split)
    media_cols = [c for c in fr.design.columns if c.startswith("media:")]
    eff = fr.contributions[media_cols].sum().values
    spd = fr.spend.sum().values
    rssd = float(np.sqrt(np.sum((eff / eff.sum() - spd / spd.sum()) ** 2))) if eff.sum() > 0 else np.nan

    out = dict(
        r2_train=float(r2),
        adj_r2_train=float(adj),
        mape_train=_mape(y[tr], f[tr]),
        mape_holdout=_mape(y[ho], f[ho]) if ho.any() else np.nan,
        nrmse_train=float(np.sqrt(ss_res / n) / (y[tr].max() - y[tr].min())),
        durbin_watson=dw,
        jarque_bera_p=jb_p,
        ljung_box_p=lb_p,
        decomp_rssd=rssd,
        n_train=int(n),
        n_holdout=int(ho.sum()),
        n_params=int(p),
    )
    out["ratings"] = dict(
        r2_train=rate(r2, 0.85, 0.70, higher_is_better=True),
        mape_holdout=rate(out["mape_holdout"], 5.0, 10.0) if ho.any() else "Not run",
        durbin_watson="Pass" if 1.5 <= dw <= 2.5 else "Warning" if 1.0 <= dw <= 3.0 else "Fail",
        ljung_box_p=rate(lb_p, 0.05, 0.01, higher_is_better=True),
        jarque_bera_p=rate(jb_p, 0.05, 0.01, higher_is_better=True),
    )
    return out


def vif(fr) -> pd.DataFrame:
    """Variance inflation factor for every column except the intercept."""
    X = fr.design[fr.train]
    cols = [c for c in X.columns if c != "intercept" and X[c].std() > 0]
    rows = []
    A = X[cols].values
    for j, c in enumerate(cols):
        others = np.column_stack([np.ones(len(A)), np.delete(A, j, axis=1)])
        beta = np.linalg.lstsq(others, A[:, j], rcond=None)[0]
        res = A[:, j] - others @ beta
        ss_tot = ((A[:, j] - A[:, j].mean()) ** 2).sum()
        r2 = 1 - (res @ res) / ss_tot if ss_tot > 0 else 0.0
        v = 1 / max(1 - r2, 1e-9)
        rows.append(dict(column=c, group=fr.groups.get(c, ""), vif=v,
                         rating="Pass" if v < 5 else "Warning" if v < 10 else "Fail"))
    return pd.DataFrame(rows).sort_values("vif", ascending=False)
