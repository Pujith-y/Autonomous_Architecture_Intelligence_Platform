"""Integration tests: need a reachable Neo4j (>= 5.26 for dynamic labels). Skipped otherwise."""
import pytest

from app.knowledge_graph.neo4j.client import check_neo4j_connection, driver
from app.knowledge_graph.neo4j.repository import Neo4jRepository
from app.knowledge_graph.neo4j.query_repository import (
    DEPENDENCY_FORWARD_KINDS, DEPENDENCY_REVERSE_KINDS, EntityNotFoundError,
    Neo4jQueryRepository, RELATIONSHIP_QUERY_MAP,
)
from app.knowledge_graph.neo4j.resolution.entity_resolver import (
    AmbiguousEntityError, EntityResolver,
)
from app.repository_model.entities import Entity
from app.repository_model.enums import EntityKind as EK, RelationshipKind as RK
from app.repository_model.model import RepositoryModel
from app.repository_model.relationships import Relationship

U, R = 990001, 1
U2 = 990002


def E(id_, kind, name, qn=None, lang="python"):
    return Entity(id=id_, kind=kind, name=name, qualified_name=qn or id_, language=lang)


def rel(s, t, k, **md):
    return Relationship(s, t, k, md)


def build_model() -> RepositoryModel:
    ents = [
        E("repository::demo", EK.REPOSITORY, "demo", "demo"),
        E("python.base", EK.MODULE, "base"),
        E("python.user", EK.MODULE, "user"),
        E("python.base.BaseUser", EK.CLASS, "BaseUser"),
        E("python.base.Mixin", EK.CLASS, "Mixin"),
        E("python.user.User", EK.CLASS, "User"),
        E("python.base.BaseUser.save", EK.METHOD, "save"),
        E("python.user.User.save", EK.METHOD, "save"),
        E("python.user.import.base.BaseUser", EK.IMPORT, "base.BaseUser", "base.BaseUser"),
        E("python.iface.Saveable", EK.INTERFACE, "Saveable"),
        E("python.audit.log", EK.FUNCTION, "log"),
        E("ts.user.User", EK.CLASS, "User", "ts.user.User", "typescript"),
        E("python.cyc.A", EK.CLASS, "A"),
        E("python.cyc.B", EK.CLASS, "B"),
        E("python.cfg", EK.CONFIGURATION, "cfg"),
        E("python.dec", EK.DECORATOR, "dec"),
    ]
    rels = [
        rel("repository::demo", "python.base", RK.CONTAINS),
        rel("repository::demo", "python.user", RK.CONTAINS),
        rel("python.base", "python.base.BaseUser", RK.CONTAINS),
        rel("python.user", "python.user.User", RK.CONTAINS),
        rel("python.user.User", "python.user.User.save", RK.CONTAINS),
        rel("python.base.BaseUser", "python.base.BaseUser.save", RK.CONTAINS),
        rel("python.user", "python.user.import.base.BaseUser", RK.IMPORTS),
        rel("python.user.User", "python.base.BaseUser", RK.INHERITS),
        rel("python.user.User", "python.base.Mixin", RK.INHERITS),
        rel("python.user.User", "python.iface.Saveable", RK.IMPLEMENTS),
        rel("python.user.User.save", "python.base.BaseUser.save", RK.OVERRIDES),
        rel("python.user.User.save", "python.audit.log", RK.CALLS, resolution_method="exact", line=7),
        rel("python.audit.log", "python.user.User.save", RK.CALLS),  # call cycle
        rel("python.user.User.save", "python.base.BaseUser", RK.ACCEPTS),
        rel("python.user.User.save", "python.audit.log", RK.REFERENCES),  # parallel edge
        rel("python.user.User.save", "python.dec", RK.DECORATED_BY),
        rel("python.cfg", "python.user.User", RK.CONFIGURES),
        rel("python.cyc.A", "python.cyc.B", RK.INHERITS),
        rel("python.cyc.B", "python.cyc.A", RK.INHERITS),
    ]
    # one generic edge per kind to exercise every relationship type
    ents += [E("gen.a", EK.CLASS, "GenA"), E("gen.b", EK.CLASS, "GenB")]
    rels += [rel("gen.a", "gen.b", k) for k in RK]
    return RepositoryModel("demo", ents, rels)


def _wipe():
    with driver.session() as s:
        s.run("MATCH (n:Entity) WHERE n.id STARTS WITH 'user:99000' DETACH DELETE n")


