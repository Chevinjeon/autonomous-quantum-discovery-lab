from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Tuple

Vector3 = Tuple[float, float, float]


@dataclass(frozen=True)
class NoiseSample:
    """One synthetic sensor-noise observation from a physical simulator."""

    step: int
    accel: Vector3
    gyro: Vector3
    bias: Vector3
    drift: Vector3


class SensorNoiseSource:
    """Base interface for sensor noise sources."""

    def next_sample(self, step: int) -> NoiseSample:  # pragma: no cover - interface
        raise NotImplementedError


class SyntheticIMUNoiseSource(SensorNoiseSource):
    """
    Simple IMU noise source:
    - Gaussian noise for accel/gyro
    - Random-walk bias + drift
    """

    def __init__(
        self,
        sigma_accel: float = 0.02,
        sigma_gyro: float = 0.01,
        bias_walk: float = 0.001,
        drift_walk: float = 0.0005,
        dt: float = 0.01,
        seed: int = 0,
    ) -> None:
        self.sigma_accel = sigma_accel
        self.sigma_gyro = sigma_gyro
        self.bias_walk = bias_walk
        self.drift_walk = drift_walk
        self.dt = dt
        self.rng = random.Random(seed)

        self._bias: Vector3 = (0.0, 0.0, 0.0)
        self._drift: Vector3 = (0.0, 0.0, 0.0)

    def _rand_walk(self, current: Vector3, sigma: float) -> Vector3:
        scale = sigma * math.sqrt(self.dt)
        return tuple(c + self.rng.gauss(0.0, scale) for c in current)  # type: ignore[return-value]

    def _rand_noise(self, sigma: float, bias: Vector3, drift: Vector3) -> Vector3:
        return tuple(self.rng.gauss(0.0, sigma) + b + d for b, d in zip(bias, drift))  # type: ignore[return-value]

    def next_sample(self, step: int) -> NoiseSample:
        self._bias = self._rand_walk(self._bias, self.bias_walk)
        self._drift = self._rand_walk(self._drift, self.drift_walk)

        accel = self._rand_noise(self.sigma_accel, self._bias, self._drift)
        gyro = self._rand_noise(self.sigma_gyro, self._bias, self._drift)

        return NoiseSample(step=step, accel=accel, gyro=gyro, bias=self._bias, drift=self._drift)


class IsaacSimNoiseSource(SensorNoiseSource):
    """
    Placeholder for Isaac Sim integration.

    Swap this to pull sensor readings from an Isaac Sim pipeline or log replay.
    """

    def next_sample(self, step: int) -> NoiseSample:
        raise RuntimeError(
            "Isaac Sim integration is not configured. "
            "Use SyntheticIMUNoiseSource or implement next_sample()."
        )
