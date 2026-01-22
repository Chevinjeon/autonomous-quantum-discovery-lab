from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from .sim_noise import NoiseSample, Vector3

Features = Tuple[float, float, float, float]


def _norm(v: Vector3) -> float:
    return math.sqrt(sum(x * x for x in v))


def feature_vector(sample: NoiseSample) -> Features:
    """
    Convert sensor noise to a compact feature vector for policy control.
    """
    return (
        _norm(sample.accel),
        _norm(sample.gyro),
        _norm(sample.bias),
        _norm(sample.drift),
    )


@dataclass
class PolicyParams:
    """Linear policy parameters mapping features -> theta."""

    weights: Features
    bias: float


class LinearPolicy:
    """Simple linear control policy with angle wrapping."""

    def __init__(self, params: PolicyParams) -> None:
        self.params = params

    def predict_theta(self, features: Features) -> float:
        w = self.params.weights
        theta = (
            w[0] * features[0]
            + w[1] * features[1]
            + w[2] * features[2]
            + w[3] * features[3]
            + self.params.bias
        )
        return theta % (2.0 * math.pi)

    def with_params(self, params: PolicyParams) -> "LinearPolicy":
        return LinearPolicy(params)
