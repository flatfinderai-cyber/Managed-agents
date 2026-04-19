import pytest
from services.vmc_validator import check_semantic_coherence

@pytest.fixture
def base_context():
    return {
        "address": "123 Main St",
        "move_in_date": "2024-01-01",
        "rent_amount": "1500",
        "property_type": "apartment",
        "city": "Vancouver"
    }

def test_semantic_coherence_happy_path(base_context):
    content = "I am interested in this apartment. When is the move-in date? Is the rent 1500?"
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is True
    assert score >= 0.60

def test_semantic_coherence_context_inclusion(base_context):
    content = "I saw the place in Vancouver on Main St. I want to apply."
    # The message includes 'vancouver', 'main', 'st', and 'apply' which match the context and base keywords
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is True
    assert score >= 0.60

def test_semantic_coherence_failure_threshold(base_context):
    content = "Hello, how are you doing today? I like the weather."
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is False
    assert score < 0.60

def test_semantic_coherence_hard_fail_filler(base_context):
    content = "I am looking for an apartment for rent. What is the recipe for chicken soup?"
    # Includes standard rental keywords, but also the hard-fail word 'recipe'
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is False
    assert score == 0.1

def test_semantic_coherence_case_and_punctuation(base_context):
    content = "APARTMENT! Rent? RENT... lease!!!"
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is True
    assert score >= 0.60

def test_semantic_coherence_empty_content(base_context):
    content = ""
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is False
    assert score == 0.0

def test_semantic_coherence_non_string_context_values():
    content = "I want to rent this apartment. Do you need a deposit? I have a pet."
    # Even with non-string values, it shouldn't crash and should still use standard rental keywords
    context = {
        "rent_amount": 1500,
        "is_available": True
    }
    is_valid, score = check_semantic_coherence(content, context)
    assert is_valid is True
    assert score >= 0.60

def test_semantic_coherence_french_keywords(base_context):
    content = "Je cherche un appartement avec un bon loyer. Est-ce que la chambre est disponible?"
    is_valid, score = check_semantic_coherence(content, base_context)
    assert is_valid is True
    assert score >= 0.60
