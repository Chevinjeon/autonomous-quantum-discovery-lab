"""
Model Comparison Eval: grok-3 vs grok-3-fast on financial analyst tasks.

Scores each model on three dimensions:
  1. Reasoning coherence  — LLM-judged (0-10): does the logic hold together?
  2. Look-ahead bias      — rule-based (0/1): does the code peek at future data?
  3. Math accuracy        — rule-based (0/1): are Sharpe/return formulas correct?

Usage:
    cd agents/ai-hedge-fund
    XAI_API_KEY=<key> poetry run python evals/model_comparison.py

Output:
    evals/results/comparison_<timestamp>.json   — full raw results
    Printed table to stdout
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# ── Path setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.llm.models import ModelProvider, get_model  # noqa: E402

# ── Test cases ────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    id: str
    category: str          # "strategy_design" | "math" | "bias_detection"
    prompt: str
    # Rubric hints used by the judge
    judge_criteria: str
    # Regex patterns that signal look-ahead bias in generated code
    bias_patterns: List[str] = field(default_factory=list)
    # Substrings that must appear for math to be considered correct
    required_math_terms: List[str] = field(default_factory=list)


TEST_CASES: List[TestCase] = [
    TestCase(
        id="tc01_mean_reversion_strategy",
        category="strategy_design",
        prompt="""\
You are a quantitative analyst. A user wants to backtest a mean-reversion strategy on AAPL
using 5-year daily close prices.

Before writing any code:
1. State the mathematical definition of the z-score entry signal you will use.
2. Prove why using a rolling window calculated on the FULL dataset before splitting
   into train/test sets constitutes look-ahead bias.
3. Then write Python (pandas + yfinance) code for the backtest that correctly avoids
   look-ahead bias by computing the rolling mean/std only on the training window.

Return your answer in three clearly labelled sections: MATH, PROOF, CODE.""",
        judge_criteria=(
            "Correct z-score formula; correctly identifies that fitting on full data "
            "leaks future info; code uses only historical window for rolling stats"
        ),
        bias_patterns=[
            r"\.mean\(\)",             # .mean() on whole series before split
            r"df\[.*\]\.std\(\)",      # std on full df
            r"scaler\.fit\(.*test",    # fitting scaler on test data
        ],
        required_math_terms=["z-score", "rolling", "train"],
    ),
    TestCase(
        id="tc02_sharpe_ratio",
        category="math",
        prompt="""\
Write a Python function `sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.04) -> float`
that computes the annualised Sharpe ratio for a daily returns series.

Requirements:
- Annualise using 252 trading days
- Subtract the daily risk-free rate (annual / 252) from each return before computing excess returns
- Return float rounded to 4 decimal places

Also write two pytest unit tests: one where Sharpe > 1 (good strategy) and one where Sharpe < 0
(strategy worse than risk-free). Show the expected values you calculated by hand.""",
        judge_criteria=(
            "Correct formula: (mean(excess_returns) / std(excess_returns)) * sqrt(252); "
            "daily rfr = annual_rfr / 252; unit tests have arithmetically correct expected values"
        ),
        required_math_terms=["252", "sqrt", "std", "mean"],
    ),
    TestCase(
        id="tc03_bias_detection",
        category="bias_detection",
        prompt="""\
Review the following backtesting code for look-ahead bias. List every instance of look-ahead
bias you find, explain why each is problematic, and provide a corrected version of each snippet.

```python
import pandas as pd
import yfinance as yf

df = yf.download("AAPL", start="2018-01-01", end="2023-12-31")
df['returns'] = df['Close'].pct_change()

# Signal: buy if today's return is in the top 20% of ALL returns in the dataset
threshold = df['returns'].quantile(0.80)
df['signal'] = (df['returns'] > threshold).astype(int)

# Normalise features using full-dataset stats
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df['norm_close'] = scaler.fit_transform(df[['Close']])

# Split: train first 3 years, test last 2 years
split = int(len(df) * 0.6)
train, test = df.iloc[:split], df.iloc[split:]
```""",
        judge_criteria=(
            "Identifies all three biases: (1) quantile computed on full df, "
            "(2) StandardScaler fit on full df, (3) signal uses future return distribution; "
            "corrected code fits scaler only on train, computes rolling/expanding quantile"
        ),
        bias_patterns=[],  # not code-generation; bias detection is the task itself
        required_math_terms=[],
    ),
    TestCase(
        id="tc04_portfolio_optimisation",
        category="math",
        prompt="""\
