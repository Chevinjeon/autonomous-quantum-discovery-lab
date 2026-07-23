# Live Trading Readiness Log

Running record of what's been built, what's been tested, and what still needs to be true
before this system trades with real money instead of Alpaca paper money. Update this file
as new tests/backtests/changes happen — don't rely on chat history to reconstruct this.

**Status as of 2026-07-22: NOT ready for real money. Paper trading only. The one statistically
meaningful backtest run so far (5 tickers, 6 months) underperformed a passive S&P 500 index by
>5.5 points — no demonstrated edge yet.**

## What's been built

- **Alpaca paper execution** (`src/tools/alpaca_broker.py`, `src/main.py --execute` flag) —
  submits real orders to an Alpaca **paper** account based on the agents' decisions. No live
  trading code path exists anywhere in the codebase — flipping to live money would require a
  deliberate new change, not a config flag.
- **Free SEC EDGAR fundamentals** (`src/tools/sec_edgar.py`) — replaces the paid
  financialdatasets.ai API for `get_financial_metrics`/`search_line_items`/`get_market_cap`,
  computing ratios from raw SEC XBRL filings. Automatic fallback when no
  `FINANCIAL_DATASETS_API_KEY` is set. Verified against Apple's actual filed financials
  (revenue, net income, R&D matched to the dollar for FY2023/FY2024).
- **Not covered by the free data path**: insider trades (`get_insider_trades`) and company
  news/sentiment (`get_company_news`) — SEC EDGAR has no free general-news equivalent. Agents
  that lean on these (`sentiment.py`, `news_sentiment.py`, parts of `phil_fisher.py`,
  `stanley_druckenmiller.py`, `growth_agent.py`) remain data-limited.

## What's been tested so far

| Date | Test | Setup | Result |
|---|---|---|---|
| 2026-07-22 | First live paper trade | AAPL, all analysts, Groq llama-3.3-70b-versatile, QUBO decision path | Bought 57 shares @ ~$324.29. Filled correctly. **Flagged concern**: analyst consensus was 0 bullish / 2 bearish / 2 neutral, yet QUBO decided BUY at 85% confidence with reasoning just `"QUBO selection"` — opaque, didn't obviously follow its own inputs. Not explained, not resolved. |
| 2026-07-22 | Second live paper trade | AAPL, `technical_analyst` only (fully free-data-compatible) | HOLD, reasoning `"QUBO selected but no budget"` — no error data this time, clean run. |
| 2026-07-22 | 1-month backtest | AAPL only, Buffett + Lynch + technical_analyst, Groq, $100k capital, 2026-06-23 to 2026-07-22 | +1.97% return vs SPY +0.52% benchmark. Sharpe 3.15, Sortino 3.69, max drawdown -1.40%. **Actual behavior**: bought once on day 1-2 (64 shares total), held every day after — a single buy-and-hold decision, not a repeatedly-tested strategy. |
| 2026-07-22 | 5-ticker, 6-month backtest — **aborted, invalid** | AAPL/MSFT/GOOGL/AMZN/NVDA, same analysts/model, 2026-01-22 to 2026-07-22 | Killed partway through. Hit Groq's free-tier **daily** token cap (100,000 tokens/day — a hard 24h ceiling, not a per-minute rate limit) after burning through the early days of the backtest. Every LLM call after that point failed with a 429 and would have kept failing for the rest of the day, silently degrading the rest of the run into fallback/no-signal decisions. Stopped before any results were produced. **Lesson: Groq's free tier (100k tokens/day) cannot sustain a multi-ticker, multi-month backtest in one sitting** — each analyst call is per-ticker-per-day, so 5 tickers × 3 analysts × ~126 trading days exhausts the daily budget quickly. Needs either a different/cheaper provider for larger backtests, running across multiple days to let the quota reset, or a much smaller scope. |
| 2026-07-22 | 5-ticker, 6-month backtest — **valid, completed** | AAPL/MSFT/GOOGL/AMZN/NVDA, Buffett + Lynch + technical_analyst, **OpenAI gpt-4.1-mini** (paid — Groq's daily quota was exhausted, Gemini's free tier had a 0-request limit on the registered model and a 20/day limit on the fallback model, so OpenAI was the only option that actually completed), $100k capital, 2026-01-22 to 2026-07-22 | **Portfolio return +3.54% vs SPY benchmark +9.18%. Sharpe 0.38, Sortino 0.54, max drawdown -14.76% (2026-06-26).** Ended nearly fully invested: AAPL 86sh/$28,186, MSFT 75sh/$29,831, GOOGL 56sh/$19,440, AMZN 86sh/$21,289, NVDA 23sh/$4,768, cash $23. **This is the most statistically meaningful result so far, and it's a red flag, not a green light: the strategy underperformed a passive S&P 500 buy-and-hold by >5.5 points, with a much larger drawdown and a mediocre Sharpe ratio.** It directly contradicts the earlier 1-month/1-ticker test's Sharpe of 3.15 — confirming that result was small-sample noise, exactly as flagged in limitation #2 below. **As currently configured, this system has not demonstrated it can beat simply buying an index fund.** |

