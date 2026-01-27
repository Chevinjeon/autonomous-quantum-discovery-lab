from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PortfolioSnapshot:
    positions: Dict[str, float]
    cash: float


class PortfolioSystemClient:
    """
    Integration point for portfolio systems (Murex/Aladdin/OMS).
    Implement these methods against internal APIs.
    """

    def fetch_positions(self) -> PortfolioSnapshot:  # pragma: no cover - interface
        raise NotImplementedError

    def propose_rebalance(self, weights: Dict[str, float]) -> None:  # pragma: no cover - interface
        raise NotImplementedError