Explain the Markowitz mean-variance optimisation framework in 3 steps, then write a Python
function using scipy.optimize to find the maximum Sharpe ratio portfolio given:
- A list of daily return series for N assets
- A scalar annual risk-free rate

The function signature must be:
    def max_sharpe_portfolio(returns_df: pd.DataFrame, rfr: float = 0.04) -> dict

Return: {"weights": list[float], "expected_return": float, "volatility": float, "sharpe": float}

Constraints: weights sum to 1, all weights >= 0 (long-only).""",
        judge_criteria=(
            "Correct covariance matrix annualisation (×252); correct Sharpe formula in objective; "
            "scipy.optimize.minimize with correct constraints; weights sum to 1"
        ),
        required_math_terms=["252", "cov", "minimize", "weights"],
    ),
    TestCase(
        id="tc05_reasoning_sandbox",
        category="strategy_design",
        prompt="""\
A trader claims: 'My strategy has a Sharpe ratio of 3.2 over 5 years of daily data on a
single stock. Therefore it will definitely perform well out-of-sample.'

Identify every statistical and logical flaw in this claim. For each flaw:
1. Name it
2. Give the mathematical or statistical reason it invalidates the claim
3. Suggest a specific corrective test or metric

Be precise — cite formulas or thresholds where applicable.""",
        judge_criteria=(
            "Identifies: overfitting/multiple testing (Bonferroni or Bailey-Lopez-de-Prado), "
            "single-stock idiosyncrasy, regime change risk, transaction costs omission, "
            "survivorship bias; at least 4 distinct flaws with quantitative detail"
        ),
        required_math_terms=[],
    ),
]

# ── Scoring ───────────────────────────────────────────────────────────────────

JUDGE_SYSTEM = """\
You are a strict quantitative finance expert evaluating LLM responses.
Score the response on the criterion provided. Return ONLY a JSON object:
{"score": <int 0-10>, "rationale": "<one sentence>"}
Do not include markdown fences."""


def _judge_coherence(response: str, criteria: str, judge_llm) -> tuple[int, str]:
    prompt = (
        f"Criterion: {criteria}\n\n"
        f"Response to evaluate:\n{response[:3000]}\n\n"
        "Score 0-10. Return JSON only."
    )
    try:
        result = judge_llm.invoke([
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ])
        parsed = json.loads(result.content.strip())
        return int(parsed["score"]), parsed.get("rationale", "")
    except Exception as exc:
        return 0, f"Judge error: {exc}"


def _check_bias(response: str, patterns: List[str]) -> tuple[int, List[str]]:
    """1 = no bias detected, 0 = bias pattern found. Returns (score, found_patterns)."""
    if not patterns:
        return 1, []  # not applicable
    found = [p for p in patterns if re.search(p, response)]
    return (0 if found else 1), found


def _check_math(response: str, required_terms: List[str]) -> tuple[int, List[str]]:
    """1 = all required terms present, 0 = missing terms."""
    if not required_terms:
        return 1, []
    missing = [t for t in required_terms if t.lower() not in response.lower()]
    return (0 if missing else 1), missing


# ── Runner ────────────────────────────────────────────────────────────────────

MODELS = [
    ("grok-3", ModelProvider.XAI),
    ("grok-3-fast", ModelProvider.XAI),
]


@dataclass
class EvalResult:
    model: str
    test_id: str
    category: str
    coherence_score: int
    coherence_rationale: str
    bias_score: int          # 1 = clean, 0 = bias detected
    bias_flags: List[str]
    math_score: int          # 1 = correct terms present, 0 = missing
    math_missing: List[str]
    composite: float         # weighted: coherence*0.6 + bias*2 + math*2  (normalised to 10)
    latency_s: float
    raw_response: str


def _composite(coherence: int, bias: int, math: int) -> float:
    # coherence out of 10 → weight 0.6 → up to 6 pts
    # bias clean → 2 pts, math correct → 2 pts  (total 10)
    return round(coherence * 0.6 + bias * 2 + math * 2, 2)


def run_eval() -> List[EvalResult]:
    results: List[EvalResult] = []

    # One judge model (grok-3-fast, cheap) re-used across all scoring
    judge_llm = get_model("grok-3-fast", ModelProvider.XAI)

    for model_name, provider in MODELS:
        print(f"\n{'='*60}")
        print(f"  Model: {model_name}")
        print(f"{'='*60}")
        llm = get_model(model_name, provider)

        for tc in TEST_CASES:
            print(f"  Running {tc.id} ...", end=" ", flush=True)
            t0 = time.time()
            try:
                resp = llm.invoke(tc.prompt)
                response_text = resp.content
            except Exception as exc:
                response_text = f"ERROR: {exc}"
            latency = round(time.time() - t0, 2)
            print(f"{latency}s")

            coherence, rationale = _judge_coherence(response_text, tc.judge_criteria, judge_llm)
            bias_score, bias_flags = _check_bias(response_text, tc.bias_patterns)
            math_score, math_missing = _check_math(response_text, tc.required_math_terms)
            composite = _composite(coherence, bias_score, math_score)

            results.append(EvalResult(
                model=model_name,
                test_id=tc.id,
                category=tc.category,
                coherence_score=coherence,
                coherence_rationale=rationale,
                bias_score=bias_score,
                bias_flags=bias_flags,
                math_score=math_score,
                math_missing=math_missing,
                composite=composite,
                latency_s=latency,
                raw_response=response_text,
            ))

    return results


def _print_table(results: List[EvalResult]):
    # Group by model
    from collections import defaultdict
    by_model: dict[str, List[EvalResult]] = defaultdict(list)
    for r in results:
        by_model[r.model].append(r)

    header = f"{'Test':<35} {'Coherence':>10} {'Bias':>6} {'Math':>6} {'Composite':>10} {'Latency':>9}"
    for model, rows in by_model.items():
        print(f"\n── {model} ──────────────────────────────────────────────────")
        print(header)
        print("-" * len(header))
        for r in rows:
            bias_str = "CLEAN" if r.bias_score else "BIASED"
            math_str = "OK" if r.math_score else "MISSING"
            print(
                f"{r.test_id:<35} {r.coherence_score:>10} {bias_str:>6} {math_str:>6} "
                f"{r.composite:>10.2f} {r.latency_s:>8.1f}s"
            )
        avg_composite = sum(r.composite for r in rows) / len(rows)
        avg_latency = sum(r.latency_s for r in rows) / len(rows)
        print(f"{'AVERAGE':<35} {'':>10} {'':>6} {'':>6} {avg_composite:>10.2f} {avg_latency:>8.1f}s")

    # Head-to-head summary
    models = list(by_model.keys())
    if len(models) == 2:
        m1, m2 = models
        s1 = sum(r.composite for r in by_model[m1]) / len(by_model[m1])
        s2 = sum(r.composite for r in by_model[m2]) / len(by_model[m2])
        l1 = sum(r.latency_s for r in by_model[m1]) / len(by_model[m1])
        l2 = sum(r.latency_s for r in by_model[m2]) / len(by_model[m2])
        print(f"\n{'='*60}")
        print(f"  HEAD-TO-HEAD SUMMARY")
        print(f"{'='*60}")
        print(f"  {m1:<20}  composite={s1:.2f}  avg_latency={l1:.1f}s")
        print(f"  {m2:<20}  composite={s2:.2f}  avg_latency={l2:.1f}s")
        winner_quality = m1 if s1 > s2 else m2
        winner_speed = m1 if l1 < l2 else m2
        print(f"\n  Quality winner : {winner_quality}")
        print(f"  Speed winner   : {winner_speed}")
        speed_delta = abs(l1 - l2)
        quality_delta = abs(s1 - s2)
        print(f"\n  Quality gap    : {quality_delta:.2f} pts")
        print(f"  Speed gap      : {speed_delta:.1f}s per query")


def main():
    if not os.getenv("XAI_API_KEY"):
        print("ERROR: XAI_API_KEY environment variable not set.")
        sys.exit(1)

    print("xAI Model Comparison Eval")
    print(f"Models  : {', '.join(m for m, _ in MODELS)}")
    print(f"Cases   : {len(TEST_CASES)}")
    print(f"Started : {datetime.now().isoformat()}")

    results = run_eval()
    _print_table(results)

    # Save full results
    out_dir = _HERE / "results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"comparison_{ts}.json"
    with open(out_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nFull results saved → {out_path}")


if __name__ == "__main__":
    main()
