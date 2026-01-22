from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

ComplexVec = List[complex]


@dataclass
class MultiTrial:
    step: int
    thetas: Tuple[float, ...]
    shots: int
    p_flip: float
    measured_energy: float


class MultiMemory:
    def __init__(self) -> None:
        self.trials: List[MultiTrial] = []

    def add(self, trial: MultiTrial) -> None:
        self.trials.append(trial)

    def best(self) -> MultiTrial | None:
        return min(self.trials, key=lambda t: t.measured_energy) if self.trials else None


def _ry(theta: float) -> Tuple[complex, complex, complex, complex]:
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    return (c, -s, s, c)


def _apply_single_qubit_gate(state: ComplexVec, gate: Tuple[complex, complex, complex, complex], qubit: int, n: int) -> None:
    g00, g01, g10, g11 = gate
    size = 1 << n
    for i in range(size):
        if (i >> qubit) & 1:
            continue
        j = i | (1 << qubit)
        a0 = state[i]
        a1 = state[j]
        state[i] = g00 * a0 + g01 * a1
        state[j] = g10 * a0 + g11 * a1


def _apply_cnot(state: ComplexVec, control: int, target: int, n: int) -> None:
    size = 1 << n
    for i in range(size):
        if ((i >> control) & 1) == 0:
            continue
        if ((i >> target) & 1) == 1:
            continue
        j = i | (1 << target)
        state[i], state[j] = state[j], state[i]


def _statevector_from_thetas(thetas: Tuple[float, ...]) -> ComplexVec:
    n = len(thetas)
    state: ComplexVec = [0.0j] * (1 << n)
    state[0] = 1.0 + 0.0j

    for idx, theta in enumerate(thetas):
        _apply_single_qubit_gate(state, _ry(theta), idx, n)

    for idx in range(n - 1):
        _apply_cnot(state, idx, idx + 1, n)

    return state


def _sample_bitstring(rng: random.Random, probs: List[float]) -> int:
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if r <= acc:
            return i
    return len(probs) - 1


def _bit_to_z(bit: int) -> int:
    return 1 if bit == 0 else -1


def _energy_for_bitstring(bits: int, n: int) -> float:
    z_vals = [_bit_to_z((bits >> i) & 1) for i in range(n)]
    energy = sum(z_vals)
    for i in range(n):
        for j in range(i + 1, n):
            energy += 0.5 * z_vals[i] * z_vals[j]
    return energy


class MultiQubitBackendSim:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def measure_energy(self, thetas: Tuple[float, ...], shots: int, p_flip: float) -> float:
        if shots <= 0:
            raise ValueError("shots must be a positive integer.")
        if not (0.0 <= p_flip <= 1.0):
            raise ValueError("p_flip must be between 0 and 1 inclusive.")

        state = _statevector_from_thetas(thetas)
        probs = [abs(a) ** 2 for a in state]
        n = len(thetas)

        total = 0.0
        for _ in range(shots):
            bits = _sample_bitstring(self.rng, probs)
            # apply independent bit flips
            for q in range(n):
                if self.rng.random() < p_flip:
                    bits ^= (1 << q)
            total += _energy_for_bitstring(bits, n)
        return total / shots


def _wrap_thetas(thetas: Tuple[float, ...]) -> Tuple[float, ...]:
    return tuple(t % (2.0 * math.pi) for t in thetas)


def spsa_optimize_multi(
    backend: MultiQubitBackendSim,
    n_qubits: int,
    steps: int,
    shots: int,
    p_flip: float,
    a: float,
    c: float,
    seed: int,
) -> MultiMemory:
    rng = random.Random(seed)
    thetas = tuple(rng.random() * 2.0 * math.pi for _ in range(n_qubits))
    memory = MultiMemory()

    for k in range(1, steps + 1):
        ak = a / (k ** 0.602)
        ck = c / (k ** 0.101)

        delta = tuple(1 if rng.random() < 0.5 else -1 for _ in range(n_qubits))
        theta_plus = _wrap_thetas(tuple(t + ck * d for t, d in zip(thetas, delta)))
        theta_minus = _wrap_thetas(tuple(t - ck * d for t, d in zip(thetas, delta)))

        e_plus = backend.measure_energy(theta_plus, shots, p_flip)
        e_minus = backend.measure_energy(theta_minus, shots, p_flip)

        grad = tuple((e_plus - e_minus) / (2.0 * ck * d) for d in delta)
        thetas = _wrap_thetas(tuple(t - ak * g for t, g in zip(thetas, grad)))

        energy = backend.measure_energy(thetas, shots, p_flip)
        memory.add(
            MultiTrial(
                step=k,
                thetas=thetas,
                shots=shots,
                p_flip=p_flip,
                measured_energy=energy,
            )
        )

    return memory


def _plot_history(history: MultiMemory, output_path: str | None) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Plotting requires matplotlib. Install it with: pip install matplotlib"
        ) from exc

    steps = [t.step for t in history.trials]
    energy = [t.measured_energy for t in history.trials]
    theta0 = [t.thetas[0] for t in history.trials]

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=False)
    axes[0].plot(steps, energy)
    axes[0].set_title("Energy vs step (multi-qubit)")
    axes[0].set_xlabel("step")
    axes[0].set_ylabel("energy")

    axes[1].plot(steps, theta0, color="tab:orange")
    axes[1].set_title("Theta[0] trajectory")
    axes[1].set_xlabel("step")
    axes[1].set_ylabel("theta (rad)")

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150)
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-qubit SPSA demo.")
    parser.add_argument("--qubits", type=int, default=2, help="Number of qubits (2-4).")
    parser.add_argument("--steps", type=int, default=40, help="SPSA steps.")
    parser.add_argument("--shots", type=int, default=400, help="Shots per step.")
    parser.add_argument("--p-flip", type=float, default=0.05, help="Bit-flip noise.")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed.")
    parser.add_argument("--plot", action="store_true", help="Show plots.")
    parser.add_argument("--plot-file", default="", help="Save plots to file.")
    args = parser.parse_args()

    if not (2 <= args.qubits <= 4):
        raise ValueError("qubits must be between 2 and 4.")

    backend = MultiQubitBackendSim(seed=args.seed)
    history = spsa_optimize_multi(
        backend=backend,
        n_qubits=args.qubits,
        steps=args.steps,
        shots=args.shots,
        p_flip=args.p_flip,
        a=0.6,
        c=0.2,
        seed=args.seed,
    )

    best = history.best()
    if best is None:
        raise RuntimeError("No trials recorded.")

    print("\n=== MULTI-QUBIT SPSA ===")
    print(f"Qubits: {args.qubits}")
    print(f"Best energy: {best.measured_energy:.4f}")
    print(f"Best thetas: {[round(t, 4) for t in best.thetas]}")
    print(f"Total steps: {len(history.trials)}")

    if args.plot:
        output = args.plot_file.strip() or None
        _plot_history(history, output)


if __name__ == "__main__":
    main()
