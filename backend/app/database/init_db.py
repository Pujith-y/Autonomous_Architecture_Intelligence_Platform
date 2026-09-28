from app.database.base import Base
from app.database.postgres import engine

from app.models.user_model import User
from app.models.repository_model import Repository
from app.models.indexing_run_model import IndexingRun

def init_db():
    Base.metadata.create_all(
        bind=engine
    )