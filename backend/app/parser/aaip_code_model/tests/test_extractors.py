"""
Per-extractor tests against the normalization fixture repository.

THE PATH CONTRACT
-----------------
`extract_file(relative_path, source_bytes)` takes a path that is genuinely
*repository-relative*. The fixture directory is the repository root here, so
the caller passes `python/user.py`, not the absolute path it happens to live
at on this machine. Passing an absolute path is what produced ids like
`python:mnt.c.VSCODE.Projects....user` -- the bug was in the caller, not in
the identity implementation, and it is fixed here rather than by teaching
`common.py` to recognise and strip anyone's checkout directory.

These tests assert entities, intra-file relationships and pending references
explicitly. Printing the graph is useful when a test fails; it is not what
makes the test protective.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.repository_model import EntityKind, RelationshipKind
from app.parser.aaip_code_model.extractor_python import extract_file as extract_python
from app.parser.aaip_code_model.extractor_java import extract_file as extract_java
from app.parser.aaip_code_model.extractor_javascript import extract_file as extract_javascript


ROOT = Path(__file__).parent / "fixtures" / "normalization"

# Fixtures that deliberately contain *unresolvable* constructs (an
# `obj.method()` call with no type information). They live outside the
# normalization repository so that its graph stays fully resolved -- the
# orchestrator test asserts `unresolved_references == []` there, and that
# assertion is only meaningful if nothing unresolvable is planted in it.
EXTRACTION_ROOT = Path(__file__).parent / "fixtures" / "normalization" 

# Any of these appearing in a canonical id means an absolute or
# machine-specific path leaked into identity.
FORBIDDEN_ID_FRAGMENTS = (
    "mnt.c.VSCODE", "mnt/c/VSCODE", "/mnt/", "C:", "\\", "Projects.AAIP",
    "site-packages", "tmp.", "/tmp/",
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def extract(extractor, relative: str, root: Path = ROOT) -> dict:
    """Read a fixture file and hand the extractor a *repository-relative*
    path, exactly as the orchestrator does."""
    relative_path = Path(relative)
    absolute = root / relative_path
    return extractor(relative_path=relative_path, source_bytes=absolute.read_bytes())


def entity_ids(result: dict) -> set[str]:
    return {e.id for e in result["entities"]}


def entity_by_id(result: dict, entity_id: str):
    for e in result["entities"]:
        if e.id == entity_id:
            return e
    raise AssertionError(f"no entity {entity_id!r} in {sorted(entity_ids(result))}")


def has_relationship(relationships, source_id: str, target_id: str, kind: RelationshipKind) -> bool:
    return any(
        r.source_id == source_id and r.target_id == target_id and r.kind == kind
        for r in relationships
    )


def assert_ids_are_repository_relative(result: dict) -> None:
    for e in result["entities"]:
        for fragment in FORBIDDEN_ID_FRAGMENTS:
            assert fragment not in e.id, f"machine-specific fragment {fragment!r} in id {e.id!r}"
        assert not e.id.startswith(("python:/", "java:/", "javascript:/", "typescript:/"))
    for e in result["entities"]:
        if e.location is not None:
            assert not Path(e.location.file).is_absolute()


def print_result(language, result):  # pragma: no cover - diagnostic aid only
    print()
    print("=" * 70)
    print(language.upper())
    print("=" * 70)
    print("\nENTITIES\n" + "-" * 70)
    for entity in result["entities"]:
        print(f"{entity.id:55} {entity.kind.value:15} {entity.qualified_name}")
    print("\nRELATIONSHIPS\n" + "-" * 70)
    for relationship in result["relationships"]:
        print(f"{relationship.source_id} --{relationship.kind.value}--> {relationship.target_id}")
    print("\nPENDING REFERENCES\n" + "-" * 70)
    for key in ("pending_bases", "pending_implements", "pending_calls",
                "pending_creates", "pending_decorators"):
        print(f"{key}:")
        for item in result[key]:
            print(f"  {item}")


# ---------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------

def test_python():
    result = extract(extract_python, "python/user.py")
    print_result("Python", result)

    got = entity_ids(result)
    assert "python:python.user" in got
    assert "python:python.user.User" in got
    assert "python:python.user.User.name" in got
    assert "python:python.user.User.get_name()" in got
    assert_ids_are_repository_relative(result)

    assert entity_by_id(result, "python:python.user").kind == EntityKind.MODULE
    assert entity_by_id(result, "python:python.user.User").kind == EntityKind.CLASS
    assert entity_by_id(result, "python:python.user.User.name").kind == EntityKind.FIELD
    assert entity_by_id(result, "python:python.user.User.get_name()").kind == EntityKind.METHOD

    rels = result["relationships"]
    assert has_relationship(rels, "python:python.user", "python:python.user.User", RelationshipKind.CONTAINS)
    assert has_relationship(rels, "python:python.user.User", "python:python.user.User.name", RelationshipKind.CONTAINS)
    assert has_relationship(
        rels, "python:python.user.User", "python:python.user.User.get_name()", RelationshipKind.CONTAINS
    )

    # The extractor states the syntactic fact and stops -- it does not decide
    # which BaseUser in the repository is meant.
    assert ("python:python.user.User", "BaseUser") in result["pending_bases"]
    assert result["parse_errors"] == []


def test_python_import_declaration_is_preserved():
    """An import declaration entity is a distinct concept from its target."""
    result = extract(extract_python, "python/user.py")
    imp_id = "python:python.user::import::base.BaseUser"
    assert imp_id in entity_ids(result)
    assert entity_by_id(result, imp_id).kind == EntityKind.IMPORT
    rels = result["relationships"]
    assert has_relationship(rels, "python:python.user", imp_id, RelationshipKind.CONTAINS)
    assert has_relationship(rels, "python:python.user", imp_id, RelationshipKind.IMPORTS)
    # Candidates, not a decision: the orchestrator picks whichever exists.
    assert result["import_candidates_by_simple_name"]["BaseUser"] == [
        "base.BaseUser",
        "python.base.BaseUser",
    ]


def test_python_typed_and_untyped_parameters():
    """Parameter *types* are part of identity; names never are."""
    result = extract(extract_python, "python/params.py", EXTRACTION_ROOT)
    got = entity_ids(result)
    assert "python:python.params.Svc.typed(?,str,int)" in got
    assert "python:python.params.Svc.untyped(?,?)" in got


# ---------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------

def test_java():
    result = extract(extract_java, "java/User.java")
    print_result("Java", result)

    got = entity_ids(result)
    assert "java:test" in got
    assert "java:test.User" in got
    assert "java:test.User.name" in got
    assert "java:test.User.getName()" in got
    assert_ids_are_repository_relative(result)

    assert entity_by_id(result, "java:test").kind == EntityKind.PACKAGE
    assert entity_by_id(result, "java:test.User.name").kind == EntityKind.FIELD

    rels = result["relationships"]
    assert has_relationship(rels, "java:test", "java:test.User", RelationshipKind.CONTAINS)
    assert has_relationship(rels, "java:test.User", "java:test.User.getName()", RelationshipKind.CONTAINS)
    assert has_relationship(rels, "java:test.User", "java:test.User.name", RelationshipKind.CONTAINS)

    assert ("java:test.User", "Base") in result["pending_bases"]
    assert ("java:test.User", "Repository") in result["pending_implements"]
    assert result["parse_errors"] == []


def test_java_overloads_do_not_collapse():
    result = extract(extract_java, "java/Calculator.java")
    got = entity_ids(result)
    assert "java:test.Calculator.add(int,int)" in got
    assert "java:test.Calculator.add(double,double)" in got
    assert "java:test.Calculator.add" not in got
    assert "java:test.Calculator.add()" not in got

    rels = result["relationships"]
    assert has_relationship(
        rels, "java:test.Calculator", "java:test.Calculator.add(int,int)", RelationshipKind.CONTAINS
    )
    assert has_relationship(
        rels, "java:test.Calculator", "java:test.Calculator.add(double,double)", RelationshipKind.CONTAINS
    )


def test_java_nested_classes_keep_ownership():
    result = extract(extract_java, "java/Outer.java")
    got = entity_ids(result)
    assert "java:test.Outer" in got
    assert "java:test.Outer.Inner" in got
    assert "java:test.Outer.Inner.hello()" in got
    assert "java:test.Inner" not in got  # flattening would lose ownership

    rels = result["relationships"]
    assert has_relationship(rels, "java:test.Outer", "java:test.Outer.Inner", RelationshipKind.CONTAINS)
    assert has_relationship(
        rels, "java:test.Outer.Inner", "java:test.Outer.Inner.hello()", RelationshipKind.CONTAINS
    )


# ---------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------

def test_javascript():
    result = extract(extract_javascript, "js/user.js")
    print_result("JavaScript", result)

    got = entity_ids(result)
    assert "javascript:js/user" in got
    assert "javascript:js/user.User" in got
    assert "javascript:js/user.User.constructor()" in got
    assert "javascript:js/user.User.getName()" in got
    assert_ids_are_repository_relative(result)

    assert entity_by_id(result, "javascript:js/user.User.constructor()").kind == EntityKind.CONSTRUCTOR
    assert entity_by_id(result, "javascript:js/user.User.getName()").kind == EntityKind.METHOD

    rels = result["relationships"]
    assert has_relationship(rels, "javascript:js/user", "javascript:js/user.User", RelationshipKind.CONTAINS)
    assert has_relationship(
        rels, "javascript:js/user.User", "javascript:js/user.User.getName()", RelationshipKind.CONTAINS
    )

    # The plain JavaScript grammar puts the base class directly under
    # class_heritage with no extends_clause wrapper. This is the assertion
    # that proves that path is exercised.
    assert ("javascript:js/user.User", "BaseUser") in result["pending_bases"]
    assert result["parse_errors"] == []


def test_javascript_import_is_resolved_to_a_module_not_a_raw_specifier():
    result = extract(extract_javascript, "js/user.js")
    imp_id = "javascript:js/user::import::./base.js"
    assert imp_id in entity_ids(result)
    rels = result["relationships"]
    assert has_relationship(rels, "javascript:js/user", imp_id, RelationshipKind.IMPORTS)
    # "./base.js" from "js/user.js" -> the module "js/base", never the
    # invented string "./base.js.BaseUser".
    assert result["import_candidates_by_simple_name"]["BaseUser"] == ["js/base.BaseUser"]


# ---------------------------------------------------------------------
# TypeScript -- a different grammar, not merely JavaScript with types
# ---------------------------------------------------------------------

def test_typescript_extends_and_implements():
    """TS wraps heritage in extends_clause / implements_clause; JS does not."""
    result = extract(extract_javascript, "ts/user.ts")
    got = entity_ids(result)
    assert "typescript:ts/user.User" in got
    assert "typescript:ts/user.User.save()" in got

    assert ("typescript:ts/user.User", "BaseUser") in result["pending_bases"]
    assert ("typescript:ts/user.User", "Repository") in result["pending_implements"]


def test_typescript_interface_extends_multiple():
    """`interface A extends B, C` -- the extends_type_clause path."""
    result = extract(extract_javascript, "ts/chain.ts")
    assert "typescript:ts/chain.A" in entity_ids(result)
    bases = {b for owner, b in result["pending_bases"] if owner == "typescript:ts/chain.A"}
    assert bases == {"B", "C"}


def test_typescript_interface_members():
    result = extract(extract_javascript, "ts/repository.ts")
    assert "typescript:ts/repository.Repository" in entity_ids(result)
    assert "typescript:ts/repository.Repository.save()" in entity_ids(result)


# ---------------------------------------------------------------------
# Conservative call handling (extraction side)
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "extractor,relative,caller,expected_root,expected_steps",
    [
        (
            extract_python,
            "python/calls.py",
            "python:python.calls.User.save()",
            ("self",),
            (("call", "validate", ()),),
        ),
        (
            extract_python,
            "python/calls.py",
            "python:python.calls.save(User)",
            ("name", "user"),
            (("call", "validate", ()),),
        ),
    ],
)
def test_calls_record_expression_chain(
    extractor,
    relative,
    caller,
    expected_root,
    expected_steps,
):
    result = extract(extractor, relative, EXTRACTION_ROOT)

    staged = {
        (c[0], c[2], c[3])
        for c in result["pending_calls"]
    }

    assert (
        caller,
        expected_root,
        expected_steps,
    ) in staged