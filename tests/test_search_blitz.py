import os
import sys
from unittest.mock import patch, MagicMock

# Mock required environment variables before importing search_blitz
os.environ["SUPABASE_URL"] = "http://dummy"
os.environ["SUPABASE_SERVICE_KEY"] = "dummy.dummy.dummy"

# Mock supabase to avoid initialization errors
sys.modules['supabase'] = MagicMock()

from search_blitz import _perplexity_model, DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_default():
    # Make sure PERPLEXITY_MODEL is not set
    with patch.dict(os.environ, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_empty_string():
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": ""}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_whitespace():
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "   "}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_custom():
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "custom-model"}, clear=True):
        assert _perplexity_model() == "custom-model"

def test_perplexity_model_custom_with_whitespace():
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "  custom-model  "}, clear=True):
        assert _perplexity_model() == "custom-model"
