
from app.ai.llm_provider import LLMProvider
from app.ai.mock_provider import MockLLMProvider
from app.config.settings import settings


def create_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.strip().lower()

    if provider == "mock":
        return MockLLMProvider()

    if provider == "openai":
        from app.ai.openai_provider import OpenAILLMProvider

        return OpenAILLMProvider()

    raise ValueError(
        f"Unsupported LLM provider: {settings.LLM_PROVIDER}"
    )
