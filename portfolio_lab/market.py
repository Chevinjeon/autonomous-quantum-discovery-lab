import numpy as np


class SyntheticMarket:
    """
    Generates correlated asset returns.
    This acts as the placeholder for a future QGAN.
    """

    def __init__(self, num_assets: int, seed: int = 0) -> None:
        self.num_assets = num_assets
        self.rng = np.random.default_rng(seed)

        a = self.rng.normal(size=(num_assets, num_assets))
        raw = a @ a.T
        diag = np.sqrt(np.diag(raw))
        corr = raw / np.outer(diag, diag)
        corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)

        vols = self.rng.uniform(0.005, 0.02, size=num_assets)
        self.cov = corr * np.outer(vols, vols)
        self.mean = self.rng.normal(0.001, 0.003, size=num_assets)

    def sample_returns(self, num_steps: int) -> np.ndarray:
        """
        Returns shape: (num_steps, num_assets)
        """
        return self.rng.multivariate_normal(
            mean=self.mean,
            cov=self.cov,
            size=num_steps,
        )


def portfolio_returns(weights: np.ndarray, returns: np.ndarray) -> np.ndarray:
    """
    Computes portfolio returns over time.

    weights: (num_assets,)
    returns: (T, num_assets)
    """
    return returns @ weights


def sharpe_ratio(r: np.ndarray, eps: float = 1e-8) -> float:
    """
    Mean / Std deviation.
    """
    return float(np.mean(r) / (np.std(r) + eps))


def volatility(r: np.ndarray) -> float:
    return float(np.std(r))


def max_drawdown(r: np.ndarray) -> float:
    """
    Computes maximum drawdown of cumulative returns.
    """
    cumulative = np.cumsum(r)
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak
    return float(np.min(drawdown))


def main() -> None:
    market = SyntheticMarket(num_assets=5, seed=42)
    w = np.ones(5) / 5.0

    returns = market.sample_returns(num_steps=500)
    pr = portfolio_returns(w, returns)

    print("Sharpe:", sharpe_ratio(pr))
    print("Volatility:", volatility(pr))
    print("Max Drawdown:", max_drawdown(pr))


if __name__ == "__main__":
    main()
