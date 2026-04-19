# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Tests: VMC Validator — Semantic Coherence

import pytest
from vmc_validator import check_semantic_coherence

class TestCheckSemanticCoherence:
    def test_sufficient_rental_keywords(self):
        # Words: rent, apartment, lease (3 words) -> overlap=3 -> score=0.6
        content = "I want to rent an apartment and sign a lease."
        listing_context = {}
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is True
        assert score == 0.6

    def test_insufficient_rental_keywords(self):
        # Words: apartment (1 word) -> overlap=1 -> score=0.2
        content = "I want an apartment."
        listing_context = {}
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is False
        assert score == 0.2

    def test_context_words_match(self):
        # Context words: toronto, condo, main, street
        # Rental words: move (1)
        # Content match: toronto, condo, main, street, move (5 words)
        content = "I will move to Toronto and want the Condo on Main street."
        listing_context = {
            "city": "Toronto",
            "property_type": "Condo",
            "address": "123 Main Street"
        }
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is True
        assert score == 1.0

    def test_known_non_rental_hard_fail(self):
        # Has "apartment" and "rent" but also "recipe"
        content = "This apartment is great to rent but here is a recipe."
        listing_context = {}
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is False
        assert score == 0.1

    def test_empty_content(self):
        content = "123 456"
        listing_context = {}
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is False
        assert score == 0.0

    def test_high_overlap(self):
        content = "rent lease apartment flat room bedroom bathroom deposit"
        listing_context = {}
        passes, score = check_semantic_coherence(content, listing_context)
        assert passes is True
        assert score == 1.0