## Known limitations / open risks

1. **QUBO decision opacity** — the portfolio manager's QUBO path (`AIF_USE_QUBO`) can produce
   decisions that don't obviously follow the analyst consensus feeding into it, and its only
   explanation is `"QUBO selection"`. This has not been investigated or resolved. Before trusting
   it with more capital, either understand why it overrode a bearish-leaning consensus, or switch
   to the LLM decision path for transparency.
2. **Statistical significance of backtests** — a single ticker over one month with one trade is
   not evidence of edge. High Sharpe ratios over tiny samples happen by chance easily. Needs a
   longer window, multiple tickers, and multiple market regimes (up and down markets) before the
   numbers mean anything.
3. **No stop-loss / exit logic** — `risk_manager.py` sizes positions going in (volatility/
   correlation-based limits) but nothing watches a filled position and cuts losses. Not built yet.
4. **SEC EDGAR fundamentals are approximations** — `"ttm"` period sums trailing 4 quarters
   (falls back to latest annual if fewer than 4 quarters available); effective tax rate for ROIC
   falls back to a flat 21% assumption when reported tax data is unavailable; some fields will
   legitimately be `None` for tickers with inconsistent XBRL tagging. See comments in
   `src/tools/sec_edgar.py` for specifics.
5. **LLM non-determinism** — the same backtest run twice on the same data may not produce
   identical decisions. Any conclusion drawn from a single run should be treated cautiously until
   repeated.
6. **No insider trades / news sentiment** — agents relying on these are running data-blind on
   those specific signals (see above).
7. **Groq free tier caps multi-ticker/multi-month backtests at ~100,000 tokens/day (hard daily
   ceiling, not per-minute)** — each analyst call is one LLM call per ticker per day, so anything
   beyond roughly 1 ticker/1 month, or a couple tickers over a few weeks, burns the whole day's
   quota partway through and silently degrades into failed/fallback calls for the rest of the run
   if not stopped. Larger backtests need either a paid tier, a different provider, or splitting
   the date range across multiple days.

## Checklist before considering real money

Do not move to live trading until these are addressed:

- [x] Multi-ticker, multi-month backtest completed (2026-07-22, 5 tickers/6 months) — but the
      result is negative (underperformed SPY) and single-run, so this is not yet a pass. Still
      need: a longer window (multi-year, spanning up/down regimes), repeated runs to confirm the
      result isn't itself noise, and — most importantly — a result that actually beats the
      benchmark before this box is really checked
- [ ] Strategy demonstrates it beats a passive index benchmark (SPY) after costs, across multiple
      independent backtest runs — not yet true (2026-07-22 run: +3.54% vs +9.18% SPY)
- [ ] QUBO opacity resolved or replaced with an explainable decision path
- [ ] Stop-loss / exit logic added and backtested
- [ ] Insider trades / news sentiment either covered by a free source or those agents excluded
      from the live analyst set
- [ ] Extended paper-trading track record (weeks/months, not one trade) showing consistent
      behavior
- [ ] Explicit, deliberate code change to support live trading (not just an env var flip) —
      current `alpaca_broker.py` hardcodes `paper=True`

## Log of future runs

Append new backtests/tests here as they happen — date, scope, and outcome.
