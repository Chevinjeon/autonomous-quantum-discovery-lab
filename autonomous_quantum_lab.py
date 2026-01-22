from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# 1) DATA STRUCTURES (for diachronic memory / lab notebook)
# ============================================================

@dataclass
class Trial:
    """
    Stores one experiment run in the autonomous lab.

    step: which iteration this happened on (diachronic index)
    theta: circuit parameter (the experiment variable)
    shots: number of measurements (sampling budget)
    p_flip: bit-flip noise probability
    measured_energy: noisy estimate of <Z>
    note: human-readable explanation of what we did and why
    """

    step: int
    theta: float
    shots: int
    p_flip: float
    measured_energy: float
    note: str


class DiachronicMemory:
    """
    A minimal "lab notebook" that stores experiment history over time.

    In a production system this could be:
    - SQLite/Postgres for time-series + metadata
    - object store for raw results
    - vector store for retrieval
    """

    def __init__(self) -> None:
        self.trials: List[Trial] = []  # Keep all trials in time order

    def add(self, trial: Trial) -> None:
        """Append a trial so we can analyze progress over time."""
        self.trials.append(trial)

    def best(self) -> Optional[Trial]:
        """Return the best (lowest energy) trial so far."""
        if not self.trials:
            return None
        return min(self.trials, key=lambda t: t.measured_energy)

    def last(self) -> Optional[Trial]:
        """Return the most recent trial."""
        return self.trials[-1] if self.trials else None

    def diff_last_two(self) -> str:
        """
        Simple diachronic diff to explain change over time.
        (In real systems you'd diff more fields and detect trends.)
        """
        if len(self.trials) < 2:
            return "No previous diff (need at least 2 trials)."

        a = self.trials[-2]
        b = self.trials[-1]

        dtheta = b.theta - a.theta
        dE = b.measured_energy - a.measured_energy

        return f"Δtheta={dtheta:+.4f}, ΔE={dE:+.4f}"


# ============================================================
# 2) QUANTUM BACKEND SIMULATOR (shots + bit-flip noise)
# ============================================================

class QuantumBackendSim:
    """
    Simulates measuring <Z> for the state Ry(theta)|0> with:
    - finite shots (binomial sampling noise)
    - bit-flip noise applied to measurement outcome (simple noise model)

    This is deliberately small and deterministic-testable.
    """

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)  # Deterministic RNG for reproducibility

    @staticmethod
    def _ideal_prob_zero(theta: float) -> float:
        """
        For Ry(theta)|0>, probability of measuring |0> in Z basis is cos^2(theta/2).
        """
        return math.cos(theta / 2.0) ** 2

    def measure_expectation_z(self, theta: float, shots: int, p_flip: float) -> float:
        """
        Return a noisy estimate of <Z> using sampling + bit-flip noise.

        shots: number of measurements (must be > 0)
        p_flip: probability that a measurement bit flips (0 <= p_flip <= 1)
        """
        if shots <= 0:
            raise ValueError("shots must be a positive integer.")
        if not (0.0 <= p_flip <= 1.0):
            raise ValueError("p_flip must be between 0 and 1 inclusive.")

        # Compute ideal probability of outcome |0>
        p0 = self._ideal_prob_zero(theta)

        total_z = 0  # Sum of Z outcomes (+1 or -1) across shots

        for _ in range(shots):
            # Sample the ideal measurement in Z basis
            is_zero = self.rng.random() < p0  # True => |0>, False => |1>

            # Convert to ideal Z outcome: |0> -> +1, |1> -> -1
            z = +1 if is_zero else -1

            # Apply bit-flip noise by flipping the outcome sign with probability p_flip
            if self.rng.random() < p_flip:
                z *= -1

            # Accumulate the noisy measurement outcome
            total_z += z

        # Average approximates expectation value <Z>
        return total_z / shots


# ============================================================
# 3) THE AUTONOMOUS "LAB" ORCHESTRATOR
# ============================================================

class AutonomousQuantumLab:
    """
    Coordinates:
      - experiment execution (backend)
      - memory logging (diachronic notebook)
      - provides helper methods for optimizers
    """

    def __init__(self, backend: QuantumBackendSim) -> None:
        self.backend = backend
        self.memory = DiachronicMemory()

    @staticmethod
    def wrap_angle(theta: float) -> float:
        """Keep theta in [0, 2π) for nicer logs and stable optimization."""
        return theta % (2.0 * math.pi)

    def run_experiment(self, step: int, theta: float, shots: int, p_flip: float, note: str) -> float:
        """
        Run one quantum experiment, log it, and return measured energy (<Z>).
        """
        theta_wrapped = self.wrap_angle(theta)
        energy = self.backend.measure_expectation_z(theta_wrapped, shots, p_flip)

        self.memory.add(
            Trial(
                step=step,
                theta=theta_wrapped,
                shots=shots,
                p_flip=p_flip,
                measured_energy=energy,
                note=note,
            )
        )

        return energy


