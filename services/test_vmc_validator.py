import pytest
from services.vmc_validator import check_semantic_coherence

def test_semantic_coherence_exactly_three_matches():
    # overlap = 3. 3/5.0 = 0.6. Should be True, 0.6.
    content = "I would like to rent this beautiful apartment with one bedroom."
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is True
    assert score == pytest.approx(0.6)

def test_semantic_coherence_high_score():
    # overlap >= 5. Should be True, 1.0.
    content = "I need to rent an apartment. When is the move date? What is the deposit?"
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is True
    assert score == pytest.approx(1.0)

def test_semantic_coherence_low_score():
    # overlap = 2. 2/5.0 = 0.4. Should be False, 0.4.
    content = "This place looks nice, I want to rent it."
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is False
    assert score == pytest.approx(0.4)

def test_semantic_coherence_no_keywords():
    # overlap = 0. 0/5.0 = 0.0. Should be False, 0.0.
    content = "Hello, how are you today?"
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is False
    assert score == pytest.approx(0.0)

def test_semantic_coherence_empty_content():
    content = "   "
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is False
    assert score == pytest.approx(0.0)

def test_semantic_coherence_with_context():
    # content has no predefined rental keywords but matches contextual info.
    # We will provide city, address, etc.
    content = "I love Vancouver and Main Street." # 3 matches
    listing_context = {
        "city": "Vancouver",
        "address": "123 Main Street",
        "rent_amount": "2000"
    }
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is True
    assert score == pytest.approx(0.6)

def test_semantic_coherence_filler_hard_fail():
    content = "I want to rent an apartment, the lease looks good for this bedroom flat lorem ipsum."
    listing_context = {}
    # Many rental keywords, but contains 'lorem ipsum'. Should hard fail.
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is False
    assert score == pytest.approx(0.1)

def test_semantic_coherence_french_keywords():
    content = "Je cherche un appartement à louer avec une chambre. Quel est le loyer ?"
    # appartement, chambre, loyer -> 3 matches
    listing_context = {}
    is_coherent, score = check_semantic_coherence(content, listing_context)
    assert is_coherent is True
    assert score == pytest.approx(0.6)
