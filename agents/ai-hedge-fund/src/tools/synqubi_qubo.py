from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class QuboResult:
    selected: list[int]
    bitstring: tuple[int, ...]


def _load_synqubi_qubo():
    synqubi_root = os.getenv("SYNQUBI_ROOT", "").strip()
    if synqubi_root:
        root_path = Path(synqubi_root).expanduser()
    else:
        default_path = Path("/Users/chevinjeon/Desktop/autonomous-quantum-discovery-lab")
        root_path = default_path if default_path.exists() else None

    if root_path is None or not root_path.exists():
        raise ImportError(
            "SynQubi QUBO backend not found. Set SYNQUBI_ROOT to the "
            "autonomous-quantum-discovery-lab repo path."
        )

    sys.path.insert(0, str(root_path))
    try:
        from portfolio_lab.qubo import build_qubo, solve_qubo  # type: ignore
    finally:
        # Keep path, avoid removing in case other imports need it.
        pass

    return build_qubo, solve_qubo


def solve_portfolio_qubo(
    mean: Iterable[float],
    cov: np.ndarray,
    target_assets: int,
    risk_aversion: float = 1.0,
    penalty: float = 10.0,
    seed: int = 7,
) -> QuboResult:
    mean_vec = np.asarray(list(mean), dtype=float)
    if mean_vec.ndim != 1:
        raise ValueError("mean must be a 1D vector.")
    if cov.shape != (mean_vec.shape[0], mean_vec.shape[0]):
        raise ValueError("cov shape must match mean length.")

    build_qubo, solve_qubo = _load_synqubi_qubo()
    problem = build_qubo(
        mean=mean_vec,
        cov=cov,
        risk_aversion=risk_aversion,
        target_assets=target_assets,
        penalty=penalty,
    )
    bitstring = tuple(int(x) for x in solve_qubo(problem, seed=seed))
    selected = [i for i, bit in enumerate(bitstring) if bit == 1]
    return QuboResult(selected=selected, bitstring=bitstring)
