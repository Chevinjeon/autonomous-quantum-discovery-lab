"""
Single-probe script for the xAI prep exercise.

Runs the mean-reversion backtest prompt against grok-3-fast, saves the full
response, then runs three specific failure-mode checks:

  1. PROOF CHECK   — did the model explain why full-dataset rolling = look-ahead bias?
  2. CODE CHECK    — does the code actually avoid look-ahead bias?
  3. MATH CHECK    — is the z-score formula correct?

Output: evals/results/probe_tc01.txt  (paste this into your submission)

Usage:
    cd agents/ai-hedge-fund
    XAI_API_KEY=xai-... poetry run python evals/probe_tc01.py
"""

import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.llm.models import ModelProvider, get_model  # noqa: E402

PROMPT = """\
You are a quantitative analyst. A user wants to backtest a mean-reversion strategy on AAPL
using 5-year daily close prices.

Before writing any code:
1. State the mathematical definition of the z-score entry signal you will use.
2. Prove why using a rolling window calculated on the FULL dataset before splitting
   into train/test sets constitutes look-ahead bias.
3. Then write Python (pandas + yfinance) code for the backtest that correctly avoids
   look-ahead bias by computing the rolling mean/std only on the training window.

Return your answer in three clearly labelled sections: MATH, PROOF, CODE."""

# ── Failure-mode checks ───────────────────────────────────────────────────────

def check_math_section(response: str) -> dict:
    """Does the response give the correct z-score formula?"""
    has_zscore_formula = bool(re.search(r"z\s*=\s*\(.*?-.*?mean.*?\)\s*/\s*.*?std", response, re.IGNORECASE | re.DOTALL)
                              or ("(x - μ)" in response or "(price - mean)" in response.lower()
                                  or "subtract the mean" in response.lower()))
    has_rolling_ref = "rolling" in response.lower()
    has_window_param = bool(re.search(r"window\s*=\s*\d+", response))
    return {
        "z_score_formula_present": has_zscore_formula,
        "rolling_window_mentioned": has_rolling_ref,
        "window_size_specified": has_window_param,
        "pass": has_zscore_formula and has_rolling_ref,
    }


def check_proof_section(response: str) -> dict:
    """Does the proof section actually explain the look-ahead mechanism?"""
    explains_future_leak = any(phrase in response.lower() for phrase in [
        "future data", "future prices", "future information",
        "not yet available", "peek", "leaks", "look-ahead"
    ])
    mentions_train_test = any(phrase in response.lower() for phrase in [
        "train", "test split", "train/test", "out-of-sample"
    ])
    mentions_mean_contamination = any(phrase in response.lower() for phrase in [
        "mean", "standard deviation", "std", "statistics", "parameters"
    ]) and any(phrase in response.lower() for phrase in [
        "contaminate", "bias", "fitted", "computed on", "calculated on"
    ])
    return {
        "explains_future_leak": explains_future_leak,
        "mentions_train_test_split": mentions_train_test,
        "explains_stat_contamination": mentions_mean_contamination,
        "pass": explains_future_leak and mentions_train_test,
    }


