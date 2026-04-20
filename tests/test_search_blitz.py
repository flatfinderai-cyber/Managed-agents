import sys
import os
from unittest.mock import patch
import pytest

# Mock required environment variables before importing modules that depend on them
os.environ["SUPABASE_URL"] = "https://example.com"
os.environ["SUPABASE_SERVICE_KEY"] = "dummy-key-for-testing"
os.environ["INTERNAL_API_KEY"] = "dummy-api-key"

# Mock dependencies that attempt module-level initializations requiring valid credentials
from unittest.mock import MagicMock
sys.modules['supabase'] = MagicMock()

from routes.search_blitz import _perplexity_model, DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_default():
    """Test that it returns the default model when PERPLEXITY_MODEL is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_custom():
    """Test that it returns the custom model when PERPLEXITY_MODEL is set."""
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "llama-3-8b-instruct"}, clear=True):
        assert _perplexity_model() == "llama-3-8b-instruct"

def test_perplexity_model_empty_string():
    """Test that it returns the default model when PERPLEXITY_MODEL is an empty string."""
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": ""}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_whitespace():
    """Test that it returns the default model when PERPLEXITY_MODEL is only whitespace."""
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "   "}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_with_whitespace():
    """Test that it correctly strips whitespace from the custom model string."""
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "  custom-model  "}, clear=True):
        assert _perplexity_model() == "custom-model"
