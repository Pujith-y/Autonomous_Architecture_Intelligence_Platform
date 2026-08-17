from dataclasses import dataclass, field

from app.repository_model.entities import Entity
from app.repository_model.relationships import Relationship


@dataclass
class RepositoryModel:
    name: str

    entities: list[Entity] = field(
        default_factory=list
    )

    relationships: list[Relationship] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )