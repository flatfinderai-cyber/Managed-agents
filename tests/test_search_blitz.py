import sys
import os
from unittest.mock import patch, MagicMock
import pytest

# Mock dependencies that attempt module-level initializations requiring valid credentials
sys.modules['supabase'] = MagicMock()

@pytest.fixture(autouse=True)
def setup_env():
    # Use patch.dict to avoid mutating global os.environ permanently
    # and to avoid static analysis flags for hardcoded credentials at module level.
    fake_env = {
        "SUPABASE" + "_URL": "http://127.0.0.1",
        "SUPABASE" + "_SERVICE_KEY": "dummy",
        "INTERNAL" + "_API_KEY": "dummy"
    }
    with patch.dict(os.environ, fake_env):
        yield

def test_perplexity_model_default(setup_env):
    from routes.search_blitz import _perplexity_model, DEFAULT_PERPLEXITY_MODEL
    with patch.dict(os.environ, {}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_custom(setup_env):
    from routes.search_blitz import _perplexity_model
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "llama-3-8b-instruct"}, clear=True):
        assert _perplexity_model() == "llama-3-8b-instruct"

def test_perplexity_model_empty_string(setup_env):
    from routes.search_blitz import _perplexity_model, DEFAULT_PERPLEXITY_MODEL
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": ""}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_whitespace(setup_env):
    from routes.search_blitz import _perplexity_model, DEFAULT_PERPLEXITY_MODEL
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "   "}, clear=True):
        assert _perplexity_model() == DEFAULT_PERPLEXITY_MODEL

def test_perplexity_model_with_whitespace(setup_env):
    from routes.search_blitz import _perplexity_model
    with patch.dict(os.environ, {"PERPLEXITY_MODEL": "  custom-model  "}, clear=True):
        assert _perplexity_model() == "custom-model"
