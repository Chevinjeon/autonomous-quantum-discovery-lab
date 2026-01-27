from __future__ import annotations

import argparse
import numpy as np

from portfolio_lab.market import SyntheticMarket
from .generator import MarketState, ScenarioGenerator
from .scorer import classify_scenarios, score_scenarios
from .report import export_scores_csv, export_cases_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="AI stress tester (scenario lab).")
    parser.add_argument("--assets", type=int, default=6, help="Number of assets.")
    parser.add_argument("--steps", type=int, default=252, help="Time steps per scenario.")
    parser.add_argument("--scenarios", type=int, default=2000, help="Scenario count.")
    parser.add_argument("--drift-shift", type=float, default=0.0, help="Mean drift shift.")
    parser.add_argument("--vol-regime", type=float, default=1.0, help="Vol regime multiplier.")
    parser.add_argument("--corr-shift", type=float, default=0.0, help="Correlation shift.")
    parser.add_argument("--top-n", type=int, default=3, help="Top N cases per bucket.")
    parser.add_argument("--export-scores", default="", help="Export all scores to CSV.")
    parser.add_argument("--export-cases", default="", help="Export bull/bear/stress cases to CSV.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed.")
    args = parser.parse_args()

    market = SyntheticMarket(num_assets=args.assets, seed=args.seed)
    generator = ScenarioGenerator(market.mean, market.cov, seed=args.seed)
    state = MarketState(
        drift_shift=args.drift_shift,
        vol_regime=args.vol_regime,
        correlation_shift=args.corr_shift,
    )

    scenarios = generator.sample(args.steps, args.scenarios, state)

    weights = np.ones(args.assets) / args.assets
    scores = score_scenarios(weights, scenarios)
    cases = classify_scenarios(scores, top_n=args.top_n)

    for label, items in cases.items():
        print(f"\n=== {label.upper()} CASES ===")
        for s in items:
            print(
                f"scenario={s.idx:>5} sharpe={s.sharpe:>7.3f} "
                f"vol={s.vol:>6.3f} drawdown={s.drawdown:>7.3f} "
                f"cvar={s.cvar:>7.3f}"
            )

    if args.export_scores:
        export_scores_csv(args.export_scores, scores)
        print(f"\nExported scores to {args.export_scores}")

    if args.export_cases:
        export_cases_csv(args.export_cases, cases)
        print(f"Exported cases to {args.export_cases}")


if __name__ == "__main__":
    main()