@pytest.fixture(scope="module", autouse=True)
def graph():
    if not check_neo4j_connection(max_retries=1, delay=0):
        pytest.skip("Neo4j not available")
    _wipe()
    Neo4jRepository().replace_repository_graph(build_model(), U, R)
    Neo4jRepository().replace_repository_graph(build_model(), U2, R)  # same ids, other user
    Neo4jRepository().replace_repository_graph(build_model(), U, 2)   # same user, other repo
    yield
    _wipe()


Q = Neo4jQueryRepository()
ids = lambda rows: [r["id"] for r in rows]


# ---- entity resolution ------------------------------------------------------
def test_resolution_priority_and_ambiguity():
    res = EntityResolver(Q)
    assert res.resolve(U, R, "python.user.User").entity["match_kind"] == "id"
    assert res.resolve(U, R, "python.base.BaseUser").resolved
    assert res.resolve(U, R, "python.user.User").entity["id"].endswith("python.user.User")
    # suffix unique -> resolved
    assert res.resolve(U, R, "base.BaseUser", kinds=["class"]).entity["match_kind"] == "qualified_name_suffix"
    # simple name duplicated across languages -> ambiguous (suffix tier ".User")
    r = res.resolve(U, R, "User")
    assert r.ambiguous and len(r.candidates) >= 2
    with pytest.raises(AmbiguousEntityError):
        res.require_id(U, R, "User")
    assert not res.resolve(U, R, "NoSuchThing").resolved
    assert not res.resolve(U, R, "NoSuchThing").ambiguous


def test_resolution_repository_isolation():
    assert Q.find_entity(U, 777, "python.user.User") == []
    for row in Q.find_entity(U, R, "User"):
        assert row["id"].startswith(f"user:{U}::repo:{R}::")


def test_unique_higher_tier_not_made_ambiguous():
    # exact qn tier hits one node even though simple-name tier ("save") has two
    assert len(Q.find_entity(U, R, "python.user.User.save")) == 1
    assert len(Q.find_entity(U, R, "save")) == 2  # same-tier duplicates reported


# ---- call graph (regression) -----------------------------------------------
def test_callers_callees():
    callees = Q.find_callees(U, R, "python.user.User.save")
    assert [c["name"] for c in callees] == ["log"]
    assert callees[0]["relationship"]["resolution_method"] == "exact"
    assert "calls" == callees[0]["relationship_type"]
    assert "function" in callees[0]["labels"]
    ns = f"user:{U}::repo:{R}::"
    save, log = ns + "python.user.User.save", ns + "python.audit.log"
    # fixture edges: save -calls-> log and log -calls-> save (a deliberate call cycle)
    assert ids(Q.find_callers(U, R, "python.user.User.save")) == [log]
    assert ids(Q.find_callees(U, R, "python.audit.log")) == [save]
    assert ids(Q.find_callers(U, R, "python.audit.log")) == [save]
    # direction consistency: X in callers(Y)  <=>  Y in callees(X)
    for a, b in ((save, log), (log, save)):
        assert a in ids(Q.find_callers(U, R, b)) and b in ids(Q.find_callees(U, R, a))
    assert Q.find_callers(U, R, "does.not.exist") == []


# ---- every relationship kind is queryable generically ----------------------
@pytest.mark.parametrize("kind", list(RK))
def test_generic_relationship_per_kind(kind):
    out = Q.find_relationships(U, R, "gen.a", kinds=[kind], direction="outgoing")
    inc = Q.find_relationships(U, R, "gen.b", kinds=[kind], direction="incoming")
    assert len(out) == len(inc) == 1
    assert out[0]["relationship_type"] == kind.value and out[0]["direction"] == "outgoing"
    assert inc[0]["direction"] == "incoming"
    assert out[0]["source"]["id"].endswith("gen.a") and out[0]["target"]["id"].endswith("gen.b")


def test_parallel_edges_preserved():
    types = {e["relationship_type"] for e in Q.find_relationships(
        U, R, "python.user.User.save", direction="outgoing") if e["target"]["id"].endswith("audit.log")}
    assert types == {"calls", "references"}


def test_relationship_map_is_complete():
    assert set(RELATIONSHIP_QUERY_MAP) == set(RK)
    assert all(hasattr(Q, m) for ms in RELATIONSHIP_QUERY_MAP.values() for m in ms)


# ---- dependencies / import representation -----------------------------------
def test_import_declaration_vs_symbol():
    deps = Q.find_dependencies(U, R, "python.user")
    imp = [d for d in deps if d["relationship_type"] == "imports"]
    assert [d["name"] for d in imp] == ["base.BaseUser"] and "import" in imp[0]["labels"]
    # no invented link from the import entity to the class
    assert Q.find_relationships(U, R, "python.user.import.base.BaseUser", direction="outgoing") == []
    # inheritance to the real symbol is independently queryable
    assert [p["qualified_name"] for p in Q.find_parent_types(U, R, "python.user.User", kinds=[RK.INHERITS])] \
        == ["python.base.BaseUser", "python.base.Mixin"]


