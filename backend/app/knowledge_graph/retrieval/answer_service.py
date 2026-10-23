from app.knowledge_graph.retrieval.context_assembler import ContextAssembler
from app.knowledge_graph.retrieval.retrieval_service import RetrievalService


class AnswerService:
    """Coordinate code retrieval and evidence assembly."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        context_assembler: ContextAssembler | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.context_assembler = context_assembler or ContextAssembler()

    def prepare_answer(
        self,
        query: str,
        user_id: int,
        repository_id: int,
        limit: int = 5,
    ) -> dict:
        retrieval_result = self.retrieval_service.retrieve(
            query=query,
            user_id=user_id,
            repository_id=repository_id,
            limit=limit,
        )

        context = self.context_assembler.assemble(retrieval_result)

        return {
            "query": context["query"],
            "repository_id": context["repository_id"],
            "evidence_count": context["evidence_count"],
            "evidence": context["evidence"],
        }
