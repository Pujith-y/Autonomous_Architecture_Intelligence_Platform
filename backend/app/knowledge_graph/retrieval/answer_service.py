from app.ai.llm_provider import LLMProvider
from app.knowledge_graph.retrieval.context_assembler import ContextAssembler
from app.knowledge_graph.retrieval.retrieval_service import RetrievalService
import logging
from time import perf_counter

logger = logging.getLogger(__name__)

class AnswerService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_provider: LLMProvider,
        context_assembler: ContextAssembler | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.llm_provider = llm_provider
        self.context_assembler = context_assembler or ContextAssembler()

    def prepare_answer(
        self,
        query: str,
        user_id: int,
        repository_id: int,
        limit: int = 5,
    ) -> dict:
        
        total_start = perf_counter()

        stage_start = perf_counter()
        retrieval_result = self.retrieval_service.retrieve(
            query=query,
            user_id=user_id,
            repository_id=repository_id,
            limit=limit,
        )
        retrieval_ms = (perf_counter() - stage_start) * 1000

        stage_start = perf_counter()
        context = self.context_assembler.assemble(retrieval_result)
        context_ms = (perf_counter() - stage_start) * 1000

        stage_start = perf_counter()
        answer = self.llm_provider.generate_answer(
            query=query,
            context=context,
        )
        generation_ms = (perf_counter() - stage_start) * 1000

        total_ms = (perf_counter() - total_start) * 1000

        logger.info(
            "AAIP answer timing: retrieval=%.1fms, "
            "context_assembly=%.1fms, generation=%.1fms, "
            "evidence=%d, total=%.1fms",
            retrieval_ms,
            context_ms,
            generation_ms,
            context["evidence_count"],
            total_ms,
        )

        return {
            "query": context["query"],
            "repository_id": context["repository_id"],
            "evidence_count": context["evidence_count"],
            "evidence": context["evidence"],
            "answer": answer,
        }
