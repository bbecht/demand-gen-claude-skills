"""Media transforms: carry-over (adstock) and diminishing returns (Hill saturation)."""

from __future__ import annotations

import numpy as np


def adstock(spend: np.ndarray, decay: float) -> np.ndarray:
    """Geometric carry-over: a_t = x_t + decay * a_{t-1}.

    Written as a convolution with the full decay kernel, so it needs numpy only (no scipy.signal, whose
    compiled filter some locked-down Windows machines block)."""
    x = np.asarray(spend, dtype=float)
    if decay <= 0:
        return x.copy()
    return np.convolve(x, np.power(decay, np.arange(len(x))))[:len(x)]


def hill(x: np.ndarray, half_sat: float, shape: float) -> np.ndarray:
    """Hill curve scaled 0..1. half_sat is in the same units as x."""
    x = np.maximum(np.asarray(x, dtype=float), 0.0)
    xs = np.power(x, shape)
    return xs / (xs + half_sat**shape)


def media_response(spend: np.ndarray, decay: float, half_sat: float, shape: float) -> np.ndarray:
    """Adstock then saturate. Output 0..1, multiply by the channel coefficient."""
    return hill(adstock(spend, decay), half_sat, shape)


def decay_weights(decay: float, weeks: int = 12) -> np.ndarray:
    """Share of one week's effect that lands in each later week."""
    w = decay ** np.arange(weeks)
    return w / w.sum() if w.sum() > 0 else w


def reference_level(adstocked: np.ndarray) -> float:
    """Typical adstocked level (mean of non-zero weeks). Half-saturation is set relative to it."""
    a = np.asarray(adstocked, dtype=float)
    pos = a[a > 1e-9]
    return float(pos.mean()) if pos.size else 1.0


def half_life(decay: float) -> float:
    """Weeks until carry-over falls to half."""
    if decay <= 0:
        return 0.0
    return float(np.log(0.5) / np.log(decay))
