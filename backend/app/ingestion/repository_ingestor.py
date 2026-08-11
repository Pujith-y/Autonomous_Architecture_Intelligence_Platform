from pathlib import Path

import tempfile

from git import Repo, GitCommandError


from app.ingestion.models import Repository
from app.ingestion.repository_source import (
    RepositorySource,
    RepositorySourceType,
)


class RepositoryIngestor:

    def ingest(self, source: RepositorySource) -> Repository:

        if source.source_type == RepositorySourceType.LOCAL:
            return self._open_local(source)

        if source.source_type == RepositorySourceType.GIT:
            return self._clone_git(source)

        raise ValueError(
            f"Unsupported repository source: {source.source_type}"
        )

    def _open_local(self, source: RepositorySource) -> Repository:

        path = Path(source.location)

        if not path.exists():
            raise FileNotFoundError(
                f"Repository path does not exist: {path}"
            )

        if not path.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {path}"
            )

        return Repository(
            name=path.name,
            path=path,
            source=source,
        )

    def _clone_git(self, source: RepositorySource) -> Repository:

        clone_path = Path(
            tempfile.mkdtemp(prefix="aaip_")
        )

        clone_kwargs = {}

        if source.branch:
            clone_kwargs["branch"] = source.branch

        if source.shallow:
            clone_kwargs["depth"] = 1

        try:
            Repo.clone_from(
                source.location,
                clone_path,
                **clone_kwargs
            )

        except GitCommandError as e:
            raise RuntimeError(
                f"Failed to clone repository: {source.location}"
            ) from e

        return Repository(
            name=clone_path.name,
            path=clone_path,
            source=source,
        )