"""
NLP Service for Sentiment and Emotion Inference.

Provides:
- TransformerNLPService: Lazy-loading cached inference with CardiffNLP / RoBERTa & GoEmotions.
- RuleBasedOfflineNLPService: Full deterministic offline fallback for offline evaluation/testing.
- Grouping of 27 GoEmotions labels into 6 target categories:
  fear/worry, sadness, anger, joy, neutral, other.
- Graceful handling of empty or whitespace text.
- Dependency injection friendly factory: get_nlp_service().
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

# ── 27 GoEmotions Labels to 6 Target Categories Mapping ────────────────────────

GO_EMOTIONS_MAPPING: Dict[str, str] = {
    # Fear / Worry
    "fear": "fear/worry",
    "nervousness": "fear/worry",

    # Sadness
    "sadness": "sadness",
    "grief": "sadness",
    "remorse": "sadness",
    "disappointment": "sadness",
    "embarrassment": "sadness",

    # Anger
    "anger": "anger",
    "annoyance": "anger",
    "disapproval": "anger",

    # Joy
    "joy": "joy",
    "amusement": "joy",
    "approval": "joy",
    "excitement": "joy",
    "gratitude": "joy",
    "love": "joy",
    "optimism": "joy",
    "pride": "joy",
    "relief": "joy",

    # Neutral
    "neutral": "neutral",

    # Other
    "admiration": "other",
    "caring": "other",
    "confusion": "other",
    "curiosity": "other",
    "desire": "other",
    "realization": "other",
    "surprise": "other",
    "disgust": "other",
}


def map_go_emotion_to_category(raw_label: str) -> str:
    """Map any raw GoEmotions label to one of the 6 target categories."""
    clean = raw_label.lower().strip()
    return GO_EMOTIONS_MAPPING.get(clean, "other")


class BaseNLPService(Protocol):
    """Protocol defining the NLP service interface."""

    def analyze_text(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Analyze text input.
        Returns:
            {
                "sentiment_label": str ("positive"|"neutral"|"negative"),
                "sentiment_score": float (0.0 to 1.0),
                "emotion_label": str ("fear/worry"|"sadness"|"anger"|"joy"|"neutral"|"other"),
                "emotion_score": float (0.0 to 1.0),
            }
        """
        ...


class RuleBasedOfflineNLPService:
    """
    Deterministic offline NLP engine used for testing and offline environments.
    Analyzes sentiment and emotions using validated psychiatric & affective lexicons.
    """

    FEAR_WORRY_WORDS = {
        "worried", "worry", "worries", "scared", "fear", "fearful", "afraid", "panic",
        "panicking", "terror", "dread", "anxious", "anxiety", "threat", "threatened",
        "stalked", "court", "hearing", "danger", "frightened", "nightmare", "unsafe",
        "nervous", "paranoia", "trembling", "intimidated",
    }
    SADNESS_WORDS = {
        "sad", "sadness", "depressed", "depression", "crying", "cried", "tears", "hopeless",
        "grief", "grieving", "empty", "numb", "worthless", "exhausted", "pain", "broken",
        "lonely", "alone", "isolated", "heavy", "miserable", "sorrow", "helpless",
    }
    ANGER_WORDS = {
        "angry", "anger", "furious", "rage", "outraged", "hateful", "resentful", "bitter",
        "disgusted", "hostile", "mad", "agitated", "yelling", "screaming",
    }
    JOY_WORDS = {
        "happy", "hopeful", "glad", "relieved", "relief", "better", "peaceful", "calm",
        "good", "safe", "supported", "grateful", "optimistic", "healing", "smile", "joy",
    }

    def analyze_text(self, text: Optional[str]) -> Dict[str, Any]:
        if not text or not text.strip():
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "emotion_label": "neutral",
                "emotion_score": 0.0,
            }

        cleaned = text.lower()
        words = set(re.findall(r"\b[a-z]{3,}\b", cleaned))

        fear_hits = len(words.intersection(self.FEAR_WORRY_WORDS))
        sadness_hits = len(words.intersection(self.SADNESS_WORDS))
        anger_hits = len(words.intersection(self.ANGER_WORDS))
        joy_hits = len(words.intersection(self.JOY_WORDS))

        # Check for negation patterns (e.g. "not sleeping", "not safe", "can't cope")
        if "not safe" in cleaned or "unsafe" in cleaned or "threat" in cleaned:
            fear_hits += 2
        if "not sleeping" in cleaned or "can't sleep" in cleaned or "cannot sleep" in cleaned:
            fear_hits += 1
            sadness_hits += 1

        emotion_counts = [
            ("fear/worry", fear_hits),
            ("sadness", sadness_hits),
            ("anger", anger_hits),
            ("joy", joy_hits),
        ]
        # Sort by occurrences
        emotion_counts.sort(key=lambda x: x[1], reverse=True)
        top_emotion, top_count = emotion_counts[0]

        if top_count > 0:
            emotion_label = top_emotion
            emotion_score = min(0.95, round(0.55 + (top_count * 0.12), 2))
        else:
            emotion_label = "neutral"
            emotion_score = 0.50

        # Sentiment inference based on emotion & words
        if emotion_label in ("fear/worry", "sadness", "anger") or (fear_hits + sadness_hits + anger_hits > 0):
            sentiment_label = "negative"
            sentiment_score = min(0.98, round(0.60 + ((fear_hits + sadness_hits + anger_hits) * 0.10), 2))
        elif emotion_label == "joy" or joy_hits > 0:
            sentiment_label = "positive"
            sentiment_score = min(0.95, round(0.60 + (joy_hits * 0.12), 2))
        else:
            sentiment_label = "neutral"
            sentiment_score = 0.60

        return {
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
            "emotion_label": emotion_label,
            "emotion_score": emotion_score,
        }


