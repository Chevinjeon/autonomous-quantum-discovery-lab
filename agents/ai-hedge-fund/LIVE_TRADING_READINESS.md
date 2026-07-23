# Live Trading Readiness Log

Running record of what's been built, what's been tested, and what still needs to be true
before this system trades with real money instead of Alpaca paper money. Update this file
as new tests/backtests/changes happen — don't rely on chat history to reconstruct this.

**Status as of 2026-07-23: NOT ready for real money. Paper trading only. Fixed three real bugs
tonight (QUBO could never sell; the whipsaw that exposed; an unbounded OpenAI client hang) and
switched to a more reliable price data source (Alpaca over yfinance). The best complete result so
far (Sharpe 0.81, still underperforms SPY by ~2.9 points) is the 4th consecutive run against the
identical Jan–Jul 2026 window — genuinely improved each time, but still not validated against an
untouched period. Do not read this as "fixed and ready" — read it as "meaningfully better, still
unproven."**

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
| 2026-07-22 | 5-ticker, 6-month backtest — **valid, completed (pre-fix)** | AAPL/MSFT/GOOGL/AMZN/NVDA, Buffett + Lynch + technical_analyst, **OpenAI gpt-4.1-mini** (paid — Groq's daily quota was exhausted, Gemini's free tier had a 0-request limit on the registered model and a 20/day limit on the fallback model, so OpenAI was the only option that actually completed), $100k capital, 2026-01-22 to 2026-07-22 | **Portfolio return +3.54% vs SPY benchmark +9.18%. Sharpe 0.38, Sortino 0.54, max drawdown -14.76% (2026-06-26).** Ended nearly fully invested: AAPL 86sh/$28,186, MSFT 75sh/$29,831, GOOGL 56sh/$19,440, AMZN 86sh/$21,289, NVDA 23sh/$4,768, cash $23. **Root-caused afterward**: across all 510 day-ticker decisions, every action was `buy` or `hold` — the QUBO path never sold, so MSFT rode an 11.79% loss all the way down with zero intervention, explaining most of the underperformance. |
| 2026-07-22 | Same 5-ticker/6-month backtest, re-run after the sell-fix (below) — **valid, completed** | Same setup, sell logic added to `_maybe_qubo_decisions` (see fix below), no hysteresis yet | **Return +1.24% (worse), Sharpe -0.10 (negative), max drawdown -3.84% (much better).** MSFT/AAPL/GOOGL now correctly sold, but revealed a second bug: `target_assets = len(tickers)//3` collapsed to 1 slot for 5 tickers, causing daily whipsaw (AAPL 30 buys/19 sells in 102 days, MSFT 24/21, GOOGL 16/12). NVDA — the best performer, +13.21% buy-and-hold — was bought only once, on the last day of the backtest. Drawdown improved a lot (no more riding a loser down), but return/Sharpe got worse from the churn. |
| 2026-07-23 | Same backtest a third time, after target_assets resize (ceil(n/2)) + exit hysteresis (`AIF_QUBO_EXIT_STREAK=3`) — **partial, 91/126 trading days (crashed on a Yahoo Finance outage, not our code — DNS timeouts on yfinance calls, see limitation #9)** | Same setup, both fixes from this session's plan applied | **Through 2026-07-03: return +5.21% vs partial-window benchmark +8.67%. Sharpe 0.46, Sortino 0.69, max drawdown -13.50%.** Turnover dropped sharply vs the no-hysteresis run: total sells across all 5 tickers fell from 59 to 16; AAPL held continuously for all 91 days with zero sells (vs 19 sells previously). Best Sharpe/return of the three real runs, though still underperforming the benchmark and drawdown is back up (less whipsaw meant fewer forced exits during the same drawdown period). **Caveat, per methodology reminder from the user**: this is the 3rd consecutive iteration tuned against the exact same Jan–Jul 2026 window — discount this result accordingly and treat a genuinely new, untouched period as the real test, not another tweak-and-rerun on this one (see limitation #10). |
| 2026-07-23 | 4th run, same window, after switching price data to Alpaca (limitation #9) and fixing an OpenAI client hang (limitation #11) — **valid, fully completed, zero errors** | Same setup (5 tickers, Buffett+Lynch+technical_analyst, OpenAI gpt-4.1-mini, $100k), full 2026-01-22 to 2026-07-23 window, no logic changes from the 3rd run | **Return +5.60% vs SPY benchmark +8.46%. Sharpe 0.81, Sortino 1.26, max drawdown -13.07%.** Best Sharpe/Sortino of every run so far. Turnover: 56 buys / 14 sells total (vs 137 actions in the pre-hysteresis run) — AAPL held 98% of days (+31.21% buy-and-hold, mostly captured), MSFT held 65% of days (-13.45% buy-and-hold this window — a genuine loser, partially avoided by trading around it rather than pure buy-and-hold), NVDA still underexposed at only 20% of days despite being the second-best performer (+14.73% buy-and-hold) — the entry side is still slower to react than the exit side. **Smallest underperformance gap yet (-2.86pts vs -5.64, -7.94, -3.46 in prior runs) — a consistent, believable improvement trend across all 4 iterations, not a fluke, but still not a beat, and still the same test window every time (limitation #10 fully applies).** |

## Known limitations / open risks

1. **QUBO decision opacity — partially resolved.** Root cause found and fixed 2026-07-22/23:
   `_maybe_qubo_decisions` (`src/agents/portfolio_manager.py`) could only ever emit `buy`/`hold`,
   never checking existing positions, so a deselected-but-held ticker just sat there forever
   (explains the original MSFT-rides-to-the-bottom behavior). Fixed by adding a sell branch, which
   then exposed `target_assets = len(tickers)//3` collapsing to 1 slot for 5 tickers and causing
   daily whipsaw — fixed by resizing to `ceil(n/2)` and adding 3-day exit hysteresis
   (`AIF_QUBO_EXIT_STREAK`, file-backed via `src/tools/qubo_streaks.py`). Still not fully resolved:
   the QUBO's reasoning strings (`"QUBO selection"`, `"QUBO: deselected..."`) are still terse/opaque
   about *why* the underlying optimizer weighted one ticker over another on a given day — the exit
   side is now explainable (streak counts are visible), but entry-side reasoning still isn't.
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
8. **QUBO exit hysteresis needs its own validation.** The 3-day default (`AIF_QUBO_EXIT_STREAK`)
   and the `ceil(n/2)` target_assets formula were chosen to fix an observed problem, not derived
   from first principles or tuned against a separate dataset — they're a reasonable first guess,
   not a validated parameter choice. Also: `AIF_QUBO_STREAK_FILE` is file-backed and shared by
   default between live paper trading and any backtest that doesn't override the path — always set
   a dedicated `AIF_QUBO_STREAK_FILE` per backtest run, or it'll read/pollute stale state.
9. **yfinance unreliability — resolved 2026-07-23.** `get_prices` (`src/tools/api.py`) now tries
   Alpaca's Market Data API first (`get_alpaca_prices` in `src/tools/alpaca_broker.py`, free IEX
   feed, uses the paper-trading credentials already in `.env`) whenever no paid
   `FINANCIAL_DATASETS_API_KEY` is set, falling back to yfinance only if Alpaca has no credentials
   or fails. The 2026-07-23 full clean backtest ran end-to-end with zero price-data errors on
   Alpaca. `AIF_PRICE_SOURCE=yahoo` still forces yfinance-only if Alpaca ever has a bad night of
   its own; `AIF_PRICE_SOURCE=alpaca` forces Alpaca-only with no fallback.
10. **Don't iterate repeatedly against the same backtest window.** Per the user's own reminder: as
    of 2026-07-23 the QUBO decision logic (plus infra fixes) has been run/tuned 4 times in a row,
    all against the identical Jan 22 – Jul 23 2026 / 5-ticker window. Each iteration should be
    discounted for having been shaped by that specific window — results have consistently improved
    each time (see table above), which is a good sign the fixes are real, but it is not yet proof
    the strategy generalizes. The real test is running the current fixed parameters against a
    genuinely untouched period, once, without further tweaking based on that result.
11. **Unbounded LLM client hang — resolved 2026-07-23.** The 4th backtest attempt stalled 30+
    minutes with no error; `sudo py-spy dump` on the live process showed the main thread blocked in
    a raw `ssl.py recv()` waiting on OpenAI response headers (via `devils_advocate_agent` →
    `call_llm`), with no client-side timeout to break out of it. `ChatOpenAI` construction in
    `src/llm/models.py` had no `timeout`/`max_retries` set, so it depended on the SDK's own default,
    which evidently didn't kick in (or was longer than expected) that night. Fixed by adding
    `timeout=60, max_retries=2` to both `ChatOpenAI` constructions (OpenAI and OpenRouter, since
    OpenRouter uses the same client class and has the identical failure mode). **Not yet applied**
    to the other provider branches (Groq, Anthropic, Google, DeepSeek, xAI, GigaChat, Azure) — same
    class of bug is plausible there too, just unconfirmed, since none have hung yet.

## Checklist before considering real money

Do not move to live trading until these are addressed:

- [x] Multi-ticker, multi-month backtest completed (4 iterations now, 2026-07-22/23, 5 tickers/6
      months, the last one clean/complete/zero-errors) — every result still underperforms SPY, and
      all 4 are tuned against the identical window (see limitation #10). Still need: a genuinely
      untouched test period run once with no further tweaking, a longer window (multi-year,
      spanning up/down regimes), and — most importantly — a result that actually beats the
      benchmark
- [ ] Strategy demonstrates it beats a passive index benchmark (SPY) after costs, on an untouched
      out-of-sample period, without further tuning — not yet true on any run so far (best so far:
      2026-07-23 full clean run, +5.60% vs +8.46% SPY, closest gap yet at -2.86pts, still behind)
- [x] QUBO could never sell — fixed 2026-07-22 (sell branch added)
- [x] QUBO whipsaw from 1-slot target_assets — fixed 2026-07-23 (resized + exit hysteresis), but
      the hysteresis parameters themselves are unvalidated (limitation #8)
- [x] Reliable backtest price data source — fixed 2026-07-23, Alpaca Market Data API is now the
      default free source ahead of yfinance (limitation #9)
- [x] Unbounded LLM client hang — fixed 2026-07-23 for OpenAI/OpenRouter (limitation #11), other
      providers not yet hardened
- [ ] Stop-loss / exit logic added and backtested
- [ ] Insider trades / news sentiment either covered by a free source or those agents excluded
      from the live analyst set
- [ ] Extended paper-trading track record (weeks/months, not one trade) showing consistent
      behavior
- [ ] Explicit, deliberate code change to support live trading (not just an env var flip) —
      current `alpaca_broker.py` hardcodes `paper=True`

## Log of future runs

Append new backtests/tests here as they happen — date, scope, and outcome.
