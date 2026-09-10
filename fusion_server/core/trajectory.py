"""
Kalman Filter Trajectory Projection - Phase 4
Predicts future position for alert enrichment
Pure numpy implementation (no filterpy/scipy dependency)
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TrajectoryPoint:
    x: float  # normalized 0-1
    y: float  # normalized 0-1
    timestamp: float  # unix timestamp


class TrajectoryProjector:
    """
    Kalman filter for trajectory projection.
    State: [x, y, vx, vy]
    Measurement: [x, y]
    """

    def __init__(self, dt: float = 1.0, process_noise: float = 0.01, measurement_noise: float = 0.1):
        self.dt = dt

        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])

        self.R = np.eye(2) * measurement_noise

        self.Q = np.eye(4) * process_noise
        self.Q[2, 2] = process_noise * 0.1
        self.Q[3, 3] = process_noise * 0.1

        self.P = np.eye(4) * 100

        self.x = np.zeros((4, 1))

        self.initialized = False

    def predict_step(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update_step(self, z: np.ndarray):
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    def update(self, x: float, y: float):
        """Update filter with new measurement."""
        z = np.array([[x], [y]])
        if not self.initialized:
            self.x[:2] = z
            self.initialized = True
        else:
            self.predict_step()
            self.update_step(z)

    def predict(self, steps: int = 1) -> List[Tuple[float, float]]:
        """Predict future positions for N steps ahead."""
        if not self.initialized:
            return []

        predictions = []
        x_save = self.x.copy()
        P_save = self.P.copy()

        for _ in range(steps):
            self.predict_step()
            pred_x = float(self.x[0, 0])
            pred_y = float(self.x[1, 0])
            pred_x = max(0.0, min(1.0, pred_x))
            pred_y = max(0.0, min(1.0, pred_y))
            predictions.append((pred_x, pred_y))

        self.x = x_save
        self.P = P_save

        return predictions

    def get_current_state(self) -> Tuple[float, float, float, float]:
        """Get current estimated position and velocity."""
        if not self.initialized:
            return 0.0, 0.0, 0.0, 0.0
        return (
            float(self.x[0, 0]),
            float(self.x[1, 0]),
            float(self.x[2, 0]),
            float(self.x[3, 0]),
        )


def project_trajectory(
    points: List[TrajectoryPoint],
    prediction_steps: int = 10,
    dt: float = 1.0,
) -> List[Tuple[float, float]]:
    """
    Project trajectory from historical points.
    Returns list of predicted (x, y) positions.
    """
    if len(points) < 2:
        return []

    projector = TrajectoryProjector(dt=dt)

    for p in points:
        projector.update(p.x, p.y)

    return projector.predict(prediction_steps)
