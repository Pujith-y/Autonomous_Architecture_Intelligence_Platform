from dataclasses import dataclass, field
from typing import Any

from app.repository_model.enums import RelationshipKind


@dataclass
class Relationship:
    source_id: str
    target_id: str

    kind: RelationshipKind

    metadata: dict[str, Any] = field(
        default_factory=dict
    )