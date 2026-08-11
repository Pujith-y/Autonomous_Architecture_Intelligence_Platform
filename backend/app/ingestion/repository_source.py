from dataclasses import dataclass
from enum import Enum


class RepositorySourceType(Enum):
    LOCAL = "local"
    GIT = "git"


@dataclass
class RepositorySource:
    source_type: RepositorySourceType
    location: str
    branch: str | None = None
    shallow: bool = False