def test_dependencies_and_dependents_semantics():
    deps = Q.find_dependencies(U, R, "python.user.User")
    assert not any(d["relationship_type"] == "contains" for d in deps)
    assert any(d["relationship_type"] == "configures" and d["direction"] == "incoming" for d in deps)
    dependents = Q.find_dependents(U, R, "python.base.BaseUser")
    assert any(d["name"] == "User" for d in dependents)
    assert {RK.CONTAINS, RK.EXPORTS, RK.EXPOSES}.isdisjoint(DEPENDENCY_FORWARD_KINDS + DEPENDENCY_REVERSE_KINDS)


def test_missing_entity_raises_for_new_methods():
    with pytest.raises(EntityNotFoundError):
        Q.find_dependencies(U, R, "nope")
    with pytest.raises(EntityNotFoundError):
        Q.analyze_impact(U, R, "nope")


# ---- hierarchy --------------------------------------------------------------
def test_hierarchy():
    anc = Q.find_ancestors(U, R, "python.user.User", max_depth=3)
    assert {a["name"] for a in anc} >= {"BaseUser", "Mixin", "Saveable"}
    assert all(a["depth"] == 1 for a in anc)
    assert [i["name"] for i in Q.find_implementations(U, R, "python.iface.Saveable")] == ["User"]
    assert [i["name"] for i in Q.find_inheriting_types(U, R, "python.base.BaseUser")] == ["User"]
    assert [o["qualified_name"] for o in Q.find_overrides(U, R, "python.user.User.save")] == ["python.base.BaseUser.save"]
    assert Q.find_overrides(U, R, "python.base.BaseUser.save", "incoming")[0]["name"] == "save"


def test_cycles_terminate_and_dedupe():
    anc = Q.find_ancestors(U, R, "python.cyc.A", max_depth=10)
    assert [a["name"] for a in anc] == ["B"]  # start never returned, no repeats
    desc = Q.find_descendants(U, R, "python.cyc.A", max_depth=10)
    assert [d["name"] for d in desc] == ["B"]


def test_depth_validation():
    for bad in (0, 11, -1, "3", True):
        with pytest.raises(ValueError):
            Q.find_ancestors(U, R, "python.user.User", max_depth=bad)
    with pytest.raises(ValueError):
        Q.find_relationships(U, R, "python.user.User", kinds=["bogus"])


# ---- structure ---------------------------------------------------------------
def test_structure():
    assert [c["name"] for c in Q.find_containers(U, R, "python.user.User")] == ["user"]
    chain = Q.find_containers(U, R, "python.user.User.save", max_depth=5)
    assert [c["depth"] for c in chain] == [1, 2, 3]
    assert [c["name"] for c in Q.find_contained(U, R, "python.user.User", entity_kinds=["method"])] == ["save"]
    tree = Q.find_repository_structure(U, R, max_depth=3)
    assert {"base", "user", "User", "BaseUser"} <= {t["name"] for t in tree}
    assert all(t["id"].startswith(f"user:{U}::repo:{R}::") for t in tree)


def test_signature_references_metadata_architecture():
    sig = Q.find_signature(U, R, "python.user.User.save")
    assert [(s["relationship_type"], s["name"]) for s in sig] == [("accepts", "BaseUser")]
    assert Q.find_signature_usages(U, R, "python.base.BaseUser")[0]["name"] == "save"
    assert Q.find_references(U, R, "python.audit.log", "incoming")[0]["name"] == "save"
    assert Q.find_metadata(U, R, "python.user.User.save")[0]["name"] == "dec"
    assert Q.find_architecture(U, R, "python.user.User", direction="incoming")[0]["relationship_type"] == "configures"


# ---- impact -------------------------------------------------------------------
def test_impact_evidence_direct_vs_indirect():
    out = Q.analyze_impact(U, R, "python.base.BaseUser", max_depth=3)
    by = {i["name"]: i for i in out["impacted"]}
    assert by["User"]["impact"] == "direct"
    assert by["save"]["impact"] == "direct"          # User.save accepts BaseUser
    assert by["User"]["edges"][0]["type"] == "inherits"
    assert by["User"]["edges"][0]["target_id"].endswith("python.base.BaseUser")
    assert "cfg" not in by  # 'configures' chains are single-direction; not mixed into a path
    deep = Q.analyze_impact(U, R, "python.base.BaseUser.save", max_depth=3)["impacted"]
    assert {"name": "save", "depth": 1} == {k: deep[0][k] for k in ("name", "depth")}
    assert deep[0]["impact"] == "direct"
    assert len({i["id"] for i in out["impacted"]}) == len(out["impacted"])
    assert "runtime" in out["disclaimer"]
    assert all(i["path"][0].endswith("python.base.BaseUser") for i in out["impacted"])


