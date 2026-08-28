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


class PythonVariableParser:

    def parse_variable(
        self,
        node,
        path: Path,
        function_id: str,
        function_qualified_name: str,
        model: RepositoryModel,
    ):

        for target in node.targets:

            if not isinstance(target, ast.Name):
                continue

            qualified_name = (
                f"{function_qualified_name}.{target.id}"
            )

            entity_id = (
                f"variable:{qualified_name}"
            )

            entity = Entity(
                id=entity_id,
                kind=EntityKind.VARIABLE,
                name=target.id,
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
                    source_id=function_id,
                    target_id=entity_id,
                    kind=RelationshipKind.CONTAINS,
                )
            )