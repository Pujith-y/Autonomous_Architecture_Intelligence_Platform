
from unittest.mock import Mock

import pytest

from app.knowledge_graph.neo4j.code_graph_tools import CodeGraphTools
from app.knowledge_graph.neo4j.query_repository import EntityNotFoundError
from app.knowledge_graph.neo4j.resolution.entity_resolver import (
    AmbiguousEntityError,
    EntityResolution,
)


@pytest.fixture
def tools():
    query = Mock()
    resolver = Mock()

    resolver.resolve.return_value = EntityResolution(
        entity={
            "id": "user:1::repo:2::python:UserService",
            "name": "UserService",
            "qualified_name": "app.services.UserService",
            "match_kind": "name",
        }
    )

    query.find_relationships.return_value = [
        {
            "relationship_type": "calls",
            "direction": "outgoing",
            "target": {"name": "save_user"},
        }
    ]

    return CodeGraphTools(query, resolver, user_id=1, repository_id=2)


def test_find_entity_returns_resolved_entity(tools):
    entity = tools.find_entity("UserService")

    assert entity["name"] == "UserService"
    tools.entity_resolver.resolve.assert_called_once_with(
        user_id=1,
        repository_id=2,
        entity_name="UserService",
    )


def test_find_entity_raises_when_missing(tools):
    tools.entity_resolver.resolve.return_value = EntityResolution()

    with pytest.raises(EntityNotFoundError):
        tools.find_entity("MissingClass")


def test_find_entity_raises_when_ambiguous(tools):
    tools.entity_resolver.resolve.return_value = EntityResolution(
        candidates=[
            {"id": "candidate-1", "match_kind": "name"},
            {"id": "candidate-2", "match_kind": "name"},
        ]
    )

    with pytest.raises(AmbiguousEntityError):
        tools.find_entity("User")


def test_inspect_entity_returns_relationships(tools):
    result = tools.inspect_entity("UserService")

    assert result["entity"]["name"] == "UserService"
    assert result["relationship_count"] == 1
    assert result["relationships"][0]["relationship_type"] == "calls"

    tools.query_repository.find_relationships.assert_called_once_with(
        user_id=1,
        repository_id=2,
        entity_id="user:1::repo:2::python:UserService",
        direction="both",
        limit=100,
    )



def test_find_callers(tools):
    tools.query_repository.find_callers.return_value = [
        {"name": "create_user"}
    ]

    result = tools.find_callers("UserService")

    assert result["count"] == 1
    assert result["callers"] == [{"name": "create_user"}]


def test_find_callees(tools):
    tools.query_repository.find_callees.return_value = [
        {"name": "save_user"}
    ]

    result = tools.find_callees("UserService")

    assert result["count"] == 1
    assert result["callees"] == [{"name": "save_user"}]


def test_find_dependencies(tools):
    tools.query_repository.find_dependencies.return_value = [
        {"name": "UserRepository"}
    ]

    result = tools.find_dependencies("UserService")

    assert result["count"] == 1
    assert result["dependencies"] == [{"name": "UserRepository"}]


def test_find_dependents(tools):
    tools.query_repository.find_dependents.return_value = [
        {"name": "UserController"}
    ]

    result = tools.find_dependents("UserService")

    assert result["count"] == 1
    assert result["dependents"] == [{"name": "UserController"}]

def test_find_implementations(tools):
    tools.query_repository.find_implementations.return_value = [
        {"name": "PostgresUserRepository"},
        {"name": "MongoUserRepository"},
    ]

    result = tools.find_implementations("UserRepository")

    assert result["count"] == 2
    assert result["implementations"] == [
        {"name": "PostgresUserRepository"},
        {"name": "MongoUserRepository"},
    ]

    tools.query_repository.find_implementations.assert_called_once_with(
        user_id=1,
        repository_id=2,
        entity_id="user:1::repo:2::python:UserService",
        limit=100,
    )


def test_analyze_impact(tools):
    expected_impact = {
        "affected_entities": [{"name": "UserController"}],
        "depth": 2,
    }
    tools.query_repository.analyze_impact.return_value = expected_impact

    result = tools.analyze_impact("UserService")

    assert result["entity"]["name"] == "UserService"
    assert result["impact"] == expected_impact

    tools.query_repository.analyze_impact.assert_called_once_with(
        user_id=1,
        repository_id=2,
        entity_id="user:1::repo:2::python:UserService",
        max_depth=3,
        limit=100,
    )


@pytest.mark.parametrize("limit", [0, -1, 10001, True, 1.5, "10"])
def test_find_callers_rejects_invalid_limit(tools, limit):
    with pytest.raises(ValueError):
        tools.find_callers("UserService", limit=limit)

    tools.entity_resolver.resolve.assert_not_called()
    tools.query_repository.find_callers.assert_not_called()


@pytest.mark.parametrize("max_depth", [0, -1, 11, True, 1.5, "3"])
def test_analyze_impact_rejects_invalid_depth(tools, max_depth):
    with pytest.raises(ValueError):
        tools.analyze_impact("UserService", max_depth=max_depth)

    tools.entity_resolver.resolve.assert_not_called()
    tools.query_repository.analyze_impact.assert_not_called()