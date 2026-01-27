from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import json
import urllib.request


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


class HttpSolver(LowLatencySolver):
    """
    Calls the deployed solver service (ALB) for weights.
    """

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")

    def solve(self, request: AllocationRequest) -> AllocationResult:
        payload = json.dumps(
            {"prices": request.prices, "max_assets": request.max_assets}
        ).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.endpoint}/solve",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return AllocationResult(weights=data.get("weights", {}), latency_ms=50.0)
