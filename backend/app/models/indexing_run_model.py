from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.indexing_status import IndexingStatus

class IndexingRun(Base):

    __tablename__ = "indexing_runs"

    id : Mapped[int] = mapped_column(
        primary_key=True
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[IndexingStatus] = mapped_column(
        String(100),
        nullable=False,
        default=IndexingStatus.PENDING,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    repository: Mapped["Repository"] = relationship(
        back_populates="indexing_runs",
    )