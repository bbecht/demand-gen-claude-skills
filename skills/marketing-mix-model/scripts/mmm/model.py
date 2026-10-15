"""Marketing mix model: adstock + Hill media transforms inside a regression.

Fitting runs in two layers:
- outer: differential evolution searches each channel's carry-over (decay), half-saturation and
  curve shape;
- inner: for each candidate, a ridge regression with non-negative media coefficients solves
  every other coefficient in closed form.

Uncertainty comes from a moving-block bootstrap of the residuals. Every draw refits the whole model,
the media curves included, so the ranges carry the doubt about carry-over and saturation too.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, lsq_linear, minimize

from mmm.transforms import adstock, hill, reference_level

EFFORT = {
    "Quick": dict(maxiter=25, popsize=8),
    "Standard": dict(maxiter=70, popsize=12),
    "Thorough": dict(maxiter=180, popsize=16),
}

BOOT_DRAWS = {"Quick": 20, "Standard": 40, "Thorough": 100}
BOOT_POP, BOOT_ITER = 6, 20   # population per parameter and generations for each bootstrap refit

GROUP_ORDER = ["Base", "Seasonality", "Holidays", "Events", "Economy and other", "Competition", "Price", "Promotions"]


@dataclass(frozen=True)
class ChannelBounds:
    decay: tuple[float, float] = (0.0, 0.85)
    half_sat: tuple[float, float] = (0.5, 3.0)
    shape: tuple[float, float] = (1.0, 3.0)


# Starting ranges for carry-over by channel type (common industry practice). Matched on words in the
# channel name; anything else gets the wide default.
SUGGESTED_DECAY = [
    (("tv", "television", "ctv", "ott"), (0.3, 0.85)),
    (("video", "youtube"), (0.2, 0.85)),
    (("radio", "audio", "podcast"), (0.1, 0.7)),
    (("print", "ooh", "outdoor", "billboard"), (0.1, 0.8)),
    (("mail", "dm"), (0.0, 0.6)),
    (("search", "sem", "ppc", "google"), (0.0, 0.4)),
    (("social", "meta", "facebook", "instagram", "linkedin", "tiktok"), (0.0, 0.6)),
    (("display", "programmatic"), (0.0, 0.6)),
    (("email",), (0.0, 0.4)),
    (("affiliate",), (0.0, 0.3)),
]


def suggested_decay(key: str) -> tuple[float, float]:
    words = set(key.lower().replace("-", "_").split("_"))
    low = key.lower()
    for names, rng in SUGGESTED_DECAY:
        if any(n in words or (len(n) > 3 and n in low) for n in names):
            return rng
    return (0.0, 0.85)


def suggested_bounds(keys) -> tuple[tuple[str, ChannelBounds], ...]:
    return tuple((k, ChannelBounds(decay=suggested_decay(k))) for k in keys)


@dataclass(frozen=True)
class ModelSpec:
    channels: tuple[str, ...]                 # spend column names
    channel_names: tuple[str, ...]            # display names
    controls: tuple[str, ...] = ()            # outside driver columns
    zero_controls: tuple[str, ...] = ()       # controls whose natural "nothing happening" level is 0 (promotions)
    control_groups: tuple[tuple[str, str], ...] = ()
    holidays: tuple[str, ...] = ()            # 0/1 week flag columns
    events: tuple[str, ...] = ()              # event signal columns (0 outside the event)
    labels: tuple[tuple[str, str], ...] = ()  # column -> display name
    fourier_order: int = 2
    trend: bool = True
    holdout_weeks: int = 13
    effort: str = "Standard"
    ridge: float = 0.001
    estimate_shape: bool = True
    n_boot: int = 0          # 0 = set by effort
    seed: int = 42
    bounds: tuple[tuple[str, ChannelBounds], ...] = ()
    calibration: tuple[tuple[str, float, float], ...] = ()   # (channel column, lift-test ROI, standard error)

    def bounds_for(self, key: str) -> ChannelBounds:
        return dict(self.bounds).get(key, ChannelBounds())

    def label(self, col: str) -> str:
        return dict(self.labels).get(col, col)

    def group_of(self, col: str) -> str:
        return dict(self.control_groups).get(col, "Economy and other")


@dataclass
class FitResult:
    spec: ModelSpec
    weeks: pd.DatetimeIndex
    y: np.ndarray
    yhat: np.ndarray
    train: np.ndarray                 # bool mask
    design: pd.DataFrame              # every column the model used, media already transformed
    groups: dict[str, str]            # column -> group name
    coef: pd.Series                   # $ per unit of each design column
    boot_coef: pd.DataFrame           # bootstrap draws of coef
    contributions: pd.DataFrame       # week x column, $
    media: pd.DataFrame               # per channel: decay, half_sat, shape, beta
    spend: pd.DataFrame               # week x channel column, $
    control_means: dict[str, float]
    metrics: dict = field(default_factory=dict)
    fit_seconds: float = 0.0
    evaluations: int = 0
    boot_media: dict = field(default_factory=dict)   # channel -> draws of decay, half_sat, shape, beta

    def draw_response(self, key: str, spend: np.ndarray) -> np.ndarray:
        """Weekly response under every bootstrap draw: draws x weeks."""
        t = self.boot_media[key]
        return np.array([b * hill(adstock(spend, d), k, s) for d, k, s, b in t[["decay", "half_sat", "shape", "beta"]].values])

    @property
    def residuals(self) -> np.ndarray:
        return self.y - self.yhat

    def group_contributions(self) -> pd.DataFrame:
        g = self.contributions.T.groupby(pd.Series(self.groups)).sum().T
        order = [c for c in GROUP_ORDER if c in g.columns] + [n for n in self.spec.channel_names if n in g.columns]
        g = g[order]
        g.index = self.weeks
        return g

    def channel_response(self, key: str, spend: np.ndarray) -> np.ndarray:
        row = self.media.loc[key]
        return row["beta"] * hill(adstock(spend, row["decay"]), row["half_sat"], row["shape"])


# ---------------------------------------------------------------------------
# Design
# ---------------------------------------------------------------------------

def build_base_design(df: pd.DataFrame, spec: ModelSpec):
    weeks = pd.DatetimeIndex(df["week"])
    n = len(df)
    cols: dict[str, np.ndarray] = {"intercept": np.ones(n)}
    groups = {"intercept": "Base"}
    if spec.trend:
        cols["trend"] = np.arange(n) / 52.18
        groups["trend"] = "Base"
    doy = weeks.dayofyear.values.astype(float)
    for k in range(1, spec.fourier_order + 1):
        cols[f"sin{k}"] = np.sin(2 * np.pi * k * doy / 365.25)
        cols[f"cos{k}"] = np.cos(2 * np.pi * k * doy / 365.25)
        groups[f"sin{k}"] = groups[f"cos{k}"] = "Seasonality"
    for h in spec.holidays:
        cols[h] = df[h].values.astype(float)
        groups[h] = "Holidays"
    for e in spec.events:
        cols[e] = df[e].values.astype(float)
        groups[e] = "Events"
    means = {}
    for c in spec.controls:
        x = df[c].values.astype(float)
        means[c] = 0.0 if c in spec.zero_controls else float(x.mean())
        cols[c] = x - means[c]
        groups[c] = spec.group_of(c)
    X = pd.DataFrame(cols, index=weeks)
    return X, groups, means


def _media_matrix(spend: np.ndarray, params: np.ndarray, n_ch: int, shape_fixed: bool):
    """spend: n x m. params: decay (m), half_sat_rel (m), shape (m, unless fixed)."""
    decay = params[:n_ch]
    hs = params[n_ch:2 * n_ch]
    shape = np.ones(n_ch) if shape_fixed else params[2 * n_ch:3 * n_ch]
    out = np.empty_like(spend, dtype=float)
    k_abs = np.empty(n_ch)
    for j in range(n_ch):
        a = adstock(spend[:, j], decay[j])
        k_abs[j] = hs[j] * reference_level(a)
        out[:, j] = hill(a, k_abs[j], shape[j])
    return out, decay, k_abs, shape


# ---------------------------------------------------------------------------
# Linear layer
# ---------------------------------------------------------------------------

class _Linear:
    """Ridge regression with non-negative media coefficients, on standardised columns.

    Lift-test calibration enters as extra rows: each says "this channel's ROI over the training
    weeks should be close to the test result", weighted by the test's standard error. ROI is linear
    in the channel's coefficient, so the solve stays a bounded least-squares problem.
    """

    def __init__(self, Xb: np.ndarray, y: np.ndarray, n_media: int, ridge: float,
                 spend_sums: np.ndarray | None = None, calib=(), sigma: float = 1.0):
        self.Xb = Xb
        self.n_media = n_media
        self.ridge = ridge
        self.y_sd = y.std() or 1.0
        self.y = y / self.y_sd
        self.n = len(y)
        self.spend_sums = spend_sums
        self.calib = list(calib)
        self.sigma = sigma
        # Projection that removes the base columns, used by the fast search objective (Frisch-Waugh).
        U, sv, _ = np.linalg.svd(Xb, full_matrices=False)
        self.U = U[:, sv > sv.max() * 1e-10]
        self.y_perp = self.y - self.U @ (self.U.T @ self.y)

    def _system(self, M: np.ndarray, y: np.ndarray):
        X = np.hstack([self.Xb, M])
        sd = X.std(axis=0)
        sd[sd < 1e-12] = 1.0
        sd[0] = 1.0  # intercept
        Xs = X / sd
        p = X.shape[1]
        pen = np.sqrt(self.ridge * self.n) * np.eye(p)
        pen[0, 0] = 0.0
        rows, targets = [pen], [np.zeros(p)]
        nb = self.Xb.shape[1]
        for j, roi, se in self.calib:
            w = self.sigma / max(se, 1e-6)
            r = np.zeros(p)
            r[nb + j] = w * self.y_sd / sd[nb + j] * M[:, j].sum() / max(self.spend_sums[j], 1e-9)
            rows.append(r[None, :])
            targets.append(np.array([w * roi]))
        A = np.vstack([Xs] + rows)
        b = np.concatenate([y] + targets)
        return A, b, sd

    def quick_sse(self, M: np.ndarray) -> float:
        """Fast loss used inside the search.

        The base columns (trend, seasons, holidays, events, drivers) are projected out once, so each
        candidate only solves for the media coefficients. Exact for the media coefficients except that
        the small ridge on the base columns is ignored here; the final solve includes it.
        """
        Mp = M - self.U @ (self.U.T @ M)
        sd = M.std(axis=0)
        sd[sd < 1e-12] = 1.0
        A = Mp / sd
        m = self.n_media
        rows, targets = [A, np.sqrt(self.ridge * self.n) * np.eye(m)], [self.y_perp, np.zeros(m)]
        for j, roi, se in self.calib:
            w = self.sigma / max(se, 1e-6)
            r = np.zeros(m)
            r[j] = w * self.y_sd / sd[j] * M[:, j].sum() / max(self.spend_sums[j], 1e-9)
            rows.append(r[None, :])
            targets.append(np.array([w * roi]))
        A = np.vstack(rows)
        b = np.concatenate(targets)
        active = np.ones(m, dtype=bool)
        coef = np.zeros(m)
        for _ in range(m + 1):
            coef = np.zeros(m)
            if active.any():
                coef[active] = np.linalg.lstsq(A[:, active], b, rcond=None)[0]
            neg = np.flatnonzero(coef < 0)
            if neg.size == 0:
                break
            active[neg[np.argmin(coef[neg])]] = False
        r = b - A @ coef
        return float(r @ r)

    def solve(self, M: np.ndarray, y: np.ndarray | None = None) -> np.ndarray:
        """Exact bounded solve. Returns coefficients in original units."""
        yy = self.y if y is None else y / self.y_sd
        A, b, sd = self._system(M, yy)
        nb = self.Xb.shape[1]
        lb = np.r_[np.full(nb, -np.inf), np.zeros(self.n_media)]
        ub = np.full(A.shape[1], np.inf)
        res = lsq_linear(A, b, bounds=(lb, ub), method="bvls")
        return res.x / sd * self.y_sd


# ---------------------------------------------------------------------------
# Fit
# ---------------------------------------------------------------------------

def fit(df: pd.DataFrame, spec: ModelSpec, kpi: str = "sales", progress=None) -> FitResult:
    t0 = time.perf_counter()
    Xb_df, groups, means = build_base_design(df, spec)
    n = len(df)
    train = np.arange(n) < n - spec.holdout_weeks
    y = df[kpi].values.astype(float)
    spend = df[list(spec.channels)].values.astype(float)
    m = len(spec.channels)
    spend_sums = spend[train].sum(axis=0)
    calib = [(spec.channels.index(k), roi, se) for k, roi, se in spec.calibration if k in spec.channels]
    sigma = 1.0
    if calib:
        # residual scale from an uncalibrated solve at mid-range curves, used to weight the tests
        mid = np.array([0.4] * m + [1.0] * m + ([1.5] * m if spec.estimate_shape else []))
        M0, *_ = _media_matrix(spend, mid, m, not spec.estimate_shape)
        lin0 = _Linear(Xb_df.values[train], y[train], m, spec.ridge)
        sigma = float(np.sqrt(lin0.quick_sse(M0[train]) / train.sum()))
    lin = _Linear(Xb_df.values[train], y[train], m, spec.ridge, spend_sums, calib, sigma)

    lo, hi = [], []
    for part in ("decay", "half_sat", "shape"):
        if part == "shape" and not spec.estimate_shape:
            continue
        for k in spec.channels:
            b = getattr(spec.bounds_for(k), part)
            lo.append(b[0])
            hi.append(b[1])
    bounds = list(zip(lo, hi))

    counter = {"n": 0}

    def objective(p):
        counter["n"] += 1
        M, *_ = _media_matrix(spend, p, m, not spec.estimate_shape)
        return lin.quick_sse(M[train])

    cfg = EFFORT.get(spec.effort, EFFORT["Standard"])
    gen = {"i": 0}

    def cb(xk, convergence=None):
        gen["i"] += 1
        if progress:
            progress(min(gen["i"] / cfg["maxiter"], 1.0))
        return False

    de = differential_evolution(objective, bounds, seed=spec.seed, maxiter=cfg["maxiter"], popsize=cfg["popsize"],
                                tol=1e-7, polish=False, init="sobol", callback=cb, updating="deferred")
    pol = minimize(objective, de.x, method="L-BFGS-B", bounds=bounds, options=dict(maxiter=200))
    best = pol.x if pol.fun <= de.fun else de.x

    M, decay, k_abs, shape = _media_matrix(spend, best, m, not spec.estimate_shape)
    coef = lin.solve(M[train])
    media_cols = [f"media:{k}" for k in spec.channels]
    X = pd.concat([Xb_df, pd.DataFrame(M, index=Xb_df.index, columns=media_cols)], axis=1)
    for k, name in zip(spec.channels, spec.channel_names):
        groups[f"media:{k}"] = name
    coef_s = pd.Series(coef, index=X.columns)
    yhat = X.values @ coef

    # Bootstrap: resample the misses in 4-week blocks, then refit everything, curves included.
    # Each draw restarts the curve search near the best answer with a shorter run.
    rng = np.random.default_rng(spec.seed)
    resid = (y - yhat)[train]
    n_tr = int(train.sum())
    block = 4
    lo_b, hi_b = np.array(lo), np.array(hi)
    dim = len(bounds)
    pop = max(5, BOOT_POP * dim)
    draws, media_draws = [], []
    n_boot = spec.n_boot or BOOT_DRAWS.get(spec.effort, 40)
    for i in range(n_boot):
        starts = rng.integers(0, n_tr - block + 1, size=int(np.ceil(n_tr / block)))
        e = np.concatenate([resid[s:s + block] for s in starts])[:n_tr]
        yb = yhat[train] + e
        lin_b = _Linear(Xb_df.values[train], yb, m, spec.ridge, spend_sums, calib, sigma)

        def obj_b(p, lin_b=lin_b):
            M_, *_ = _media_matrix(spend, p, m, not spec.estimate_shape)
            return lin_b.quick_sse(M_[train])

        init = best + rng.normal(0, 0.15, (pop, dim)) * (hi_b - lo_b)
        init[0] = best
        half = pop // 2
        init[half:] = lo_b + rng.random((pop - half, dim)) * (hi_b - lo_b)
        init = np.clip(init, lo_b, hi_b)
        de_b = differential_evolution(obj_b, bounds, seed=spec.seed + 1 + i, maxiter=BOOT_ITER, init=init,
                                      tol=1e-7, polish=False, updating="deferred")
        Mb, db, kb, shb = _media_matrix(spend, de_b.x, m, not spec.estimate_shape)
        cb_ = lin_b.solve(Mb[train])
        draws.append(cb_)
        media_draws.append(np.column_stack([db, kb, shb, cb_[-m:]]))
        if progress:
            progress(1.0)
    boot = pd.DataFrame(draws, columns=X.columns)
    boot_media = {k: pd.DataFrame([d_[j] for d_ in media_draws], columns=["decay", "half_sat", "shape", "beta"])
                  for j, k in enumerate(spec.channels)}

    contrib = X * coef_s
    media = pd.DataFrame(dict(key=list(spec.channels), channel=list(spec.channel_names), decay=decay,
                              half_sat_rel=best[m:2 * m], half_sat=k_abs, shape=shape,
                              beta=coef[-m:])).set_index("key")

    fr = FitResult(spec=spec, weeks=pd.DatetimeIndex(df["week"]), y=y, yhat=yhat, train=train, design=X,
                   groups=groups, coef=coef_s, boot_coef=boot, contributions=contrib, media=media,
                   spend=pd.DataFrame(spend, columns=list(spec.channels), index=Xb_df.index),
                   control_means=means, fit_seconds=time.perf_counter() - t0, evaluations=counter["n"],
                   boot_media=boot_media)
    from mmm.diagnostics import fit_metrics
    fr.metrics = fit_metrics(fr)
    return fr
