from dataclasses import dataclass, field
from typing import Any

from app.repository_model.enums import EntityKind
from app.repository_model.locations import SourceLocation


@dataclass
class Entity:
    id: str
    kind: EntityKind

    name: str
    qualified_name: str | None = None

    location: SourceLocation | None = None

    language: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )