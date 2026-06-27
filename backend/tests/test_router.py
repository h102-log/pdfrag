"""Router must not advertise `.eml` support that the installed Unstructured
build cannot satisfy (no email extra in unstructured>=0.15 / 0.23.x)."""
import pytest

from app.loaders import router


def test_eml_not_in_unstructured_extensions():
    assert ".eml" not in router._UNSTRUCTURED_EXT


def test_supported_unstructured_extensions_remain():
    # the formats that DO have valid Unstructured extras stay supported
    for ext in (".docx", ".xlsx", ".pptx", ".html", ".htm"):
        assert ext in router._UNSTRUCTURED_EXT


def test_load_eml_raises_unsupported():
    with pytest.raises(ValueError):
        router.load("nonexistent.eml")
