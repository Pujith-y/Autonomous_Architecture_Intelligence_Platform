from dataclasses import dataclass
from pathlib import Path

from app.ingestion.repository_source import RepositorySource


@dataclass
class Repository:
    name: str
    path: Path
    source: RepositorySource
    