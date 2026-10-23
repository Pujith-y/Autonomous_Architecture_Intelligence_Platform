from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate_answer(
        self,
        query: str,
        context: dict,
    ) -> str:
        """Generate an answer using the supplied repository evidence."""
        raise NotImplementedError