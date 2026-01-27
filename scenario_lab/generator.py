from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class MarketState:
    drift_shift: float = 0.0
    vol_regime: float = 1.0
    correlation_shift: float = 0.0


class ScenarioGenerator:
    def __init__(self, mean: np.ndarray, cov: np.ndarray, seed: int = 0) -> None:
        self.mean = mean
        self.cov = cov
        self.rng = np.random.default_rng(seed)

    def sample(self, steps: int, scenarios: int, state: MarketState) -> np.ndarray:
        mean = self.mean + state.drift_shift
        cov = self._adjust_covariance(self.cov, state.vol_regime, state.correlation_shift)
        data = self.rng.multivariate_normal(mean=mean, cov=cov, size=(scenarios, steps))
        return data

    @staticmethod
    def _adjust_covariance(cov: np.ndarray, vol_regime: float, corr_shift: float) -> np.ndarray:
        vols = np.sqrt(np.diag(cov))
        corr = cov / np.outer(vols, vols)
        corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
        corr = np.clip(corr + corr_shift, -0.99, 0.99)
        adjusted = corr * np.outer(vols * vol_regime, vols * vol_regime)
        return adjusted
