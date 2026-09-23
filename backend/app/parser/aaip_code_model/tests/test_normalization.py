"""
Repository-level tests for the normalization layer (spec 36-42).

These assert the *final graph* -- entities, relationships, resolution
metadata, unresolved references, external entities -- not just what an
extractor happened to stage in a pending list. A test that only checks
`pending_bases == [...]` cannot tell a correct resolution from a lucky one.

Everything runs against a real on-disk repository written into tmp_path, so
canonical ids are exercised end to end and any absolute-path leakage shows
up immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.repository_model import RelationshipKind
from app.parser.aaip_code_model.orchestrator import build_repository_graph
from app.parser.aaip_code_model.common import parse_type_reference


# ---------------------------------------------------------------------
# Minimal stand-ins for the discovery-stage repository/file objects. The
# orchestrator only reads these five attributes (see its _LegacyFile
# Protocol), so the tests don't depend on the scanner implementation.
# ---------------------------------------------------------------------

@dataclass
class FakeFile:
    path: Path
    relative_path: Path
    name: str
    extension: str
    is_binary: bool = False
    language: str | None = None


@dataclass
class FakeRepo:
    name: str
    files: list


def make_repo(tmp_path: Path, files: dict[str, str], name: str = "testrepo") -> FakeRepo:
    entries = []
    for rel, content in files.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        entries.append(
            FakeFile(path=full, relative_path=Path(rel), name=full.name, extension=full.suffix)
        )
    # Shuffled on purpose: the orchestrator must sort, not inherit our order.
    entries.reverse()
    return FakeRepo(name=name, files=entries)


def build(tmp_path: Path, files: dict[str, str]):
    return build_repository_graph(make_repo(tmp_path, files))


def ids(model) -> set[str]:
    return {e.id for e in model.entities}


def edges(model, kind: RelationshipKind) -> set[tuple[str, str]]:
    return {(r.source_id, r.target_id) for r in model.relationships if r.kind == kind}


def edge_metadata(model, source: str, target: str, kind: RelationshipKind) -> dict:
    for r in model.relationships:
        if r.source_id == source and r.target_id == target and r.kind == kind:
            return r.metadata
    raise AssertionError(f"no {kind} edge {source} -> {target}")


def reasons(model) -> set[str]:
    return {u["reason"] for u in model.metadata["unresolved_references"]}


# =====================================================================
# Python (spec 36)
# =====================================================================

PY_BASE = "class BaseUser:\n    pass\n"
PY_USER = "from base import BaseUser\n\n\nclass User(BaseUser):\n    pass\n"


def test_python_inheritance_through_absolute_import(tmp_path):
    """spec 4 + 48: `from base import BaseUser` in python/user.py must reach
    the repository entity python.base.BaseUser, not a bare simple name."""
    model = build(tmp_path, {"python/base.py": PY_BASE, "python/user.py": PY_USER})

    assert "python:python.base.BaseUser" in ids(model)
    assert "python:python.user.User" in ids(model)
    assert ("python:python.user.User", "python:python.base.BaseUser") in edges(
        model, RelationshipKind.INHERITS
    )
    meta = edge_metadata(
        model, "python:python.user.User", "python:python.base.BaseUser", RelationshipKind.INHERITS
    )
    assert meta["resolution_method"] == "explicit_import"
    assert meta["file"] == "python/user.py"
    assert meta["line"] == 4


def test_python_relative_import_single_dot(tmp_path):
    """spec 5: `from .base import BaseUser` resolves against the importer's package."""
    model = build(
        tmp_path,
        {
            "python/users/base.py": PY_BASE,
            "python/users/user.py": "from .base import BaseUser\n\nclass User(BaseUser):\n    pass\n",
        },
    )
    assert ("python:python.users.user.User", "python:python.users.base.BaseUser") in edges(
        model, RelationshipKind.INHERITS
    )


def test_python_relative_import_parent_package(tmp_path):
    """spec 5: `from ..common.types import User` walks up one package."""
    model = build(
        tmp_path,
        {
            "python/common/types.py": "class User:\n    pass\n",
            "python/users/admin.py": "from ..common.types import User\n\nclass Admin(User):\n    pass\n",
        },
    )
    assert ("python:python.users.admin.Admin", "python:python.common.types.User") in edges(
        model, RelationshipKind.INHERITS
    )


