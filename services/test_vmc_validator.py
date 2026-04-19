import pytest
from services.vmc_validator import _cosine_similarity

def test_cosine_similarity_empty_strings():
    assert _cosine_similarity("", "") == 0.0

def test_cosine_similarity_one_empty_string():
    assert _cosine_similarity("hello world", "") == 0.0
    assert _cosine_similarity("", "hello world") == 0.0

def test_cosine_similarity_identical_strings():
    assert _cosine_similarity("hello world", "hello world") == pytest.approx(1.0)

def test_cosine_similarity_disjoint_strings():
    assert _cosine_similarity("hello world", "goodbye friend") == 0.0

def test_cosine_similarity_case_and_punctuation():
    # "hello world" vs "Hello, WORLD!"
    assert _cosine_similarity("hello world", "Hello, WORLD!") == pytest.approx(1.0)

def test_cosine_similarity_partial_overlap():
    # a = "hello world", b = "hello friend"
    # fa = {hello: 1, world: 1}, mag = sqrt(2)
    # fb = {hello: 1, friend: 1}, mag = sqrt(2)
    # dot = 1
    # sim = 1 / 2 = 0.5
    assert _cosine_similarity("hello world", "hello friend") == pytest.approx(0.5)

def test_cosine_similarity_repeated_words():
    # a = "hello hello", b = "hello"
    # fa = {hello: 2}, mag_a = 2
    # fb = {hello: 1}, mag_b = 1
    # dot = 2 * 1 = 2
    # sim = 2 / (2 * 1) = 1.0
    assert _cosine_similarity("hello hello", "hello") == pytest.approx(1.0)

def test_cosine_similarity_diacritics():
    assert _cosine_similarity("café", "café") == pytest.approx(1.0)
    assert _cosine_similarity("résumé", "RÉSUMÉ!") == pytest.approx(1.0)
