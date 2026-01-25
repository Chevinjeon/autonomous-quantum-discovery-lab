from __future__ import annotations

import argparse
from dataclasses import dataclass
import csv
from typing import List

import numpy as np

from .market import SyntheticMarket, max_drawdown, portfolio_returns, sharpe_ratio, volatility
from .risk import value_at_risk, conditional_value_at_risk
from .qubo import QuboProblem, build_qubo, solve_qubo


@dataclass
class PortfolioTrial:
    step: int
    selected: List[int]
    weights: np.ndarray
    sharpe: float
    vol: float
    drawdown: float
    var: float
    cvar: float


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
            var=value_at_risk(pr),
            cvar=conditional_value_at_risk(pr),
        )
        self.trials.append(trial)
        return trial

    def best(self) -> PortfolioTrial | None:
        return max(self.trials, key=lambda t: t.sharpe) if self.trials else None

    def export_csv(self, path: str) -> None:
        if not self.trials:
            raise RuntimeError("No trials to export.")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["step", "sharpe", "volatility", "drawdown", "var", "cvar", "selected"]
            )
            for t in self.trials:
                writer.writerow(
                    [
                        t.step,
                        f"{t.sharpe:.6f}",
                        f"{t.vol:.6f}",
                        f"{t.drawdown:.6f}",
                        f"{t.var:.6f}",
                        f"{t.cvar:.6f}",
                        ",".join(map(str, t.selected)),
                    ]
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous portfolio risk lab (QUBO).")
    parser.add_argument("--assets", type=int, default=6, help="Number of assets.")
    parser.add_argument("--horizon", type=int, default=252, help="Return horizon.")
    parser.add_argument("--steps", type=int, default=30, help="Optimization steps.")
    parser.add_argument("--risk-aversion", type=float, default=1.0, help="Risk penalty.")
    parser.add_argument("--target-assets", type=int, default=3, help="Assets to select.")
    parser.add_argument("--penalty", type=float, default=10.0, help="Constraint penalty.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed.")
    parser.add_argument("--export-csv", default="", help="Export trials to CSV.")
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

    if args.export_csv:
        lab.export_csv(args.export_csv)
        print(f"Exported trials to {args.export_csv}")


if __name__ == "__main__":
    main()
