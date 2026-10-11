"""
Rule-based support category suggestion engine.

IMPORTANT ETHICAL & SYSTEM RULE:
All suggested support categories are marked as 'pending professional review'.
The system NEVER automatically decides or enforces support actions.
"""
from __future__ import annotations

import re
from typing import List, Optional


def suggest_support_categories(
    feels_safe: bool,
    faces_threat: bool,
    wants_counselling: bool,
    sleep_difficulty: bool,
    free_text: Optional[str] = None,
) -> List[str]:
    """
    Generate non-binding support category suggestions for counsellor review.

    Rules:
    - Safety concern -> 'Protection & Emergency Relocation'
    - Counselling request -> 'Psychological Support & Counselling'
    - Sleep disturbance -> 'Sleep Hygiene & Somatic Care'
    - Financial keywords -> 'Emergency Financial Assistance'
    - Legal keywords -> 'Legal Aid & Witness Protection'
    - Healthcare keywords -> 'Medical & Healthcare Support'
    - Shelter keywords -> 'Emergency Shelter & Housing'
    """
    suggestions = []

    # 1. Physical safety
    if not feels_safe or faces_threat:
        suggestions.append("Protection & Emergency Relocation")

    # 2. Counselling
    if wants_counselling:
        suggestions.append("Psychological Support & Counselling")

    # 3. Sleep & Somatics
    if sleep_difficulty:
        suggestions.append("Sleep Hygiene & Somatic Care")

    # 4. Text-derived keyword cues
    if free_text:
        text_lower = free_text.lower()

        # Financial cues
        if re.search(r"\b(money|financial|rent|bills?|funds?|food|broke|poverty|debt|compensation)\b", text_lower):
            suggestions.append("Emergency Financial Assistance")

        # Legal cues
        if re.search(r"\b(court|lawyer|legal|police|fir|judge|trial|hearing|prosecut\w+|testif\w+|witness)\b", text_lower):
            suggestions.append("Legal Aid & Witness Protection")

        # Healthcare / Medical cues
        if re.search(r"\b(doctor|hospital|injur\w+|pain|medic\w+|wound|bleed\w+|clinic|prescript\w+)\b", text_lower):
            suggestions.append("Medical & Healthcare Support")

        # Shelter / Housing cues
        if re.search(r"\b(shelter|safehouse|evict\w+|homeless|nowhere to stay|kicked out)\b", text_lower):
            if "Protection & Emergency Relocation" not in suggestions:
                suggestions.append("Emergency Shelter & Housing")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    return deduped
