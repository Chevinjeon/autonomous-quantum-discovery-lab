from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List

import numpy as np

from .market import SyntheticMarket, max_drawdown, portfolio_returns, sharpe_ratio, volatility
from .qubo import QuboProblem, build_qubo, solve_qubo


@dataclass
class PortfolioTrial:
    step: int
    selected: List[int]
    weights: np.ndarray
    sharpe: float
    vol: float
    drawdown: float


class PortfolioRiskLab:
    def __init__(self, market: SyntheticMarket) -> None:
        self.market = market
        self.trials: List[PortfolioTrial] = []

    def run_step(
        self,
        step: int,
        horizon: int,
        risk_aversion: float,
        target_assets: int,
        penalty: float,
        seed: int,
    ) -> PortfolioTrial:
        returns = self.market.sample_returns(num_steps=horizon)
        mean = returns.mean(axis=0)
        cov = np.cov(returns.T)

        qubo = build_qubo(
            mean=mean,
            cov=cov,
            risk_aversion=risk_aversion,
            target_assets=target_assets,
            penalty=penalty,
        )
        x = solve_qubo(qubo, seed=seed)
        selected = [i for i, bit in enumerate(x) if bit == 1]
        if not selected:
            selected = [int(np.argmax(mean))]

        weights = np.zeros_like(mean)
        weights[selected] = 1.0 / len(selected)

        pr = portfolio_returns(weights, returns)
        trial = PortfolioTrial(
            step=step,
            selected=selected,
            weights=weights,
            sharpe=sharpe_ratio(pr),
            vol=volatility(pr),
            drawdown=max_drawdown(pr),
        )
        self.trials.append(trial)
        return trial

    def best(self) -> PortfolioTrial | None:
        return max(self.trials, key=lambda t: t.sharpe) if self.trials else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous portfolio risk lab (QUBO).")
    parser.add_argument("--assets", type=int, default=6, help="Number of assets.")
    parser.add_argument("--horizon", type=int, default=252, help="Return horizon.")
    parser.add_argument("--steps", type=int, default=30, help="Optimization steps.")
    parser.add_argument("--risk-aversion", type=float, default=1.0, help="Risk penalty.")
    parser.add_argument("--target-assets", type=int, default=3, help="Assets to select.")
    parser.add_argument("--penalty", type=float, default=10.0, help="Constraint penalty.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed.")
    args = parser.parse_args()

    market = SyntheticMarket(num_assets=args.assets, seed=args.seed)
    lab = PortfolioRiskLab(market)

    for step in range(1, args.steps + 1):
        trial = lab.run_step(
            step=step,
            horizon=args.horizon,
            risk_aversion=args.risk_aversion,
            target_assets=args.target_assets,
            penalty=args.penalty,
            seed=args.seed + step,
        )
        if step % 5 == 0:
            print(
                f"step={step:>3} sharpe={trial.sharpe:>6.3f} "
                f"vol={trial.vol:>6.3f} drawdown={trial.drawdown:>6.3f} "
                f"selected={trial.selected}"
            )

    best = lab.best()
    if best is None:
        raise RuntimeError("No trials recorded.")

    print("\n=== PORTFOLIO RISK LAB ===")
    print(f"Best sharpe: {best.sharpe:.4f}")
    print(f"Volatility: {best.vol:.4f}")
    print(f"Drawdown: {best.drawdown:.4f}")
    print(f"Selected assets: {best.selected}")


if __name__ == "__main__":
    main()
