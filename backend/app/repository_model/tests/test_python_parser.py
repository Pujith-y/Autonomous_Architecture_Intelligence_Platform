from pathlib import Path

from app.parser.python.parser import (
    PythonRepositoryParser,
)
from app.repository_model import (
    EntityKind,
    RelationshipKind,
)


def test_parser_detects_function(tmp_path):

    source = """
def create_user():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    functions = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    ]

    assert len(functions) == 1

    function = functions[0]

    assert function.name == "create_user"
    assert function.qualified_name == "service.create_user"


def test_parser_distinguishes_function_and_method(
    tmp_path,
):

    source = """
def create_user():
    pass


class UserService:

    def get_user(self):
        pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    functions = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    ]

    methods = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.METHOD
    ]

    assert len(functions) == 1
    assert functions[0].name == "create_user"

    assert len(methods) == 1
    assert methods[0].name == "get_user"


def test_parser_creates_method_relationship(
    tmp_path,
):

    source = """
class UserService:

    def get_user(self):
        pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    user_service = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.CLASS
            and entity.name == "UserService"
        )
    )

    get_user = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.METHOD
            and entity.name == "get_user"
        )
    )

    assert any(
        relationship.source_id == user_service.id
        and relationship.target_id == get_user.id
        and relationship.kind
        == RelationshipKind.CONTAINS
        for relationship in model.relationships
    )

def test_parser_detects_inheritance(
    tmp_path,
):

    source = """
class UserService(BaseService):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    relationships = [
        relationship
        for relationship in model.relationships
        if relationship.kind
        == RelationshipKind.INHERITS
    ]

    assert len(relationships) == 1

    relationship = relationships[0]

    assert (
        relationship.source_id
        == "class:service.UserService"
    )

    assert (
        relationship.target_id
        == "class:BaseService"
    )

def test_parser_extracts_function_parameters(
    tmp_path,
):

    source = """
def get_user(
    user_id: int,
    username: str,
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    assert len(function.parameters) == 2

    assert (
        function.parameters[0].name
        == "user_id"
    )

    assert (
        function.parameters[0].type.name
        == "int"
    )

    assert (
        function.parameters[1].name
        == "username"
    )

    assert (
        function.parameters[1].type.name
        == "str"
    )

def test_parser_extracts_function_parameters(
    tmp_path,
):

    source = """
