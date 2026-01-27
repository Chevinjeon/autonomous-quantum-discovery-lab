from __future__ import annotations

from dataclasses import dataclass
from typing import List
import numpy as np

from portfolio_lab.market import portfolio_returns
from portfolio_lab.risk import conditional_value_at_risk, value_at_risk
from portfolio_lab.market import max_drawdown, volatility, sharpe_ratio


@dataclass
class ScenarioScore:
    idx: int
    sharpe: float
    vol: float
    drawdown: float
    var: float
    cvar: float


def score_scenarios(weights: np.ndarray, scenarios: np.ndarray) -> List[ScenarioScore]:
    results: List[ScenarioScore] = []
    for idx, scenario in enumerate(scenarios):
        pr = portfolio_returns(weights, scenario)
        results.append(
            ScenarioScore(
                idx=idx,
                sharpe=sharpe_ratio(pr),
                vol=volatility(pr),
                drawdown=max_drawdown(pr),
                var=value_at_risk(pr),
                cvar=conditional_value_at_risk(pr),
            )
        )
    return results


def classify_scenarios(scores: List[ScenarioScore], top_n: int = 3) -> dict[str, List[ScenarioScore]]:
    # Bull: highest Sharpe
    bull = sorted(scores, key=lambda s: s.sharpe, reverse=True)[:top_n]
    # Bear: lowest Sharpe
    bear = sorted(scores, key=lambda s: s.sharpe)[:top_n]
    # Stress: lowest CVaR (most negative tail)
    stress = sorted(scores, key=lambda s: s.cvar)[:top_n]

    return {"bull": bull, "bear": bear, "stress": stress}
