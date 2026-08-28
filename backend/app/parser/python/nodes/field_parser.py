import ast
from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
    RepositoryModel,
)

from app.parser.python.utils.ast_utils import (
    location,
)


class PythonFieldParser:

    def parse_field(
        self,
        node: ast.Assign,
        path: Path,
        class_id: str,
        class_qualified_name: str,
        model: RepositoryModel,
    ):
        for target in node.targets:

            if not isinstance(
                target,
                ast.Name,
            ):
                continue

            self._create_field(
                name=target.id,
                path=path,
                node=node,
                class_id=class_id,
                class_qualified_name=class_qualified_name,
                model=model,
            )

    def parse_annotated_field(
        self,
        node: ast.AnnAssign,
        path: Path,
        class_id: str,
        class_qualified_name: str,
        model: RepositoryModel,
    ):
        if not isinstance(
            node.target,
            ast.Name,
        ):
            return

        self._create_field(
            name=node.target.id,
            path=path,
            node=node,
            class_id=class_id,
            class_qualified_name=class_qualified_name,
            model=model,
        )

    def _create_field(
        self,
        name: str,
        path: Path,
        node,
        class_id: str,
        class_qualified_name: str,
        model: RepositoryModel,
    ):
        qualified_name = (
            f"{class_qualified_name}.{name}"
        )

        entity_id = (
            f"field:{qualified_name}"
        )

        entity = Entity(
            id=entity_id,
            kind=EntityKind.FIELD,
            name=name,
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
                source_id=class_id,
                target_id=entity_id,
                kind=RelationshipKind.CONTAINS,
            )
        )