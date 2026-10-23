from app.ai.llm_provider import LLMProvider


class MockLLMProvider(LLMProvider):
    def generate_answer(
        self,
        query: str,
        context: dict,
    ) -> str:
        evidence_count = context.get("evidence_count", 0)

        if evidence_count == 0:
            return "I couldn't find relevant evidence in this repository."

        return (
            f"Mock answer for: {query}. "
            f"Found {evidence_count} pieces of repository evidence."
        )