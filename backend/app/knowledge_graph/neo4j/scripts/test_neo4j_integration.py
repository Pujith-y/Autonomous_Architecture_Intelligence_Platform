import os

import pytest

from app.knowledge_graph.neo4j.client import driver
from app.knowledge_graph.neo4j.query_repository import Neo4jQueryRepository
from app.knowledge_graph.neo4j.resolution.entity_resolver import (
    AmbiguousEntityError,
    EntityResolver,
)
from app.knowledge_graph.code_graph_tools import CodeGraphTools


pytestmark = pytest.mark.integration

USER_ID = 1
REPOSITORY_ID = 1
USER_ENTITY_ID = "user:1::repo:1::python:python.test.User"
SAVE_ENTITY_ID = "user:1::repo:1::python:python.calls.User.save()"
VALIDATE_ENTITY_ID = "user:1::repo:1::python:python.calls.User.validate()"


@pytest.fixture(scope="module")
def graph_tools():
    if os.getenv("RUN_NEO4J_INTEGRATION") != "1":
        pytest.skip("Set RUN_NEO4J_INTEGRATION=1 to run live Neo4j tests")

    driver.verify_connectivity()

    query_repository = Neo4jQueryRepository(neo4j_driver=driver)
    resolver = EntityResolver(query_repository)

    yield CodeGraphTools(
        query_repository=query_repository,
        entity_resolver=resolver,
        user_id=USER_ID,
        repository_id=REPOSITORY_ID,
    )


def test_find_entity_by_exact_id(graph_tools):
    entity = graph_tools.find_entity(USER_ENTITY_ID)

    assert entity["id"] == USER_ENTITY_ID
    assert entity["name"] == "User"


def test_find_entity_rejects_ambiguous_name(graph_tools):
    with pytest.raises(AmbiguousEntityError) as exc_info:
        graph_tools.find_entity("User")

    assert len(exc_info.value.candidates) > 1


def test_inspect_entity_returns_relationships(graph_tools):
    result = graph_tools.inspect_entity(USER_ENTITY_ID, limit=10)

    assert result["entity"]["id"] == USER_ENTITY_ID
    assert result["relationship_count"] > 0
    assert len(result["relationships"]) == result["relationship_count"]


def test_find_callers(graph_tools):
    result = graph_tools.find_callers(VALIDATE_ENTITY_ID)

    caller_ids = {caller["id"] for caller in result["callers"]}

    assert result["count"] >= 1
    assert SAVE_ENTITY_ID in caller_ids


def test_find_callees(graph_tools):
    result = graph_tools.find_callees(SAVE_ENTITY_ID)

    callee_ids = {callee["id"] for callee in result["callees"]}

    assert result["count"] >= 1
    assert VALIDATE_ENTITY_ID in callee_ids
