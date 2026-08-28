from dataclasses import dataclass, field
from typing import Any

from app.repository_model.types import TypeReference


@dataclass(frozen=True)
class GenericParameter:
    name: str

    constraints: tuple[TypeReference, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class Parameter:
    name: str

    type: TypeReference | None = None

    default_value: str | None = None

    is_variadic: bool = False

    is_keyword_only: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )