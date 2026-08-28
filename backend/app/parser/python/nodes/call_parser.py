import ast

from app.repository_model import (
    Relationship,
    RelationshipKind,
    RepositoryModel,
)

from app.parser.python.utils.ast_utils import (
    attribute_name,
)

class PythonCallParser:

    def parse_calls(
        self,
        node,
        function_id: str,
        model: RepositoryModel,
    ):
        for child in ast.walk(node):

            if not isinstance(
                child,
                ast.Call,
            ):
                continue

            called_name = self._call_name(
                child.func,
            )

            if not called_name:
                continue

            target_id = (
                f"function:{called_name}"
            )

            model.relationships.append(
                Relationship(
                    source_id=function_id,
                    target_id=target_id,
                    kind=RelationshipKind.CALLS,
                )
            )

    def _call_name(
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
            return attribute_name(node)

        return None
