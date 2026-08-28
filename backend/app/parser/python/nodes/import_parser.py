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
    location
)


class PythonImportParser:

    def parse_import(
        self,
        node: ast.Import,
        path: Path,
        parent_id: str,
        model: RepositoryModel,
    ):

        for alias in node.names:

            self._create_import(
                name=alias.name,
                display_name=alias.asname or alias.name,
                node=node,
                path=path,
                parent_id=parent_id,
                model=model,
            )
    
    def parse_import_from(
        self,
        node: ast.ImportFrom,
        path: Path,
        parent_id: str,
        model: RepositoryModel,
    ):

        module = node.module or ""

        for alias in node.names:

            if alias.name == "*":
                imported_name = module
            elif module:
                imported_name = (
                    f"{module}.{alias.name}"
                )
            else:
                imported_name = alias.name

            self._create_import(
                name=imported_name,
                display_name=alias.asname or alias.name,
                node=node,
                path=path,
                parent_id=parent_id,
                model=model,
            )

    def _create_import(
        self,
        name: str,
        display_name: str,
        node,
        path: Path,
        parent_id: str,
        model: RepositoryModel,
    ):

        entity_id = (
            f"import:{name}"
        )

        entity = Entity(
            id=entity_id,
            kind=EntityKind.IMPORT,
            name=display_name,
            qualified_name=name,
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
                kind=RelationshipKind.IMPORTS,
            )
        )
