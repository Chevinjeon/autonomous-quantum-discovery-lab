import json
from typing_extensions import Literal

import numpy as np
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_company_news, get_financial_metrics, get_prices
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class DexterSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Concise, evidence-based reasoning")


def _summarize_prices(prices: list) -> dict:
    if not prices:
        return {}

    closes = [p.close for p in prices if p.close is not None]
    if len(closes) < 2:
        return {}

    start = closes[0]
    end = closes[-1]
    pct_return = (end / start - 1.0) if start else 0.0

    daily_returns = np.diff(closes) / closes[:-1]
    volatility = float(np.std(daily_returns)) if len(daily_returns) > 1 else 0.0

    return {
        "start_close": round(start, 2),
        "end_close": round(end, 2),
        "period_return_pct": round(pct_return * 100, 2),
        "daily_volatility": round(volatility * 100, 2),
    }


def _summarize_news(news_items: list, max_titles: int = 3) -> dict:
    if not news_items:
        return {}

    sentiments = [n.sentiment for n in news_items if n.sentiment]
    sentiment_counts = {
        "positive": sentiments.count("positive"),
        "negative": sentiments.count("negative"),
        "neutral": sentiments.count("neutral"),
    }

    titles = [n.title for n in news_items[:max_titles]]
    return {
        "sentiment_counts": sentiment_counts,
        "recent_titles": titles,
    }


def _summarize_metrics(metrics: list) -> dict:
    if not metrics:
        return {}

    latest = metrics[0]
    return {
        "market_cap": latest.market_cap,
        "revenue_growth": latest.revenue_growth,
        "free_cash_flow_growth": latest.free_cash_flow_growth,
        "gross_margin": latest.gross_margin,
        "operating_margin": latest.operating_margin,
        "net_margin": latest.net_margin,
        "return_on_equity": latest.return_on_equity,
        "current_ratio": latest.current_ratio,
        "debt_to_equity": latest.debt_to_equity,
        "price_to_earnings": latest.price_to_earnings_ratio,
        "price_to_book": latest.price_to_book_ratio,
    }


def dexter_agent(state: AgentState, agent_id: str = "dexter_agent"):
    """Dexter-style autonomous research analyst with compact, evidence-based output."""
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    dexter_analysis: dict[str, dict] = {}

    prompt = ChatPromptTemplate.from_template(
        """
You are Dexter, an autonomous financial research analyst.
Use the provided data to produce a single trading signal.

Ticker: {ticker}
Price Summary: {price_summary}
Financial Metrics Summary: {metrics_summary}
News Summary: {news_summary}

Rules:
- Return a signal of bullish, bearish, or neutral.
- Confidence is 0-100.
- Reasoning must be concise (2-4 sentences) and cite the strongest evidence.
"""
    )

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Gathering market data")
        prices = get_prices(ticker, start_date, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=6, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news_items = get_company_news(ticker, end_date, limit=20, api_key=api_key)

        price_summary = _summarize_prices(prices)
        metrics_summary = _summarize_metrics(metrics)
        news_summary = _summarize_news(news_items)

        progress.update_status(agent_id, ticker, "Synthesizing Dexter analysis")
        dexter_output = call_llm(
            prompt.format(
                ticker=ticker,
                price_summary=json.dumps(price_summary, indent=2),
                metrics_summary=json.dumps(metrics_summary, indent=2),
                news_summary=json.dumps(news_summary, indent=2),
            ),
            DexterSignal,
            agent_name=agent_id,
            state=state,
        )

        dexter_analysis[ticker] = {
            "signal": dexter_output.signal,
            "confidence": dexter_output.confidence,
            "reasoning": dexter_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=dexter_output.reasoning)

    message = HumanMessage(content=json.dumps(dexter_analysis), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(dexter_analysis, "Dexter Analyst")

    state["data"]["analyst_signals"][agent_id] = dexter_analysis
    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": data}
