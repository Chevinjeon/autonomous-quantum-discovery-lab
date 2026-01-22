from __future__ import annotations

import math
from dataclasses import dataclass

from .sim_noise import NoiseSample, Vector3


@dataclass(frozen=True)
class QuantumErrorRates:
    """Simple quantum error model parameters derived from sensor noise."""

    p_flip: float
    depolarizing: float
    amp_damp: float


@dataclass(frozen=True)
class NoiseToQuantumMapConfig:
    """
    Linear mapping from physical disturbance magnitude to quantum error rates.
    Tune these values as you calibrate against real sensor logs or hardware.
    """

    accel_scale: float = 0.08
    gyro_scale: float = 0.06
    bias_scale: float = 0.04
    drift_scale: float = 0.02
    base_flip: float = 0.01
    base_depol: float = 0.005
    base_amp_damp: float = 0.005
    max_rate: float = 0.25


def _norm(v: Vector3) -> float:
    return math.sqrt(sum(x * x for x in v))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def map_noise_to_error_rates(
    sample: NoiseSample, config: NoiseToQuantumMapConfig
) -> QuantumErrorRates:
    """
    Map synthetic sensor noise to a simple quantum error model.

    This is a deliberately transparent, linear mapping so you can calibrate it
    against Isaac Sim or hardware logs later.
    """
    severity = (
        config.accel_scale * _norm(sample.accel)
        + config.gyro_scale * _norm(sample.gyro)
        + config.bias_scale * _norm(sample.bias)
        + config.drift_scale * _norm(sample.drift)
    )

    p_flip = _clamp(config.base_flip + severity, 0.0, config.max_rate)
    depol = _clamp(config.base_depol + 0.6 * severity, 0.0, config.max_rate)
    amp_damp = _clamp(config.base_amp_damp + 0.4 * severity, 0.0, config.max_rate)

    return QuantumErrorRates(p_flip=p_flip, depolarizing=depol, amp_damp=amp_damp)
