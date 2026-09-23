"""
Repository-level regression test for the normalization fixture.

This asserts the *final* graph -- resolved relationships, resolution
metadata, and the three diagnostic lists -- rather than only that a graph
was produced. `len(entities) > 0` cannot tell a correct resolution from a
lucky one.

The fixture repository is deliberately fully resolvable: every reference in
it resolves through an explicit import or a same-module qualified name, so
`unresolved_references == []` is a real assertion about the resolver and not
an accident of an empty fixture. Constructs that are *meant* to stay
unresolved live in `fixtures/extraction/` and in `test_normalization.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.repository_model import EntityKind, RelationshipKind
from app.parser.aaip_code_model.orchestrator import build_repository_graph


ROOT = Path(__file__).parent / "fixtures" / "normalization"

FORBIDDEN_ID_FRAGMENTS = (
    "mnt.c.VSCODE", "mnt/c/VSCODE", "/mnt/", "C:", "\\", "Projects.AAIP",
)


class FixtureFile:
    def __init__(self, path: Path, root: Path):
        self.path = path
        self.relative_path = path.relative_to(root)
        self.name = path.name
        self.extension = path.suffix
        self.is_binary = False
        self.language = None


class FixtureRepo:
    def __init__(self, root: Path, reverse: bool = False):
        self.name = "normalization-test-repo"
        files = [FixtureFile(path, root) for path in sorted(root.rglob("*")) if path.is_file()]
        if reverse:
            # The orchestrator must sort for itself; handing it a reversed
            # list is how we prove it does.
            files.reverse()
        self.files = files


@pytest.fixture(scope="module")
def graph():
    return build_repository_graph(FixtureRepo(ROOT))


def entity_ids(model) -> set[str]:
    return {e.id for e in model.entities}


def entity_by_id(model, entity_id: str):
    for e in model.entities:
        if e.id == entity_id:
            return e
    raise AssertionError(f"no entity {entity_id!r}")


def relationship_exists(model, source_id: str, target_id: str, kind: RelationshipKind) -> bool:
    return any(
        r.source_id == source_id and r.target_id == target_id and r.kind == kind
        for r in model.relationships
    )


def relationship_metadata(model, source_id: str, target_id: str, kind: RelationshipKind) -> dict:
    for r in model.relationships:
        if r.source_id == source_id and r.target_id == target_id and r.kind == kind:
            return r.metadata
    raise AssertionError(f"no {kind.value} edge {source_id} -> {target_id}")


def print_graph(model):  # pragma: no cover - diagnostic aid only
    print()
    print("=" * 80)
    print("REPOSITORY GRAPH")
    print("=" * 80)
    print("\nENTITIES\n" + "-" * 80)
    for entity in model.entities:
        print(f"{entity.id:70} {entity.kind.value:15} {entity.parameters} {entity.return_type} {entity.generic_parameters} {entity.metadata} external={entity.metadata.get('external', False)}")
    print("\nRELATIONSHIPS\n" + "-" * 80)
    for relationship in model.relationships:
        print(f"{relationship.source_id:70} --{relationship.kind.value}--> {relationship.target_id}")
    print("\nMETADATA\n" + "-" * 80)
    print(model.metadata)


def test_orchestrator(graph):
    print_graph(graph)
    assert graph is not None
    assert len(graph.entities) > 0
    assert len(graph.relationships) > 0


# ---------------------------------------------------------------------
# Resolved relationships -- the point of the whole layer
# ---------------------------------------------------------------------

def test_java_inheritance_and_implementation(graph):
    assert relationship_exists(graph, "java:test.User", "java:test.Base", RelationshipKind.INHERITS)
    assert relationship_exists(graph, "java:test.User", "java:test.Repository", RelationshipKind.IMPLEMENTS)


def test_javascript_inheritance_through_import(graph):
    assert relationship_exists(
        graph, "javascript:js/user.User", "javascript:js/base.BaseUser", RelationshipKind.INHERITS
    )
    meta = relationship_metadata(
        graph, "javascript:js/user.User", "javascript:js/base.BaseUser", RelationshipKind.INHERITS
    )
    assert meta["resolution_method"] == "explicit_import"


def test_python_inheritance_through_import(graph):
    assert relationship_exists(
        graph, "python:python.user.User", "python:python.base.BaseUser", RelationshipKind.INHERITS
    )
    meta = relationship_metadata(
        graph, "python:python.user.User", "python:python.base.BaseUser", RelationshipKind.INHERITS
    )
    assert meta["resolution_method"] == "explicit_import"


def test_typescript_inheritance_and_implementation(graph):
    assert relationship_exists(
        graph, "typescript:ts/user.User", "typescript:ts/base.BaseUser", RelationshipKind.INHERITS
    )
    assert relationship_exists(
        graph, "typescript:ts/user.User", "typescript:ts/repository.Repository", RelationshipKind.IMPLEMENTS
    )
    assert relationship_exists(graph, "typescript:ts/chain.A", "typescript:ts/chain.B", RelationshipKind.INHERITS)
    assert relationship_exists(graph, "typescript:ts/chain.A", "typescript:ts/chain.C", RelationshipKind.INHERITS)


def test_same_simple_name_across_languages_stays_separate(graph):
    """BaseUser exists in Python, JavaScript and TypeScript. Each inheritance
    edge must land in its own language's module."""
    got = entity_ids(graph)
    assert {"python:python.base.BaseUser", "javascript:js/base.BaseUser", "typescript:ts/base.BaseUser"} <= got
    assert not relationship_exists(
        graph, "python:python.user.User", "javascript:js/base.BaseUser", RelationshipKind.INHERITS
    )
    assert not relationship_exists(
        graph, "javascript:js/user.User", "python:python.base.BaseUser", RelationshipKind.INHERITS
    )


