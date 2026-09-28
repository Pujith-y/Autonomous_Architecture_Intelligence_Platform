from app.services.indexing.repository_indexer import RepositoryIndexer
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.services.auth.dependencies import get_current_user
from app.database.postgres import get_db

from app.schemas.repositories_schemas import (
    ListOfRepositoryResponse, 
    NewRepository, 
    RepositoryResponse,
)

from app.schemas.indexing_run_schemas import (
    IndexingRunResponse,
    ListOfIndexingRunResponse
)

from app.models.repository_model import Repository
from app.models.user_model import User
from app.models.indexing_run_model import IndexingRun

router = APIRouter(
    tags=["Repositories"],
)

@router.post("/repositories")
def new_repo(
    body : NewRepository,
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    new_repository = Repository(
        name = body.name,
        path = body.path,
        user_id = current_user.id 
    )

    db.add(new_repository)
    db.commit()
    db.refresh(new_repository)

    return {
        "id" : new_repository.id,
        "name" : new_repository.name,
        "path" : new_repository.path,
        "user_id" : new_repository.user_id,
    }


@router.post("/repositories/{repository_id}/index")
def index_repository(
    repository_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = (
        db.query(Repository)
        .filter(
            Repository.id == repository_id,
            Repository.user_id == current_user.id,
        )
        .first()
    )

    if not repository:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
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

@router.get("/repositories", response_model=ListOfRepositoryResponse)
def get_all_repos(
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    return {
        "repositories": repos
    }

@router.get("/repositories/{id}", response_model=RepositoryResponse)
def get_repo_by_id(
    id: int,
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    repo = db.query(Repository).filter(
        Repository.id == id,
        Repository.user_id == current_user.id
    ).first()

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )
    
    return repo

@router.get("/repositories/{id}/indexing-runs", response_model=ListOfIndexingRunResponse)
def get_indexing_runs_of_repo(
    id: int,
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    repo = db.query(Repository).filter(
        Repository.id == id,
        Repository.user_id == current_user.id
    ).first()

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
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
    current_user : User = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    repo = db.query(Repository).filter(
        Repository.id == id,
        Repository.user_id == current_user.id
    ).first()

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    db.delete(repo)
    db.commit()

    return {"message": "Repository deleted successfully."}