import ast
from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
    RepositoryModel,
    Parameter,
)

from app.parser.python.types.type_parser import (
    PythonTypeParser,
)

from app.parser.python.utils.ast_utils import (
    location,
    attribute_name,
)

class PythonFunctionParser:

    def __init__(
        self,
        type_parser: PythonTypeParser,
    ):
        self.type_parser = type_parser

    def parse_function(
        self,
        node,
        path: Path,
        parent_id: str,
        parent_qualified_name: str,
        model: RepositoryModel,
    ):
        qualified_name = f"{parent_qualified_name}.{node.name}"

        entity_id = f"function:{qualified_name}"

        entity = Entity(
            id=entity_id,
            kind=EntityKind.FUNCTION,
            name=node.name,
            qualified_name=qualified_name,
            location=location(path, node),
            language="python",
        )

        self.parse_signature(
            node=node,
            entity=entity,
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

    def parse_method(
        self,
        node,
        path: Path,
        class_id: str,
        class_qualified_name: str,
        model: RepositoryModel,
    ):
        qualified_name = f"{class_qualified_name}.{node.name}"

        entity_id = f"method:{qualified_name}"

        entity = Entity(
            id=entity_id,
            kind=EntityKind.METHOD,
            name=node.name,
            qualified_name=qualified_name,
            location=location(path, node),
            language="python",
        )

        self.parse_signature(
            node=node,
            entity=entity,
        )

        model.entities.append(entity)

        model.relationships.append(
            Relationship(
                source_id=class_id,
                target_id=entity_id,
                kind=RelationshipKind.CONTAINS,
            )
        )

        return entity

    def parse_signature(
        self,
        node,
        entity: Entity,
    ):

        arguments = node.args

        positional_arguments = (
            arguments.posonlyargs
            + arguments.args
        )

        defaults = (
            [None]
            * (
                len(positional_arguments)
                - len(arguments.defaults)
            )
            + list(arguments.defaults)
        )

        # *args
        if arguments.vararg is not None:

            argument = arguments.vararg

            entity.parameters.append(
                Parameter(
                    name=argument.arg,
                    type=self.type_parser._type_reference(
                        argument.annotation,
                    ),
                    default_value=None,
                    is_variadic=True,
                    is_keyword_only=False,
                )
            )

        # Positional / normal arguments
        for argument, default in zip(
            positional_arguments,
            defaults,
        ):

            entity.parameters.append(
                Parameter(
                    name=argument.arg,
                    type=self.type_parser._type_reference(
                        argument.annotation,
                    ),
                    default_value=self._expression_name(
                        default,
                    ),
                )
            )

        # Keyword-only arguments
        for argument, default in zip(
            arguments.kwonlyargs,
            arguments.kw_defaults,
        ):

            entity.parameters.append(
                Parameter(
                    name=argument.arg,
                    type=self.type_parser._type_reference(
                        argument.annotation,
                    ),
                    default_value=self._expression_name(
                        default,
                    ),
                    is_keyword_only=True,
                )
            )

        # **kwargs
        if arguments.kwarg is not None:

            argument = arguments.kwarg

            entity.parameters.append(
                Parameter(
                    name=argument.arg,
                    type=self.type_parser._type_reference(
                        argument.annotation,
                    ),
                    default_value=None,
                    is_variadic=True,
                    is_keyword_only=False,
                )
            )

        # Return type
        if node.returns is not None:

            entity.return_type = (
                self.type_parser._type_reference(
                    node.returns,
                )
            )

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

    