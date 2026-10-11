"""
Distress Scoring Engine for Victims of Atrocities.

IMPORTANT DISCLAIMER:
This module implements an experimental support-prioritisation indicator,
NOT a clinically validated diagnostic tool or crisis probability predictor.
Outputs are intended solely to assist authorized human counsellors in triage.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

# ── Configurable Weights & Thresholds ──────────────────────────────────────────

STRESS_MAX_POINTS: float = 30.0
SAFETY_MAX_POINTS: float = 25.0
SENTIMENT_MAX_POINTS: float = 15.0
EMOTION_MAX_POINTS: float = 10.0
SLEEP_MAX_POINTS: float = 5.0
DELTA_MAX_POINTS: float = 10.0
COUNSELLING_MAX_POINTS: float = 5.0

MAX_DISTRESS_SCORE: float = 100.0

BAND_LOW: str = "low"
BAND_MODERATE: str = "moderate"
BAND_HIGHER: str = "higher"

BAND_LOW_MAX: float = 33.0
BAND_MODERATE_MAX: float = 66.0

DISTRESS_EMOTIONS: Set[str] = {
    "fear/worry",
    "fear",
    "worry",
    "nervousness",
    "sadness",
    "grief",
    "remorse",
    "disappointment",
    "anger",
}


def get_distress_band(score: float) -> str:
    """Classify a 0-100 distress score into priority bands."""
    if score <= BAND_LOW_MAX:
        return BAND_LOW
    elif score <= BAND_MODERATE_MAX:
        return BAND_MODERATE
    else:
        return BAND_HIGHER


def calculate_distress_score(
    stress_level: int,
    feels_safe: bool,
    faces_threat: bool,
    sleep_difficulty: bool,
    wants_counselling: bool,
    sentiment_label: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    emotion_label: Optional[str] = None,
    emotion_score: Optional[float] = None,
    previous_distress_score: Optional[float] = None,
) -> Tuple[float, str, Dict[str, Any]]:
    """
    Calculate 0-100 distress score with transparent factor decomposition.

    Parameters:
    - stress_level (1-10): Self-reported subjective stress. Contributes up to 30 pts.
    - feels_safe (bool): False indicates acute lack of physical or psychological safety.
    - faces_threat (bool): True indicates ongoing direct harassment or danger.
      Safety concern (not feels_safe or faces_threat): contributes 25 pts.
    - sleep_difficulty (bool): Physiological distress indicator. Contributes 5 pts.
    - wants_counselling (bool): Explicit ask for intervention. Contributes 5 pts.
    - sentiment_label / score: Negative sentiment scaled by model confidence. Up to 15 pts.
    - emotion_label / score: Distress emotions scaled by confidence. Up to 10 pts.
    - previous_distress_score: If provided, acute increase adds up to 10 pts.

    Returns:
    - final_score: float bounded between 0.0 and 100.0
    - band: "low" | "moderate" | "higher"
    - breakdown: Dict detailing exact contribution of each factor.
    """
    # 1. Stress level (1-10 mapped to 0-30 points)
    clamped_stress = max(1, min(10, int(stress_level)))
    stress_points = round((clamped_stress / 10.0) * STRESS_MAX_POINTS, 2)

    # 2. Safety concern (25 points)
    has_safety_concern = (not feels_safe) or faces_threat
    safety_points = SAFETY_MAX_POINTS if has_safety_concern else 0.0

    # 3. Negative sentiment (up to 15 points scaled by confidence)
    sentiment_points = 0.0
    if sentiment_label and sentiment_label.lower() in ("negative", "neg"):
        conf = max(0.0, min(1.0, float(sentiment_score if sentiment_score is not None else 1.0)))
        sentiment_points = round(conf * SENTIMENT_MAX_POINTS, 2)

    # 4. Fear / worry / sadness / anger emotion (up to 10 points scaled by confidence)
    emotion_points = 0.0
    if emotion_label and emotion_label.lower().strip() in DISTRESS_EMOTIONS:
        conf = max(0.0, min(1.0, float(emotion_score if emotion_score is not None else 1.0)))
        emotion_points = round(conf * EMOTION_MAX_POINTS, 2)

    # 5. Sleep difficulty (5 points)
    sleep_points = SLEEP_MAX_POINTS if sleep_difficulty else 0.0

    # 6. Explicit counselling request (5 points)
    counselling_points = COUNSELLING_MAX_POINTS if wants_counselling else 0.0

    # Baseline partial sum before delta
    base_partial = (
        stress_points
        + safety_points
        + sentiment_points
        + emotion_points
        + sleep_points
        + counselling_points
    )

    # 7. Increase versus previous check-in (up to 10 points)
    delta_points = 0.0
    raw_delta = 0.0
    if previous_distress_score is not None:
        raw_delta = base_partial - float(previous_distress_score)
        if raw_delta > 0:
            # Positive jump adds points directly up to DELTA_MAX_POINTS
            delta_points = round(min(DELTA_MAX_POINTS, raw_delta), 2)

    raw_total = base_partial + delta_points
    final_score = round(min(MAX_DISTRESS_SCORE, max(0.0, raw_total)), 2)
    band = get_distress_band(final_score)

    breakdown = {
        "stress_points": stress_points,
        "safety_points": safety_points,
        "sentiment_points": sentiment_points,
        "emotion_points": emotion_points,
        "sleep_points": sleep_points,
        "counselling_points": counselling_points,
        "delta_points": delta_points,
        "raw_delta": round(raw_delta, 2) if previous_distress_score is not None else None,
        "raw_total": round(raw_total, 2),
        "final_score": final_score,
        "band": band,
    }

    return final_score, band, breakdown
