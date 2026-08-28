from pathlib import Path

from app.repository_model import (
    Entity,
    EntityKind,
    Relationship,
    RelationshipKind,
    RepositoryModel,
    SourceLocation,
    TypeReference,
    Parameter,
    GenericParameter,
)


def test_entity_creation():

    entity = Entity(
        id="class:user-service",
        kind=EntityKind.CLASS,
        name="UserService",
        qualified_name="app.services.UserService",
        language="Python",
    )

    assert entity.id == "class:user-service"
    assert entity.kind == EntityKind.CLASS
    assert entity.name == "UserService"
    assert entity.qualified_name == (
        "app.services.UserService"
    )
    assert entity.language == "Python"


def test_source_location():

    location = SourceLocation(
        file=Path(
            "app/services/user_service.py"
        ),
        start_line=10,
        end_line=50,
        start_column=1,
        end_column=20,
    )

    assert location.file == Path(
        "app/services/user_service.py"
    )

    assert location.start_line == 10
    assert location.end_line == 50
    assert location.start_column == 1
    assert location.end_column == 20


def test_relationship_creation():

    relationship = Relationship(
        source_id="class:user-service",
        target_id="class:base-service",
        kind=RelationshipKind.INHERITS,
    )

    assert relationship.source_id == (
        "class:user-service"
    )

    assert relationship.target_id == (
        "class:base-service"
    )

    assert relationship.kind == (
        RelationshipKind.INHERITS
    )


def test_repository_model():

    user_service = Entity(
        id="class:user-service",
        kind=EntityKind.CLASS,
        name="UserService",
    )

    base_service = Entity(
        id="class:base-service",
        kind=EntityKind.CLASS,
        name="BaseService",
    )

    inheritance = Relationship(
        source_id=user_service.id,
        target_id=base_service.id,
        kind=RelationshipKind.INHERITS,
    )

    repository = RepositoryModel(
        name="example",
        entities=[
            user_service,
            base_service,
        ],
        relationships=[
            inheritance,
        ],
    )

    assert repository.name == "example"
    assert len(repository.entities) == 2
    assert len(repository.relationships) == 1

    assert (
        repository.relationships[0].kind
        == RelationshipKind.INHERITS
    )


def test_entity_metadata():

    entity = Entity(
        id="endpoint:get-users",
        kind=EntityKind.ENDPOINT,
        name="get_users",
        metadata={
            "http_method": "GET",
            "path": "/users",
        },
    )

    assert entity.metadata["http_method"] == "GET"
    assert entity.metadata["path"] == "/users"


def test_type_reference():

    user_type = TypeReference(
        name="User",
    )

    assert user_type.name == "User"
    assert user_type.generic_arguments == ()
    assert user_type.is_optional is False


def test_generic_type_reference():

    user_type = TypeReference(
        name="User",
    )

    list_type = TypeReference(
        name="List",
        generic_arguments=(user_type,),
        is_collection=True,
    )

    assert list_type.name == "List"
    assert list_type.is_collection is True
    assert len(list_type.generic_arguments) == 1
    assert list_type.generic_arguments[0].name == "User"


def test_parameter():

    parameter = Parameter(
        name="user_id",
        type=TypeReference(
            name="int"
        ),
    )

    assert parameter.name == "user_id"
    assert parameter.type.name == "int"


def test_parameter_with_default():

    parameter = Parameter(
        name="include_orders",
        type=TypeReference(
            name="bool"
        ),
        default_value="False",
    )

    assert parameter.default_value == "False"


def test_generic_parameter():

    generic = GenericParameter(
        name="T",
        constraints=(
            TypeReference(
                name="BaseEntity"
            ),
        ),
    )

    assert generic.name == "T"
    assert len(generic.constraints) == 1
    assert (
        generic.constraints[0].name
        == "BaseEntity"
    )


def test_function_signature():

    entity = Entity(
        id="function:get-user",
        kind=EntityKind.FUNCTION,
        name="get_user",
        language="Python",
        parameters=[
            Parameter(
                name="user_id",
                type=TypeReference(
                    name="int"
                ),
            ),
            Parameter(
                name="include_orders",
                type=TypeReference(
                    name="bool"
                ),
                default_value="False",
            ),
        ],
        return_type=TypeReference(
            name="User"
        ),
    )

    assert len(entity.parameters) == 2

    assert (
        entity.parameters[0].type.name
        == "int"
    )

    assert (
        entity.parameters[1].default_value
        == "False"
    )

    assert (
        entity.return_type.name
        == "User"
    )