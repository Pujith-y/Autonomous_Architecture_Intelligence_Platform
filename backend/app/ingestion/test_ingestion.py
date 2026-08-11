from app.ingestion.repository_ingestor import RepositoryIngestor
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


source = RepositorySource(
    source_type=RepositorySourceType.GIT,
    location="https://github.com/Pujith-y/Local-Repo",
    branch="this-branch-does-not-exist"
)
ingestor = RepositoryIngestor()

repository = ingestor.ingest(source)

print(repository)