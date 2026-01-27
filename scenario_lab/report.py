from __future__ import annotations

import csv
from typing import List

from .scorer import ScenarioScore


def export_scores_csv(path: str, scores: List[ScenarioScore]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "sharpe", "volatility", "drawdown", "var", "cvar"])
        for s in scores:
            writer.writerow(
                [
                    s.idx,
                    f"{s.sharpe:.6f}",
                    f"{s.vol:.6f}",
                    f"{s.drawdown:.6f}",
                    f"{s.var:.6f}",
                    f"{s.cvar:.6f}",
                ]
            )


def export_cases_csv(path: str, cases: dict[str, List[ScenarioScore]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "scenario", "sharpe", "volatility", "drawdown", "var", "cvar"])
        for label, items in cases.items():
            for s in items:
                writer.writerow(
                    [
                        label,
                        s.idx,
                        f"{s.sharpe:.6f}",
                        f"{s.vol:.6f}",
                        f"{s.drawdown:.6f}",
                        f"{s.var:.6f}",
                        f"{s.cvar:.6f}",
                    ]
                )
