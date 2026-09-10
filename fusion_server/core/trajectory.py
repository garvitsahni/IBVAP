"""
Kalman Filter Trajectory Projection - Phase 4
Predicts future position for alert enrichment
"""
import numpy as np
from filterpy.kalman import KalmanFilter
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
        self.kf = KalmanFilter(dim_x=4, dim_z=2)

        # State transition matrix
        self.kf.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])

        # Measurement matrix
        self.kf.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])

        # Measurement noise
        self.kf.R = np.eye(2) * measurement_noise

        # Process noise
        self.kf.Q = np.eye(4) * process_noise
        self.kf.Q[2, 2] = process_noise * 0.1  # velocity noise smaller
        self.kf.Q[3, 3] = process_noise * 0.1

        # Initial covariance
        self.kf.P = np.eye(4) * 100

        # Initial state
        self.kf.x = np.zeros((4, 1))

        self.initialized = False

    def update(self, x: float, y: float):
        """Update filter with new measurement."""
        z = np.array([[x], [y]])
        if not self.initialized:
            self.kf.x[:2] = z
            self.initialized = True
        else:
            self.kf.predict()
            self.kf.update(z)

    def predict(self, steps: int = 1) -> List[Tuple[float, float]]:
        """Predict future positions for N steps ahead."""
        if not self.initialized:
            return []

        predictions = []
        # Save current state
        x_save = self.kf.x.copy()
        P_save = self.kf.P.copy()

        for _ in range(steps):
            self.kf.predict()
            pred_x = float(self.kf.x[0, 0])
            pred_y = float(self.kf.x[1, 0])
            # Clamp to valid range [0, 1]
            pred_x = max(0.0, min(1.0, pred_x))
            pred_y = max(0.0, min(1.0, pred_y))
            predictions.append((pred_x, pred_y))

        # Restore state
        self.kf.x = x_save
        self.kf.P = P_save

        return predictions

    def get_current_state(self) -> Tuple[float, float, float, float]:
        """Get current estimated position and velocity."""
        if not self.initialized:
            return 0.0, 0.0, 0.0, 0.0
        return (
            float(self.kf.x[0, 0]),
            float(self.kf.x[1, 0]),
            float(self.kf.x[2, 0]),
            float(self.kf.x[3, 0]),
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

    # Feed historical points
    for p in points:
        projector.update(p.x, p.y)

    # Predict future
    return projector.predict(prediction_steps)