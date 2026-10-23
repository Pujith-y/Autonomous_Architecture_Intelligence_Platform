"""Neo4j graph query layer for AAIP.

Storage facts this module relies on (verified against ``repository.py``):

* Entities are ``(:Entity:<kind>)`` nodes; kind labels are LOWERCASE enum values
  (``class``, ``method``...), plus the capitalised ``Entity`` label.
* Node ids are namespaced: ``user:{u}::repo:{r}::{local_id}``; the repository
  entity's id is the bare namespace (see ``_namespace``).
* Relationship types are LOWERCASE enum values (``calls``, ``inherits``...).
  One edge per (source, type, target) because persistence uses MERGE; metadata
  of repeated edges is merged with ``SET r +=`` (last write wins).
* Entity ``qualified_name`` / ``name`` are NOT namespaced.

Every query is scoped to ``user_id``/``repository_id`` (both endpoints of every
edge, and every node on every path). Unless noted, ids returned are the stored
namespaced ids. Entity-specific methods accept repository-local ids or the
namespaced id of the same repository.

Compatibility: find_callers/find_callees keep returning ``[]`` for unknown
entities (legacy). All newer entity-specific methods raise EntityNotFoundError.
"""
from __future__ import annotations

from typing import Iterable

from neo4j.exceptions import DriverError, Neo4jError

from app.core.logger import logger
from app.database.neo4j import driver
from app.knowledge_graph.neo4j.namespace import _namespace
from app.repository_model.enums import RelationshipKind as RK

# --------------------------------------------------------------------------
# Semantic mapping of relationship kinds
# --------------------------------------------------------------------------
HIERARCHY_KINDS = (RK.INHERITS, RK.EXTENDS, RK.IMPLEMENTS)
CONTAINMENT_KINDS = (RK.CONTAINS,)
SIGNATURE_KINDS = (RK.ACCEPTS, RK.RETURNS)
METADATA_KINDS = (RK.DECORATED_BY, RK.ANNOTATED_WITH)
ARCHITECTURE_KINDS = (RK.EXPOSES, RK.HANDLED_BY, RK.MAPS_TO, RK.RELATES_TO, RK.CONFIGURES)

# "source relies on target" (forward). Included in find_dependencies.
DEPENDENCY_FORWARD_KINDS = (
    RK.IMPORTS, RK.USES, RK.DEPENDS_ON, RK.CALLS, RK.REFERENCES,
    RK.ACCEPTS, RK.RETURNS, RK.CREATES, RK.COMPOSES,
    RK.INHERITS, RK.EXTENDS, RK.IMPLEMENTS, RK.OVERRIDES,
    RK.DECORATED_BY, RK.ANNOTATED_WITH, RK.MAPS_TO, RK.HANDLED_BY, RK.RELATES_TO,
)
# "target relies on source" (reverse): config -configures-> thing.
DEPENDENCY_REVERSE_KINDS = (RK.CONFIGURES,)
# Excluded from dependencies: CONTAINS (structure), EXPORTS (provision, not reliance),
# EXPOSES (ownership of an endpoint, not reliance). Use specialised queries.
# NOTE: edge directions of handled_by/configures/exposes/maps_to/relates_to are
# assumptions taken from the vocabulary; verify against extractor output.

# Every RelationshipKind -> intended query entry points (completeness is tested).
RELATIONSHIP_QUERY_MAP: dict[RK, tuple[str, ...]] = {
    RK.CONTAINS: ("find_containers", "find_contained", "find_repository_structure"),
    RK.CREATES: ("find_created",),
    RK.IMPORTS: ("find_dependencies", "find_dependents"),
    RK.EXPORTS: ("find_exports",),
    RK.USES: ("find_dependencies", "find_dependents"),
    RK.DEPENDS_ON: ("find_dependencies", "find_dependents"),
    RK.CALLS: ("find_callers", "find_callees"),
    RK.INHERITS: ("find_parent_types", "find_ancestors", "find_inheriting_types"),
    RK.IMPLEMENTS: ("find_implementations", "find_parent_types"),
    RK.EXTENDS: ("find_inheriting_types", "find_parent_types"),
    RK.COMPOSES: ("find_composition",),
    RK.OVERRIDES: ("find_overrides",),
    RK.REFERENCES: ("find_references",),
    RK.RETURNS: ("find_signature", "find_signature_usages"),
    RK.ACCEPTS: ("find_signature", "find_signature_usages"),
    RK.DECORATED_BY: ("find_metadata",),
    RK.ANNOTATED_WITH: ("find_metadata",),
    RK.EXPOSES: ("find_architecture",),
    RK.HANDLED_BY: ("find_architecture",),
    RK.MAPS_TO: ("find_architecture",),
    RK.RELATES_TO: ("find_architecture",),
    RK.CONFIGURES: ("find_architecture",),
}
# find_relationships() handles every kind generically.