def test_python_nested_classes_keep_owner_stack(tmp_path):
    """spec 14: nested types stay qualified; methods bind to the nearest class."""
    src = "class Outer:\n    class Inner:\n        def hello(self):\n            pass\n"
    model = build(tmp_path, {"python/module.py": src})
    got = ids(model)
    assert "python:python.module.Outer" in got
    assert "python:python.module.Outer.Inner" in got
    assert "python:python.module.Outer.Inner.hello()" in got
    assert "python:python.module.Inner" not in got  # never flattened
    contains = edges(model, RelationshipKind.CONTAINS)
    assert ("python:python.module.Outer", "python:python.module.Outer.Inner") in contains
    assert ("python:python.module.Outer.Inner", "python:python.module.Outer.Inner.hello()") in contains


def test_python_self_call_resolves_to_own_class(tmp_path):
    """spec 19."""
    src = (
        "class User:\n"
        "    def save(self):\n"
        "        pass\n"
        "    def run(self):\n"
        "        self.save()\n"
    )
    model = build(tmp_path, {"python/user.py": src})
    assert ("python:python.user.User.run()", "python:python.user.User.save()") in edges(
        model, RelationshipKind.CALLS
    )


def test_python_self_call_reaches_inherited_method(tmp_path):
    """spec 19: every link in the chain was itself resolved, so this is a
    derivation from the graph, not a same-name guess."""
    model = build(
        tmp_path,
        {
            "python/base.py": "class BaseUser:\n    def save(self):\n        pass\n",
            "python/user.py": (
                "from base import BaseUser\n\n"
                "class User(BaseUser):\n"
                "    def go(self):\n"
                "        self.save()\n"
            ),
        },
    )
    assert ("python:python.user.User.go()", "python:python.base.BaseUser.save()") in edges(
        model, RelationshipKind.CALLS
    )
    meta = edge_metadata(
        model, "python:python.user.User.go()", "python:python.base.BaseUser.save()",
        RelationshipKind.CALLS,
    )
    assert meta["resolution_method"] == "inherited_method"


def test_python_object_creation(tmp_path):
    """spec 20: User() becomes a creation edge only because User resolves to a class."""
    model = build(
        tmp_path,
        {
            "python/user.py": "class User:\n    pass\n",
            "python/service.py": (
                "from user import User\n\n"
                "class Service:\n"
                "    def create_user(self):\n"
                "        return User()\n"
            ),
        },
    )
    creates = edges(model, RelationshipKind.CREATES)
    assert ("python:python.service.Service.create_user()", "python:python.user.User") in creates


def test_python_capitalized_factory_function_is_not_a_creation(tmp_path):
    """spec 20: capitalization alone must not manufacture a CREATES edge."""
    model = build(
        tmp_path,
        {
            "python/factory.py": "def Build():\n    return 1\n",
            "python/app.py": "from factory import Build\n\ndef run():\n    return Build()\n",
        },
    )
    creates = edges(model, RelationshipKind.CREATES)
    assert ("python:python.app.run()", "python:python.factory.Build()") not in creates
    assert ("python:python.app.run()", "python:python.factory.Build()") in edges(
        model, RelationshipKind.CALLS
    )


def test_python_fields(tmp_path):
    """spec 17: annotated class attributes and self-assignments are fields."""
    src = (
        "class User:\n"
        "    name: str\n"
        "    def __init__(self, email):\n"
        "        self.email = email\n"
        "        local = 1\n"
        "        return local\n"
    )
    model = build(tmp_path, {"python/user.py": src})
    got = ids(model)
    assert "python:python.user.User.name" in got
    assert "python:python.user.User.email" in got
    assert "python:python.user.User.local" not in got  # local variable, not a field