# ============================================================
# 4) BRUTE FORCE SOLUTION (grid search)
# ============================================================

def brute_force_grid_search(
    lab: AutonomousQuantumLab,
    shots: int,
    p_flip: float,
    grid_points: int,
) -> Trial:
    """
    Brute force approach:
      - Try many theta values on a uniform grid in [0, 2π)
      - Pick the theta with lowest measured energy

    Time:  O(grid_points * shots)
    Space: O(grid_points) stored in memory (you can stream if desired)
    """
    if grid_points <= 1:
        raise ValueError("grid_points must be > 1.")

    for i in range(grid_points):
        theta = (2.0 * math.pi) * (i / grid_points)
        lab.run_experiment(
            step=i,
            theta=theta,
            shots=shots,
            p_flip=p_flip,
            note="brute_force_grid_search",
        )

    best = lab.memory.best()
    assert best is not None, "Best trial should exist after grid search."
    return best


# ============================================================
# 5) FASTEST PRACTICAL SOLUTION (SPSA optimizer)
# ============================================================

def spsa_optimize(
    lab: AutonomousQuantumLab,
    shots: int,
    p_flip: float,
    steps: int,
    a: float,
    c: float,
) -> Trial:
    """
    SPSA (Simultaneous Perturbation Stochastic Approximation):
      - Great for noisy measurements (like real quantum hardware)
      - Uses only TWO function evaluations per step to estimate gradient

    Per step:
      - sample random delta ∈ {+1, -1}
      - evaluate E(theta + ck*delta) and E(theta - ck*delta)
      - estimate gradient and update theta

    Time:  O(steps * shots)  (actually ~2 evaluations/step => ~2*steps*shots)
    Space: O(steps) logs in memory

    Returns the best trial observed.
    """
    if steps <= 0:
        raise ValueError("steps must be positive.")
    if a <= 0 or c <= 0:
        raise ValueError("a and c must be positive.")

    # Start from a random theta (could also start from brute-force best)
    theta = lab.backend.rng.random() * 2.0 * math.pi

    for k in range(1, steps + 1):
        ak = a / (k**0.602)
        ck = c / (k**0.101)

        # Random perturbation direction (+1 or -1)
        delta = +1 if (lab.backend.rng.random() < 0.5) else -1

        # Evaluate at two symmetric points
        e_plus = lab.backend.measure_expectation_z(lab.wrap_angle(theta + ck * delta), shots, p_flip)
        e_minus = lab.backend.measure_expectation_z(lab.wrap_angle(theta - ck * delta), shots, p_flip)

        # SPSA gradient estimate (scalar case)
        g_hat = (e_plus - e_minus) / (2.0 * ck * delta)

        # Update theta in descent direction
        theta = lab.wrap_angle(theta - ak * g_hat)

        lab.run_experiment(
            step=k,
            theta=theta,
            shots=shots,
            p_flip=p_flip,
            note=f"SPSA update; {lab.memory.diff_last_two() if k > 1 else 'init'}",
        )

    best = lab.memory.best()
    assert best is not None, "Best trial should exist after SPSA."
    return best


# ============================================================
# 6) TEST HARNESS (rigorous + edge cases)
# ============================================================

def approx_equal(a: float, b: float, tol: float) -> bool:
    """Helper for floating comparisons with tolerance."""
    return abs(a - b) <= tol


