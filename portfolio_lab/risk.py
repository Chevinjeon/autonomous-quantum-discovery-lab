from __future__ import annotations

import numpy as np


def value_at_risk(r: np.ndarray, alpha: float = 0.05) -> float:
    """
    Historical VaR at confidence level (1 - alpha).
    Returns a negative number for loss.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be between 0 and 1.")
    return float(np.quantile(r, alpha))


def conditional_value_at_risk(r: np.ndarray, alpha: float = 0.05) -> float:
    """
    Historical CVaR (expected shortfall) at confidence level (1 - alpha).
    Returns a negative number for loss.
    """
    var = value_at_risk(r, alpha)
    tail = r[r <= var]
    if tail.size == 0:
        return var
    return float(np.mean(tail))
