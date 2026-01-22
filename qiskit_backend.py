from __future__ import annotations

import math
from dataclasses import dataclass

try:
    from qiskit import QuantumCircuit  # type: ignore[import-not-found]
    from qiskit_aer import AerSimulator  # type: ignore[import-not-found]
    from qiskit_aer.noise import NoiseModel, pauli_error  # type: ignore[import-not-found]
except Exception as exc:  # pragma: no cover - optional dependency
    QuantumCircuit = None
    AerSimulator = None
    NoiseModel = None
    pauli_error = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass(frozen=True)
class QiskitBackendConfig:
    shots: int = 1000
    seed: int = 0


class QiskitAerBackend:
    """
    Qiskit Aer backend for measuring <Z> on Ry(theta)|0>.
    Uses a simple bit-flip measurement noise model to mirror p_flip.
    """

    def __init__(self, config: QiskitBackendConfig = QiskitBackendConfig()) -> None:
        if _IMPORT_ERROR is not None:
            raise RuntimeError(
                "Qiskit is not installed. Run: pip install qiskit qiskit-aer"
            ) from _IMPORT_ERROR

        self.config = config
        self._sim = AerSimulator(seed_simulator=config.seed, seed_transpiler=config.seed)

    def measure_expectation_z(self, theta: float, shots: int, p_flip: float) -> float:
        if shots <= 0:
            raise ValueError("shots must be a positive integer.")
        if not (0.0 <= p_flip <= 1.0):
            raise ValueError("p_flip must be between 0 and 1 inclusive.")

        qc = QuantumCircuit(1, 1)
        qc.ry(theta, 0)
        qc.measure(0, 0)

        noise_model = NoiseModel()
        if p_flip > 0.0:
            error = pauli_error([("X", p_flip), ("I", 1.0 - p_flip)])
            noise_model.add_readout_error(error, [0])

        job = self._sim.run(qc, shots=shots, noise_model=noise_model)
        result = job.result()
        counts = result.get_counts(0)

        shots_total = sum(counts.values())
        if shots_total == 0:
            return 0.0

        # For Z-basis: |0> -> +1, |1> -> -1
        p0 = counts.get("0", 0) / shots_total
        p1 = counts.get("1", 0) / shots_total
        return (p0 - p1)


def ideal_expectation_z(theta: float) -> float:
    """Analytic expectation for Ry(theta)|0>."""
    return math.cos(theta)