def check_code_section(response: str) -> dict:
    """Does the generated code actually avoid look-ahead bias?"""
    # Extract code blocks
    code_blocks = re.findall(r"```python(.*?)```", response, re.DOTALL)
    code = "\n".join(code_blocks).lower()

    if not code:
        return {"code_found": False, "pass": False, "reason": "No Python code block found"}

    # Bad patterns — signs of look-ahead bias
    bias_patterns = {
        "global_mean": bool(re.search(r"df\[.+\]\.mean\(\)\s*(?!\s*\.)", code)),
        "global_std": bool(re.search(r"df\[.+\]\.std\(\)\s*(?!\s*\.)", code)),
        "fit_on_full_df": bool(re.search(r"fit\(.*df\[", code)),
        "quantile_on_full": bool(re.search(r"df\[.+\]\.quantile\(", code)),
    }

    # Good patterns — signs of correct rolling computation
    good_patterns = {
        "rolling_mean": ".rolling(" in code and ".mean()" in code,
        "rolling_std": ".rolling(" in code and ".std()" in code,
        "train_split": "train" in code and ("iloc" in code or "loc" in code),
        "fit_on_train_only": "fit(" in code and "train" in code,
    }

    bias_found = [k for k, v in bias_patterns.items() if v]
    good_found = [k for k, v in good_patterns.items() if v]

    return {
        "code_found": True,
        "look_ahead_bias_patterns_found": bias_found,
        "correct_patterns_found": good_found,
        "pass": len(bias_found) == 0 and len(good_found) >= 2,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.getenv("XAI_API_KEY"):
        print("ERROR: set XAI_API_KEY before running.")
        sys.exit(1)

    model_name = "grok-3-fast"
    print(f"Probing {model_name} with tc01 (mean-reversion backtest)...")
    print("This takes ~20-40 seconds.\n")

    llm = get_model(model_name, ModelProvider.XAI)

    t0 = time.time()
    response = llm.invoke(PROMPT)
    latency = round(time.time() - t0, 1)
    text = response.content

    # Run checks
    math_result  = check_math_section(text)
    proof_result = check_proof_section(text)
    code_result  = check_code_section(text)

    overall_pass = math_result["pass"] and proof_result["pass"] and code_result["pass"]

    # ── Print report ──────────────────────────────────────────────────────────
    divider = "=" * 70
    report_lines = [
        divider,
        f"  PROBE: tc01 — Mean-Reversion Backtest",
        f"  Model   : {model_name}",
        f"  Latency : {latency}s",
        f"  Result  : {'PASS' if overall_pass else 'FAIL — failure modes detected'}",
        divider,
        "",
        "── DIMENSION 1: MATH (z-score formula) ──────────────────────────────",
        f"  z-score formula present   : {math_result['z_score_formula_present']}",
        f"  rolling window mentioned  : {math_result['rolling_window_mentioned']}",
        f"  window size specified     : {math_result['window_size_specified']}",
        f"  → PASS: {math_result['pass']}",
        "",
        "── DIMENSION 2: PROOF (look-ahead bias explanation) ─────────────────",
        f"  explains future data leak : {proof_result['explains_future_leak']}",
        f"  mentions train/test split : {proof_result['mentions_train_test_split']}",
        f"  explains stat contamination: {proof_result['explains_stat_contamination']}",
        f"  → PASS: {proof_result['pass']}",
        "",
        "── DIMENSION 3: CODE (bias-free implementation) ─────────────────────",
    ]

    if not code_result.get("code_found"):
        report_lines.append("  No Python code block found — FAIL")
    else:
        bias_found = code_result["look_ahead_bias_patterns_found"]
        good_found = code_result["correct_patterns_found"]
        if bias_found:
            report_lines.append(f"  Look-ahead bias patterns detected: {bias_found}")
        else:
            report_lines.append("  No look-ahead bias patterns detected")
        report_lines.append(f"  Correct rolling patterns found: {good_found}")
        report_lines.append(f"  → PASS: {code_result['pass']}")

    report_lines += [
        "",
        divider,
        "  FULL MODEL RESPONSE",
        divider,
        "",
        text,
    ]

    report = "\n".join(report_lines)
    print(report)

    # Save
    out_dir = _HERE / "results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"probe_tc01_{ts}.txt"
    out_path.write_text(report)
    print(f"\n\nSaved → {out_path}")

    # Summary for submission
    print("\n── WHAT TO INCLUDE IN YOUR SUBMISSION ──────────────────────────────")
    if not overall_pass:
        failures = []
        if not math_result["pass"]:
            failures.append("incomplete z-score formula")
        if not proof_result["pass"]:
            failures.append("weak/missing look-ahead bias proof")
        if not code_result["pass"]:
            b = code_result.get("look_ahead_bias_patterns_found", [])
            if b:
                failures.append(f"code still contains bias ({', '.join(b)})")
            else:
                failures.append("code missing correct rolling window patterns")
        print(f"  Model FAILED on: {'; '.join(failures)}")
        print("  → This is your evidence. Quote the specific failing output in your submission.")
        print("  → Then describe how your eval catches it automatically.")
    else:
        print("  Model passed all checks on this run.")
        print("  → Run model_comparison.py to find edge cases where grok-3 outperforms grok-3-fast.")


if __name__ == "__main__":
    main()
