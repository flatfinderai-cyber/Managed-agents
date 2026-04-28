# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Tests: VMC Validator — check_length

import pytest
from services.vmc_validator import check_length

class TestCheckLength:
    def test_exactly_40_words(self):
        content = " ".join(["word"] * 40)
        passed, count = check_length(content)
        assert passed is True
        assert count == 40

    def test_below_40_words(self):
        content = " ".join(["word"] * 39)
        passed, count = check_length(content)
        assert passed is False
        assert count == 39

    def test_above_40_words(self):
        content = " ".join(["word"] * 41)
        passed, count = check_length(content)
        assert passed is True
        assert count == 41

    def test_empty_string(self):
        passed, count = check_length("")
        assert passed is False
        assert count == 0

    def test_whitespace_only(self):
        passed, count = check_length("   \n\t  ")
        assert passed is False
        assert count == 0

    def test_extra_whitespace(self):
        content = "word1  word2\nword3\tword4"
        passed, count = check_length(content)
        assert passed is False
        assert count == 4

    def test_forty_words_with_messy_whitespace(self):
        # 40 words with mixed tabs, newlines, and multiple spaces
        base = ["word"] * 40
        content = "  ".join(base[:10]) + "\n" + "\t".join(base[10:20]) + "   " + " ".join(base[20:])
        passed, count = check_length(content)
        assert passed is True
        assert count == 40