@pytest.mark.parametrize(
    "text,expected_name,optional,collection",
    [
        ("Optional[str]", "str", True, False),
        ("typing.Optional[str]", "str", True, False),
        ("str | None", "str", True, False),
        ("Union[str, int]", "Union", False, False),
        ("typing.Union[str, int]", "Union", False, False),
        ("typing.Union[str, None]", "str", True, False),
        ("list[str]", "list", False, True),
        ("List[str]", "List", False, True),
        ("typing.List[str]", "List", False, True),
        ("dict[str, int]", "dict", False, True),
        ("typing.Dict[str, int]", "Dict", False, True),
        ('"Optional[str]"', "str", True, False),
    ],
)
def test_python_type_normalization(text, expected_name, optional, collection):
    """spec 6."""
    t = parse_type_reference(text)
    assert t is not None
    assert t.name == expected_name
    assert t.is_optional is optional
    assert t.is_collection is collection
    assert t.qualified_name is None or not t.qualified_name.startswith("typing.")


# =====================================================================
# Java (spec 37)
# =====================================================================

def test_java_extends_implements_and_annotation(tmp_path):
    src = (
        "package test;\n"
        "class Repository {}\n"
        "class Base {}\n"
        "class User extends Base implements Repository {\n"
        "    @Override\n"
        "    public void run() {}\n"
        "}\n"
    )
    model = build(tmp_path, {"test/User.java": src})
    assert ("java:test.User", "java:test.Base") in edges(model, RelationshipKind.INHERITS)
    assert ("java:test.User", "java:test.Repository") in edges(model, RelationshipKind.IMPLEMENTS)
    assert "external::Override" in ids(model)
    assert ("java:test.User.run()", "external::Override") in edges(
        model, RelationshipKind.DECORATED_BY
    )


def test_java_nested_classes(tmp_path):
    src = "package test;\nclass Outer {\n    class Inner {\n        void hello() {}\n    }\n}\n"
    model = build(tmp_path, {"test/Outer.java": src})
    got = ids(model)
    assert "java:test.Outer" in got
    assert "java:test.Outer.Inner" in got
    assert "java:test.Outer.Inner.hello()" in got
    assert "java:test.Inner" not in got
    contains = edges(model, RelationshipKind.CONTAINS)
    assert ("java:test.Outer", "java:test.Outer.Inner") in contains
    assert ("java:test.Outer.Inner", "java:test.Outer.Inner.hello()") in contains


def test_java_method_overloads_coexist(tmp_path):
    """spec 15: parameter types are part of identity; dedup must not merge them."""
    src = (
        "package test;\n"
        "class Calculator {\n"
        "    int add(int a, int b) { return a + b; }\n"
        "    double add(double a, double b) { return a + b; }\n"
        "}\n"
    )
    model = build(tmp_path, {"test/Calculator.java": src})
    got = ids(model)
    assert "java:test.Calculator.add(int,int)" in got
    assert "java:test.Calculator.add(double,double)" in got
    assert "java:test.Calculator.add" not in got


def test_java_constructor_and_fields(tmp_path):
    src = (
        "package test;\n"
        "class User {\n"
        "    private String name;\n"
        "    User(int id, String name) {}\n"
        "}\n"
    )
    model = build(tmp_path, {"test/User.java": src})
    got = ids(model)
    assert "java:test.User.name" in got
    assert "java:test.User.<init>(int,String)" in got


def test_java_file_without_package_uses_directory(tmp_path):
    """spec 2/34: identity stays repository-relative with no package declared."""
    model = build(tmp_path, {"test/User.java": "class User {}\n"})
    assert "java:test.User" in ids(model)


# =====================================================================
# JavaScript / TypeScript (spec 38)
# =====================================================================

JS_BASE = "export class BaseUser {\n}\n"
JS_USER = (
    'import { BaseUser } from "./base.js";\n'
    "\n"
    "export class User extends BaseUser {\n"
    "\n"
    "    constructor() {\n"
    "        super();\n"
    "    }\n"
    "\n"
    "    getName() {\n"
    '        return "Pujith";\n'
    "    }\n"
    "}\n"
)