def test_impact_respects_kind_filter_and_cycles():
    out = Q.analyze_impact(U, R, "python.audit.log", max_depth=10, kinds=[RK.CALLS])
    assert [i["name"] for i in out["impacted"]] == ["save"]


# ---- isolation ----------------------------------------------------------------
def test_user_and_repo_isolation_including_malformed_cross_edges():
    foreign = f"user:{U2}::repo:{R}::python.audit.log"
    mine = f"user:{U}::repo:{R}::python.audit.log"
    with driver.session() as s:  # malformed cross-user edge
        s.run("MATCH (a:Entity {id:$a}),(b:Entity {id:$b}) MERGE (a)-[:calls]->(b)", a=mine, b=foreign)
        s.run("MATCH (a:Entity {id:$a}),(b:Entity {id:$b}) MERGE (b)-[:calls]->(a)", a=mine, b=foreign)
    try:
        assert all(r["id"].startswith(f"user:{U}::repo:{R}::") for r in Q.find_callees(U, R, "python.audit.log"))
        assert all(r["id"].startswith(f"user:{U}::repo:{R}::") for r in Q.find_callers(U, R, "python.audit.log"))
        out = Q.analyze_impact(U, R, "python.audit.log", max_depth=5)
        assert all(i["id"].startswith(f"user:{U}::repo:{R}::") for i in out["impacted"])
        # a foreign namespaced id must not be queryable
        with pytest.raises(EntityNotFoundError):
            Q.find_dependencies(U, R, foreign)
    finally:
        with driver.session() as s:
            s.run("MATCH (a:Entity {id:$a})-[r:calls]-(b:Entity {id:$b}) DELETE r", a=mine, b=foreign)


# ---- persistence diagnostics / limitations ------------------------------------
PR = 99  # scratch repository id for persistence tests


def _tiny(rels, extra=()):
    ents = [E("repository::t", EK.REPOSITORY, "t", "t"), E("p.a", EK.FUNCTION, "a"),
            E("p.b", EK.FUNCTION, "b"), *extra]
    return RepositoryModel("t", ents, rels)


def test_dangling_relationship_is_detected_and_not_persisted():
    model = _tiny([rel("p.a", "p.b", RK.CALLS), rel("p.a", "p.ghost", RK.IMPORTS)])
    seen = []
    orig = Neo4jRepository._log_dangling
    Neo4jRepository._log_dangling = staticmethod(lambda d, total, ns: seen.append((d, total)))
    try:
        Neo4jRepository().replace_repository_graph(model, U, PR)
    finally:
        Neo4jRepository._log_dangling = orig
    assert len(seen) == 1 and seen[0][1] == 2
    assert [d["kind"] for d in seen[0][0]] == ["imports"]
    assert [r["name"] for r in Q.find_callees(U, PR, "p.a")] == ["b"]
    assert Q.find_relationships(U, PR, "p.a", kinds=[RK.IMPORTS]) == []  # confirms silent drop


def test_replacement_is_a_full_swap():
    Neo4jRepository().replace_repository_graph(_tiny([rel("p.a", "p.b", RK.CALLS)]), U, PR)
    Neo4jRepository().replace_repository_graph(_tiny([rel("p.b", "p.a", RK.CALLS)]), U, PR)
    assert Q.find_callees(U, PR, "p.a") == []
    assert [r["name"] for r in Q.find_callees(U, PR, "p.b")] == ["a"]


def test_multiple_call_sites_characterization():
    """Documents CURRENT behaviour: MERGE collapses repeated (src, kind, tgt) edges and
    `SET r += metadata` keeps the LAST call site's properties. If the extractor emits
    several call-site relationships, earlier sites are lost. This test pins that fact;
    change it together with any persistence fix (e.g. aggregating call sites)."""
    model = _tiny([rel("p.a", "p.b", RK.CALLS, line=1), rel("p.a", "p.b", RK.CALLS, line=9)])
    Neo4jRepository().replace_repository_graph(model, U, PR)
    rows = Q.find_callees(U, PR, "p.a")
    assert len(rows) == 1 and rows[0]["relationship"]["line"] == 9