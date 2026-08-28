import ast
from pathlib import Path

from app.parser.python.nodes.function_parser import (
    PythonFunctionParser,
)

from app.parser.python.nodes.decorator_parser import (
    PythonDecoratorParser,
)

from app.parser.python.nodes.call_parser import (
    PythonCallParser,
)

from app.parser.python.nodes.class_parser import (
    PythonClassParser,
)

from app.parser.python.nodes.field_parser import (
    PythonFieldParser,
)

from app.repository_model import (
    Entity,
    EntityKind,
    RepositoryModel,
)

from app.parser.python.types.type_parser import (
    PythonTypeParser,
)

from app.parser.python.nodes.import_parser import (
    PythonImportParser,
)


from app.parser.python.nodes.variable_parser import (
    PythonVariableParser,
)

from app.parser.python.utils.ast_utils import (
    location,
)

class PythonRepositoryParser:

    def __init__(self):
        self.type_parser = PythonTypeParser()
        self.function_parser = (
            PythonFunctionParser(
                type_parser=self.type_parser,
            )
        )

        self.decorator_parser = PythonDecoratorParser()

        self.import_parser = PythonImportParser()

        self.class_parser = PythonClassParser(
            decorator_parser=self.decorator_parser,
        )

        self.field_parser = PythonFieldParser()

        self.variable_parser = PythonVariableParser()

        self.call_parser = PythonCallParser()



    def parse(
        self,
        path: Path,
    ) -> RepositoryModel:

        source = path.read_text(
            encoding="utf-8",
        )

        tree = ast.parse(
            source,
            filename=str(path),
        )

        model = RepositoryModel(
            name=path.stem,
        )

        module_name = path.stem
        module_id = f"module:{module_name}"

        module = Entity(
            id=module_id,
            kind=EntityKind.MODULE,
            name=module_name,
            qualified_name=module_name,
            location=location(
                path,
                tree,
            ),
            language="python",
        )

        model.entities.append(module)

        self._parse_nodes(
            nodes=tree.body,
            path=path,
            parent_id=module_id,
            parent_qualified_name=module_name,
            model=model,
        )

        return model

  
    # Node traversal

    def _parse_nodes(
        self,
        nodes,
        path: Path,
        parent_id: str,
        parent_qualified_name: str,
        model: RepositoryModel,
    ):

        for node in nodes:

            if isinstance(
                node,
                ast.ClassDef,
            ):
                self.class_parser.parse_class(
                    node=node,
                    path=path,
                    parent_id=parent_id,
                    parent_qualified_name=parent_qualified_name,
                    model=model,
                    parse_body=self._parse_body,
                )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                self._parse_function(
                    node=node,
                    path=path,
                    parent_id=parent_id,
                    parent_qualified_name=parent_qualified_name,
                    model=model,
                )

            elif isinstance(
                node,
                ast.Import,
            ):
                self.import_parser.parse_import(
                    node=node,
                    path=path,
                    parent_id=parent_id,
                    model=model,
                )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                self.import_parser.parse_import_from(
                    node=node,
                    path=path,
                    parent_id=parent_id,
                    model=model,
                )


    def _parse_body(
        self,
        body,
        path: Path,
        model: RepositoryModel,
        parent: Entity,
    ):
        for node in body:

            if isinstance(node, ast.ClassDef):

                self.class_parser.parse_class(
                    node=node,
                    path=path,
                    parent_id=parent.id,
                    parent_qualified_name=parent.qualified_name,
                    model=model,
                    parse_body=self._parse_body,
                )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):

                if parent.kind == EntityKind.CLASS:

                    self._parse_method(
                        node=node,
                        path=path,
                        class_id=parent.id,
                        class_qualified_name=parent.qualified_name,
                        model=model,
                    )

                else:

                    self._parse_function(
                        node=node,
                        path=path,
                        parent_id=parent.id,
                        parent_qualified_name=parent.qualified_name,
                        model=model,
                    )

            elif (
                parent.kind == EntityKind.CLASS
                and isinstance(node, ast.AnnAssign)
            ):

                self.field_parser.parse_annotated_field(
                    node=node,
                    path=path,
                    class_id=parent.id,
                    class_qualified_name=parent.qualified_name,
                    model=model,
                )

            elif (
                parent.kind == EntityKind.CLASS
                and isinstance(node, ast.Assign)
            ):

                self.field_parser.parse_field(
                    node=node,
                    path=path,
                    class_id=parent.id,
                    class_qualified_name=parent.qualified_name,
                    model=model,
                )

            elif (
                parent.kind == EntityKind.FUNCTION
                and isinstance(node, ast.Assign)
            ):

                self.variable_parser.parse_variable(
                    node=node,
                    path=path,
                    function_id=parent.id,
                    function_qualified_name=parent.qualified_name,
                    model=model,
                )

    # Classes


    

    # Functions

    def _parse_function(
        self,
        node,
        path,
        parent_id,
        parent_qualified_name,
        model,
    ):

        entity = self.function_parser.parse_function(
            node=node,
            path=path,
            parent_id=parent_id,
            parent_qualified_name=parent_qualified_name,
            model=model,
        )

        self.decorator_parser.parse_decorators(
            node=node,
            entity=entity,
            model=model,
            path=path,
        )

        self.call_parser.parse_calls(
            node=node,
            function_id=entity.id,
            model=model,
        )

        self._parse_body(
            body=node.body,
            path=path,
            model=model,
            parent=entity,
        )


    # Methods

    def _parse_method(
        self,
        node,
        path,
        class_id,
        class_qualified_name,
        model,
    ):

        entity = self.function_parser.parse_method(
            node=node,
            path=path,
            class_id=class_id,
            class_qualified_name=class_qualified_name,
            model=model,
        )

        self.decorator_parser.parse_decorators(
            node=node,
            entity=entity,
            model=model,
            path=path,
        )

        self.call_parser.parse_calls(
            node=node,
            function_id=entity.id,
            model=model,
        )

        self._parse_body(
            body=node.body,
            path=path,
            model=model,
            parent=entity,
        )
