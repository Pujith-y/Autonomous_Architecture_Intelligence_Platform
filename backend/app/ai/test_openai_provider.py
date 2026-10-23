
from unittest.mock import Mock, patch

import pytest

from app.ai.openai_provider import OpenAILLMProvider


@patch("app.ai.openai_provider.settings")
@patch("app.ai.openai_provider.OpenAI")
def test_generate_answer_returns_model_response(mock_openai, mock_settings):
    mock_settings.LLM_API_KEY = "test-key"
    mock_settings.LLM_BASE_URL = None
    mock_settings.LLM_MODEL = "test-model"
    mock_settings.LLM_TEMPERATURE = 0.1
    mock_settings.LLM_MAX_TOKENS = 1000

    client = Mock()
    mock_openai.return_value = client

    message = Mock()
    message.content = "The login function is in auth.py."

    client.chat.completions.create.return_value.choices = [
        Mock(message=message)
    ]

    provider = OpenAILLMProvider()
    answer = provider.generate_answer(
        query="Where is login implemented?",
        context={"evidence_count": 1},
    )

    assert answer == "The login function is in auth.py."
    client.chat.completions.create.assert_called_once()


@patch("app.ai.openai_provider.settings")
def test_provider_requires_api_key(mock_settings):
    mock_settings.LLM_API_KEY = None

    with pytest.raises(ValueError, match="LLM_API_KEY is required"):
        OpenAILLMProvider()


@patch("app.ai.openai_provider.settings")
@patch("app.ai.openai_provider.OpenAI")
def test_generate_answer_rejects_empty_response(mock_openai, mock_settings):
    mock_settings.LLM_API_KEY = "test-key"
    mock_settings.LLM_BASE_URL = None
    mock_settings.LLM_MODEL = "test-model"
    mock_settings.LLM_TEMPERATURE = 0.1
    mock_settings.LLM_MAX_TOKENS = 1000

    client = Mock()
    mock_openai.return_value = client
    client.chat.completions.create.return_value.choices = [
        Mock(message=Mock(content="  "))
    ]

    provider = OpenAILLMProvider()

    with pytest.raises(RuntimeError, match="empty answer"):
        provider.generate_answer("Test query", {"evidence_count": 1})
