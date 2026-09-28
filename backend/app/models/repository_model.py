from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.repository_status import RepositoryStatus


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[RepositoryStatus] = mapped_column(
        String(100),
        nullable=False,
        default=RepositoryStatus.PENDING,
    )

    last_indexed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default = datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    last_indexing_error: Mapped[str] = mapped_column(
        String(1000),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="repositories",
    )

    indexing_runs: Mapped[list["IndexingRun"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )