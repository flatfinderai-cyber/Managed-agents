# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — VMC Message Validation Service (FF-CORE-007 §4)
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

"""
Validates each VMC message against the 7 completion criteria:
  4.1  Message count (tracked at thread level)
  4.2  Minimum length — 40 words
  4.3  Dictionary integrity — 85% threshold (English + French)
  4.4  Semantic coherence — score >= 0.60 against listing context
  4.5  Uniqueness — < 60% cosine similarity to prior messages
  4.6  No template bypass
  4.7  Response pairing — min 90s gap from other party's last message
"""

import re
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Known filler fingerprints (FF-CORE-007 §4.6) ──────────────────────────────
FILLER_PATTERNS = [
    r"^sounds good[.,!]?\s*(looking forward to it[.]?)?$",
    r"^as discussed[,.]?\s*please confirm[.]?$",
    r"^thank you for your (message|email|response)[.]?$",
    r"^(great|perfect|wonderful)[.,!]?\s*(thank you)?[.]?$",
    r"^(ok|okay)[.,!]?\s*(thank you)?[.]?$",
    r"^(sure|absolutely|of course)[.,!]?\s*$",
    r"^(noted|understood)[.,!]?\s*$",
    r"^(yes|no)[.,!]?\s*$",
    r"^(will do|done|confirmed)[.]?$",
    r"^lorem ipsum",
    r"^(asdf|qwerty|zxcv|hjkl|aaaa|zzzz)",
]

# ── Common English + French words (fast lookup set — abbreviated for runtime) ──
# In production this is backed by the full OED/Larousse API.
# Here we use a curated heuristic: words that pass basic morphological tests.
def _is_likely_real_word(word: str) -> bool:
    """
    Heuristic for whether a token is a real dictionary word.
    Production replaces this with the OED/Larousse corpus lookup.
    """
    w = word.lower().strip("'\".,!?;:-")
    if len(w) < 2:
        return False
    # Reject pure numeric sequences
    if w.isdigit():
        return False
    # Reject keyboard runs (same char repeated > 3 times consecutively)
    if re.search(r'(.)\1{3,}', w):
        return False
    # Reject sequences with no vowels (length > 3) — not a real English/French word
    if len(w) > 3 and not re.search(r'[aeiouàâäéèêëîïôùûüæœy]', w, re.IGNORECASE):
        return False
    # Reject sequences that are entirely non-alpha (punctuation runs, etc.)
    if not re.search(r'[a-zA-ZÀ-ÿ]', w):
        return False
    return True


def check_length(content: str) -> tuple[bool, int]:
    """§4.2 — 40 word minimum."""
    words = [w for w in content.split() if w.strip()]
    count = len(words)
    return count >= 40, count


def check_dictionary_integrity(content: str) -> tuple[bool, float]:
    """§4.3 — 85% of words must resolve to real dictionary entries."""
    words = [w for w in content.split() if w.strip()]
    if not words:
        return False, 0.0
    real = sum(1 for w in words if _is_likely_real_word(w))
    pct = real / len(words)
    return pct >= 0.85, round(pct, 3)