def test_java_overloads_coexist_in_the_final_graph(graph):
    got = entity_ids(graph)
    assert "java:test.Calculator.add(int,int)" in got
    assert "java:test.Calculator.add(double,double)" in got
    assert "java:test.Calculator.add" not in got


def test_java_nested_classes_in_the_final_graph(graph):
    assert relationship_exists(graph, "java:test.Outer", "java:test.Outer.Inner", RelationshipKind.CONTAINS)
    assert relationship_exists(
        graph, "java:test.Outer.Inner", "java:test.Outer.Inner.hello()", RelationshipKind.CONTAINS
    )
    assert "java:test.Inner" not in entity_ids(graph)


# ---------------------------------------------------------------------
# FILE vs MODULE
# ---------------------------------------------------------------------

def test_file_entities_are_distinct_from_modules(graph):
    got = entity_ids(graph)
    assert "file:java/User.java" in got
    assert entity_by_id(graph, "file:java/User.java").kind == EntityKind.FILE

    # Three Java files, one package: the file layer is what keeps them
    # distinguishable once the package entity has deduplicated.
    for name in ("Base", "Repository", "User"):
        assert relationship_exists(graph, f"file:java/{name}.java", "java:test", RelationshipKind.CONTAINS)
    assert relationship_exists(graph, "java:test", "java:test.User", RelationshipKind.CONTAINS)
    assert relationship_exists(
        graph, "repository::normalization-test-repo", "file:java/User.java", RelationshipKind.CONTAINS
    )


def test_import_declaration_entities_are_preserved(graph):
    got = entity_ids(graph)
    assert "python:python.user::import::base.BaseUser" in got
    assert "javascript:js/user::import::./base.js" in got
    assert relationship_exists(
        graph, "javascript:js/user", "javascript:js/user::import::./base.js", RelationshipKind.IMPORTS
    )
    # The declaration must never shadow the entity it points at.
    assert "javascript:js/base.BaseUser" in got


# ---------------------------------------------------------------------
# Diagnostics and identity
# ---------------------------------------------------------------------

def test_fixture_repository_is_fully_resolved(graph):
    assert graph.metadata["parse_errors"] == []
    assert graph.metadata["unresolved_references"] == []
    assert graph.metadata["identity_collisions"] == []


def test_no_machine_specific_paths_in_canonical_ids(graph):
    for e in graph.entities:
        for fragment in FORBIDDEN_ID_FRAGMENTS:
            assert fragment not in e.id, f"{fragment!r} leaked into id {e.id!r}"
        assert not e.id.startswith(("python:/", "java:/", "javascript:/", "typescript:/"))


def test_source_locations_are_repository_relative(graph):
    for e in graph.entities:
        if e.location is not None:
            assert not Path(e.location.file).is_absolute()
    user = entity_by_id(graph, "python:python.user.User")
    assert Path(user.location.file).as_posix() == "python/user.py"


def test_relationships_are_deduplicated(graph):
    keys = [(r.source_id, r.target_id, r.kind.value) for r in graph.relationships]
    assert len(keys) == len(set(keys))


def test_graph_is_deterministic_regardless_of_file_order():
    forward = build_repository_graph(FixtureRepo(ROOT))
    reversed_input = build_repository_graph(FixtureRepo(ROOT, reverse=True))
    assert [e.id for e in forward.entities] == [e.id for e in reversed_input.entities]
    assert [
        (r.source_id, r.target_id, r.kind.value) for r in forward.relationships
    ] == [(r.source_id, r.target_id, r.kind.value) for r in reversed_input.relationships]