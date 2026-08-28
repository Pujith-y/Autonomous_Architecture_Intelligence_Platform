import ast

from app.repository_model import TypeReference


class PythonTypeParser:

    def _type_reference(
            self,
            node,
        ) -> TypeReference | None:
    
            if node is None:
                return None
    
            # Simple name
            if isinstance(node, ast.Name):
    
                return TypeReference(
                    name=node.id,
                )
    
            # Qualified name
            if isinstance(node, ast.Attribute):
    
                qualified_name = self._attribute_name(
                    node
                )
    
                return TypeReference(
                    name=node.attr,
                    qualified_name=qualified_name,
                )
    
            # Generic types
            if isinstance(node, ast.Subscript):
    
                base = self._type_reference(
                    node.value
                )
    
                if base is None:
                    return None
    
                arguments = self._subscript_arguments(
                    node.slice
                )
    
                # Optional[User]
                if (
                    base.name == "Optional"
                    and len(arguments) == 1
                ):
    
                    inner = arguments[0]
    
                    return TypeReference(
                        name=inner.name,
                        qualified_name=inner.qualified_name,
                        generic_arguments=(
                            inner.generic_arguments
                        ),
                        union_types=(
                            inner.union_types
                        ),
                        is_optional=True,
                        is_collection=(
                            inner.is_collection
                        ),
                        metadata=inner.metadata,
                    )
    
                return TypeReference(
                    name=base.name,
                    qualified_name=base.qualified_name,
                    generic_arguments=tuple(
                        arguments
                    ),
                    is_optional=base.is_optional,
                    is_collection=self._is_collection_type(
                        base.name
                    ),
                    metadata=base.metadata,
                )
    
            # Union types
            #
            # User | Admin
            # int | float | str
            # User | None
            if isinstance(node, ast.BinOp):
    
                if isinstance(node.op, ast.BitOr):
    
                    types = self._union_types(node)
    
                    non_none_types = [
                        type_reference
                        for type_reference in types
                        if (
                            type_reference is not None
                            and type_reference.name != "None"
                        )
                    ]
    
                    contains_none = (
                        len(non_none_types)
                        < len(types)
                    )
    
                    # User | None
                    if (
                        contains_none
                        and len(non_none_types) == 1
                    ):
    
                        inner = non_none_types[0]
    
                        return TypeReference(
                            name=inner.name,
                            qualified_name=(
                                inner.qualified_name
                            ),
                            generic_arguments=(
                                inner.generic_arguments
                            ),
                            union_types=(
                                inner.union_types
                            ),
                            is_optional=True,
                            is_collection=(
                                inner.is_collection
                            ),
                            metadata=inner.metadata,
                        )
    
                    # User | Admin
                    # int | float | str
                    if len(non_none_types) >= 2:
    
                        return TypeReference(
                            name="union",
                            union_types=tuple(
                                non_none_types
                            ),
                        )
    
            # None
            if (
                isinstance(node, ast.Constant)
                and node.value is None
            ):
    
                return TypeReference(
                    name="None",
                )
    
            return None

    def _attribute_name(
            self,
            node,
        ) -> str:
    
            parts = []
    
            current = node
    
            while isinstance(
                current,
                ast.Attribute,
            ):
    
                parts.append(
                    current.attr
                )
    
                current = current.value
    
            if isinstance(
                current,
                ast.Name,
            ):
    
                parts.append(
                    current.id
                )
    
            parts.reverse()
    
            return ".".join(parts)

    def _subscript_arguments(
            self,
            node,
        ) -> list[TypeReference]:
    
            if isinstance(
                node,
                ast.Tuple,
            ):
    
                arguments = node.elts
    
            else:
    
                arguments = [node]
    
            result = []
    
            for argument in arguments:
    
                type_reference = (
                    self._type_reference(
                        argument
                    )
                )
    
                if type_reference is not None:
                    result.append(
                        type_reference
                    )
    
            return result

    def _union_types(
            self,
            node,
        ) -> list[TypeReference | None]:
    
            if (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.BitOr)
            ):
    
                return (
                    self._union_types(node.left)
                    + self._union_types(node.right)
                )
    
            return [
                self._type_reference(node)
            ]

    def _is_collection_type(
            self,
            name: str,
        ) -> bool:
    
            return name.lower() in {
                "list",
                "set",
                "frozenset",
                "tuple",
                "sequence",
                "iterable",
                "iterator",
                "collection",
            }