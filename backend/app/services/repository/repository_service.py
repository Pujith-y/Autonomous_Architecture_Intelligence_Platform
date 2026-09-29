from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.repository_model import Repository
from app.models.user_model import User
from app.schemas.repositories_schemas import NewRepository


class RepositoryService:

    def create(
        self,
        body: NewRepository,
        current_user: User,
        db: Session,
    ) -> Repository:

        repository = Repository(
            name=body.name,
            path=body.path,
            user_id=current_user.id,
        )

        db.add(repository)
        db.commit()
        db.refresh(repository)

        return repository

    def get_all(
        self,
        current_user: User,
        db: Session,
    ) -> list[Repository]:

        return (
            db.query(Repository)
            .filter(
                Repository.user_id == current_user.id
            )
            .all()
        )

    def get_by_id(
        self,
        repository_id: int,
        current_user: User,
        db: Session,
    ) -> Repository:

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

        return repository

    def delete(
        self,
        repository_id: int,
        current_user: User,
        db: Session,
    ) -> None:

        repository = self.get_by_id(
            repository_id,
            current_user,
            db,
        )

        db.delete(repository)
        db.commit()