def get_user(
    user_id: int,
    username: str,
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    assert len(function.parameters) == 2

    assert (
        function.parameters[0].name
        == "user_id"
    )

    assert (
        function.parameters[0].type.name
        == "int"
    )

    assert (
        function.parameters[1].name
        == "username"
    )

    assert (
        function.parameters[1].type.name
        == "str"
    )

def test_parser_extracts_default_parameters(
    tmp_path,
):

    source = """
def search(
    query,
    limit=10,
    offset=0,
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    assert len(function.parameters) == 3

    assert (
        function.parameters[0].default_value
        is None
    )

    assert (
        function.parameters[1].default_value
        == "10"
    )

    assert (
        function.parameters[2].default_value
        == "0"
    )

def test_parser_extracts_keyword_only_parameters(
    tmp_path,
):

    source = """
def search(
    query,
    *,
    limit=10,
    offset=0,
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    parameters = {
        parameter.name: parameter
        for parameter in function.parameters
    }

    assert "query" in parameters
    assert "limit" in parameters
    assert "offset" in parameters

    assert (
        parameters["limit"].default_value
        == "10"
    )

    assert (
        parameters["offset"].default_value
        == "0"
    )

def test_parser_detects_imports(
    tmp_path,
):

    source = """
import os
import json

from app.models import User
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    imports = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.IMPORT
    ]

    assert len(imports) == 3

    names = {
        entity.qualified_name
        for entity in imports
    }

    assert "os" in names
    assert "json" in names
    assert "app.models.User" in names


def test_parser_detects_class_fields(
    tmp_path,
):

    source = """
class User:

    name = "Pujith"
    age = 20
"""

    path = tmp_path / "models.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    fields = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FIELD
    ]

    assert len(fields) == 2

    names = {
        field.name
        for field in fields
    }

    assert names == {
        "name",
        "age",
    }

def test_parser_detects_annotated_fields(
    tmp_path,
):

    source = """
class User:

    name: str
    age: int
"""

    path = tmp_path / "models.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    fields = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FIELD
    ]

    assert len(fields) == 2

    names = {
        field.name
        for field in fields
    }

    assert names == {
        "name",
        "age",
    }

def test_parser_detects_function_calls(
    tmp_path,
):

    source = """
def create_user():
    validate_user()
    save_user()
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    calls = [
        relationship
        for relationship in model.relationships
        if relationship.kind
        == RelationshipKind.CALLS
    ]

    assert len(calls) == 2

    targets = {
        relationship.target_id
        for relationship in calls
    }

    assert "function:validate_user" in targets
    assert "function:save_user" in targets


def test_parser_detects_attribute_calls(
    tmp_path,
):

    source = """
class UserService:

    def get_user(self):
        return self.repository.find()
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    calls = [
        relationship
        for relationship in model.relationships
        if relationship.kind
        == RelationshipKind.CALLS
    ]

    assert len(calls) == 1

    assert (
        calls[0].target_id
        == "function:self.repository.find"
    )

def test_parser_records_source_location(
    tmp_path,
):

    source = """


class UserService:
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    entity = next(
        entity
        for entity in model.entities
        if entity.name == "UserService"
    )

    assert (
        entity.location.file
        == path
    )

    assert entity.location.start_line == 4
    assert entity.location.end_line == 5

def test_parser_extracts_variadic_parameters(
    tmp_path,
):

    source = """
def log(message, *args, **kwargs):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    parameters = {
        parameter.name: parameter
        for parameter in function.parameters
    }

    assert "message" in parameters
    assert "args" in parameters
    assert "kwargs" in parameters

    assert (
        parameters["message"].is_variadic
        is False
    )

    assert (
        parameters["args"].is_variadic
        is True
    )

    assert (
        parameters["kwargs"].is_variadic
        is True
    )

def test_parser_extracts_complex_function_signature(
    tmp_path,
):

    source = """
def search(
    query: str,
    *fields,
    limit: int = 10,
    **filters,
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    parameters = {
        parameter.name: parameter
        for parameter in function.parameters
    }

    assert parameters["query"].is_variadic is False
    assert parameters["query"].is_keyword_only is False

    assert parameters["fields"].is_variadic is True
    assert parameters["fields"].is_keyword_only is False

    assert parameters["limit"].is_variadic is False
    assert parameters["limit"].is_keyword_only is True
    assert parameters["limit"].default_value == "10"

    assert parameters["filters"].is_variadic is True
    assert parameters["filters"].is_keyword_only is False

def test_parser_extracts_simple_type_reference(
    tmp_path,
):

    source = """
def get_user(user: User):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    parameter = function.parameters[0]

    assert parameter.type is not None
    assert parameter.type.name == "User"
    assert parameter.type.qualified_name is None
    assert parameter.type.generic_arguments == ()


def test_parser_extracts_multiple_generic_arguments(
    tmp_path,
):

    source = """
def get_users(users: dict[str, User]):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = function.parameters[0].type

    assert type_reference is not None
    assert type_reference.name == "dict"

    assert len(
        type_reference.generic_arguments
    ) == 2

    assert (
        type_reference.generic_arguments[0].name
        == "str"
    )

    assert (
        type_reference.generic_arguments[1].name
        == "User"
    )

def test_parser_extracts_nested_generic_type(
    tmp_path,
):

    source = """
def get_users(
    users: dict[str, list[User]],
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = function.parameters[0].type

    assert type_reference is not None
    assert type_reference.name == "dict"

    assert len(
        type_reference.generic_arguments
    ) == 2

    key_type = (
        type_reference.generic_arguments[0]
    )

    value_type = (
        type_reference.generic_arguments[1]
    )

    assert key_type.name == "str"

    assert value_type.name == "list"

    assert len(
        value_type.generic_arguments
    ) == 1

    assert (
        value_type.generic_arguments[0].name
        == "User"
    )

def test_parser_extracts_optional_union_type(
    tmp_path,
):

    source = """
def get_user(user: User | None):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = function.parameters[0].type

    assert type_reference is not None
    assert type_reference.name == "User"
    assert type_reference.is_optional is True

def test_parser_extracts_optional_generic_type(
    tmp_path,
):

    source = """
from typing import Optional

def get_user(user: Optional[User]):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = function.parameters[0].type

    assert type_reference is not None
    assert type_reference.name == "User"
    assert type_reference.is_optional is True

def test_parser_marks_collection_types(
    tmp_path,
):

    source = """
def get_users(users: list[User]):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = function.parameters[0].type

    assert type_reference is not None
    assert type_reference.name == "list"
    assert type_reference.is_collection is True

def test_parser_extracts_generic_return_type(
    tmp_path,
):

    source = """
def get_users() -> list[User]:
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    return_type = function.return_type

    assert return_type is not None
    assert return_type.name == "list"

    assert len(
        return_type.generic_arguments
    ) == 1

    assert (
        return_type.generic_arguments[0].name
        == "User"
    )


def test_parser_extracts_union_type(
    tmp_path,
):

    source = """
def get_user(user: User | Admin):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = (
        function.parameters[0].type
    )

    assert type_reference is not None
    assert type_reference.name == "union"

    assert len(
        type_reference.union_types
    ) == 2

    assert (
        type_reference.union_types[0].name
        == "User"
    )

    assert (
        type_reference.union_types[1].name
        == "Admin"
    )

def test_optional_union_is_not_general_union(
    tmp_path,
):

    source = """
def get_user(user: User | None):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = (
        function.parameters[0].type
    )

    assert type_reference is not None

    assert type_reference.name == "User"

    assert (
        type_reference.is_optional
        is True
    )

    assert (
        type_reference.union_types
        == ()
    )

def test_parser_extracts_nested_union_type(
    tmp_path,
):

    source = """
def get_users(
    users: list[User | Admin],
):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = (
        function.parameters[0].type
    )

    assert type_reference is not None

    assert type_reference.name == "list"

    assert (
        type_reference.is_collection
        is True
    )

    assert len(
        type_reference.generic_arguments
    ) == 1

    union = (
        type_reference.generic_arguments[0]
    )

    assert union.name == "union"

    assert len(
        union.union_types
    ) == 2

    assert (
        union.union_types[0].name
        == "User"
    )

    assert (
        union.union_types[1].name
        == "Admin"
    )

def test_parser_extracts_three_way_union(
    tmp_path,
):

    source = """
def parse(value: int | float | str):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    type_reference = (
        function.parameters[0].type
    )

    assert type_reference is not None
    assert type_reference.name == "union"

    assert len(
        type_reference.union_types
    ) == 3

    assert [
        type_reference.name
        for type_reference
        in type_reference.union_types
    ] == [
        "int",
        "float",
        "str",
    ]

def test_parser_creates_module_entity(tmp_path):

    source = """
class UserService:
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    module = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.MODULE
    )

    assert module.name == "service"
    assert module.qualified_name == "service"
    assert module.id == "module:service"

def test_parser_module_contains_class(tmp_path):

    source = """
class UserService:
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    module = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.MODULE
    )

    user_service = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.CLASS
    )

    relationship = next(
        relationship
        for relationship in model.relationships
        if (
            relationship.source_id
            == module.id
            and relationship.target_id
            == user_service.id
            and relationship.kind
            == RelationshipKind.CONTAINS
        )
    )

    assert relationship is not None

def test_parser_builds_qualified_class_name(
    tmp_path,
):

    source = """
class UserService:
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    user_service = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.CLASS
    )

    assert (
        user_service.qualified_name
        == "service.UserService"
    )

    assert (
        user_service.id
        == "class:service.UserService"
    )

def test_parser_module_contains_top_level_function(
    tmp_path,
):

    source = """
def create_user():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    module = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.MODULE
    )

    function = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    )

    assert function.qualified_name == (
        "service.create_user"
    )

    assert function.id == (
        "function:service.create_user"
    )

    assert any(
        relationship.source_id == module.id
        and relationship.target_id == function.id
        and relationship.kind
        == RelationshipKind.CONTAINS
        for relationship in model.relationships
    )

def test_parser_detects_nested_class(tmp_path):

    source = """
class UserService:

    class Cache:
        pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    classes = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.CLASS
    ]

    assert len(classes) == 2

    outer = next(
        entity
        for entity in classes
        if entity.name == "UserService"
    )

    inner = next(
        entity
        for entity in classes
        if entity.name == "Cache"
    )

    assert outer.qualified_name == (
        "service.UserService"
    )

    assert inner.qualified_name == (
        "service.UserService.Cache"
    )

    assert any(
        relationship.source_id == outer.id
        and relationship.target_id == inner.id
        and relationship.kind
        == RelationshipKind.CONTAINS
        for relationship in model.relationships
    )

