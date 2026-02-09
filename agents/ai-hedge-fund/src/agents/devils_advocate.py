import json
from typing_extensions import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from src.graph.state import AgentState, show_agent_reasoning
from src.utils.llm import call_llm
from src.utils.progress import progress


class DevilsAdvocateTickerAnalysis(BaseModel):
    majority_position: Literal["bullish", "bearish", "neutral"]
    contrarian_signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="How strong the contrarian case is, 0-100")
    bull_case: str = Field(description="Strongest bull argument in 1-2 sentences")
    bear_case: str = Field(description="Strongest bear argument in 1-2 sentences")
    reasoning: str = Field(description="Why the contrarian view has merit")


class DevilsAdvocateOutput(BaseModel):
    analyses: dict[str, DevilsAdvocateTickerAnalysis] = Field(
        description="Per-ticker devil's advocate analysis, keyed by ticker symbol"
    )


SYSTEM_PROMPT = """You are a Devil's Advocate analyst on a hedge fund trading desk.
You receive signals from multiple analyst agents and your job is to stress-test the consensus.

For each ticker:
1. Count the bullish vs bearish vs neutral signals to determine the majority position.
2. Construct the STRONGEST possible counter-argument against the majority.
3. Present both the bull and bear case concisely.
4. Your signal is ALWAYS contrarian to the majority (if majority is bullish, you are bearish; vice versa).
5. If signals are evenly split or majority is neutral, pick the side with weaker representation.

Rules:
- bull_case and bear_case: 1-2 sentences each, cite specific evidence from analyst reasoning.
- reasoning: concise explanation of why the contrarian view deserves consideration.
- confidence: how compelling the contrarian case is (0-100). Higher = stronger counter-argument.
- Be specific. Reference actual data points the analysts mentioned.

Return JSON only."""

HUMAN_PROMPT = """Analyst signals per ticker:
{signals}

Return JSON with this structure:
{{
  "analyses": {{
    "TICKER": {{
      "majority_position": "bullish|bearish|neutral",
      "contrarian_signal": "bullish|bearish|neutral",
      "confidence": 0-100,
      "bull_case": "...",
      "bear_case": "...",
      "reasoning": "..."
    }}
  }}
}}"""


def devils_advocate_agent(state: AgentState, agent_id: str = "devils_advocate_agent"):
    """Synthesizes bull vs bear debate from all analyst signals and produces a contrarian signal."""
    data = state["data"]
    tickers = data["tickers"]
    analyst_signals = data["analyst_signals"]

    progress.update_status(agent_id, None, "Reading analyst signals")

    # Build compact signal summary per ticker: {ticker: {agent: {sig, conf, reasoning}}}
    signals_by_ticker = {}
    for ticker in tickers:
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if "risk_management" in agent:
                continue
            if ticker in signals:
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                reasoning = signals[ticker].get("reasoning", "")
                if sig is not None and conf is not None:
                    ticker_signals[agent.replace("_agent", "")] = {
                        "signal": sig,
                        "confidence": conf,
                        "reasoning": reasoning[:200] if isinstance(reasoning, str) else str(reasoning)[:200],
                    }
        signals_by_ticker[ticker] = ticker_signals

    progress.update_status(agent_id, None, "Synthesizing bull vs bear cases")

    # Single LLM call for all tickers
    prompt = f"{SYSTEM_PROMPT}\n\nHuman: {HUMAN_PROMPT.format(signals=json.dumps(signals_by_ticker, indent=2))}"

    def create_default():
        analyses = {}
        for ticker in tickers:
            analyses[ticker] = DevilsAdvocateTickerAnalysis(
                majority_position="neutral",
                contrarian_signal="neutral",
                confidence=50,
                bull_case="Insufficient data for bull case.",
                bear_case="Insufficient data for bear case.",
                reasoning="Default: insufficient analyst signals to synthesize.",
            )
        return DevilsAdvocateOutput(analyses=analyses)

    result = call_llm(
        prompt=prompt,
        pydantic_model=DevilsAdvocateOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default,
    )

    # Convert to standard analyst_signals format
    devils_advocate_analysis = {}
    for ticker in tickers:
        if ticker in result.analyses:
            analysis = result.analyses[ticker]
            devils_advocate_analysis[ticker] = {
                "signal": analysis.contrarian_signal,
                "confidence": analysis.confidence,
                "reasoning": (
                    f"MAJORITY: {analysis.majority_position.upper()} | "
                    f"BULL: {analysis.bull_case} | "
                    f"BEAR: {analysis.bear_case} | "
                    f"VERDICT: {analysis.reasoning}"
                ),
            }
            progress.update_status(
                agent_id, ticker, "Done",
                analysis=devils_advocate_analysis[ticker]["reasoning"],
            )
        else:
            devils_advocate_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 50,
                "reasoning": "No analysis generated for this ticker.",
            }

    message = HumanMessage(content=json.dumps(devils_advocate_analysis), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(devils_advocate_analysis, "Devil's Advocate")

    state["data"]["analyst_signals"][agent_id] = devils_advocate_analysis
    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": data}
