"""
Unit tests for distress scoring engine (backend/app/scoring.py).

Verifies:
- Individual factor computations (stress, safety, sentiment, emotion, sleep, counselling, delta)
- 100 point cap enforcement
- Distress priority band thresholds and boundary conditions
- Score breakdown transparency
- Edge cases (min values, max values, zero/negative deltas, clamping)
"""
import pytest
from app.scoring import (
    BAND_HIGHER,
    BAND_LOW,
    BAND_LOW_MAX,
    BAND_MODERATE,
    BAND_MODERATE_MAX,
    COUNSELLING_MAX_POINTS,
    DELTA_MAX_POINTS,
    EMOTION_MAX_POINTS,
    MAX_DISTRESS_SCORE,
    SAFETY_MAX_POINTS,
    SENTIMENT_MAX_POINTS,
    SLEEP_MAX_POINTS,
    STRESS_MAX_POINTS,
    calculate_distress_score,
    get_distress_band,
)


def test_stress_factor_scaling_and_clamping():
    """Stress 1 to 10 should scale linearly to up to 30 points, clamped between 1 and 10."""
    # Min stress (1)
    score, _, bd = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd["stress_points"] == 3.0

    # Max stress (10)
    score, _, bd = calculate_distress_score(
        stress_level=10, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd["stress_points"] == 30.0

    # Intermediate stress (5)
    score, _, bd = calculate_distress_score(
        stress_level=5, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd["stress_points"] == 15.0

    # Clamping out-of-range inputs
    _, _, bd_low = calculate_distress_score(
        stress_level=-5, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd_low["stress_points"] == 3.0  # Clamped to 1

    _, _, bd_high = calculate_distress_score(
        stress_level=99, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd_high["stress_points"] == 30.0  # Clamped to 10


def test_safety_concern_factor():
    """Safety concern triggers 25 points if feels_safe=False OR faces_threat=True."""
    # Safe and no threat -> 0 pts
    _, _, bd1 = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd1["safety_points"] == 0.0

    # Not safe -> 25 pts
    _, _, bd2 = calculate_distress_score(
        stress_level=1, feels_safe=False, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd2["safety_points"] == SAFETY_MAX_POINTS

    # Faces threat -> 25 pts
    _, _, bd3 = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=True,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd3["safety_points"] == SAFETY_MAX_POINTS

    # Both unsafe and faces threat -> still 25 pts (not doubled)
    _, _, bd4 = calculate_distress_score(
        stress_level=1, feels_safe=False, faces_threat=True,
        sleep_difficulty=False, wants_counselling=False,
    )
    assert bd4["safety_points"] == SAFETY_MAX_POINTS


def test_sentiment_factor():
    """Negative sentiment scaled by confidence contributes up to 15 points; others 0."""
    # Positive sentiment
    _, _, bd_pos = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        sentiment_label="positive", sentiment_score=0.99,
    )
    assert bd_pos["sentiment_points"] == 0.0

    # Neutral sentiment
    _, _, bd_neu = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        sentiment_label="neutral", sentiment_score=0.85,
    )
    assert bd_neu["sentiment_points"] == 0.0

    # Negative sentiment with 0.80 confidence -> 0.8 * 15 = 12.0
    _, _, bd_neg = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        sentiment_label="negative", sentiment_score=0.80,
    )
    assert bd_neg["sentiment_points"] == 12.0

    # Negative with full 1.0 confidence -> 15.0
    _, _, bd_full = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        sentiment_label="negative", sentiment_score=1.0,
    )
    assert bd_full["sentiment_points"] == SENTIMENT_MAX_POINTS


def test_emotion_factor():
    """Distress emotions scaled by confidence contribute up to 10 points."""
    # Joy -> 0 pts
    _, _, bd_joy = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        emotion_label="joy", emotion_score=0.95,
    )
    assert bd_joy["emotion_points"] == 0.0

    # Fear/worry with confidence 0.8 -> 8.0 pts
    _, _, bd_fear = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        emotion_label="fear/worry", emotion_score=0.80,
    )
    assert bd_fear["emotion_points"] == 8.0

    # Sadness with full confidence -> 10.0 pts
    _, _, bd_sad = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        emotion_label="sadness", emotion_score=1.0,
    )
    assert bd_sad["emotion_points"] == EMOTION_MAX_POINTS


def test_sleep_and_counselling_factors():
    """Sleep difficulty is 5 points, counselling request is 5 points."""
    _, _, bd_sleep = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=True, wants_counselling=False,
    )
    assert bd_sleep["sleep_points"] == SLEEP_MAX_POINTS

    _, _, bd_counsel = calculate_distress_score(
        stress_level=1, feels_safe=True, faces_threat=False,
        sleep_difficulty=False, wants_counselling=True,
    )
    assert bd_counsel["counselling_points"] == COUNSELLING_MAX_POINTS


def test_previous_checkin_delta():
    """Score jump versus previous check-in contributes up to 10 points."""
    # Base partial score: stress 10 (30) + safety (25) = 55
    # Previous score = 40 -> delta = 15 -> capped at 10 points
    score, _, bd = calculate_distress_score(
        stress_level=10, feels_safe=False, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        previous_distress_score=40.0,
    )
    assert bd["raw_delta"] == 15.0
    assert bd["delta_points"] == DELTA_MAX_POINTS

    # Base partial score = 55, previous score = 50 -> delta = 5 -> delta_points = 5.0
    _, _, bd2 = calculate_distress_score(
        stress_level=10, feels_safe=False, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        previous_distress_score=50.0,
    )
    assert bd2["raw_delta"] == 5.0
    assert bd2["delta_points"] == 5.0

    # Score decreased (previous 70, base 55) -> delta <= 0 -> 0 points
    _, _, bd3 = calculate_distress_score(
        stress_level=10, feels_safe=False, faces_threat=False,
        sleep_difficulty=False, wants_counselling=False,
        previous_distress_score=70.0,
    )
    assert bd3["raw_delta"] == -15.0
    assert bd3["delta_points"] == 0.0


def test_max_score_cap_at_100():
    """Even when all factors are maximized, final score must never exceed 100."""
    score, band, bd = calculate_distress_score(
        stress_level=10,           # 30
        feels_safe=False,          # 25
        faces_threat=True,
        sleep_difficulty=True,     # 5
        wants_counselling=True,    # 5
        sentiment_label="negative",
        sentiment_score=1.0,       # 15
        emotion_label="fear/worry",
        emotion_score=1.0,         # 10
        previous_distress_score=0.0, # base 90 - 0 = +10 -> total 100
    )
    assert score == MAX_DISTRESS_SCORE
    assert band == BAND_HIGHER
    assert bd["final_score"] == 100.0


def test_distress_band_thresholds_and_boundaries():
    """Verify low (0-33), moderate (34-66), higher (67-100) band boundaries."""
    assert get_distress_band(0.0) == BAND_LOW
    assert get_distress_band(15.5) == BAND_LOW
    assert get_distress_band(BAND_LOW_MAX) == BAND_LOW  # 33.0 is low

    assert get_distress_band(33.1) == BAND_MODERATE
    assert get_distress_band(50.0) == BAND_MODERATE
    assert get_distress_band(BAND_MODERATE_MAX) == BAND_MODERATE  # 66.0 is moderate

    assert get_distress_band(66.1) == BAND_HIGHER
    assert get_distress_band(85.0) == BAND_HIGHER
    assert get_distress_band(100.0) == BAND_HIGHER
