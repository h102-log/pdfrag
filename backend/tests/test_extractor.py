"""Unit tests for the `_is_placeholder` API-key guard in build_llm.

The guard must reject the dummy keys shipped in backend/.env.example
(`sk-ant-xxxx`, `sk-xxxx`) so PoC3 fails fast with a clear message instead of
a late 401 from the Anthropic API, while accepting a realistic key.
"""
import pytest

# llama_index / anthropic stack is heavy; skip cleanly if it cannot import.
extractor = pytest.importorskip("app.graph.extractor")


@pytest.mark.parametrize("key", [
    "",
    None,
    "your-key",
    "sk-ant-xxxx",                       # .env.example default
    "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx",    # long sk-xxx dummy
    "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx",    # long all-x anthropic dummy
])
def test_placeholder_keys_are_rejected(key):
    assert extractor._is_placeholder(key) is True


def test_realistic_key_is_accepted():
    real = "sk-ant-api03-R4nd0mKeyMaterialABCDEFGH1234567890wXyZ"
    assert extractor._is_placeholder(real) is False