def test_parser_detects_nested_function(tmp_path):

    source = """
def get_user():

    def validate():
        pass

    return validate()
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    functions = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.FUNCTION
    ]

    assert len(functions) == 2

    outer = next(
        entity
        for entity in functions
        if entity.name == "get_user"
    )

    inner = next(
        entity
        for entity in functions
        if entity.name == "validate"
    )

    assert outer.qualified_name == (
        "service.get_user"
    )

    assert inner.qualified_name == (
        "service.get_user.validate"
    )

    assert any(
        relationship.source_id == outer.id
        and relationship.target_id == inner.id
        and relationship.kind
        == RelationshipKind.CONTAINS
        for relationship in model.relationships
    )

def test_parser_handles_nested_class_and_method(
    tmp_path,
):

    source = """
class Outer:

    class Inner:

        def run(self):
            pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    inner = next(
        entity
        for entity in model.entities
        if entity.name == "Inner"
    )

    method = next(
        entity
        for entity in model.entities
        if entity.name == "run"
    )

    assert inner.qualified_name == (
        "service.Outer.Inner"
    )

    assert method.qualified_name == (
        "service.Outer.Inner.run"
    )

    assert any(
        relationship.source_id == inner.id
        and relationship.target_id == method.id
        and relationship.kind
        == RelationshipKind.CONTAINS
        for relationship in model.relationships
    )

