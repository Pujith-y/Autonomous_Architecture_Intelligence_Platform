from dataclasses import dataclass, field
from pathlib import Path

from app.discovery.models import (
    DiscoveredFile,
    DiscoveredDirectory,
)
from app.discovery.repository_analyzer import (
    RepositoryMetadata,
)


@dataclass
class RepositoryModel:
    name: str
    path: Path

    files: list[DiscoveredFile] = field(
        default_factory=list
    )

    directories: list[DiscoveredDirectory] = field(
        default_factory=list
    )

    metadata: RepositoryMetadata | None = None

    languages: dict[str, int] = field(
        default_factory=dict
    )

    frameworks: list[str] = field(
        default_factory=list
    )