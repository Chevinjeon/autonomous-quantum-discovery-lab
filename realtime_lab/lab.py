from __future__ import annotations

import argparse
import asyncio

from .integration import PortfolioSystemClient
from .market_feed import MockMarketFeed
from .solver import AllocationRequest, GreedySolver


class MockPortfolioClient(PortfolioSystemClient):
    def fetch_positions(self):
        return {"cash": 1_000_000.0, "positions": {}}

    def propose_rebalance(self, weights):
        print(f"Proposed weights: {weights}")


async def run_loop(symbols: list[str], max_assets: int, risk_aversion: float, iterations: int) -> None:
    feed = MockMarketFeed(symbols=symbols)
    solver = GreedySolver()
    client = MockPortfolioClient()

    count = 0
    async for tick in feed.stream():
        req = AllocationRequest(
            prices=tick.prices,
            max_assets=max_assets,
            risk_aversion=risk_aversion,
        )
        result = solver.solve(req)
        client.propose_rebalance(result.weights)
        count += 1
        if count >= iterations:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time optimization loop (scaffold).")
    parser.add_argument("--symbols", default="A,B,C,D", help="Comma-separated symbols.")
    parser.add_argument("--max-assets", type=int, default=3, help="Max assets to hold.")
    parser.add_argument("--risk-aversion", type=float, default=1.0, help="Risk aversion.")
    parser.add_argument("--iterations", type=int, default=5, help="Number of ticks to process.")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    asyncio.run(
        run_loop(
            symbols=symbols,
            max_assets=args.max_assets,
            risk_aversion=args.risk_aversion,
            iterations=args.iterations,
        )
    )


if __name__ == "__main__":
    main()
