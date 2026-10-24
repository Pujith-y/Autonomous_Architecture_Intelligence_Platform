
from openai import OpenAI

from app.ai.llm_provider import LLMProvider
from app.config.settings import settings


class OpenAILLMProvider(LLMProvider):
    def __init__(self):
        if not settings.LLM_API_KEY:
            raise ValueError("LLM_API_KEY is required for OpenAI")

        self.client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL or None,
        )

    def generate_answer(self, query: str, context: dict) -> str:
        response = self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            reasoning_effort="low",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AAIP, a repository architecture assistant. "
                        "Answer using only the supplied repository evidence. "
                        "Do not invent files, functions, or relationships. "
                        "If the evidence is insufficient, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{query}\n\n"
                        f"Repository evidence:\n{context}"
                    ),
                },
            ],
        )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise RuntimeError("The LLM returned an empty answer")

        return answer.strip()