class TransformerNLPService:
    """
    HuggingFace Transformer-backed NLP service with lazy initialization and caching.
    
    Defaults:
    - Sentiment: 'cardiffnlp/twitter-roberta-base-sentiment-latest'
    - Emotion: 'SamLowe/roberta-base-go_emotions'
    """

    def __init__(
        self,
        sentiment_model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest",
        emotion_model_name: str = "SamLowe/roberta-base-go_emotions",
    ):
        self.sentiment_model_name = sentiment_model_name
        self.emotion_model_name = emotion_model_name
        self._sentiment_pipe = None
        self._emotion_pipe = None
        self._fallback = RuleBasedOfflineNLPService()

    def _get_sentiment_pipe(self):
        if self._sentiment_pipe is None:
            try:
                from transformers import pipeline
                self._sentiment_pipe = pipeline(
                    "sentiment-analysis",
                    model=self.sentiment_model_name,
                    device=-1,  # CPU by default
                )
            except Exception as exc:
                logger.warning("Could not load sentiment model %s: %s", self.sentiment_model_name, exc)
                return None
        return self._sentiment_pipe

    def _get_emotion_pipe(self):
        if self._emotion_pipe is None:
            try:
                from transformers import pipeline
                self._emotion_pipe = pipeline(
                    "text-classification",
                    model=self.emotion_model_name,
                    device=-1,
                )
            except Exception as exc:
                logger.warning("Could not load emotion model %s: %s", self.emotion_model_name, exc)
                return None
        return self._emotion_pipe

    def analyze_text(self, text: Optional[str]) -> Dict[str, Any]:
        if not text or not text.strip():
            return {
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "emotion_label": "neutral",
                "emotion_score": 0.0,
            }

        sent_pipe = self._get_sentiment_pipe()
        emo_pipe = self._get_emotion_pipe()

        # If pipelines are not available, gracefully use offline fallback
        if sent_pipe is None or emo_pipe is None:
            return self._fallback.analyze_text(text)

        try:
            # Sentiment
            sent_res = sent_pipe(text[:512])[0]
            raw_sent_label = sent_res["label"].lower()
            sent_score = round(float(sent_res["score"]), 4)

            # Map sentiment labels (e.g., LABEL_0/1/2 or POSITIVE/NEGATIVE/NEUTRAL)
            if "neg" in raw_sent_label or raw_sent_label == "label_0":
                sentiment_label = "negative"
            elif "pos" in raw_sent_label or raw_sent_label == "label_2":
                sentiment_label = "positive"
            else:
                sentiment_label = "neutral"

            # Emotion
            emo_res = emo_pipe(text[:512])[0]
            raw_emo_label = emo_res["label"]
            emo_score = round(float(emo_res["score"]), 4)
            grouped_emotion = map_go_emotion_to_category(raw_emo_label)

            return {
                "sentiment_label": sentiment_label,
                "sentiment_score": sent_score,
                "emotion_label": grouped_emotion,
                "emotion_score": emo_score,
                "raw_emotion_label": raw_emo_label,
            }
        except Exception as exc:
            logger.error("Inference failed, falling back to offline analyzer: %s", exc)
            return self._fallback.analyze_text(text)


# ── Global Singleton and Factory for Dependency Injection ────────────────────

_cached_nlp_service: Optional[BaseNLPService] = None


def get_nlp_service() -> BaseNLPService:
    """
    Factory providing dependency-injected NLP service.
    Configured via environment variable NLP_BACKEND:
      - 'offline': RuleBasedOfflineNLPService (guaranteed no download/network requirement)
      - 'transformer': TransformerNLPService (loads HuggingFace models)
      - 'auto' (default): tries transformer, gracefully falls back if unavailable.
    """
    global _cached_nlp_service
    if _cached_nlp_service is not None:
        return _cached_nlp_service

    backend = os.getenv("NLP_BACKEND", "auto").lower()
    if backend == "offline":
        _cached_nlp_service = RuleBasedOfflineNLPService()
    else:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            _cached_nlp_service = TransformerNLPService()
        except ImportError:
            logger.info("Torch/Transformers not available; using RuleBasedOfflineNLPService.")
            _cached_nlp_service = RuleBasedOfflineNLPService()

    return _cached_nlp_service


def set_nlp_service(service: BaseNLPService) -> None:
    """Explicitly override the NLP service (useful in tests)."""
    global _cached_nlp_service
    _cached_nlp_service = service