def test_javascript_inheritance_through_import(tmp_path):
    """spec 7/8/38/48: the exact required fixture."""
    model = build(tmp_path, {"js/base.js": JS_BASE, "js/user.js": JS_USER})
    got = ids(model)
    assert "javascript:js/user.User" in got
    assert "javascript:js/base.BaseUser" in got
    assert "javascript:js/user.User.constructor()" in got
    assert "javascript:js/user.User.getName()" in got
    assert ("javascript:js/user.User", "javascript:js/base.BaseUser") in edges(
        model, RelationshipKind.INHERITS
    )
    meta = edge_metadata(
        model, "javascript:js/user.User", "javascript:js/base.BaseUser", RelationshipKind.INHERITS
    )
    assert meta["resolution_method"] == "explicit_import"


def test_typescript_implements(tmp_path):
    model = build(
        tmp_path,
        {
            "ts/iuser.ts": "export interface IUser {}\n",
            "ts/user.ts": 'import { IUser } from "./iuser";\nexport class User implements IUser {}\n',
        },
    )
    assert ("typescript:ts/user.User", "typescript:ts/iuser.IUser") in edges(
        model, RelationshipKind.IMPLEMENTS
    )


def test_typescript_extends_and_implements_together(tmp_path):
    model = build(
        tmp_path,
        {
            "ts/base.ts": "export class BaseUser {}\nexport interface IUser {}\n",
            "ts/user.ts": (
                'import { BaseUser, IUser } from "./base";\n'
                "export class User extends BaseUser implements IUser {}\n"
            ),
        },
    )
    assert ("typescript:ts/user.User", "typescript:ts/base.BaseUser") in edges(
        model, RelationshipKind.INHERITS
    )
    assert ("typescript:ts/user.User", "typescript:ts/base.IUser") in edges(
        model, RelationshipKind.IMPLEMENTS
    )


def test_typescript_multiple_interfaces_are_separate_references(tmp_path):
    """spec 9."""
    model = build(
        tmp_path,
        {
            "ts/ifaces.ts": "export interface IUser {}\nexport interface Serializable {}\nexport interface Comparable {}\n",
            "ts/user.ts": (
                'import { IUser, Serializable, Comparable } from "./ifaces";\n'
                "export class User implements IUser, Serializable, Comparable<User> {}\n"
            ),
        },
    )
    implemented = {t for s, t in edges(model, RelationshipKind.IMPLEMENTS) if s == "typescript:ts/user.User"}
    assert implemented == {
        "typescript:ts/ifaces.IUser",
        "typescript:ts/ifaces.Serializable",
        "typescript:ts/ifaces.Comparable",
    }


def test_javascript_import_variants(tmp_path):
    """spec 10: default, named, aliased, namespace and side-effect imports."""
    model = build(
        tmp_path,
        {
            "js/base.js": "export class BaseUser {}\n",
            "js/user.js": "export class User {}\n",
            "js/utils.js": "export function help() {}\n",
            "js/startup.js": "export function boot() {}\n",
            "js/app.js": (
                'import { BaseUser } from "./base.js";\n'
                'import * as Utils from "./utils.js";\n'
                'import { User as AppUser } from "./user.js";\n'
                'import "./startup.js";\n'
                "export class Admin extends BaseUser {}\n"
                "export class Staff extends AppUser {}\n"
            ),
        },
    )
    inherits = edges(model, RelationshipKind.INHERITS)
    assert ("javascript:js/app.Admin", "javascript:js/base.BaseUser") in inherits
    assert ("javascript:js/app.Staff", "javascript:js/user.User") in inherits


def test_javascript_extensionless_and_index_resolution(tmp_path):
    """spec 11: candidates come from repository contents, not a guessed extension."""
    model = build(
        tmp_path,
        {
            "js/base.js": "export class BaseUser {}\n",
            "js/widgets/index.js": "export class Widget {}\n",
            "js/app.js": (
                'import { BaseUser } from "./base";\n'
                'import { Widget } from "./widgets";\n'
                "export class A extends BaseUser {}\n"
                "export class B extends Widget {}\n"
            ),
        },
    )
    inherits = edges(model, RelationshipKind.INHERITS)
    assert ("javascript:js/app.A", "javascript:js/base.BaseUser") in inherits
    assert ("javascript:js/app.B", "javascript:js/widgets/index.Widget") in inherits