# Default impact kinds: everything in dependency semantics (impact flows opposite
# to dependency direction: a dependent of a changed entity may be affected).
DEFAULT_IMPACT_KINDS = DEPENDENCY_FORWARD_KINDS + DEPENDENCY_REVERSE_KINDS

MAX_DEPTH_LIMIT = 10
DEFAULT_LIMIT = 1000
MAX_LIMIT = 10000

IMPACT_DISCLAIMER = (
    "Graph reachability indicates potential, statically-inferred impact only; "
    "it does not prove runtime impact."
)


class GraphQueryError(Exception):
    """Sanitised failure of a graph query (details are only logged)."""


class EntityNotFoundError(GraphQueryError):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _emap(var: str) -> str:
    return (
        f"{{id: {var}.id, name: {var}.name, qualified_name: {var}.qualified_name, "
        f"labels: labels({var}), language: {var}.language, file: {var}.file, "
        f"start_line: {var}.start_line, end_line: {var}.end_line}}"
    )


def _scope(var: str) -> str:
    return f"({var}.id = $ns OR {var}.id STARTS WITH $prefix)"


def _kinds(kinds: Iterable | None, default: Iterable) -> list[str]:
    raw = default if kinds is None else kinds
    if isinstance(raw, (str, RK)):
        raw = [raw]
    out: list[str] = []
    for k in raw:
        try:
            v = RK(k).value
        except ValueError:
            raise ValueError(f"Unknown relationship kind: {k!r}") from None
        if v not in out:
            out.append(v)
    if not out:
        raise ValueError("At least one relationship kind is required")
    return out


def _depth(max_depth: int) -> int:
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) \
            or not 1 <= max_depth <= MAX_DEPTH_LIMIT:
        raise ValueError(f"max_depth must be an integer in 1..{MAX_DEPTH_LIMIT}")
    return max_depth


def _limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer in 1..{MAX_LIMIT}")
    return limit


def _direction(direction: str, allowed=("outgoing", "incoming", "both")) -> str:
    if direction not in allowed:
        raise ValueError(f"direction must be one of {allowed}")
    return direction


def _flatten(edge: dict, entity_id: str) -> dict:
    """Edge -> flat row describing the *other* endpoint (legacy row shape)."""
    outgoing = edge["direction"] == "outgoing"
    other = edge["target"] if outgoing else edge["source"]
    return {
        **other,
        "relationship_type": edge["relationship_type"],
        "relationship": edge["relationship"],
        "direction": edge["direction"],
    }


