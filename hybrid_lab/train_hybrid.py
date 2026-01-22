from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from autonomous_quantum_lab import AutonomousQuantumLab, QuantumBackendSim

from .control_policy import Features, LinearPolicy, PolicyParams, feature_vector
from .noise_mapping import NoiseToQuantumMapConfig, QuantumErrorRates, map_noise_to_error_rates
from .sim_noise import NoiseSample, SensorNoiseSource, SyntheticIMUNoiseSource


@dataclass(frozen=True)
class HybridStepResult:
    step: int
    theta: float
    energy: float
    rates: QuantumErrorRates
    features: Features


class HybridLab:
    """
    Hybrid physical-quantum loop:
      - sample physical disturbance (sensor noise)
      - map to quantum error rates
      - choose control theta via policy
      - run noisy quantum experiment
    """

    def __init__(
        self,
        noise_source: SensorNoiseSource,
        backend: QuantumBackendSim,
        map_config: NoiseToQuantumMapConfig,
        policy: LinearPolicy,
    ) -> None:
        self.noise_source = noise_source
        self.backend = backend
        self.map_config = map_config
        self.policy = policy
        self.lab = AutonomousQuantumLab(backend)
        self.history: List[HybridStepResult] = []

    @staticmethod
    def _effective_p_flip(rates: QuantumErrorRates) -> float:
        # Compress multiple error rates into the simple backend p_flip
        return min(1.0, rates.p_flip + 0.5 * rates.depolarizing + 0.5 * rates.amp_damp)

    def run_step(self, step: int, shots: int) -> HybridStepResult:
        sample = self.noise_source.next_sample(step)
        features = feature_vector(sample)
        rates = map_noise_to_error_rates(sample, self.map_config)

        theta = self.policy.predict_theta(features)
        p_flip = self._effective_p_flip(rates)

        energy = self.lab.run_experiment(
            step=step,
            theta=theta,
            shots=shots,
            p_flip=p_flip,
            note="hybrid_lab_step",
        )

        result = HybridStepResult(
            step=step, theta=theta, energy=energy, rates=rates, features=features
        )
        self.history.append(result)
        return result


def _perturb_params(params: PolicyParams, deltas: Tuple[int, int, int, int, int], scale: float) -> PolicyParams:
    w = params.weights
    return PolicyParams(
        weights=(
            w[0] + scale * deltas[0],
            w[1] + scale * deltas[1],
            w[2] + scale * deltas[2],
            w[3] + scale * deltas[3],
        ),
        bias=params.bias + scale * deltas[4],
    )


def _evaluate_policy(
    policy: LinearPolicy,
    sample: NoiseSample,
    backend: QuantumBackendSim,
    map_config: NoiseToQuantumMapConfig,
    shots: int,
) -> float:
    features = feature_vector(sample)
    rates = map_noise_to_error_rates(sample, map_config)
    theta = policy.predict_theta(features)
    p_flip = min(1.0, rates.p_flip + 0.5 * rates.depolarizing + 0.5 * rates.amp_damp)
    return backend.measure_expectation_z(theta, shots, p_flip)


def spsa_train(
    steps: int = 40,
    shots: int = 400,
    a: float = 0.5,
    c: float = 0.1,
    seed: int = 7,
) -> HybridLab:
    """
    SPSA training loop for the hybrid policy parameters.

    Returns the configured HybridLab with its training history.
    """
    rng = random.Random(seed)
    noise_source = SyntheticIMUNoiseSource(seed=seed)
    backend = QuantumBackendSim(seed=seed)
    map_config = NoiseToQuantumMapConfig()

    params = PolicyParams(weights=(0.2, -0.1, 0.05, -0.03), bias=math.pi / 2.0)
    policy = LinearPolicy(params)
    lab = HybridLab(noise_source, backend, map_config, policy)

    for k in range(1, steps + 1):
        ak = a / (k**0.602)
        ck = c / (k**0.101)

        deltas = tuple(1 if rng.random() < 0.5 else -1 for _ in range(5))

        sample = noise_source.next_sample(k)
        policy_plus = LinearPolicy(_perturb_params(params, deltas, ck))
        policy_minus = LinearPolicy(_perturb_params(params, deltas, -ck))

        e_plus = _evaluate_policy(policy_plus, sample, backend, map_config, shots)
        e_minus = _evaluate_policy(policy_minus, sample, backend, map_config, shots)

        grads = tuple((e_plus - e_minus) / (2.0 * ck * d) for d in deltas)
        params = _perturb_params(
            params,
            tuple(-1 if g > 0 else 1 for g in grads),
            ak,
        )

        lab.policy = LinearPolicy(params)
        lab.run_step(step=k, shots=shots)

    return lab


def main() -> None:
    lab = spsa_train()
    best = min(lab.history, key=lambda r: r.energy)

    print("\n=== HYBRID TRAINING ===")
    print(f"Best theta: {best.theta:.4f}")
    print(f"Best energy: {best.energy:.4f}")
    print(f"Total steps: {len(lab.history)}")

    print("\n--- Recent Hybrid Steps ---")
    for r in lab.history[-5:]:
        print(
            "step={:>3} theta={:>7.4f} E={:>7.4f} p_flip={:.4f}".format(
                r.step, r.theta, r.energy, r.rates.p_flip
            )
        )


if __name__ == "__main__":
    main()
