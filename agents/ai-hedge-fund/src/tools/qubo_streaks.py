"""File-backed per-ticker streak counters for QUBO exit hysteresis.

Plain dicts passed through agent state don't survive across days (a fresh state
is built on every run_hedge_fund call), and Portfolio/PortfolioSnapshot get
rebuilt fresh each call too - so this persists the one piece of state that
needs to survive across days (consecutive deselected-day counts) independent
of the portfolio/snapshot type system entirely.
"""

import json
import os
from pathlib import Path

DEFAULT_STREAK_FILE = Path(__file__).resolve().parent.parent.parent / ".cache" / "qubo_streaks.json"


def _resolve_path() -> Path:
    override = os.environ.get("AIF_QUBO_STREAK_FILE", "").strip()
    return Path(override).expanduser() if override else DEFAULT_STREAK_FILE


def load_streaks(path: Path | None = None) -> dict[str, int]:
    target = path or _resolve_path()
    if not target.exists():
        return {}
    try:
        with open(target) as f:
            data = json.load(f)
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def save_streaks(streaks: dict[str, int], path: Path | None = None) -> None:
    target = path or _resolve_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        json.dump(streaks, f)