class Neo4jQueryRepository:
    def __init__(self, neo4j_driver=None):
        self._driver = neo4j_driver

    # ---- infrastructure ---------------------------------------------------
    def _run(self, cypher: str, **params) -> list[dict]:
        drv = self._driver or driver
        try:
            with drv.session() as session:
                return session.run(cypher, **params).data()
        except (Neo4jError, DriverError):
            logger.exception("Neo4j graph query failed")
            raise GraphQueryError("Graph query failed") from None

    @staticmethod
    def _scope_params(user_id: int, repository_id: int) -> dict:
        for v in (user_id, repository_id):
            if isinstance(v, bool) or not isinstance(v, int):
                raise ValueError("user_id and repository_id must be integers")
        ns = f"user:{user_id}::repo:{repository_id}"
        return {"ns": ns, "prefix": f"{ns}::"}

    def _scoped_id(self, user_id: int, repository_id: int, entity_id: str) -> str:
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("entity id must be a non-empty string")
        p = self._scope_params(user_id, repository_id)
        if entity_id == p["ns"] or entity_id.startswith(p["prefix"]):
            return entity_id  # already namespaced for this repository
        return _namespace(user_id, repository_id, entity_id)

    def get_entity(self, user_id: int, repository_id: int, entity_id: str) -> dict | None:
        p = self._scope_params(user_id, repository_id)
        rows = self._run(
            f"MATCH (e:Entity {{id: $id}}) WHERE {_scope('e')} RETURN {_emap('e')} AS e",
            id=self._scoped_id(user_id, repository_id, entity_id), **p,
        )
        return rows[0]["e"] if rows else None

    def _require(self, user_id, repository_id, entity_id) -> str:
        if self.get_entity(user_id, repository_id, entity_id) is None:
            raise EntityNotFoundError("Entity not found")
        return self._scoped_id(user_id, repository_id, entity_id)

    # ---- A. entity lookup -------------------------------------------------
    def find_entity(
        self,
        user_id: int,
        repository_id: int,
        entity_name: str,
        *,
        kinds: Iterable | None = None,
        exclude_kinds: Iterable | None = None,
    ) -> list[dict]:
        """Return candidates of the best (lowest) matching tier only.

        Tiers: 0 exact id (local or namespaced) -> 1 exact qualified_name ->
        2 qualified_name suffix on a '.', '::' or '/' boundary -> 3 exact simple name.
        Result rows carry ``match_kind``. >1 row means ambiguity at that tier.
        ``kinds``/``exclude_kinds`` take EntityKind values (e.g. "class", "import").
        """
        if not isinstance(entity_name, str) or not entity_name.strip():
            raise ValueError("entity_name must be a non-empty string")
        name = entity_name.strip()
        p = self._scope_params(user_id, repository_id)
        rows = self._run(
            """
            MATCH (e:Entity)
            WHERE (e.id = $ns OR e.id STARTS WITH $prefix)
            WITH e, CASE
                WHEN e.id = $exact_id THEN 0
                WHEN e.qualified_name = $name THEN 1
                WHEN e.qualified_name ENDS WITH $dot
                  OR e.qualified_name ENDS WITH $colons
                  OR e.qualified_name ENDS WITH $slash THEN 2
                WHEN e.name = $name THEN 3
            END AS tier
            WHERE tier IS NOT NULL
              AND ($kinds IS NULL OR any(l IN labels(e) WHERE l IN $kinds))
              AND NOT any(l IN labels(e) WHERE l IN $exclude)
            RETURN e.id AS id, e.name AS name, e.qualified_name AS qualified_name,
                   labels(e) AS labels, e.language AS language, tier
            ORDER BY tier, e.id
            """,
            exact_id=self._scoped_id(user_id, repository_id, name),
            name=name, dot=f".{name}", colons=f"::{name}", slash=f"/{name}",
            kinds=None if kinds is None else [str(getattr(k, "value", k)) for k in kinds],
            exclude=[str(getattr(k, "value", k)) for k in (exclude_kinds or [])],
            **p,
        )
        if not rows:
            return []
        best = rows[0]["tier"]
        names = {0: "id", 1: "qualified_name", 2: "qualified_name_suffix", 3: "name"}
        out = []
        for r in rows:
            if r["tier"] == best:
                r = dict(r)
                r["match_kind"] = names[r.pop("tier")]
                out.append(r)
        return out

    # ---- generic edge / neighborhood -------------------------------------
    def _edges(self, user_id, repository_id, entity_id, out_kinds, in_kinds, limit) -> list[dict]:
        p = self._scope_params(user_id, repository_id)
        sid = self._scoped_id(user_id, repository_id, entity_id)
        return self._run(
            f"""
            CALL () {{
                MATCH (a:Entity {{id: $id}})-[r]->(b:Entity)
                WHERE type(r) IN $out_kinds AND {_scope('b')}
                RETURN {_emap('a')} AS source, {_emap('b')} AS target,
                       type(r) AS relationship_type, properties(r) AS relationship,
                       'outgoing' AS direction
                UNION
                MATCH (a:Entity)-[r]->(b:Entity {{id: $id}})
                WHERE type(r) IN $in_kinds AND {_scope('a')}
                RETURN {_emap('a')} AS source, {_emap('b')} AS target,
                       type(r) AS relationship_type, properties(r) AS relationship,
                       'incoming' AS direction
            }}
            RETURN source, target, relationship_type, relationship, direction
            ORDER BY source.id, relationship_type, target.id, direction
            LIMIT $limit
            """,
            id=sid, out_kinds=out_kinds, in_kinds=in_kinds, limit=_limit(limit), **p,
        )

    def find_relationships(
        self, user_id, repository_id, entity_id: str,
        kinds: Iterable | None = None, direction: str = "both",
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        """Direct edges of one entity. ``kinds=None`` means all kinds.

        Row: {source, target, relationship_type, relationship, direction}
        where direction is relative to ``entity_id``.
        """
        _direction(direction)
        ks = _kinds(kinds, RK)
        self._require(user_id, repository_id, entity_id)
        return self._edges(
            user_id, repository_id, entity_id,
            ks if direction in ("outgoing", "both") else [],
            ks if direction in ("incoming", "both") else [],
            limit,
        )

    def find_neighbors(self, user_id, repository_id, entity_id, direction="both",
                       kinds=None, limit=DEFAULT_LIMIT) -> list[dict]:
        """Alias of find_relationships (neighborhood inspection)."""
        return self.find_relationships(user_id, repository_id, entity_id, kinds, direction, limit)

    def _flat(self, user_id, repository_id, entity_id, kinds, direction, limit,
              require=True) -> list[dict]:
        _direction(direction)
        ks = _kinds(kinds, ())  if kinds is not None else []
        if require:
            self._require(user_id, repository_id, entity_id)
        edges = self._edges(
            user_id, repository_id, entity_id,
            ks if direction in ("outgoing", "both") else [],
            ks if direction in ("incoming", "both") else [],
            limit,
        )
        return [_flatten(e, entity_id) for e in edges]

    # ---- B. call graph (legacy-compatible) --------------------------------
    def find_callers(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT) -> list[dict]:
        rows = self._flat(user_id, repository_id, entity_id, [RK.CALLS], "incoming", limit, False)
        return [self._legacy(r) for r in rows]

    def find_callees(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT) -> list[dict]:
        rows = self._flat(user_id, repository_id, entity_id, [RK.CALLS], "outgoing", limit, False)
        return [self._legacy(r) for r in rows]

    @staticmethod
    def _legacy(r: dict) -> dict:
        r = dict(r)
        r.pop("direction", None)
        return r  # keeps id/name/qualified_name/labels/language/relationship (+type, file, lines)

    # ---- C. dependencies / dependents ------------------------------------
    def find_dependencies(self, user_id, repository_id, entity_id, kinds=None,
                          limit=DEFAULT_LIMIT) -> list[dict]:
        """Entities this entity relies on (see DEPENDENCY_* constants).

        Import declarations are returned as IMPORT entities; no link to the
        imported symbol is invented.
        """
        fwd, rev = self._dep_split(kinds)
        self._require(user_id, repository_id, entity_id)
        return [_flatten(e, entity_id) for e in
                self._edges(user_id, repository_id, entity_id, fwd, rev, limit)]

    def find_dependents(self, user_id, repository_id, entity_id, kinds=None,
                        limit=DEFAULT_LIMIT) -> list[dict]:
        """Entities that rely on this entity (inverse of find_dependencies)."""
        fwd, rev = self._dep_split(kinds)
        self._require(user_id, repository_id, entity_id)
        return [_flatten(e, entity_id) for e in
                self._edges(user_id, repository_id, entity_id, rev, fwd, limit)]

    @staticmethod
    def _dep_split(kinds):
        ks = _kinds(kinds, DEPENDENCY_FORWARD_KINDS + DEPENDENCY_REVERSE_KINDS)
        rev_vals = {k.value for k in DEPENDENCY_REVERSE_KINDS}
        return [k for k in ks if k not in rev_vals], [k for k in ks if k in rev_vals]

    # ---- bounded traversal ------------------------------------------------
    def _reachable(self, user_id, repository_id, entity_id, kinds, direction, max_depth,
                   limit, entity_kinds=None) -> list[dict]:
        d = _depth(max_depth)
        types = "|".join(f"`{k}`" for k in kinds)
        if not types:
            return []
        arrow = f"-[:{types}*1..{d}]->" if direction == "outgoing" else f"<-[:{types}*1..{d}]-"
        p = self._scope_params(user_id, repository_id)
        rows = self._run(
            f"""
            MATCH path = (s:Entity {{id: $id}}){arrow}(n:Entity)
            WHERE all(x IN nodes(path) WHERE {_scope('x')})
              AND all(x IN nodes(path) WHERE single(y IN nodes(path) WHERE y = x))
              AND ($entity_kinds IS NULL OR any(l IN labels(n) WHERE l IN $entity_kinds))
            WITH n, path, length(path) AS depth
            ORDER BY depth, [x IN nodes(path) | x.id]
            WITH n, collect(path) AS paths
            WITH n, head(paths) AS best, size(paths) AS path_count
            RETURN {_emap('n')} AS entity, length(best) AS depth,
                   [x IN nodes(best) | x.id] AS path,
                   [r IN relationships(best) | {{type: type(r), source_id: startNode(r).id,
                        target_id: endNode(r).id, properties: properties(r)}}] AS edges,
                   path_count
            ORDER BY depth, entity.id
            LIMIT $limit
            """,
            id=self._scoped_id(user_id, repository_id, entity_id),
            entity_kinds=None if entity_kinds is None else [str(getattr(k, "value", k)) for k in entity_kinds],
            limit=_limit(limit), **p,
        )
        return [{**r["entity"], "depth": r["depth"], "path": r["path"],
                 "edges": r["edges"], "path_count": r["path_count"]} for r in rows]

    # ---- D. type hierarchy -------------------------------------------------
    def find_parent_types(self, user_id, repository_id, entity_id, kinds=None, limit=DEFAULT_LIMIT):
        """Direct parents (inherits/extends/implements; filter via ``kinds``)."""
        return self._direct(user_id, repository_id, entity_id, kinds, HIERARCHY_KINDS, "outgoing", limit)

    def find_child_types(self, user_id, repository_id, entity_id, kinds=None, limit=DEFAULT_LIMIT):
        """Direct children (types inheriting/extending/implementing this one)."""
        return self._direct(user_id, repository_id, entity_id, kinds, HIERARCHY_KINDS, "incoming", limit)

    def find_implementations(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT):
        """Types that IMPLEMENT the given interface/trait."""
        return self._direct(user_id, repository_id, entity_id, [RK.IMPLEMENTS], HIERARCHY_KINDS, "incoming", limit)

    def find_inheriting_types(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT):
        """Types that INHERIT or EXTEND the given type."""
        return self._direct(user_id, repository_id, entity_id, [RK.INHERITS, RK.EXTENDS], HIERARCHY_KINDS, "incoming", limit)

    def find_overrides(self, user_id, repository_id, entity_id, direction="outgoing", limit=DEFAULT_LIMIT):
        """outgoing: methods this one overrides; incoming: methods overriding it."""
        return self._direct(user_id, repository_id, entity_id, [RK.OVERRIDES], (RK.OVERRIDES,), direction, limit)

    def find_ancestors(self, user_id, repository_id, entity_id, max_depth=5, kinds=None, limit=DEFAULT_LIMIT):
        """Transitive supertypes with depth and shortest-path evidence (cycle-safe)."""
        ks = _kinds(kinds, HIERARCHY_KINDS)
        self._require(user_id, repository_id, entity_id)
        return self._reachable(user_id, repository_id, entity_id, ks, "outgoing", max_depth, limit)

    def find_descendants(self, user_id, repository_id, entity_id, max_depth=5, kinds=None, limit=DEFAULT_LIMIT):
        ks = _kinds(kinds, HIERARCHY_KINDS)
        self._require(user_id, repository_id, entity_id)
        return self._reachable(user_id, repository_id, entity_id, ks, "incoming", max_depth, limit)

    def _direct(self, u, r, eid, kinds, default, direction, limit):
        _direction(direction)
        ks = _kinds(kinds, default)
        allowed = {k.value for k in default}
        if not set(ks) <= allowed:
            raise ValueError(f"kinds must be a subset of {sorted(allowed)}")
        self._require(u, r, eid)
        edges = self._edges(u, r, eid,
                            ks if direction in ("outgoing", "both") else [],
                            ks if direction in ("incoming", "both") else [], limit)
        return [_flatten(e, eid) for e in edges]

    # ---- E. structure -------------------------------------------------------
    def find_containers(self, user_id, repository_id, entity_id, max_depth=1, limit=DEFAULT_LIMIT):
        """Parent container(s); max_depth>1 walks up the containment chain."""
        self._require(user_id, repository_id, entity_id)
        return self._reachable(user_id, repository_id, entity_id, [RK.CONTAINS.value],
                               "incoming", max_depth, limit)

    def find_contained(self, user_id, repository_id, entity_id, max_depth=1,
                       entity_kinds: Iterable | None = None, limit=DEFAULT_LIMIT):
        """Contained children; ``entity_kinds`` filters on result labels (e.g. ["method"])."""
        self._require(user_id, repository_id, entity_id)
        return self._reachable(user_id, repository_id, entity_id, [RK.CONTAINS.value],
                               "outgoing", max_depth, limit, entity_kinds)

    def find_repository_structure(self, user_id, repository_id, max_depth=3, limit=DEFAULT_LIMIT):
        """Containment tree below the repository entity (id == namespace)."""
        root = _namespace(user_id, repository_id, "repository::")
        return self.find_contained(user_id, repository_id, root, max_depth, None, limit)

    def find_created(self, user_id, repository_id, entity_id, direction="outgoing", limit=DEFAULT_LIMIT):
        """CREATES: entities created by this one (incoming: its creators)."""
        return self._flat(user_id, repository_id, entity_id, [RK.CREATES], direction, limit)

    # ---- F. signatures / members / composition -------------------------------
    def find_signature(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT):
        """Outgoing ACCEPTS / RETURNS of a callable (relationship_type tells which)."""
        return self._flat(user_id, repository_id, entity_id, SIGNATURE_KINDS, "outgoing", limit)

    def find_signature_usages(self, user_id, repository_id, entity_id, limit=DEFAULT_LIMIT):
        """Callables whose signature accepts/returns this entity (incoming)."""
        return self._flat(user_id, repository_id, entity_id, SIGNATURE_KINDS, "incoming", limit)

    def find_references(self, user_id, repository_id, entity_id, direction="both", limit=DEFAULT_LIMIT):
        """Non-call member/value REFERENCES (distinct from calls and uses)."""
        return self._flat(user_id, repository_id, entity_id, [RK.REFERENCES], direction, limit)

    def find_composition(self, user_id, repository_id, entity_id, direction="both", limit=DEFAULT_LIMIT):
        return self._flat(user_id, repository_id, entity_id, [RK.COMPOSES], direction, limit)

    # ---- G. metadata / architecture / exports --------------------------------
    def find_metadata(self, user_id, repository_id, entity_id, direction="outgoing", limit=DEFAULT_LIMIT):
        """DECORATED_BY / ANNOTATED_WITH."""
        return self._flat(user_id, repository_id, entity_id, METADATA_KINDS, direction, limit)

    def find_architecture(self, user_id, repository_id, entity_id, kinds=None, direction="both",
                          limit=DEFAULT_LIMIT):
        """EXPOSES / HANDLED_BY / MAPS_TO / RELATES_TO / CONFIGURES."""
        ks = _kinds(kinds, ARCHITECTURE_KINDS)
        return self._flat(user_id, repository_id, entity_id, ks, direction, limit)

    def find_exports(self, user_id, repository_id, entity_id, direction="outgoing", limit=DEFAULT_LIMIT):
        return self._flat(user_id, repository_id, entity_id, [RK.EXPORTS], direction, limit)

    # ---- H. impact analysis ----------------------------------------------------
    def analyze_impact(self, user_id, repository_id, entity_id, max_depth=3,
                       kinds: Iterable | None = None, limit=DEFAULT_LIMIT) -> dict:
        """Potentially impacted entities if ``entity_id`` changes.

        Impact flows against dependency direction: for forward kinds the traversal
        follows INCOMING edges (dependents); for reverse kinds (configures) it
        follows OUTGOING edges. Each hop-chain uses one direction.
        Rows: entity fields + impact ('direct' depth 1 | 'indirect'), depth,
        path (entity ids), edges (type/source/target/properties evidence),
        path_count, via_direction. Deduplicated by entity at minimal depth.
        """
        ks = _kinds(kinds, DEFAULT_IMPACT_KINDS)
        start = self.get_entity(user_id, repository_id, entity_id)
        if start is None:
            raise EntityNotFoundError("Entity not found")
        fwd, rev = self._dep_split(ks)
        merged: dict[str, dict] = {}
        for ks_, direction in ((fwd, "incoming"), (rev, "outgoing")):
            for row in self._reachable(user_id, repository_id, entity_id, ks_, direction,
                                       max_depth, limit):
                row["via_direction"] = direction
                cur = merged.get(row["id"])
                if cur is None or row["depth"] < cur["depth"]:
                    merged[row["id"]] = row
                elif row["depth"] == cur["depth"]:
                    cur["path_count"] += row["path_count"]
        impacted = sorted(merged.values(), key=lambda r: (r["depth"], r["id"]))[:limit]
        for r in impacted:
            r["impact"] = "direct" if r["depth"] == 1 else "indirect"
        return {
            "start": start, "max_depth": max_depth, "kinds": ks,
            "impacted": impacted, "disclaimer": IMPACT_DISCLAIMER,
        }