def test_javascript_class_expression_and_anonymous_class(tmp_path):
    """spec 12: deterministic, unique, repository-relative identities."""
    model = build(
        tmp_path,
        {
            "js/base.js": "export class BaseUser {}\n",
            "js/anon.js": (
                'import { BaseUser } from "./base.js";\n'
                "const Foo = class extends BaseUser {};\n"
                "export default class {}\n"
            ),
        },
    )
    got = ids(model)
    assert "javascript:js/anon.Foo" in got
    assert ("javascript:js/anon.Foo", "javascript:js/base.BaseUser") in edges(
        model, RelationshipKind.INHERITS
    )
    anon = [i for i in got if "<anon-class>@" in i]
    assert len(anon) == 1
    assert "<anonymous>" not in "".join(got)


def test_javascript_fields_and_this_calls(tmp_path):
    """spec 17 + 19."""
    src = (
        "export class User {\n"
        "    name;\n"
        "    getName() { return this.name; }\n"
        "    run() { this.getName(); }\n"
        "}\n"
    )
    model = build(tmp_path, {"js/user.js": src})
    assert "javascript:js/user.User.name" in ids(model)
    assert ("javascript:js/user.User.run()", "javascript:js/user.User.getName()") in edges(
        model, RelationshipKind.CALLS
    )


def test_javascript_new_expression_creates(tmp_path):
    model = build(
        tmp_path,
        {
            "js/user.js": "export class User {}\n",
            "js/service.js": (
                'import { User } from "./user.js";\n'
                "export function make() { return new User(); }\n"
            ),
        },
    )
    creates = edges(model, RelationshipKind.CREATES)
    assert ("javascript:js/service.make()", "javascript:js/user.User") in creates


# =====================================================================
# Cross-language collision (spec 39) and ambiguity (spec 40)
# =====================================================================

def test_cross_language_name_collision_resolves_to_python(tmp_path):
    """spec 39, the critical test: an explicit Python import must never be
    satisfied by a same-named JavaScript class."""
    model = build(
        tmp_path,
        {
            "python/base.py": PY_BASE,
            "python/user.py": PY_USER,
            "javascript/base.js": "export class BaseUser {}\n",
        },
    )
    inherits = edges(model, RelationshipKind.INHERITS)
    assert ("python:python.user.User", "python:python.base.BaseUser") in inherits
    assert ("python:python.user.User", "javascript:javascript/base.BaseUser") not in inherits


def test_ambiguous_simple_name_creates_no_edge(tmp_path):
    """spec 22/40: two equally valid candidates and no import -> no guess."""
    model = build(
        tmp_path,
        {
            "a.py": "class BaseUser:\n    pass\n",
            "b.py": "class BaseUser:\n    pass\n",
            "c.py": "class User(BaseUser):\n    pass\n",
        },
    )
    inherits = {s for s, _ in edges(model, RelationshipKind.INHERITS)}
    assert "python:c.User" not in inherits
    ambiguous = [
        u for u in model.metadata["unresolved_references"]
        if u["reason"] == "ambiguous_simple_name" and u["referrer_id"] == "python:c.User"
    ]
    assert len(ambiguous) == 1
    assert set(ambiguous[0]["candidates"]) == {"python:a.BaseUser", "python:b.BaseUser"}


def test_attribute_call_is_never_guessed(tmp_path):
    """spec 18: `user.save()` must not resolve to an arbitrary save()."""
    model = build(
        tmp_path,
        {
            "python/user.py": "class User:\n    def save(self):\n        pass\n",
            "python/svc.py": "def go(user):\n    user.save()\n",
        },
    )
    assert ("python:python.svc.go(?)", "python:python.user.User.save(?)") not in edges(
        model, RelationshipKind.CALLS
    )
    assert "receiver_type_unknown" in reasons(model)


# =====================================================================
# External entities (spec 23/24) and import-entity distinction (spec 25)
# =====================================================================

