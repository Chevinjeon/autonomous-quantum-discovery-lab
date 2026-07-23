"""Standalone momentum/trend-following backtest - no LLM calls, no QUBO.

Signal construction follows Rohrbach et al., "Momentum and Trend Following
Trading Strategies for Currencies Revisited": EMA(short) - EMA(long),
normalized by rolling realized volatility, clipped to [-1, 1]. Long-only
here (unlike the paper's FX long/short setup) since this targets equities.

Reuses the existing backtesting scaffolding (Portfolio/TradeExecutor/
PerformanceMetricsCalculator/BenchmarkCalculator) rather than reinventing
execution or metrics code - the only new logic is the signal itself and
the day-loop that turns it into target positions.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.backtesting.benchmarks import BenchmarkCalculator
from src.backtesting.metrics import PerformanceMetricsCalculator
from src.backtesting.portfolio import Portfolio
from src.backtesting.trader import TradeExecutor
from src.backtesting.valuation import calculate_portfolio_value
from src.data.models import Price
from src.tools.alpaca_broker import get_alpaca_prices


def _prices_to_close_series(prices: list[Price]) -> pd.Series:
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df = df.set_index("Date").sort_index()
    return df["close"]


def compute_momentum_signal(close: pd.Series, short_window: int, long_window: int, vol_window: int = 63) -> pd.Series:
    """EMA(short) - EMA(long) as a fraction of price, normalized by rolling
    realized volatility of daily returns, clipped to [-1, 1]. Dividing by
    price first (not just by volatility) keeps the signal scale-invariant
    across tickers at very different price levels.
    """
    ema_short = close.ewm(span=short_window, adjust=False).mean()
    ema_long = close.ewm(span=long_window, adjust=False).mean()
    relative_gap = (ema_short - ema_long) / close

    daily_returns = close.pct_change()
    rolling_vol = daily_returns.rolling(window=vol_window).std()

    normalized = relative_gap / rolling_vol.replace(0, np.nan)
    return normalized.clip(-1, 1)


def run_momentum_backtest(
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    short_window: int,
    long_window: int,
    vol_window: int = 63,
) -> dict:
    # Warm up the long EMA + vol window with history before start_date so the
    # signal is already stable on day 1 of the actual test range.
    warmup_days = max(long_window, vol_window) * 3
    fetch_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=warmup_days)).strftime("%Y-%m-%d")

    closes: dict[str, pd.Series] = {}
    signals: dict[str, pd.Series] = {}
    for ticker in tickers:
        prices = get_alpaca_prices(ticker, fetch_start, end_date)
        if not prices:
            continue
        close = _prices_to_close_series(prices)
        closes[ticker] = close
        signals[ticker] = compute_momentum_signal(close, short_window, long_window, vol_window)

    portfolio = Portfolio(tickers=tickers, initial_cash=initial_capital, margin_requirement=0.0)
    executor = TradeExecutor()
    perf_calc = PerformanceMetricsCalculator()
    benchmark = BenchmarkCalculator()
    ticker_budget = initial_capital / len(tickers)

    trading_dates = pd.bdate_range(start_date, end_date)
    portfolio_values = []
    for current_date in trading_dates:
        current_prices = {}
        missing = False
        for ticker in tickers:
            close = closes.get(ticker)
            if close is None or current_date not in close.index:
                missing = True
                break
            current_prices[ticker] = float(close.loc[current_date])
        if missing:
            continue

        for ticker in tickers:
            signal_series = signals[ticker]
            if current_date not in signal_series.index:
                continue
            signal = signal_series.loc[current_date]
            if pd.isna(signal):
                continue

            price = current_prices[ticker]
            target_shares = int(max(signal, 0.0) * ticker_budget / price) if price > 0 else 0
            current_shares = portfolio.get_positions()[ticker]["long"]
            delta = target_shares - current_shares
            if delta > 0:
                executor.execute_trade(ticker, "buy", delta, price, portfolio)
            elif delta < 0:
                executor.execute_trade(ticker, "sell", -delta, price, portfolio)

        total_value = calculate_portfolio_value(portfolio, current_prices)
        portfolio_values.append({"Date": current_date, "Portfolio Value": total_value})

    metrics = perf_calc.compute_metrics(portfolio_values)
    final_value = portfolio_values[-1]["Portfolio Value"] if portfolio_values else initial_capital
    portfolio_return_pct = (final_value / initial_capital - 1.0) * 100.0

    benchmark_returns = [benchmark.get_return_pct(t, start_date, end_date) for t in tickers]
    spy_return_pct = benchmark.get_return_pct("SPY", start_date, end_date)

    return {
        "short_window": short_window,
        "long_window": long_window,
        "start_date": start_date,
        "end_date": end_date,
        "final_value": final_value,
        "portfolio_return_pct": portfolio_return_pct,
        "spy_return_pct": spy_return_pct,
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "sortino_ratio": metrics.get("sortino_ratio"),
        "max_drawdown": metrics.get("max_drawdown"),
        "max_drawdown_date": metrics.get("max_drawdown_date"),
        "num_days": len(portfolio_values),
    }
