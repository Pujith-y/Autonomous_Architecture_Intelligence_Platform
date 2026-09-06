from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str]