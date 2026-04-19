import pytest
from services.vmc_validator import _cosine_similarity
import math

def test_cosine_similarity_empty_strings():
    # Both empty
    assert _cosine_similarity("", "") == 0.0
    # One empty
    assert _cosine_similarity("hello", "") == 0.0
    assert _cosine_similarity("", "world") == 0.0

def test_cosine_similarity_identical_strings():
    text = "hello beautiful world"
    assert math.isclose(_cosine_similarity(text, text), 1.0)

def test_cosine_similarity_disjoint_strings():
    assert _cosine_similarity("hello there", "goodbye world") == 0.0

def test_cosine_similarity_partial_overlap():
    # text_a: hello (1), world (1) => mag_a = sqrt(2)
    # text_b: hello (1), there (1) => mag_b = sqrt(2)
    # dot = 1
    # sim = 1 / 2 = 0.5
    assert math.isclose(_cosine_similarity("hello world", "hello there"), 0.5)

def test_cosine_similarity_case_insensitivity():
    assert math.isclose(_cosine_similarity("Hello World", "hello WORLD"), 1.0)

def test_cosine_similarity_punctuation_handling():
    assert math.isclose(_cosine_similarity("Hello, world!", "Hello world"), 1.0)

def test_cosine_similarity_multiple_occurrences():
    # text_a: word (2) => mag_a = sqrt(4) = 2
    # text_b: word (1) => mag_b = sqrt(1) = 1
    # dot = 2
    # sim = 2 / (2 * 1) = 1.0
    assert math.isclose(_cosine_similarity("word word", "word"), 1.0)
