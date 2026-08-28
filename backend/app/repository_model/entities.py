from dataclasses import dataclass, field
from typing import Any

from app.repository_model.enums import EntityKind
from app.repository_model.locations import SourceLocation
from app.repository_model.signatures import (
    GenericParameter,
    Parameter,
)
from app.repository_model.types import TypeReference


@dataclass
class Entity:
    id: str
    kind: EntityKind

    name: str
    qualified_name: str | None = None

    location: SourceLocation | None = None

    language: str | None = None

    parameters: list[Parameter] = field(
        default_factory=list
    )

    return_type: TypeReference | None = None

    generic_parameters: list[GenericParameter] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )