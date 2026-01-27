from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Dict


@dataclass(frozen=True)
class MarketTick:
    timestamp: float
    prices: Dict[str, float]


class MarketFeed:
    async def stream(self) -> AsyncIterator[MarketTick]:  # pragma: no cover - interface
        raise NotImplementedError


class MockMarketFeed(MarketFeed):
    """
    Simple mock feed for local testing. Replace with real feed integration.
    """

    def __init__(self, symbols: list[str], interval: float = 0.5) -> None:
        self.symbols = symbols
        self.interval = interval
        self._prices = {s: 100.0 for s in symbols}

    async def stream(self) -> AsyncIterator[MarketTick]:
        while True:
            for sym in self.symbols:
                self._prices[sym] *= 1.0 + (0.001 * (0.5 - 0.25))
            yield MarketTick(timestamp=asyncio.get_event_loop().time(), prices=dict(self._prices))
            await asyncio.sleep(self.interval)
