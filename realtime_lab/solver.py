from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class AllocationRequest:
    prices: Dict[str, float]
    max_assets: int
    risk_aversion: float


@dataclass(frozen=True)
class AllocationResult:
    weights: Dict[str, float]
    latency_ms: float


class LowLatencySolver:
    def solve(self, request: AllocationRequest) -> AllocationResult:  # pragma: no cover - interface
        raise NotImplementedError


class GreedySolver(LowLatencySolver):
    """
    Placeholder low-latency solver.
    Picks lowest-priced assets equally (dummy strategy).
    """

    def solve(self, request: AllocationRequest) -> AllocationResult:
        sorted_assets: List[str] = sorted(request.prices, key=request.prices.get)
        chosen = sorted_assets[: max(request.max_assets, 1)]
        weight = 1.0 / len(chosen)
        return AllocationResult(weights={a: weight for a in chosen}, latency_ms=1.0)
