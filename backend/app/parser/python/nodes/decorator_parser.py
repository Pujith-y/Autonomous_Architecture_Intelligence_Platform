import ast
from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
)

from app.parser.python.utils.ast_utils import (
    location,
    attribute_name,
)



class PythonDecoratorParser:

    def parse_decorators(
        self,
        node,
        entity,
        model,
        path,
    ):

        for decorator_node in node.decorator_list:

            decorator_name = self._decorator_name(
                decorator_node
            )

            if decorator_name is None:
                continue

            metadata = {}

            if isinstance(
                decorator_node,
                ast.Call,
            ):

                metadata = {
                    "arguments": [
                        self._expression_name(
                            argument
                        )
                        for argument
                        in decorator_node.args
                    ],
                    "keywords": {
                        keyword.arg:
                        self._expression_name(
                            keyword.value
                        )
                        for keyword
                        in decorator_node.keywords
                        if keyword.arg is not None
                    },
                }

            decorator_id = (
                "decorator:"
                + decorator_name
            )

            decorator_entity = next(
                (
                    existing
                    for existing in model.entities
                    if existing.id
                    == decorator_id
                ),
                None,
            )

            if decorator_entity is None:

                decorator_entity = Entity(
                    id=decorator_id,
                    kind=EntityKind.DECORATOR,
                    name=decorator_name.split(".")[-1],
                    qualified_name=decorator_name,
                    location=location(
                        path,
                        decorator_node,
                    ),
                    language="python",
                    metadata=metadata,
                )

                model.entities.append(
                    decorator_entity
                )

            model.relationships.append(
                Relationship(
                    source_id=entity.id,
                    target_id=decorator_entity.id,
                    kind=RelationshipKind.DECORATED_BY,
                )
            )

    def _decorator_name(
        self,
        node,
    ):

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            return attribute_name(node)

        if isinstance(node, ast.Call):
            return self._decorator_name(
                node.func
            )

        return None


    def _expression_name(
        self,
        node,
    ):

        if node is None:
            return None

        if isinstance(node, ast.Constant):

            if isinstance(node.value, str):

                return (
                    '"'
                    + node.value.replace(
                        "\\",
                        "\\\\",
                    ).replace(
                        '"',
                        '\\"',
                    )
                    + '"'
                )

            return str(node.value)

        if isinstance(node, ast.Name):

            return node.id

        if isinstance(node, ast.Attribute):

            return attribute_name(node)

        if isinstance(node, ast.Call):

            return self._expression_name(
                node.func,
            )

        if isinstance(node, ast.List):

            values = [
                self._expression_name(
                    element,
                )
                for element in node.elts
            ]

            return (
                "["
                + ", ".join(values)
                + "]"
            )

        if isinstance(node, ast.Tuple):

            values = [
                self._expression_name(
                    element,
                )
                for element in node.elts
            ]

            return (
                "("
                + ", ".join(values)
                + ")"
            )

        if isinstance(node, ast.Dict):

            values = []

            for key, value in zip(
                node.keys,
                node.values,
            ):

                key_name = self._expression_name(
                    key,
                )

                value_name = self._expression_name(
                    value,
                )

                values.append(
                    f"{key_name}: {value_name}"
                )

            return (
                "{"
                + ", ".join(values)
                + "}"
            )

        return ast.unparse(node)
