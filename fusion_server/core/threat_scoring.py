"""
Deterministic Threat Scoring - Phase 4
Calculates threat_score (0.0-1.0) based on rule violations and context
NO ML - pure deterministic function per ARCHITECTURE.md
"""
from dataclasses import dataclass
from typing import List, Optional
from fusion_server.core.rule_engine import RuleViolation


@dataclass
class ThreatContext:
    """Context for threat scoring."""
    object_type: str  # "person" | "vehicle"
    time_of_day: str  # "day" | "night" | "dawn" | "dusk"
    camera_zone: str  # "perimeter" | "inner" | "critical"
    previous_violations: int = 0
    is_watchlist_match: bool = False


# Base threat scores by violation type (deterministic, not learned)
VIOLATION_BASE_SCORES = {
    "enter": 0.5,
    "exit": 0.4,
    "dwell": 0.6,
    "speed": 0.7,
    "direction": 0.3,
    "virtual_fence_crossing": 0.7,
    "suspicious_activity": 0.6,
    "loitering": 0.5,
    "camera_tamper": 0.9,
    "camera_drift": 0.7,
    "camera_blinding": 0.8,
    "camera_frozen": 0.7,
    "unauthorized_object": 0.6,
}

# Multipliers (deterministic)
CONTEXT_MULTIPLIERS = {
    "object_type": {"person": 1.0, "vehicle": 1.2},
    "time_of_day": {"day": 1.0, "night": 1.3, "dawn": 1.1, "dusk": 1.1},
    "camera_zone": {"perimeter": 1.0, "inner": 1.2, "critical": 1.5},
}


def calculate_threat_score(
    violations: List[RuleViolation],
    context: ThreatContext,
) -> float:
    """
    Deterministic threat score calculation.
    Pure function - same inputs always produce same output.
    NO ML, NO randomness, NO hidden state.
    """
    # Watchlist match is maximum threat — applies even without violations
    if context.is_watchlist_match:
        return 0.9

    if not violations:
        return 0.0

    # Start with highest base score among violations
    base_score = max(VIOLATION_BASE_SCORES.get(v.violation_type, 0.3) for v in violations)

    # Apply context multipliers
    score = base_score
    score *= CONTEXT_MULTIPLIERS["object_type"].get(context.object_type, 1.0)
    score *= CONTEXT_MULTIPLIERS["time_of_day"].get(context.time_of_day, 1.0)
    score *= CONTEXT_MULTIPLIERS["camera_zone"].get(context.camera_zone, 1.0)

    # Escalation for repeat violations
    if context.previous_violations > 0:
        score *= 1.0 + (0.1 * min(context.previous_violations, 5))

    # Cap at 1.0
    return min(score, 1.0)


def get_threat_level(score: float) -> str:
    """Convert numeric score to threat level for UI."""
    if score >= 0.8:
        return "critical"
    elif score >= 0.5:
        return "high"
    elif score >= 0.3:
        return "medium"
    elif score > 0:
        return "low"
    return "none"