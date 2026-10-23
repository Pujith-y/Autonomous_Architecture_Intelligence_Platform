from app.services.indexing.repository_indexer import RepositoryIndexer
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.qdrant import client as qdrant_client

from app.services.auth.dependencies import get_current_user
from app.database.postgres import get_db

from app.schemas.repositories_schemas import (
    ListOfRepositoryResponse, 
    NewRepository, 
    RepositoryResponse,
)

from app.schemas.indexing_run_schemas import (
    ListOfIndexingRunResponse
)

from app.models.user_model import User
from app.models.indexing_run_model import IndexingRun

from app.services.repository.repository_service import (
    RepositoryService,
)

from app.schemas.answers import AskRepositoryRequest

from app.ai.provider_factory import create_llm_provider

from app.knowledge_graph.semantic.embedding_provider import EmbeddingProvider
from app.knowledge_graph.semantic.vector_store import QdrantVectorStore
from app.knowledge_graph.neo4j.query_repository import Neo4jQueryRepository

from app.knowledge_graph.retrieval.retrieval_service import RetrievalService
from app.knowledge_graph.retrieval.context_assembler import ContextAssembler
from app.knowledge_graph.retrieval.answer_service import AnswerService


repository_service = RepositoryService()

router = APIRouter(
    tags=["Repositories"],
)

@router.post(
    "/repositories",
    response_model=RepositoryResponse,
)
def new_repo(
    body: NewRepository,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return repository_service.create(
        body,
        current_user,
        db,
    )




@router.post("/repositories/{repository_id}/index")
def index_repository(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = repository_service.get_by_id(
        repository_id,
        current_user,
        db,
    )

    indexer = RepositoryIndexer()

    run = indexer.index(
        repository,
        db,
    )

    return {
        "repository_id": repository.id,
        "indexing_run_id": run.id,
        "status": run.status,
    }




@router.get(
    "/repositories",
    response_model=ListOfRepositoryResponse,
)
def get_all_repos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repositories = repository_service.get_all(
        current_user,
        db,
    )

    return {
        "repositories": repositories
    }



@router.get("/repositories/{id}", response_model=RepositoryResponse)
def get_repo_by_id(
    id: int,
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    return repository_service.get_by_id(
        id,
        current_user,
        db,
    )



@router.get("/repositories/{id}/indexing-runs", response_model=ListOfIndexingRunResponse)
def get_indexing_runs_of_repo(
    id: int,
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    repo = repository_service.get_by_id(
        id,
        current_user,
        db,
    )

    indexing_runs = db.query(IndexingRun).filter(
        IndexingRun.repository_id == repo.id
    ).all()
    return {
        "indexing_runs": indexing_runs
    }



@router.delete("/repositories/{id}")
def delete_repo(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository_service.delete(
        id,
        current_user,
        db,
    )

    return {
        "message": "Repository deleted successfully."
    }


@router.post("/repositories/{repository_id}/ask")
def ask_repository(
    repository_id: int,
    body: AskRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify repository ownership before accessing its indexed data.
    repository = repository_service.get_by_id(
        repository_id,
        current_user,
        db,
    )


    vector_store = QdrantVectorStore(
        client=qdrant_client,
    )

    # Build the retrieval service.
    retrieval_service = RetrievalService(
        embedding_provider=EmbeddingProvider(),
        vector_store=vector_store,
        graph_repository=Neo4jQueryRepository(),
    )

    # Connect retrieval, context assembly, and answer generation.
    answer_service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=create_llm_provider(),
        context_assembler=ContextAssembler(),
    )

    try:
        return answer_service.prepare_answer(
            query=body.query,
            user_id=current_user.id,
            repository_id=repository.id,
            limit=body.limit,
        )
    except Exception:
        from app.core.logger import logger

        logger.exception(
            "Answer generation failed for repository_id=%s",
            repository.id,
        )
        raise HTTPException(
            status_code=503,
            detail="Answer generation is temporarily unavailable",
        ) from None
