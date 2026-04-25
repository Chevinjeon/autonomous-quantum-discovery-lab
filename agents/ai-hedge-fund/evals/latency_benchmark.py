"""
Measures real-world latency and throughput for grok-3-fast via langchain-xai.

Runs N requests — some sequential, some concurrent — and reports:
  - p50 / p95 / p99 latency
  - tokens/sec (output)
  - effective RPS under concurrency

Usage:
    cd agents/ai-hedge-fund
    XAI_API_KEY=xai-... poetry run python evals/latency_benchmark.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from statistics import mean, median, quantiles

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.llm.models import ModelProvider, get_model  # noqa: E402

# ── Prompts of varying complexity ─────────────────────────────────────────────

PROMPTS = {
    "short":  "What is a z-score? One sentence.",
    "medium": "Explain look-ahead bias in backtesting in 3 bullet points.",
    "long":   (
        "You are a quant. Write a Python function that computes the annualised "
        "Sharpe ratio for a daily returns series. Include two pytest unit tests."
    ),
}

N_SEQUENTIAL = 5    # requests per prompt type, sequential
N_CONCURRENT  = 10  # concurrent requests for the short prompt throughput test


def _run_sequential(llm, prompt: str, n: int) -> list[float]:
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        resp = llm.invoke(prompt)
        latencies.append(time.perf_counter() - t0)
        tokens = len(resp.content.split())
        print(f"    [{i+1}/{n}] {latencies[-1]:.2f}s  ~{tokens} tokens")
    return latencies


async def _async_call(llm, prompt: str) -> float:
    loop = asyncio.get_event_loop()
    t0 = time.perf_counter()
    await loop.run_in_executor(None, llm.invoke, prompt)
    return time.perf_counter() - t0


async def _run_concurrent(llm, prompt: str, n: int) -> tuple[float, list[float]]:
    t0 = time.perf_counter()
    latencies = await asyncio.gather(*[_async_call(llm, prompt) for _ in range(n)])
    wall = time.perf_counter() - t0
    return wall, list(latencies)


def _stats(latencies: list[float]) -> dict:
    s = sorted(latencies)
    qs = quantiles(s, n=100) if len(s) >= 2 else [s[0]] * 99
    return {
        "min":  round(min(s), 2),
        "p50":  round(median(s), 2),
        "p95":  round(qs[94], 2),
        "p99":  round(qs[98], 2) if len(s) >= 10 else "n/a (need ≥10 samples)",
        "max":  round(max(s), 2),
        "mean": round(mean(s), 2),
    }


def main():
    if not os.getenv("XAI_API_KEY"):
        print("ERROR: set XAI_API_KEY before running.")
        sys.exit(1)

    model_name = "grok-3-fast"
    llm = get_model(model_name, ModelProvider.XAI)

    print(f"\n{'='*60}")
    print(f"  Latency Benchmark: {model_name}")
    print(f"{'='*60}\n")

    all_latencies: dict[str, list[float]] = {}

    # ── Sequential by prompt length ───────────────────────────────────────────
    for label, prompt in PROMPTS.items():
        print(f"── Sequential ({label} prompt, n={N_SEQUENTIAL}) ──────────────")
        lats = _run_sequential(llm, prompt, N_SEQUENTIAL)
        all_latencies[label] = lats
        s = _stats(lats)
        print(f"   p50={s['p50']}s  p95={s['p95']}s  mean={s['mean']}s\n")

    # ── Concurrent throughput (short prompt) ──────────────────────────────────
    print(f"── Concurrent throughput (short prompt, n={N_CONCURRENT}) ──────")
    wall, c_lats = asyncio.run(_run_concurrent(llm, PROMPTS["short"], N_CONCURRENT))
    rps = round(N_CONCURRENT / wall, 2)
    cs = _stats(c_lats)
    print(f"   Wall time : {round(wall, 2)}s for {N_CONCURRENT} concurrent requests")
    print(f"   RPS       : {rps}")
    print(f"   p50={cs['p50']}s  p95={cs['p95']}s  mean={cs['mean']}s\n")

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"  SUMMARY — {model_name}")
    print(f"{'='*60}")
    print(f"  {'Prompt':<10} {'min':>6} {'p50':>6} {'p95':>6} {'max':>6} {'mean':>6}")
    print(f"  {'-'*46}")
    for label, lats in all_latencies.items():
        s = _stats(lats)
        print(f"  {label:<10} {s['min']:>6} {s['p50']:>6} {s['p95']:>6} {s['max']:>6} {s['mean']:>6}")
    print(f"  {'concurrent':<10} {cs['min']:>6} {cs['p50']:>6} {cs['p95']:>6} {cs['max']:>6} {cs['mean']:>6}")
    print(f"\n  Effective RPS (concurrent): {rps}")
    print(f"\n  Interpretation:")
    print(f"  - Your conversations worker uses 10 calls/s outbound limit")
    print(f"  - At p50={cs['p50']}s per call, that's the right ceiling")
    print(f"  - If p95 > 5s, consider reducing batch size or adding timeout")


if __name__ == "__main__":
    main()
