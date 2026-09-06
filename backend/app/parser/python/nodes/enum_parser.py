import ast
from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
    RepositoryModel,
    SourceLocation,
)

from app.parser.python.utils.ast_utils import (
    location,
    attribute_name,
)

class PythonEnumParser:

    def parse_enum(
        self,
        node: ast.ClassDef,
        path: Path,
        parent_id: str,
        parent_qualified_name: str,
        model: RepositoryModel,
    ) -> Entity:

        qualified_name = (
            f"{parent_qualified_name}.{node.name}"
        )

        entity_id = (
            f"enum:{qualified_name}"
        )

        entity = Entity(
            id=entity_id,
            kind=EntityKind.ENUM,
            name=node.name,
            qualified_name=qualified_name,
            location=location(
                path,
                node,
            ),
            language="python",
        )

        model.entities.append(entity)

        model.relationships.append(
            Relationship(
                source_id=parent_id,
                target_id=entity_id,
                kind=RelationshipKind.CONTAINS,
            )
        )

        return entity

    def is_enum(
        self,
        node: ast.ClassDef,
    ) -> bool:

        for base in node.bases:

            base_name = self._base_name(base)

            if base_name in {
                "Enum",
                "IntEnum",
                "StrEnum",
                "Flag",
                "IntFlag",
            }:
                return True

        return False

    def _base_name(
        self,
        node,
    ) -> str | None:

        if isinstance(
            node,
            ast.Name,
        ):
            return node.id

        if isinstance(
            node,
            ast.Attribute,
        ):

            return node.attr

        return None
