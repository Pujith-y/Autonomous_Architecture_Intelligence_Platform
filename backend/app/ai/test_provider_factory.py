
from unittest.mock import patch

import pytest

from app.ai.mock_provider import MockLLMProvider
from app.ai.provider_factory import create_llm_provider


@patch("app.ai.provider_factory.settings")
def test_factory_creates_mock_provider(mock_settings):
    mock_settings.LLM_PROVIDER = "mock"

    provider = create_llm_provider()

    assert isinstance(provider, MockLLMProvider)


@patch("app.ai.provider_factory.settings")
def test_factory_rejects_unknown_provider(mock_settings):
    mock_settings.LLM_PROVIDER = "unknown"

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_llm_provider()