def check_semantic_coherence(content: str, listing_context: dict) -> tuple[bool, float]:
    """
    §4.4 — Semantic coherence >= 0.60 against listing context.

    listing_context keys: address, move_in_date, rent_amount, property_type, city

    In production this calls an embedding model for cosine similarity.
    Here we use keyword overlap as a reliable proxy.
    """
    rental_keywords = {
        # English
        'rent', 'lease', 'apartment', 'unit', 'flat', 'room', 'bedroom', 'bathroom',
        'move', 'moving', 'available', 'deposit', 'utilities', 'landlord', 'tenant',
        'property', 'address', 'viewing', 'application', 'income', 'month', 'year',
        'parking', 'laundry', 'pet', 'pets', 'furnished', 'unfurnished', 'lease',
        'tenancy', 'agreement', 'schedule', 'date', 'prefer', 'require', 'need',
        'question', 'information', 'interest', 'interested', 'place', 'home',
        # French
        'loyer', 'appartement', 'chambre', 'bail', 'déménager', 'disponible',
        'charges', 'propriétaire', 'locataire', 'logement', 'caution',
    }

    # Add location-specific keywords from listing context
    context_words = set()
    for val in listing_context.values():
        if isinstance(val, str):
            context_words.update(val.lower().split())

    all_relevant = rental_keywords | context_words

    content_lower = content.lower()
    content_words = set(re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', content_lower))

    if not content_words:
        return False, 0.0

    overlap = len(content_words & all_relevant)

    # Scale: 5+ rental keyword matches → score approaches 1.0
    raw_score = min(overlap / 5.0, 1.0)

    # Hard-fail known filler sources
    known_non_rental = [
        'recipe', 'ingredient', 'tablespoon', 'lyrics', 'chorus', 'verse',
        'lorem', 'ipsum', 'dolor', 'amet', 'consectetur',
    ]
    if any(w in content_lower for w in known_non_rental):
        return False, 0.1

    return raw_score >= 0.60, round(raw_score, 3)


def _cosine_similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity on word frequency vectors."""
    def word_freq(text: str) -> dict:
        words = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', text.lower())
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        return freq

    fa, fb = word_freq(text_a), word_freq(text_b)
    vocab = set(fa) | set(fb)

    dot = sum(fa.get(w, 0) * fb.get(w, 0) for w in vocab)
    mag_a = math.sqrt(sum(v ** 2 for v in fa.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in fb.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def check_uniqueness(content: str, prior_messages: list[str]) -> tuple[bool, float]:
    """§4.5 — Max 60% cosine similarity to any prior message from same sender."""
    if not prior_messages:
        return True, 0.0
    similarities = [_cosine_similarity(content, prior) for prior in prior_messages]
    max_sim = max(similarities)
    return max_sim < 0.60, round(max_sim, 3)


def check_template_bypass(content: str) -> bool:
    """
    §4.6 — Returns True (passes) if message is NOT predominantly filler.
    Returns False (fails) if it matches a known filler pattern.
    """
    stripped = content.strip().lower()
    for pattern in FILLER_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return False  # is filler — fails
    return True  # not filler — passes


def check_response_pairing(
    submitted_at: datetime,
    other_party_last_message_at: Optional[datetime],
) -> bool:
    """
    §4.7 — At least 90 seconds must have elapsed between the other party's
    last message and this submission.
    If there is no prior message from the other party, pairing is not required yet.
    """
    if other_party_last_message_at is None:
        return True  # no requirement yet
    gap = (submitted_at - other_party_last_message_at).total_seconds()
    return gap >= 90


def validate_message(
    content: str,
    listing_context: dict,
    prior_sender_messages: list[str],
    submitted_at: datetime,
    other_party_last_message_at: Optional[datetime],
) -> dict:
    """
    Run all 6 submission-time checks against a message.
    Returns a dict with the full validation result.
    """
    length_ok, word_count = check_length(content)
    dict_ok, dict_pct = check_dictionary_integrity(content)
    semantic_ok, semantic_score = check_semantic_coherence(content, listing_context)
    unique_ok, max_sim = check_uniqueness(content, prior_sender_messages)
    template_ok = check_template_bypass(content)
    responsive_ok = check_response_pairing(submitted_at, other_party_last_message_at)

    is_valid = all([length_ok, dict_ok, semantic_ok, unique_ok, template_ok, responsive_ok])

    # Build plain-language rejection reason
    rejection_reason = None
    if not is_valid:
        reasons = []
        if not length_ok:
            shortfall = 40 - word_count
            reasons.append(
                f"Your message is {word_count} word{'s' if word_count != 1 else ''} long. "
                f"The minimum is 40 words — please add at least {shortfall} more word{'s' if shortfall != 1 else ''}."
            )
        if not dict_ok:
            reasons.append(
                "Your message contains too many words that are not real English or French words. "
                "Please write in plain language."
            )
        if not semantic_ok:
            reasons.append(
                "Your message does not appear to be about the rental. "
                "Please discuss the property, move-in date, or tenancy terms."
            )
        if not unique_ok:
            reasons.append(
                "Your message is too similar to one you have already sent. "
                "Please write a new, original message."
            )
        if not template_ok:
            reasons.append(
                "Your message consists entirely of a standard phrase and does not count as a substantive message. "
                "Please provide more detail about the tenancy."
            )
        if not responsive_ok:
            reasons.append(
                "Please allow at least 90 seconds after reading the other party's message before submitting your response."
            )
        rejection_reason = " ".join(reasons)

    return {
        "is_valid":       is_valid,
        "word_count":     word_count,
        "check_length":   length_ok,
        "check_dict":     dict_ok,
        "check_semantic": semantic_ok,
        "check_unique":   unique_ok,
        "check_template": template_ok,
        "check_responsive": responsive_ok,
        "semantic_score": semantic_score,
        "dict_pct":       dict_pct,
        "similarity_max": max_sim,
        "rejection_reason": rejection_reason,
    }