def test_parser_detects_function_decorator(tmp_path):

    source = """
@staticmethod
def get_user():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorator = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.DECORATOR
            and entity.name == "staticmethod"
        )
    )

    assert decorator is not None


def test_parser_creates_decorator_relationship(tmp_path):

    source = """
@staticmethod
def get_user():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    function = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.FUNCTION
            and entity.name == "get_user"
        )
    )

    decorator = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.DECORATOR
            and entity.name == "staticmethod"
        )
    )

    assert any(
        relationship.source_id == function.id
        and relationship.target_id == decorator.id
        and relationship.kind
        == RelationshipKind.DECORATED_BY
        for relationship in model.relationships
    )


def test_parser_detects_qualified_decorator(tmp_path):

    source = """
@app.get("/users")
def get_users():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorator = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.DECORATOR
    )

    assert decorator.name == "get"
    assert decorator.qualified_name == "app.get"


def test_parser_detects_multiple_decorators(tmp_path):

    source = """
@router.get("/users")
@authenticated
def get_users():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorators = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.DECORATOR
    ]

    assert len(decorators) == 2

    names = {
        decorator.qualified_name
        for decorator in decorators
    }

    assert names == {
        "router.get",
        "authenticated",
    }

def test_parser_extracts_decorator_arguments(tmp_path):

    source = """
@app.get("/users")
def get_users():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorator = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.DECORATOR
    )

    assert decorator.name == "get"

    assert decorator.metadata["arguments"] == [
        '"/users"',
    ]

def test_parser_extracts_decorator_keyword_arguments(
    tmp_path,
):

    source = """
@app.get(
    "/users",
    response_model=User,
)
def get_users():
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorator = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.DECORATOR
    )

    assert decorator.metadata["arguments"] == [
        '"/users"',
    ]

    assert decorator.metadata["keywords"][
        "response_model"
    ] == "User"

def test_parser_detects_class_decorator(
    tmp_path,
):

    source = """
@dataclass
class User:
    name: str
"""

    path = tmp_path / "models.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    user = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.CLASS
            and entity.name == "User"
        )
    )

    decorator = next(
        entity
        for entity in model.entities
        if (
            entity.kind == EntityKind.DECORATOR
            and entity.name == "dataclass"
        )
    )

    assert any(
        relationship.source_id == user.id
        and relationship.target_id == decorator.id
        and relationship.kind
        == RelationshipKind.DECORATED_BY
        for relationship
        in model.relationships
    )

def test_parser_extracts_complex_decorator(
    tmp_path,
):

    source = """
@router.get(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
)
def get_user(user_id: int):
    pass
"""

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    decorator = next(
        entity
        for entity in model.entities
        if entity.kind == EntityKind.DECORATOR
    )

    assert (
        decorator.qualified_name
        == "router.get"
    )

    assert decorator.metadata["arguments"] == [
        '"/users/{user_id}"',
    ]

    assert (
        decorator.metadata["keywords"][
            "response_model"
        ]
        == "User"
    )

    assert (
        decorator.metadata["keywords"]["tags"]
        == '["users"]'
    )

def test_parser_detects_local_variable(tmp_path):

    source = """
def get_user():
    user = User()
    return user
    """

    path = tmp_path / "service.py"

    path.write_text(
        source,
        encoding="utf-8",
    )

    model = PythonRepositoryParser().parse(path)

    variables = [
        entity
        for entity in model.entities
        if entity.kind == EntityKind.VARIABLE
    ]

    assert len(variables) == 1
    assert variables[0].name == "user"