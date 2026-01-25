from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

BinaryVec = Tuple[int, ...]


@dataclass(frozen=True)
class QuboProblem:
    q: np.ndarray
    linear: np.ndarray


def build_qubo(
    mean: np.ndarray,
    cov: np.ndarray,
    risk_aversion: float,
    target_assets: int,
    penalty: float,
) -> QuboProblem:
    """
    Build QUBO for binary selection x in {0,1}^n:
      maximize  mean^T x - risk_aversion * x^T cov x
      subject to sum(x) = target_assets

    Convert to minimization with quadratic penalty:
      minimize  -mean^T x + risk_aversion * x^T cov x
               + penalty * (sum(x) - target_assets)^2
    """
    n = mean.shape[0]
    q = risk_aversion * cov.copy()

    # Quadratic penalty expansion for (sum x - k)^2
    # (sum x)^2 - 2k sum x + k^2
    for i in range(n):
        for j in range(n):
            q[i, j] += penalty
    linear = -mean - 2.0 * penalty * target_assets * np.ones(n)

    return QuboProblem(q=q, linear=linear)


def energy(problem: QuboProblem, x: BinaryVec) -> float:
    vec = np.asarray(x, dtype=float)
    quad = float(vec.T @ problem.q @ vec)
    lin = float(problem.linear @ vec)
    return quad + lin


def brute_force_optimize(problem: QuboProblem) -> BinaryVec:
    n = problem.q.shape[0]
    best_x: BinaryVec | None = None
    best_e = float("inf")
    for mask in range(1 << n):
        x = tuple((mask >> i) & 1 for i in range(n))
        e = energy(problem, x)
        if e < best_e:
            best_e = e
            best_x = x
    if best_x is None:
        raise RuntimeError("No solution found.")
    return best_x


def simulated_annealing_optimize(
    problem: QuboProblem,
    steps: int = 5000,
    t_start: float = 5.0,
    t_end: float = 0.05,
    seed: int = 0,
) -> BinaryVec:
    rng = random.Random(seed)
    n = problem.q.shape[0]
    x = [1 if rng.random() < 0.5 else 0 for _ in range(n)]
    e = energy(problem, tuple(x))

    for step in range(steps):
        t = t_start * ((t_end / t_start) ** (step / max(steps - 1, 1)))
        idx = rng.randrange(n)
        x[idx] ^= 1
        e_new = energy(problem, tuple(x))
        if e_new < e or rng.random() < math.exp((e - e_new) / max(t, 1e-8)):
            e = e_new
        else:
            x[idx] ^= 1

    return tuple(x)


def solve_qubo(problem: QuboProblem, brute_force_limit: int = 20, seed: int = 0) -> BinaryVec:
    n = problem.q.shape[0]
    if n <= brute_force_limit:
        return brute_force_optimize(problem)
    return simulated_annealing_optimize(problem, seed=seed)
