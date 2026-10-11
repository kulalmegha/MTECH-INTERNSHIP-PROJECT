"""
Unit tests for NLP service (backend/app/ai/nlp_service.py).

Verifies:
- Graceful handling of empty or whitespace text
- GoEmotions 27 labels mapped to 6 target clusters
- RuleBasedOfflineNLPService deterministic outputs
- Dependency injection override
"""
import pytest
from app.ai.nlp_service import (
    GO_EMOTIONS_MAPPING,
    RuleBasedOfflineNLPService,
    get_nlp_service,
    map_go_emotion_to_category,
    set_nlp_service,
)


def test_empty_and_whitespace_handling():
    """Empty or None text must return neutral labels with zero scores gracefully."""
    service = RuleBasedOfflineNLPService()

    for sample in [None, "", "   ", "\n\t"]:
        res = service.analyze_text(sample)
        assert res["sentiment_label"] == "neutral"
        assert res["sentiment_score"] == 0.0
        assert res["emotion_label"] == "neutral"
        assert res["emotion_score"] == 0.0


def test_go_emotions_category_mapping():
    """Verify that GoEmotions labels map to the required 6 categories."""
    target_categories = {"fear/worry", "sadness", "anger", "joy", "neutral", "other"}

    # All labels in map must belong to the target categories
    for raw_label, category in GO_EMOTIONS_MAPPING.items():
        assert category in target_categories, f"Invalid category {category} for {raw_label}"

    # Verify specific key mappings
    assert map_go_emotion_to_category("fear") == "fear/worry"
    assert map_go_emotion_to_category("nervousness") == "fear/worry"
    assert map_go_emotion_to_category("sadness") == "sadness"
    assert map_go_emotion_to_category("grief") == "sadness"
    assert map_go_emotion_to_category("anger") == "anger"
    assert map_go_emotion_to_category("annoyance") == "anger"
    assert map_go_emotion_to_category("joy") == "joy"
    assert map_go_emotion_to_category("relief") == "joy"
    assert map_go_emotion_to_category("neutral") == "neutral"
    assert map_go_emotion_to_category("admiration") == "other"
    assert map_go_emotion_to_category("unrecognized_xyz") == "other"


def test_offline_nlp_service_classification():
    """Test realistic distress sentences through the offline NLP service."""
    service = RuleBasedOfflineNLPService()

    # Fear / worry check-in
    fear_text = "I am terrified and worried about the court hearing tomorrow. I cannot sleep."
    res_fear = service.analyze_text(fear_text)
    assert res_fear["sentiment_label"] == "negative"
    assert res_fear["emotion_label"] == "fear/worry"
    assert res_fear["sentiment_score"] > 0.5
    assert res_fear["emotion_score"] > 0.5

    # Sadness check-in
    sad_text = "I feel so lonely, empty and hopeless. The grief is unbearable."
    res_sad = service.analyze_text(sad_text)
    assert res_sad["sentiment_label"] == "negative"
    assert res_sad["emotion_label"] == "sadness"

    # Joy / relief check-in
    joy_text = "I feel much safer and hopeful today after talking to the counsellor."
    res_joy = service.analyze_text(joy_text)
    assert res_joy["sentiment_label"] == "positive"
    assert res_joy["emotion_label"] == "joy"


def test_nlp_service_dependency_injection():
    """Verify that get_nlp_service returns a valid service and can be overridden."""
    original = get_nlp_service()
    assert original is not None

    custom = RuleBasedOfflineNLPService()
    set_nlp_service(custom)
    assert get_nlp_service() is custom

    # Restore
    set_nlp_service(original)
