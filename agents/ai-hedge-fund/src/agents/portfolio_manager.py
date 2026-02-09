import json
import os
import time
import numpy as np
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.tools.synqubi_qubo import solve_portfolio_qubo


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager"):
    """Makes final trading decisions and generates orders for multiple tickers"""

    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    risk_by_ticker = {}
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Processing analyst signals")

        # Find the corresponding risk manager for this portfolio manager
        if agent_id.startswith("portfolio_manager_"):
            suffix = agent_id.split('_')[-1]
            risk_manager_id = f"risk_management_agent_{suffix}"
        else:
            risk_manager_id = "risk_management_agent"  # Fallback for CLI

        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0.0)
        current_prices[ticker] = float(risk_data.get("current_price", 0.0))
        risk_by_ticker[ticker] = risk_data

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] // current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Compress analyst signals to {sig, conf}
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if not agent.startswith("risk_management_agent") and ticker in signals:
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                if sig is not None and conf is not None:
                    ticker_signals[agent] = {"sig": sig, "conf": conf}
        signals_by_ticker[ticker] = ticker_signals

    state["data"]["current_prices"] = current_prices

    progress.update_status(agent_id, None, "Generating trading decisions")

    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        risk_by_ticker=risk_by_ticker,
        agent_id=agent_id,
        state=state,
    )
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()},
                             "Portfolio Manager")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def compute_allowed_actions(
        tickers: list[str],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
) -> dict[str, dict[str, int]]:
    """Compute allowed actions and max quantities for each ticker deterministically."""
    allowed = {}
    cash = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {}) or {}
    margin_requirement = float(portfolio.get("margin_requirement", 0.5))
    margin_used = float(portfolio.get("margin_used", 0.0))
    equity = float(portfolio.get("equity", cash))

    for ticker in tickers:
        price = float(current_prices.get(ticker, 0.0))
        pos = positions.get(
            ticker,
            {"long": 0, "long_cost_basis": 0.0, "short": 0, "short_cost_basis": 0.0},
        )
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        max_qty = int(max_shares.get(ticker, 0) or 0)

        # Start with zeros
        actions = {"buy": 0, "sell": 0, "short": 0, "cover": 0, "hold": 0}

        # Long side
        if long_shares > 0:
            actions["sell"] = long_shares
        if cash > 0 and price > 0:
            max_buy_cash = int(cash // price)
            max_buy = max(0, min(max_qty, max_buy_cash))
            if max_buy > 0:
                actions["buy"] = max_buy

        # Short side
        if short_shares > 0:
            actions["cover"] = short_shares
        if price > 0 and max_qty > 0:
            if margin_requirement <= 0.0:
                # If margin requirement is zero or unset, only cap by max_qty
                max_short = max_qty
            else:
                available_margin = max(0.0, (equity / margin_requirement) - margin_used)
                max_short_margin = int(available_margin // price)
                max_short = max(0, min(max_qty, max_short_margin))
            if max_short > 0:
                actions["short"] = max_short

        # Hold always valid
        actions["hold"] = 0

        # Prune zero-capacity actions to reduce tokens, keep hold
        pruned = {"hold": 0}
        for k, v in actions.items():
            if k != "hold" and v > 0:
                pruned[k] = v

        allowed[ticker] = pruned

    return allowed


def _compact_signals(signals_by_ticker: dict[str, dict]) -> dict[str, dict]:
    """Keep only {agent: {sig, conf}} and drop empty agents."""
    out = {}
    for t, agents in signals_by_ticker.items():
        if not agents:
            out[t] = {}
            continue
        compact = {}
        for agent, payload in agents.items():
            sig = payload.get("sig") or payload.get("signal")
            conf = payload.get("conf") if "conf" in payload else payload.get("confidence")
            if sig is not None and conf is not None:
                compact[agent] = {"sig": sig, "conf": conf}
        out[t] = compact
    return out


def _signal_to_score(signal: str | None) -> float:
    if signal is None:
        return 0.0
    normalized = str(signal).strip().lower()
    mapping = {
        "strong_buy": 1.5,
        "buy": 1.0,
        "overweight": 0.75,
        "hold": 0.0,
        "neutral": 0.0,
        "underweight": -0.75,
        "sell": -1.0,
        "strong_sell": -1.5,
        "short": -1.25,
        "cover": 0.25,
    }
    return mapping.get(normalized, 0.0)


def _aggregate_expected_returns(signals_by_ticker: dict[str, dict]) -> dict[str, float]:
    expected = {}
    for ticker, agents in signals_by_ticker.items():
        if not agents:
            expected[ticker] = 0.0
            continue
        total = 0.0
        weight = 0.0
        for payload in agents.values():
            score = _signal_to_score(payload.get("sig") or payload.get("signal"))
            conf = float(payload.get("conf") or payload.get("confidence") or 0.0)
            conf = max(0.0, min(100.0, conf))
            total += score * conf
            weight += conf
        expected[ticker] = total / weight if weight > 0 else 0.0
    return expected


def _build_covariance(tickers: list[str], risk_by_ticker: dict[str, dict]) -> np.ndarray:
    n = len(tickers)
    cov = np.zeros((n, n), dtype=float)
    for i, ticker in enumerate(tickers):
        vol = (
            risk_by_ticker.get(ticker, {})
            .get("volatility_metrics", {})
            .get("annualized_volatility", 0.25)
        )
        variance = float(vol) ** 2
        cov[i, i] = variance
    return cov


def _maybe_qubo_decisions(
    *,
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict[str, float],
    risk_by_ticker: dict[str, dict],
    state: AgentState,
) -> dict[str, "PortfolioDecision"] | None:
    enabled = os.getenv("AIF_USE_QUBO", "1").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        return None

    expected = _aggregate_expected_returns(signals_by_ticker)
    mean = np.array([expected.get(t, 0.0) for t in tickers], dtype=float)
    cov = _build_covariance(tickers, risk_by_ticker)

    target_env = os.getenv("AIF_QUBO_TARGET", "").strip()
    target_assets = int(target_env) if target_env.isdigit() else None
    if target_assets is None:
        target_assets = max(1, min(len(tickers), len(tickers) // 3 or 1))

    risk_aversion = float(os.getenv("AIF_QUBO_RISK_AVERSION", "1.0"))
    penalty = float(os.getenv("AIF_QUBO_PENALTY", "10.0"))

    result = solve_portfolio_qubo(
        mean=mean,
        cov=cov,
        target_assets=target_assets,
        risk_aversion=risk_aversion,
        penalty=penalty,
    )

    selected = {tickers[i] for i in result.selected if i < len(tickers)}
    state["data"]["qubo_selection"] = sorted(selected)

    cash = float(portfolio.get("cash", 0.0))
    per_budget = cash / len(selected) if selected and cash > 0 else 0.0

    decisions: dict[str, PortfolioDecision] = {}
    for ticker in tickers:
        if ticker not in selected:
            decisions[ticker] = PortfolioDecision(
                action="hold",
                quantity=0,
                confidence=80,
                reasoning="QUBO: not selected",
            )
            continue

        price = float(current_prices.get(ticker, 0.0))
        max_qty = int(max_shares.get(ticker, 0) or 0)
        qty = int(per_budget // price) if price > 0 else 0
        qty = max(0, min(max_qty, qty))
        if qty > 0:
            decisions[ticker] = PortfolioDecision(
                action="buy",
                quantity=qty,
                confidence=85,
                reasoning="QUBO selection",
            )
        else:
            decisions[ticker] = PortfolioDecision(
                action="hold",
                quantity=0,
                confidence=60,
                reasoning="QUBO selected but no budget",
            )

    return decisions


def generate_trading_decision(
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
        risk_by_ticker: dict[str, dict],
        agent_id: str,
        state: AgentState,
) -> PortfolioManagerOutput:
    """Get decisions from the LLM with deterministic constraints and a minimal prompt."""

    qubo_decisions = _maybe_qubo_decisions(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        risk_by_ticker=risk_by_ticker,
        state=state,
    )
    if qubo_decisions is not None:
        return PortfolioManagerOutput(decisions=qubo_decisions)

    # Deterministic constraints
    allowed_actions_full = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)

    # Pre-fill pure holds to avoid sending them to the LLM at all
    prefilled_decisions: dict[str, PortfolioDecision] = {}
    tickers_for_llm: list[str] = []
    for t in tickers:
        aa = allowed_actions_full.get(t, {"hold": 0})
        # If only 'hold' key exists, there is no trade possible
        if set(aa.keys()) == {"hold"}:
            prefilled_decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=100.0, reasoning="No valid trade available"
            )
        else:
            tickers_for_llm.append(t)

    if not tickers_for_llm:
        return PortfolioManagerOutput(decisions=prefilled_decisions)

    # Build compact payloads only for tickers sent to LLM
    compact_signals = _compact_signals({t: signals_by_ticker.get(t, {}) for t in tickers_for_llm})
    compact_allowed = {t: allowed_actions_full[t] for t in tickers_for_llm}

    # Minimal prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a portfolio manager.\n"
                "Inputs per ticker: analyst signals and allowed actions with max qty (already validated).\n"
                "Pick one allowed action per ticker and a quantity ≤ the max. "
                "Keep reasoning very concise (max 100 chars). No cash or margin math. Return JSON only."
            ),
            (
                "human",
                "Signals:\n{signals}\n\n"
                "Allowed:\n{allowed}\n\n"
                "Format:\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "TICKER": {{"action":"...","quantity":int,"confidence":int,"reasoning":"..."}}\n'
                "  }}\n"
                "}}"
            ),
        ]
    )

    prompt_data = {
        "signals": json.dumps(compact_signals, separators=(",", ":"), ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, separators=(",", ":"), ensure_ascii=False),
    }
    prompt = template.invoke(prompt_data)

    # Default factory fills remaining tickers as hold if the LLM fails
    def create_default_portfolio_output():
        # start from prefilled
        decisions = dict(prefilled_decisions)
        for t in tickers_for_llm:
            decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=0.0, reasoning="Default decision: hold"
            )
        return PortfolioManagerOutput(decisions=decisions)

    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
    )

    # Merge prefilled holds with LLM results
    merged = dict(prefilled_decisions)
    merged.update(llm_out.decisions)
    return PortfolioManagerOutput(decisions=merged)
