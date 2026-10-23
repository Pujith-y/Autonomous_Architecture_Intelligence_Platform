import pytest

from app.ai.llm_provider import LLMProvider
from app.ai.mock_provider import MockLLMProvider


def test_mock_provider_implements_interface():
    provider = MockLLMProvider()

    assert isinstance(provider, LLMProvider)


def test_mock_provider_generates_answer():
    provider = MockLLMProvider()

    answer = provider.generate_answer(
        query="Where is authentication handled?",
        context={"evidence_count": 2},
    )

    assert "Where is authentication handled?" in answer
    assert "2 pieces" in answer


def test_mock_provider_handles_empty_evidence():
    provider = MockLLMProvider()

    answer = provider.generate_answer(
        query="Where is authentication handled?",
        context={"evidence_count": 0},
    )

    assert "couldn't find relevant evidence" in answer


def test_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        LLMProvider()