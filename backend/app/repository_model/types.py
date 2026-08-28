from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TypeReference:
    name: str

    qualified_name: str | None = None

    generic_arguments: tuple["TypeReference", ...] = ()

    union_types: tuple["TypeReference", ...] = ()

    is_optional: bool = False

    is_collection: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )