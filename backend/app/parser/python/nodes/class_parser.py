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

from app.parser.python.nodes.decorator_parser import (
    PythonDecoratorParser,
)

from app.parser.python.utils.ast_utils import (
    location,
    attribute_name
)

class PythonClassParser:

    def __init__(
        self,
        decorator_parser: PythonDecoratorParser,
    ):
        self.decorator_parser = decorator_parser

    def parse_class(
        self,
        node: ast.ClassDef,
        path: Path,
        parent_id: str,
        parent_qualified_name: str,
        model: RepositoryModel,
        parse_body,
    ):

        qualified_name = (
            f"{parent_qualified_name}.{node.name}"
        )

        entity_id = (
            f"class:{qualified_name}"
        )

        entity = Entity(
            id=entity_id,
            kind=EntityKind.CLASS,
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

        self.decorator_parser.parse_decorators(
            node=node,
            entity=entity,
            model=model,
            path=path,
        )

        self._parse_inheritance(
            node=node,
            class_id=entity_id,
            model=model,
        )

        parse_body(
            body=node.body,
            path=path,
            model=model,
            parent=entity,
        )

        return entity

    def _parse_inheritance(
        self,
        node: ast.ClassDef,
        class_id: str,
        model: RepositoryModel,
    ):

        for base in node.bases:

            base_name = self._type_name(
                base,
            )

            if not base_name:
                continue

            base_id = (
                f"class:{base_name}"
            )

            model.relationships.append(
                Relationship(
                    source_id=class_id,
                    target_id=base_id,
                    kind=RelationshipKind.INHERITS,
                )
            )

    def _type_name(
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
            return attribute_name(
                node,
            )

        if isinstance(
            node,
            ast.Subscript,
        ):

            base = self._type_name(
                node.value,
            )

            if base is None:
                return None

            return base

        if isinstance(
            node,
            ast.Constant,
        ):

            if isinstance(
                node.value,
                str,
            ):
                return node.value

        return None