def run_tests() -> None:
    """
    Inclusive tests:
    - edge cases for input validation
    - sanity checks for expected behavior
    - deterministic reproducibility checks
    """
    backend = QuantumBackendSim(seed=123)
    try:
        backend.measure_expectation_z(theta=0.0, shots=0, p_flip=0.0)
        raise AssertionError("Expected ValueError for shots <= 0.")
    except ValueError:
        pass

    try:
        backend.measure_expectation_z(theta=0.0, shots=10, p_flip=-0.1)
        raise AssertionError("Expected ValueError for p_flip < 0.")
    except ValueError:
        pass

    try:
        backend.measure_expectation_z(theta=0.0, shots=10, p_flip=1.1)
        raise AssertionError("Expected ValueError for p_flip > 1.")
    except ValueError:
        pass

    # At theta=0, cos(theta)=1 so expectation should be near +1
    e0 = backend.measure_expectation_z(theta=0.0, shots=5000, p_flip=0.0)
    assert e0 > 0.9, f"Expected near +1 at theta=0, got {e0}"

    # At theta=pi, cos(pi)=-1 so expectation should be near -1
    epi = backend.measure_expectation_z(theta=math.pi, shots=5000, p_flip=0.0)
    assert epi < -0.9, f"Expected near -1 at theta=pi, got {epi}"

    backend2 = QuantumBackendSim(seed=123)
    e_theta = backend2.measure_expectation_z(theta=0.3, shots=20000, p_flip=0.0)
    e_theta_flip = backend2.measure_expectation_z(theta=0.3, shots=20000, p_flip=1.0)
    assert approx_equal(e_theta_flip, -e_theta, tol=0.05), (
        f"Flip test failed: {e_theta_flip} vs {-e_theta}"
    )

    backend3 = QuantumBackendSim(seed=7)
    lab3 = AutonomousQuantumLab(backend3)
    best_bf = brute_force_grid_search(lab3, shots=400, p_flip=0.05, grid_points=80)
    assert best_bf.measured_energy < -0.6, (
        f"Brute force should find near-negative energy, got {best_bf.measured_energy}"
    )

    backend4 = QuantumBackendSim(seed=7)
    lab4 = AutonomousQuantumLab(backend4)
    best_spsa = spsa_optimize(lab4, shots=400, p_flip=0.05, steps=35, a=0.6, c=0.2)
    assert best_spsa.measured_energy < -0.6, (
        f"SPSA should find near-negative energy, got {best_spsa.measured_energy}"
    )

    backend5a = QuantumBackendSim(seed=999)
    backend5b = QuantumBackendSim(seed=999)
    lab5a = AutonomousQuantumLab(backend5a)
    lab5b = AutonomousQuantumLab(backend5b)
    best_a = spsa_optimize(lab5a, shots=300, p_flip=0.02, steps=20, a=0.6, c=0.2)
    best_b = spsa_optimize(lab5b, shots=300, p_flip=0.02, steps=20, a=0.6, c=0.2)
    assert approx_equal(best_a.theta, best_b.theta, tol=1e-9), (
        "Expected deterministic theta with same seed."
    )
    assert approx_equal(best_a.measured_energy, best_b.measured_energy, tol=1e-9), (
        "Expected deterministic energy with same seed."
    )

    print("All tests passed.")


# ============================================================
# 7) MAIN DEMO (runs brute force + SPSA and prints lab notebook)
# ============================================================

def main() -> None:
    """
    Demo run:
      - Runs brute force grid search
      - Runs SPSA
      - Prints best results and a few recent log entries
      - Runs tests
    """
    seed = 42
    shots = 500
    p_flip = 0.05

    backend_bf = QuantumBackendSim(seed=seed)
    lab_bf = AutonomousQuantumLab(backend_bf)

    best_bf = brute_force_grid_search(
        lab=lab_bf,
        shots=shots,
        p_flip=p_flip,
        grid_points=90,
    )

    print("\n=== BRUTE FORCE GRID SEARCH ===")
    print(f"Best theta: {best_bf.theta:.4f} rad")
    print(f"Measured energy: {best_bf.measured_energy:.4f}")
    print(f"Total trials logged: {len(lab_bf.memory.trials)}")

    backend_spsa = QuantumBackendSim(seed=seed)
    lab_spsa = AutonomousQuantumLab(backend_spsa)

    best_spsa = spsa_optimize(
        lab=lab_spsa,
        shots=shots,
        p_flip=p_flip,
        steps=40,
        a=0.6,
        c=0.2,
    )

    print("\n=== SPSA OPTIMIZATION ===")
    print(f"Best theta: {best_spsa.theta:.4f} rad")
    print(f"Measured energy: {best_spsa.measured_energy:.4f}")
    print(f"Total trials logged: {len(lab_spsa.memory.trials)}")

    print("\n--- Recent Lab Notebook Entries (SPSA) ---")
    for t in lab_spsa.memory.trials[-5:]:
        print(f"step={t.step:>3} theta={t.theta:>7.4f} E={t.measured_energy:>7.4f} note={t.note}")

    print("\n=== RUNNING TESTS ===")
    run_tests()


if __name__ == "__main__":
    main()