def test_third_party_import_becomes_external_not_a_fake_internal(tmp_path):
    model = build(
        tmp_path,
        {"python/api.py": "from fastapi import FastAPI\n\nclass App(FastAPI):\n    pass\n"},
    )
    got = ids(model)
    assert "external::fastapi.FastAPI" in got
    assert "python:python.fastapi.FastAPI" not in got
    assert ("python:python.api.App", "external::fastapi.FastAPI") in edges(
        model, RelationshipKind.INHERITS
    )


def test_unknown_bare_symbol_is_unresolved_not_external(tmp_path):
    """spec 24: an unresolved symbol is not automatically an external entity."""
    model = build(tmp_path, {"python/user.py": "class User(Mystery):\n    pass\n"})
    assert "external::Mystery" not in ids(model)
    assert "unresolved_symbol" in reasons(model)


def test_import_declaration_entity_is_distinct_from_target(tmp_path):
    """spec 25."""
    model = build(tmp_path, {"js/base.js": JS_BASE, "js/user.js": JS_USER})
    got = ids(model)
    assert "javascript:js/user::import::./base.js" in got
    assert "javascript:js/base.BaseUser" in got
    assert ("javascript:js/user", "javascript:js/user::import::./base.js") in edges(
        model, RelationshipKind.IMPORTS
    )


# =====================================================================
# Identity, determinism, diagnostics (spec 2, 29-33, 35)
# =====================================================================

def test_no_absolute_paths_in_canonical_ids(tmp_path):
    model = build(
        tmp_path,
        {"python/user.py": PY_USER, "python/base.py": PY_BASE, "js/user.js": JS_USER, "js/base.js": JS_BASE},
    )
    root = tmp_path.as_posix()
    for e in model.entities:
        assert root not in e.id
        assert "/mnt/" not in e.id
        assert ":\\" not in e.id
        assert not e.id.startswith("python:/")
        assert not e.id.startswith("javascript:/")


def test_source_locations_are_repository_relative(tmp_path):
    model = build(tmp_path, {"python/user.py": PY_USER, "python/base.py": PY_BASE})
    user = next(e for e in model.entities if e.id == "python:python.user.User")
    assert Path(user.location.file).as_posix() == "python/user.py"
    assert user.location.start_line == 4
    assert user.location.start_column == 0


def test_determinism_across_runs(tmp_path):
    files = {
        "python/base.py": PY_BASE,
        "python/user.py": PY_USER,
        "js/base.js": JS_BASE,
        "js/user.js": JS_USER,
        "test/User.java": "package test;\nclass User {}\n",
    }
    first = build(tmp_path / "a", files)
    second = build(tmp_path / "b", files)
    assert [e.id for e in first.entities] == [e.id for e in second.entities]
    assert [
        (r.source_id, r.target_id, r.kind.value) for r in first.relationships
    ] == [(r.source_id, r.target_id, r.kind.value) for r in second.relationships]


def test_relationships_are_deduplicated(tmp_path):
    """spec 27: (source, target, kind) is unique."""
    model = build(tmp_path, {"python/base.py": PY_BASE, "python/user.py": PY_USER})
    keys = [(r.source_id, r.target_id, r.kind.value) for r in model.relationships]
    assert len(keys) == len(set(keys))


def test_parse_errors_reported_without_discarding_the_file(tmp_path):
    """spec 30."""
    model = build(
        tmp_path,
        {"python/broken.py": "class Good:\n    pass\n\n)\n"},
    )
    assert "python:python.broken.Good" in ids(model)
    errs = model.metadata["parse_errors"]
    assert errs
    assert errs[0]["file"] == "python/broken.py"
    assert "start_column" in errs[0] and "node_type" in errs[0]


def test_file_entities_exist_and_contain_modules(tmp_path):
    """spec 35."""
    model = build(tmp_path, {"python/user.py": "class User:\n    pass\n"})
    assert "file:python/user.py" in ids(model)
    assert ("file:python/user.py", "python:python.user") in edges(model, RelationshipKind.CONTAINS)


def test_no_identity_collisions_in_a_clean_repository(tmp_path):
    model = build(
        tmp_path,
        {"python/base.py": PY_BASE, "python/user.py": PY_USER, "js/base.js": JS_BASE, "js/user.js": JS_USER},
    )
    assert model.metadata["identity_collisions"] == []
