"""
Two-pass orchestrator: turns the discovery-stage file list into the
language-independent Entity/Relationship graph.

Pass 1 (per file, in deterministic order): dispatch to the matching
language extractor. Each extractor returns a plain dict -- entities,
intra-file relationships (CONTAINS/IMPORTS), and "pending" reference lists
(bases, implements, decorators, calls, creates) that name *symbols*, not
resolved ids yet, since resolution needs the whole-repo view.

Pass 2 (repo-wide): resolve every pending reference through a strict
priority order (see `_resolve`) that never falls back to "just grab any
same-named entity" -- ambiguous or unresolvable references are recorded in
`metadata["unresolved_references"]` and no relationship is created for
them, rather than guessing and creating a false edge.

Entity/relationship identity is centralized here too: a single registry
keyed by `Entity.id` means the same id discovered from multiple files
(e.g. a Java package declared in five files) becomes exactly one Entity,
and a (source_id, target_id, kind) relationship is only ever added once.

Only uses the dataclasses already defined in `app.repository_model`
(Entity, EntityKind, Relationship, RelationshipKind, RepositoryModel).
Everything else in here is plain dict/list -- no new model types. FILE and
CREATES are members of the central EntityKind/RelationshipKind enums, not a
local vocabulary defined here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from app.repository_model import Entity, EntityKind, Relationship, RelationshipKind, RepositoryModel, Parameter

import app.parser.aaip_code_model.extractor_python as extractor_python
import app.parser.aaip_code_model.extractor_java as extractor_java
import app.parser.aaip_code_model.extractor_javascript as extractor_javascript
from app.parser.aaip_code_model.common import (
    normalize_reference, simple_name_of, normalize_relative_path,
)
from app.parser.aaip_code_model.resolution import ResolutionMethod as RM, UnresolvedReason as UR
from app.repository_model.types import TypeReference


class _LegacyFile(Protocol):
    path: Path
    relative_path: Path
    name: str
    extension: str
    is_binary: bool
    language: str | None


class _LegacyRepo(Protocol):
    name: str
    files: list[_LegacyFile]


_EXTENSION_TO_EXTRACTOR = {
    ".py": extractor_python,
    ".pyi": extractor_python,
    ".java": extractor_java,
    ".js": extractor_javascript,
    ".jsx": extractor_javascript,
    ".mjs": extractor_javascript,
    ".cjs": extractor_javascript,
    ".ts": extractor_javascript,
    ".tsx": extractor_javascript,
    ".mts": extractor_javascript,
    ".cts": extractor_javascript,
}

_BUILTIN_CALL_NAMES = {
    # Deliberately conservative: skip resolving calls/creates to these rather
    # than let them pollute the symbol table or get treated as unresolved-
    # and-worth-recording. Not exhaustive -- expand as false positives show up.
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "range", "enumerate", "zip", "map", "filter", "isinstance", "super", "open",
    "console", "require", "setTimeout", "setInterval", "parseInt", "parseFloat",
    "Array", "Object", "Promise", "Map", "Set", "JSON", "Math", "Error",
    "System", "String", "Integer", "Double", "Boolean",
}

_NATIVE_TYPES_BY_LANGUAGE = {
    "python": {
        "str", "int", "float", "bool", "bytes",
        "list", "dict", "set", "tuple",
        "frozenset", "complex", "object",
        "None", "NoneType",
    },
    "java": {
        "byte", "short", "int", "long",
        "float", "double", "boolean", "char",
        "String", "Object", "void", "Void", "Integer", "Double", "Boolean",
        "Character", "Long", "Float", "Short", "Byte",

    },
    "javascript": {
        "string", "number", "boolean", "bigint",
        "symbol", "object", "undefined", "null",
        "any", "unknown", "never", "void",
    },
    "typescript": {
        "string", "number", "boolean", "bigint",
        "symbol", "object", "undefined", "null",
        "any", "unknown", "never", "void",
    },
}

_TYPE_LIKE_KINDS = {
    EntityKind.CLASS,
    EntityKind.INTERFACE,
    EntityKind.ENUM,
}

# Entities whose `return_type` means "what this callable returns" and whose
# `parameters` mean "what this callable accepts" -- the RETURNS/ACCEPTS
# signature relationships only ever originate from these. A FIELD entity
# also stores its declared type in `.return_type` (an existing, established
# convention in this codebase used by `_field_entity_type` below), but a
# field's type is a different relationship, not RETURNS/ACCEPTS, so FIELD is
# deliberately excluded here.
_CALLABLE_KINDS = {
    EntityKind.FUNCTION,
    EntityKind.METHOD,
    EntityKind.CONSTRUCTOR,
}


def _extractor_for(file: _LegacyFile):
    return _EXTENSION_TO_EXTRACTOR.get(file.extension.lower())


class _EntityRegistry:
    """Centralized id -> Entity index. Enforces: never silently overwrite a
    colliding id with a semantically different entity; never append a second
    copy of an id that's already present (dedup, not just "don't crash")."""

    def __init__(self) -> None:
        self.by_id: dict[str, Entity] = {}
        self.collisions: list[dict[str, Any]] = []

    def add(self, entity: Entity) -> None:
        existing = self.by_id.get(entity.id)
        if existing is None:
            self.by_id[entity.id] = entity
            return
        if existing.kind == entity.kind and existing.qualified_name == entity.qualified_name:
            # Same semantic entity re-discovered (e.g. a Java package entity
            # emitted once per file that declares it) -- dedup silently, that's
            # the expected/normal case, not an error.
            return
        # Genuinely different entities landed on the same id: don't corrupt
        # the graph by picking one arbitrarily -- keep the first, record it.
        self.collisions.append(
            {
                "entity_id": entity.id,
                "kept": {
                    "kind": existing.kind.value,
                    "qualified_name": existing.qualified_name,
                    "file": _location_file(existing),
                    "line": _location_line(existing),
                },
                "dropped": {
                    "kind": entity.kind.value,
                    "qualified_name": entity.qualified_name,
                    "file": _location_file(entity),
                    "line": _location_line(entity),
                },
            }
        )

    def values(self) -> list[Entity]:
        return list(self.by_id.values())


class _RelationshipRegistry:
    """Dedup key is (source_id, target_id, kind) -- the same edge discovered
    twice (e.g. via two extraction paths) collapses to one. First-seen
    metadata wins; later metadata for the same edge is merged in (union of
    keys, first value wins on conflict) rather than silently dropped."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str, str], Relationship] = {}

    def add(self, rel: Relationship) -> None:
        key = (rel.source_id, rel.target_id, rel.kind.value)
        existing = self._seen.get(key)
        if existing is None:
            self._seen[key] = rel
            return
        if rel.metadata:
            for k, v in rel.metadata.items():
                existing.metadata.setdefault(k, v)

    def values(self) -> list[Relationship]:
        return list(self._seen.values())


def _location_file(entity: Entity | None) -> str | None:
    loc = getattr(entity, "location", None)
    if loc is None:
        return None
    f = getattr(loc, "file", None)
    return Path(f).as_posix() if f is not None else None


def _location_line(entity: Entity | None) -> int | None:
    loc = getattr(entity, "location", None)
    return getattr(loc, "start_line", None) if loc is not None else None

def _namespace_repository_graph(
    repository_name: str,
    entities: list[Entity],
    relationships: list[Relationship],
    metadata: dict[str, Any],
) -> tuple[list[Entity], list[Relationship], dict[str, Any]]:
    """
    Make entity IDs globally unique across repositories.

    Internal orchestration uses repository-local IDs so that all resolution
    logic remains simple. Only the final RepositoryModel is namespaced.

    Example:

        python:test.User
            ->
        normalization::python:test.User

    The repository entity itself is already globally identified as:

        repository::normalization

    so it is left unchanged.
    """

    repository_id = f"repository::{repository_name}"

    # old_id -> globally unique new_id
    id_map: dict[str, str] = {}

    for entity in entities:
        if entity.id == repository_id:
            id_map[entity.id] = entity.id
        else:
            id_map[entity.id] = f"{repository_name}::{entity.id}"

    # Update entity IDs.
    for entity in entities:
        entity.id = id_map[entity.id]

    # Update every relationship endpoint.
    for relationship in relationships:
        relationship.source_id = id_map.get(
            relationship.source_id,
            relationship.source_id,
        )
        relationship.target_id = id_map.get(
            relationship.target_id,
            relationship.target_id,
        )

    # Some orchestrator metadata contains entity IDs too.
    # Keep that metadata consistent with the final graph.
    if "external_entity_ids" in metadata:
        metadata["external_entity_ids"] = [
            id_map.get(entity_id, entity_id)
            for entity_id in metadata["external_entity_ids"]
        ]

    if "unresolved_references" in metadata:
        for reference in metadata["unresolved_references"]:
            if "referrer_id" in reference:
                reference["referrer_id"] = id_map.get(
                    reference["referrer_id"],
                    reference["referrer_id"],
                )

            if "candidates" in reference:
                reference["candidates"] = [
                    id_map.get(candidate, candidate)
                    for candidate in reference["candidates"]
                ]

    if "identity_collisions" in metadata:
        for collision in metadata["identity_collisions"]:
            if "id" in collision:
                collision["id"] = id_map.get(
                    collision["id"],
                    collision["id"],
                )

            for side in ("kept", "dropped"):
                entity_info = collision.get(side)
                if entity_info and "id" in entity_info:
                    entity_info["id"] = id_map.get(
                        entity_info["id"],
                        entity_info["id"],
                    )

    return entities, relationships, metadata

def build_repository_graph(legacy: _LegacyRepo) -> RepositoryModel:
    entity_registry = _EntityRegistry()
    relationship_registry = _RelationshipRegistry()

    # Repo-wide symbol indexes, filled during pass 1. All are built from real
    # declarations only -- IMPORT marker entities and FILE entities are
    # excluded, since they'd otherwise shadow the real thing they point at
    # depending on which file happened to be processed first.
    by_qualified_name: dict[str, str] = {}                       # qualified_name -> entity id (first wins)
    ids_by_qualified_name: dict[str, list[str]] = {}             # qualified_name -> [entity id, ...] (all languages)
    by_language_qualified_name: dict[tuple[str, str], str] = {}  # (language, qualified_name) -> entity id
    by_simple_name: dict[str, list[str]] = {}                    # simple name -> [entity id, ...]

    # Per-module context, needed in pass 2 for precise resolution.
    imports_by_module: dict[str, dict[str, str]] = {}
    import_candidates_by_module: dict[str, dict[str, list[str]]] = {}
    module_language: dict[str, str] = {}
    module_qn_by_id: dict[str, str] = {}

    # entity id -> the module it was declared in (spec: "critical missing
    # context"). Type-reference resolution needs the *declaring* module's
    # imports/language/scope, not the caller's -- so this is its own index,
    # not a reuse of `imports_by_module` (keyed by module, not entity) or
    # any existing per-call context. First module wins on a repeat sighting
    # of the same id (mirrors `_EntityRegistry.add`'s own dedup: the entity
    # itself doesn't change meaning just because another file referenced it
    # again), so this never gets arbitrarily overwritten.
    entity_module_by_id: dict[str, str] = {}

    # Deferred cross-references collected across every file.
    pending_bases: list[tuple[str, str, str]] = []
    pending_implements: list[tuple[str, str, str]] = []
    pending_decorators: list[tuple[str, str, str]] = []
    pending_calls: list[tuple[str, str, str | None, tuple, tuple]] = []  # module_id, caller_id, owner_class_id, root, steps
    pending_creates: list[tuple[str, str, str]] = []
    pending_member_refs: list[tuple[str, str, str | None, tuple, tuple]] = []

    unresolved_references: list[dict[str, Any]] = []

    repo_id = f"repository::{legacy.name}"
    entity_registry.add(Entity(id=repo_id, kind=EntityKind.REPOSITORY, name=legacy.name, qualified_name=legacy.name))

    parse_errors: list[dict[str, Any]] = []
    files_by_language: dict[str, int] = {}

    # Deterministic processing order -- the resulting graph must not depend
    # on filesystem iteration order (which varies by OS/checkout), only on
    # repository *contents*.
    files = sorted(
        (f for f in legacy.files if not f.is_binary and _extractor_for(f) is not None),
        key=lambda f: normalize_relative_path(f.relative_path).as_posix(),
    )

    for file in files:
        extractor = _extractor_for(file)
        rel_path = normalize_relative_path(file.relative_path)
        try:
            source_bytes = file.path.read_bytes()
        except OSError as exc:
            parse_errors.append({"file": rel_path.as_posix(), "kind": "read_error", "message": str(exc)})
            continue

        try:
            result = extractor.extract_file(file.relative_path, source_bytes)
        except Exception as exc:  # a single bad file should not abort the whole scan
            parse_errors.append({"file": rel_path.as_posix(), "kind": "exception", "message": str(exc)})
            continue

        module_id = result["module_id"]
        lang_label = result.get("language") or getattr(extractor, "LANGUAGE", "javascript")
        files_by_language[lang_label] = files_by_language.get(lang_label, 0) + 1
        parse_errors.extend(result.get("parse_errors", []))

        for e in result["entities"]:
            entity_registry.add(e)
            entity_module_by_id.setdefault(e.id, module_id)
        for r in result["relationships"]:
            relationship_registry.add(r)

        # FILE is a first-class entity distinct from MODULE: one file can be a
        # module, and (for Java) many files share one package. Keeping both
        # lets file-level architecture questions be answered without
        # overloading module semantics.
        file_id = f"file:{rel_path.as_posix()}"
        entity_registry.add(
            Entity(
                id=file_id, kind=EntityKind.FILE, name=rel_path.name,
                qualified_name=rel_path.as_posix(), language=lang_label,
                metadata={"is_file": True, "extension": file.extension.lower()},
            )
        )
        relationship_registry.add(Relationship(source_id=repo_id, target_id=file_id, kind=RelationshipKind.CONTAINS))
        relationship_registry.add(Relationship(source_id=file_id, target_id=module_id, kind=RelationshipKind.CONTAINS))
        relationship_registry.add(Relationship(source_id=repo_id, target_id=module_id, kind=RelationshipKind.CONTAINS))

        for e in result["entities"]:
            if e.kind == EntityKind.IMPORT:
                continue  # import markers aren't resolution targets, only real declarations are
            if e.qualified_name:
                by_qualified_name.setdefault(e.qualified_name, e.id)
                bucket = ids_by_qualified_name.setdefault(e.qualified_name, [])
                if e.id not in bucket:
                    bucket.append(e.id)
                if e.language:
                    by_language_qualified_name.setdefault((e.language, e.qualified_name), e.id)
            by_simple_name.setdefault(e.name, [])
            if e.id not in by_simple_name[e.name]:
                by_simple_name[e.name].append(e.id)

        imports_by_module[module_id] = result.get("imports_by_simple_name", {})
        import_candidates_by_module[module_id] = result.get("import_candidates_by_simple_name") or {
            # Older extractors only expose the single-value map; treat each
            # value as a one-element candidate list so resolution is uniform.
            k: [v] for k, v in result.get("imports_by_simple_name", {}).items()
        }
        module_language[module_id] = lang_label
        module_qn_by_id[module_id] = result.get("module_qualified_name") or ""

        for class_id, base_name in result["pending_bases"]:
            pending_bases.append((module_id, class_id, base_name))
        for class_id, iface_name in result["pending_implements"]:
            pending_implements.append((module_id, class_id, iface_name))
        for entity_id, dec_name in result["pending_decorators"]:
            pending_decorators.append((module_id, entity_id, dec_name))
        for call in result["pending_calls"]:
            caller_id, owner_class_id, root, steps = call
            pending_calls.append((module_id, caller_id, owner_class_id, root, steps))
        for caller_id, created_name in result["pending_creates"]:
            pending_creates.append((module_id, caller_id, created_name))
        for ref in result.get("pending_member_refs", []):
            caller_id, owner_class_id, root, steps = ref
            pending_member_refs.append((module_id, caller_id, owner_class_id, root, steps))

    # ------------------------------------------------------------------
    # Pass 2: resolve every pending reference via a strict priority order.
    # ------------------------------------------------------------------
    external_registry: dict[str, Entity] = {}

    def _external(ext_key: str, simple: str, kind_hint: EntityKind) -> str:
        """External entities are namespaced `external::` so they can never be
        confused with a repository entity, and are never fabricated into a
        repo-language id like `python:python.fastapi.FastAPI`."""
        ext_id = f"external::{ext_key}"
        if ext_id not in external_registry:
            external_registry[ext_id] = Entity(
                id=ext_id, kind=kind_hint, name=simple,
                qualified_name=ext_key if ext_key != simple else None,
                metadata={"external": True},
            )
        return ext_id

    def _qualified_lookup(qn: str, language: str | None) -> str | None:
        """Exact qualified-name hit. Same language first; otherwise only when
        exactly one entity repo-wide carries that qualified name (never a
        pick among several, and never a language *preference* among equals)."""
        if not qn:
            return None
        if language is not None:
            hit = by_language_qualified_name.get((language, qn))
            if hit is not None:
                return hit
        ids = ids_by_qualified_name.get(qn, [])
        if len(ids) == 1:
            return ids[0]
        return None

    def _record_unresolved(referrer_id: str, relation: str, reference: str, reason: str, candidates: list[str]) -> None:
        unresolved_references.append(
            {
                "referrer_id": referrer_id,
                "relation": relation,
                "reference": reference,
                "reason": reason,
                "candidates": sorted(candidates),
                "file": _location_file(entity_registry.by_id.get(referrer_id)),
                "line": _location_line(entity_registry.by_id.get(referrer_id)),
            }
        )

    def _resolve(
        module_id: str, original_reference: str, kind_hint: EntityKind,
        referrer_id: str, relation: str, allow_external: bool = False, record: bool = True,
    ) -> tuple[str | None, str | None]:
        """Returns (target_id, resolution_method). Priority order (spec 21):

        1. Explicit import mapping (this module's own import candidates)
        2. Language/module-qualified reference (exact qualified name)
        3. Same-module / enclosing-scope qualified reference
        4. Unique repository-qualified match (dotted references only)
        5. Unique simple-name match
        6. External (only when we positively know the symbol came from
           outside, e.g. an import or a language-supplied annotation) --
           otherwise unresolved

        It never returns an arbitrary pick among multiple same-name
        candidates, never uses insertion, alphabetical or language order to
        break a tie, and never invents a repository entity for a symbol the
        repository does not contain.

        `record=False` suppresses `_record_unresolved` on a miss/ambiguity:
        used only for speculative lookups that aren't themselves a reference
        the person wrote (spec 7's "is this identifier itself a class"
        check) -- a failed speculation isn't a real unresolved reference and
        shouldn't be reported as one.
        """
        language = module_language.get(module_id)
        normalized = normalize_reference(original_reference)
        if not normalized:
            return None, None
        simple = simple_name_of(normalized)

        candidate_qns = import_candidates_by_module.get(module_id, {}).get(simple) or []
        imported_qn = candidate_qns[0] if candidate_qns else None

        # 1. Explicit import in this file, in the order the extractor ranked
        #    the candidates. The repository decides which one exists.
        for qn in candidate_qns:
            hit = _qualified_lookup(qn, language)
            if hit is not None:
                return hit, RM.EXPLICIT_IMPORT.value

        # 1b. Dotted reference whose *head* is imported: `Utils.Helper` where
        #     `Utils` is a namespace import, or `mod.Thing` after `import mod`.
        head = normalized.split(".", 1)[0]
        if head != normalized:
            tail = normalized[len(head):]
            for qn in import_candidates_by_module.get(module_id, {}).get(head) or []:
                hit = _qualified_lookup(qn + tail, language)
                if hit is not None:
                    return hit, RM.EXPLICIT_IMPORT.value

        # 2. The reference is itself a resolvable qualified name (e.g. a fully
        #    package-qualified Java type used without an explicit import).
        hit = _qualified_lookup(normalized, language)
        if hit is not None:
            return hit, RM.QUALIFIED_NAME.value

        # 3. Same-module, then each enclosing scope of the referrer (a nested
        #    class referring to a sibling nested type by its short name).
        module_qn = module_qn_by_id.get(module_id)
        if module_qn:
            hit = _qualified_lookup(f"{module_qn}.{normalized}", language)
            if hit is not None:
                return hit, RM.SAME_MODULE.value

        referrer = entity_registry.by_id.get(referrer_id)
        if referrer is not None and referrer.qualified_name:
            scope_parts = referrer.qualified_name.split(".")
            for i in range(len(scope_parts) - 1, 0, -1):
                hit = _qualified_lookup(".".join(scope_parts[:i]) + "." + normalized, language)
                if hit is not None:
                    return hit, RM.ENCLOSING_SCOPE.value

        # 4. Unique repository-qualified match -- only for dotted references,
        #    where the dots carry real disambiguating information. A bare
        #    simple name falls through to step 5 instead, so this can never
        #    become a back door for arbitrary same-name matching.
        if "." in normalized:
            suffix = "." + normalized
            matches = sorted(
                {
                    eid
                    for qn, ids in ids_by_qualified_name.items()
                    if qn.endswith(suffix)
                    for eid in ids
                }
            )
            if len(matches) == 1:
                return matches[0], RM.QUALIFIED_SUFFIX.value
            if len(matches) > 1:
                if record:
                    _record_unresolved(referrer_id, relation, original_reference, UR.AMBIGUOUS_QUALIFIED_NAME.value, matches)
                return None, None

        # 5. Unique repository-local simple-name match. Exactly one candidate
        #    repo-wide, or nothing -- deliberately *not* filtered by language,
        #    because preferring the referrer's own language here would be a
        #    guess dressed up as a rule (spec 21/22).
        candidates = by_simple_name.get(simple, [])
        if len(candidates) == 1:
            return candidates[0], RM.UNIQUE_SIMPLE_NAME.value
        if len(candidates) > 1:
            if record:
                _record_unresolved(referrer_id, relation, original_reference, UR.AMBIGUOUS_SIMPLE_NAME.value, candidates)
            return None, None  # never guess -- a false edge is worse than a missing one

        # 6. Nothing in the repository matches. Only call it external when we
        #    positively know it came from outside -- an explicit import, or a
        #    language-supplied annotation/decorator. An otherwise-unknown bare
        #    name is reported unresolved rather than promoted to a fake
        #    external dependency (spec 24).
        if imported_qn is not None or allow_external:
            ext_key = imported_qn or normalized
            return _external(ext_key, simple, kind_hint), RM.EXTERNAL.value

        if record:
            _record_unresolved(referrer_id, relation, original_reference, UR.UNRESOLVED_SYMBOL.value, [])
        return None, None

    def _meta(module_id: str, referrer_id: str, method: str | None) -> dict[str, Any]:
        referrer = entity_registry.by_id.get(referrer_id)
        meta: dict[str, Any] = {
            "resolution_method": method,
            "language": module_language.get(module_id),
        }
        file = _location_file(referrer)
        line = _location_line(referrer)
        if file is not None:
            meta["file"] = file
        if line is not None:
            meta["line"] = line
        return meta

    def _resolve_type_name(
        module_id: str, type_name: str, referrer_id: str, relation: str = "receiver_type",
    ) -> tuple[str | None, str | None]:
        """Resolve a type *name* (from a parameter annotation, a field
        declaration, or a callee's declared return type) to a real
        CLASS/INTERFACE/ENUM entity via the normal `_resolve` pipeline --
        shared by every receiver-typing path (typed parameter, field
        access, alias chase, return-type propagation) *and* by the
        declaration-level RETURNS/ACCEPTS signature resolution below, so
        every one of them applies the same priority order and the same
        "never guess" rule through a single implementation. Returns
        (target_id, resolution_method); either half is None if `_resolve`
        can't pin down a single entity, or if what it found isn't actually
        a type (e.g. resolves to a function instead).

        `relation` is only the diagnostic label attached to an
        unresolved/ambiguous reference (what `_record_unresolved` calls it
        "trying to do") -- it never changes resolution behavior. Existing
        receiver-typing callers don't pass it and keep the historical
        "receiver_type" label unchanged; RETURNS/ACCEPTS resolution passes
        its own so an unresolved signature type is correctly described as
        such rather than mislabeled as a receiver-type lookup.
        """

        language = module_language.get(module_id)
        if type_name in _NATIVE_TYPES_BY_LANGUAGE.get(language, set()):
            return None, None

        target, method = _resolve(module_id, type_name, EntityKind.CLASS, referrer_id, relation)
        if target is None:
            return None, None
        if method == RM.EXTERNAL.value:
            # An import-evidenced but not repository-defined type (e.g.
            # `from typing import List` with no `List` entity in this
            # repository) resolves "successfully" as far as `_resolve` is
            # concerned -- that's the correct, intentional behavior for
            # decorator/annotation resolution, which allow_external exists
            # for. But `_resolve_type_name` promises callers a *repository*
            # type-like entity (its own docstring: "a real CLASS/INTERFACE/
            # ENUM entity"), and every caller -- receiver typing as much as
            # the new RETURNS/ACCEPTS signature resolution -- exists to
            # answer "does this repository define this type", never "is
            # this recognized as coming from somewhere". Treating an
            # external symbol as an acceptable target here is exactly the
            # native/external leak this function is supposed to prevent
            # (spec: "ignore native/external types", never a graph node for
            # `List`/`Dict`/`Union` themselves). This costs existing
            # receiver-typing callers nothing observable: an external class
            # has no CONTAINS-based members in the registry, so a call
            # resolved against it was already going to fail to find any
            # method and end up unresolved either way -- only the recorded
            # reason changes (receiver_type_unknown instead of a
            # method-not-found against a phantom external class).
            return None, None
        target_entity = entity_registry.by_id.get(target)
        if target_entity is None or target_entity.kind not in (
            EntityKind.CLASS, EntityKind.INTERFACE, EntityKind.ENUM,
        ):
            return None, None
        return target, method

    def _resolve_type_reference_entities(
        module_id: str,
        type_ref: TypeReference,
        referrer_id: str,
        relation: str = "receiver_type",
    ) -> list[tuple[str, str | None]]:
        """Resolve every repository-defined type reachable from a
        TypeReference -- the top-level type, its generic arguments, and its
        union members, recursively (`List[User]` -> User; `Dict[str, User]`
        -> User; `Union[User, Admin]` -> User, Admin). This is the single
        shared traversal for both RETURNS (declared return types) and
        ACCEPTS (declared parameter types); it does not duplicate
        `_resolve_type_name`'s resolution logic, only recurses around it.

        Native/external types are ignored (never fabricated into fake graph
        nodes). Unresolved or ambiguous types are ignored -- `_resolve_type_name`
        already recorded *why* via the normal unresolved-reference
        machinery, so nothing here needs to guess or re-report.

        Returns a deduplicated, first-occurrence-order list of
        `(target_id, resolution_method)` pairs -- the same provenance
        `_resolve_type_name` produced, not discarded, so a RETURNS/ACCEPTS
        relationship built from this can carry real metadata (spec:
        preserve provenance) rather than a fabricated resolution method.
        Encountering the same repository type via more than one path
        (e.g. it appears in two generic arguments) collapses to one entry,
        keeping the resolution method from wherever it was first found.
        """
        resolved: list[tuple[str, str | None]] = []

        type_name = type_ref.qualified_name or type_ref.name
        if type_name:
            target, method = _resolve_type_name(module_id, type_name, referrer_id, relation)
            if target is not None:
                resolved.append((target, method))

        for argument in type_ref.generic_arguments:
            resolved.extend(
                _resolve_type_reference_entities(module_id, argument, referrer_id, relation)
            )

        for union_type in type_ref.union_types:
            resolved.extend(
                _resolve_type_reference_entities(module_id, union_type, referrer_id, relation)
            )

        deduped: dict[str, str | None] = {}
        for target, method in resolved:
            deduped.setdefault(target, method)
        return list(deduped.items())

    # RETURNS / ACCEPTS: declaration-level signature relationships (distinct
    # from the *value*-type questions `_field_entity_type`/`_method_return_type`
    # answer above -- those exist for call/receiver propagation and must
    # keep returning a single concrete class, e.g. List for `-> List[User]`,
    # not User). This is the integration point the recursive TypeReference
    # resolver was missing: every FUNCTION/METHOD/CONSTRUCTOR entity's
    # declared return type and parameter types are walked -- including
    # nested generic arguments and union members -- and every
    # repository-defined type found becomes a relationship. Native,
    # external, unresolved and ambiguous types are already filtered out by
    # `_resolve_type_reference_entities` itself (which also already
    # recorded *why*, via the normal `_resolve` unresolved-reference path)
    # -- nothing here second-guesses that by guessing a target.
    for entity in entity_registry.values():
        if entity.kind not in _CALLABLE_KINDS:
            continue
        decl_module_id = entity_module_by_id.get(entity.id)
        if decl_module_id is None:
            continue  # no recorded module context for this entity -- can't resolve against its imports/scope

        if entity.return_type is not None:
            for target, method in _resolve_type_reference_entities(
                decl_module_id, entity.return_type, entity.id, "returns",
            ):
                relationship_registry.add(
                    Relationship(
                        source_id=entity.id, target_id=target, kind=RelationshipKind.RETURNS,
                        metadata=_meta(decl_module_id, entity.id, method),
                    )
                )

        for parameter in entity.parameters:
            if parameter.type is None:
                continue
            for target, method in _resolve_type_reference_entities(
                decl_module_id, parameter.type, entity.id, "accepts",
            ):
                relationship_registry.add(
                    Relationship(
                        source_id=entity.id, target_id=target, kind=RelationshipKind.ACCEPTS,
                        metadata=_meta(decl_module_id, entity.id, method),
                    )
                )

    for module_id, class_id, base_name in pending_bases:
        target, method = _resolve(module_id, base_name, EntityKind.CLASS, class_id, "inherits")
        if target:
            relationship_registry.add(
                Relationship(source_id=class_id, target_id=target, kind=RelationshipKind.INHERITS,
                             metadata=_meta(module_id, class_id, method))
            )

    for module_id, class_id, iface_name in pending_implements:
        target, method = _resolve(module_id, iface_name, EntityKind.INTERFACE, class_id, "implements")
        if target:
            relationship_registry.add(
                Relationship(source_id=class_id, target_id=target, kind=RelationshipKind.IMPLEMENTS,
                             metadata=_meta(module_id, class_id, method))
            )

    for module_id, entity_id, dec_name in pending_decorators:
        # Decorators/annotations that aren't in the repo are genuinely
        # external by construction (`@Override`, `@app.route`), so external
        # fallback is allowed here.
        target, method = _resolve(
            module_id, dec_name, EntityKind.DECORATOR, entity_id, "decorated_by", allow_external=True
        )
        if target:
            relationship_registry.add(
                Relationship(source_id=entity_id, target_id=target, kind=RelationshipKind.DECORATED_BY,
                             metadata=_meta(module_id, entity_id, method))
            )

    # Inheritance chain, built from the INHERITS edges resolved just above --
    # so a self/this call can reach an inherited method without any guessing:
    # every link in the chain was itself resolved by the rules in `_resolve`.
    # Direct-membership index (spec 30 performance + spec 32 correctness):
    # built once from the already-emitted CONTAINS edges, so "the methods
    # owned directly by this class" is an O(1) lookup rather than an O(N)
    # scan of every entity id's string prefix on every call site (which was
    # also unsafe -- prefix matching on qualified ids can't distinguish a
    # class's own method from a same-named method on a nested class whose id
    # happens to share the prefix).
    _bases_of: dict[str, list[str]] = {}
    _direct_children: dict[str, list[str]] = {}
    for rel in relationship_registry.values():
        if rel.kind == RelationshipKind.INHERITS:
            _bases_of.setdefault(rel.source_id, []).append(rel.target_id)
        elif rel.kind == RelationshipKind.CONTAINS:
            _direct_children.setdefault(rel.source_id, []).append(rel.target_id)
    for bucket in _bases_of.values():
        bucket.sort()

    def _c3_merge(sequences: list[list[str]]) -> list[str] | None:
        """Textbook C3 linearization merge. Returns None on a genuinely
        inconsistent hierarchy (the merge can't produce a single linear
        order that respects every input sequence) rather than picking an
        arbitrary order -- the caller falls back to the language-agnostic
        BFS order in that case instead of crashing the whole analysis."""
        seqs = [list(s) for s in sequences if s]
        result: list[str] = []
        while True:
            seqs = [s for s in seqs if s]
            if not seqs:
                return result
            candidate = None
            for seq in seqs:
                head = seq[0]
                if not any(head in s[1:] for s in seqs):
                    candidate = head
                    break
            if candidate is None:
                return None  # inconsistent precedence order
            result.append(candidate)
            for seq in seqs:
                if candidate in seq:
                    seq.remove(candidate)

    def _mro(class_id: str, _stack: frozenset[str] = frozenset()) -> list[str]:
        """The class's method-resolution order (spec 5). For Python classes
        with more than one resolved base, this is real C3 linearization --
        the same algorithm CPython itself uses -- so `super()`, inherited
        methods/fields, overrides and receiver resolution all see the exact
        order Python would actually search. Every other case (a single base,
        no base, or a non-Python class -- Java/JS/TS only have single class
        inheritance, so their linearization is trivially "class, then each
        ancestor in order") falls back to the simple breadth-first walk,
        which is already correct there and remains cycle-guarded and
        deterministic (sorted tie-breaking, not dict/insertion order)."""
        if class_id in _stack:
            return [class_id]  # cycle guard for the recursive C3 case below

        bases = _bases_of.get(class_id, [])
        entity = entity_registry.by_id.get(class_id)
        if entity is not None and entity.language == "python" and len(bases) > 1:
            try:
                base_seqs = [_mro(b, _stack | {class_id}) for b in bases]
                merged = _c3_merge([*base_seqs, list(bases)])
            except RecursionError:
                merged = None
            if merged is not None:
                return [class_id] + [c for c in merged if c != class_id]
            # Inconsistent hierarchy -- fall through to the BFS order below
            # rather than raising and aborting the whole repository analysis
            # over one class's bad multiple-inheritance declaration.

        order: list[str] = []
        seen = {class_id}
        frontier = [class_id]
        while frontier:
            order.extend(frontier)
            nxt: list[str] = []
            for cid in frontier:
                for base in _bases_of.get(cid, []):
                    if base not in seen:
                        seen.add(base)
                        nxt.append(base)
            frontier = sorted(nxt)
        return order

    def _own_methods_by_name(class_id: str) -> dict[str, list[str]]:
        """This class's own directly-contained METHOD entities, grouped by
        simple name -- via the CONTAINS index, so a nested class's
        same-named method is never conflated with this class's own (spec
        27/32)."""
        result: dict[str, list[str]] = {}
        for child_id in _direct_children.get(class_id, []):
            ent = entity_registry.by_id.get(child_id)
            if ent is not None and ent.kind == EntityKind.METHOD:
                result.setdefault(ent.name, []).append(child_id)
        return result

    def _signature_compatible(a_params: list[Parameter], b_params: list[Parameter]) -> bool:
        """Conservative parameter-signature compatibility (spec 6): same
        arity (unless either side is variadic), and every position where
        *both* sides carry an explicit type name must agree. An untyped
        parameter on either side never rules a candidate out -- there's no
        language-justified conversion table needed here, just "don't treat
        foo(String) and foo(int) as the same signature."""
        has_variadic = any(p.is_variadic for p in a_params) or any(p.is_variadic for p in b_params)
        if not has_variadic and len(a_params) != len(b_params):
            return False
        for pa, pb in zip(a_params, b_params):
            na = pa.type.name if pa.type else None
            nb = pb.type.name if pb.type else None
            if na and nb and na.lower() != nb.lower():
                return False
        return True

    # Method overrides (spec 6/13): a method on a subclass overrides the
    # nearest same-named, signature-compatible method on a resolved base,
    # found by walking the already-resolved inheritance chain (MRO, now
    # language-aware per spec 5) -- never by matching same-named methods on
    # unrelated classes, and never by matching a same-named method whose
    # parameter signature clearly belongs to a different overload (spec 6's
    # Base.foo(String)/foo(int) example). Conservative on ambiguity: if a
    # candidate base level has more than one signature-compatible match,
    # there's no safe single target, so no OVERRIDES edge is created for
    # that level -- but unlike a same-name-only match, an incompatible
    # signature at one level doesn't stop the search; the walk continues
    # up the chain looking for the actual overridden overload.
    for class_id in sorted(_bases_of.keys()):
        own = _own_methods_by_name(class_id)
        mro = _mro(class_id)
        for simple_name, own_ids in own.items():
            if len(own_ids) != 1:
                continue
            subclass_method = own_ids[0]
            subclass_params = entity_registry.by_id[subclass_method].parameters
            for base_id in mro[1:]:
                base_methods = _own_methods_by_name(base_id).get(simple_name, [])
                if not base_methods:
                    continue
                compatible = [
                    bid for bid in base_methods
                    if _signature_compatible(subclass_params, entity_registry.by_id[bid].parameters)
                ]
                if len(compatible) == 1:
                    relationship_registry.add(
                        Relationship(
                            source_id=subclass_method,
                            target_id=compatible[0],
                            kind=RelationshipKind.OVERRIDES,
                            metadata={"resolution_method": RM.INHERITED_METHOD.value},
                        )
                    )
                    break  # nearest compatible override only
                if len(compatible) > 1:
                    break  # ambiguous even after signature narrowing -- stop rather than guess
                # Zero signature-compatible candidates at this level (a
                # different overload family shares the name) -- keep
                # looking further up the chain for the real match.

    def _find_field_entity(class_id: str, field_name: str) -> tuple[str | None, int | None]:
        """Nearest FIELD entity named `field_name` on `class_id`'s MRO (spec
        5/9/13/19): `depth` is its position in the MRO (0 = the class
        itself), used only to distinguish "declared here" from "inherited"
        for provenance elsewhere. Returns (None, None) if no class in the
        chain declares such a field."""
        for depth, cid in enumerate(_mro(class_id)):
            field_entity = entity_registry.by_id.get(f"{cid}.{field_name}")
            if field_entity is not None and field_entity.kind == EntityKind.FIELD:
                return field_entity.id, depth
        return None, None

    def _field_entity_type(field_entity_id: str, module_id: str, caller_id: str) -> str | None:
        """The class a FIELD entity's declared type names, resolved through
        the same evidence-based pipeline as everything else (spec 11)."""
        entity = entity_registry.by_id.get(field_entity_id)
        if entity is None or entity.return_type is None:
            return None
        type_name = entity.return_type.qualified_name or entity.return_type.name
        if not type_name:
            return None
        target, _method = _resolve_type_name(module_id, type_name, caller_id)
        return target

    def _method_return_type(method_entity_id: str, module_id: str, caller_id: str) -> str | None:
        """The class a METHOD/FUNCTION entity's declared return type names
        (spec 4/18/19) -- never inferred from the method's name, only its
        recorded, explicit return-type annotation.

        This is deliberately a *single* value-type answer, distinct from
        the RETURNS signature-relationship resolution below: for `def
        get_users() -> List[User]:` the runtime receiver type a further
        `.something()` call chains through is List, not User, so this must
        never be swapped for the recursive TypeReference resolver."""
        entity = entity_registry.by_id.get(method_entity_id)
        if entity is None or entity.return_type is None:
            return None
        type_name = entity.return_type.qualified_name or entity.return_type.name
        if not type_name:
            return None
        target, _method = _resolve_type_name(module_id, type_name, caller_id)
        return target

    def _resolve_bare_call(module_id: str, simple: str) -> tuple[str | None, str | None]:
        """A receiverless call (`get_user()`, spec 20): explicit import
        first, then a unique module-local symbol -- the same two rules the
        historical "bare" pending_calls branch used, now shared by every
        composable chain that starts with a plain function call, whether or
        not it continues further (`get_user().profile.save()`)."""
        for qn in import_candidates_by_module.get(module_id, {}).get(simple) or []:
            hit = _qualified_lookup(qn, module_language.get(module_id))
            if hit is not None:
                return hit, RM.EXPLICIT_IMPORT.value
        module_local = sorted(
            eid for eid in by_simple_name.get(simple, [])
            if eid.startswith(module_id + ".") or eid == module_id
        )
        if len(module_local) == 1:
            return module_local[0], RM.MODULE_LOCAL.value
        return None, None

    def _resolve_local_root(
        caller_id: str, name: str, module_id: str, owner_class_id: str | None, guard: frozenset[str],
    ) -> tuple[str | None, str | None]:
        """Instance-evidence-based typing for a plain identifier, scoped
        entirely to the *enclosing function's own* parameters and recorded
        local bindings (spec 9: a parameter or local always shadows a
        same-named module/import-level symbol in every supported language,
        so consulting only this function's own bindings is what makes that
        shadowing correct by construction, not an extra check).

        Priority, all function-scoped (spec 2/3/11): typed parameter >
        high-confidence local constructor type (`x = ClassName(...)`) >
        conservative alias chase (`y = x`) > recorded call-return chase
        (`y = get_user()`) > general composable chain chase (`y =
        service.user`, `y = service.get_user().profile` -- spec 2/3/4, the
        same chain engine used everywhere else, so a variable typed from an
        arbitrary supported expression participates in further resolution
        exactly like one typed by a simpler, higher-confidence form).

        `guard` bounds recursion through self-referential or mutually
        aliasing local bindings (`x = x.parent`, `a = b; b = a`) -- the
        moment a name reappears, resolution stops there rather than
        looping, and the binding is left unresolved (a clearly conservative
        approximation, spec 3, not a guess)."""
        if name in guard:
            return None, None

        caller = entity_registry.by_id.get(caller_id)
        if caller is None:
            return None, None

        for parameter in caller.parameters:
            if parameter.name != name:
                continue
            type_ref = parameter.type
            if type_ref is None:
                return None, None
            type_name = type_ref.qualified_name or type_ref.name
            if not type_name:
                return None, None
            target, _method = _resolve_type_name(module_id, type_name, caller_id)
            return (target, RM.TYPED_RECEIVER.value) if target else (None, None)

        local_types = caller.metadata.get("local_constructor_types") or {}
        local_aliases = caller.metadata.get("local_aliases") or {}
        local_call_types = caller.metadata.get("local_call_types") or {}
        local_chains = caller.metadata.get("local_chains") or {}

        current = name
        visited: set[str] = set()
        first_hop = True
        while current not in visited:
            visited.add(current)

            local_type_name = local_types.get(current)
            if local_type_name:
                target, _method = _resolve_type_name(module_id, local_type_name, caller_id)
                method = RM.LOCAL_CONSTRUCTOR.value if first_hop else RM.LOCAL_ALIAS.value
                return (target, method) if target else (None, None)

            call_ref = local_call_types.get(current)
            if call_ref:
                target = _resolve_return_type(module_id, owner_class_id, caller_id, call_ref)
                return (target, RM.RETURN_TYPE.value) if target else (None, None)

            chain_ref = local_chains.get(current)
            if chain_ref:
                result = _resolve_chain(
                    module_id, owner_class_id, caller_id,
                    tuple(chain_ref["root"]), [tuple(s) for s in chain_ref["steps"]],
                    guard | {name},
                )
                target = result["continuing_type"]
                return (target, RM.FIELD_TYPE.value) if target else (None, None)

            next_hop = local_aliases.get(current)
            if not next_hop:
                break
            current = next_hop
            first_hop = False

        return None, None

    def _resolve_root_step(
        root: tuple, module_id: str, owner_class_id: str | None, caller_id: str, guard: frozenset[str],
    ) -> tuple[str | None, str | None, bool, bool]:
        """Resolve the first link of a composable chain (spec 2/7/9/11):
        Returns (class_id_or_None, resolution_method, is_static_root,
        is_bare). `root` is `("self",)`, `("bare",)`, `("name", ident)`, or
        `("unsupported", raw_text)` (see `_flatten_expression` in each
        extractor).

        For `("name", ident)`: instance evidence (`_resolve_local_root`,
        function-scoped so it always shadows a same-named module symbol) is
        tried first; only when *no* instance evidence exists does the
        identifier get a chance to be a class/type reference itself (spec 7
        -- `User.create()`), and even then only through real evidence
        (import / qualified name / a unique module-local symbol via
        `_resolve`, `record=False` since this is a speculative check, not
        itself a reference the person wrote) -- never a capitalization
        guess."""
        kind = root[0]
        if kind in ("self", "this"):
            return owner_class_id, None, False, False
        if kind == "bare":
            return None, None, False, True
        if kind == "unsupported":
            return None, None, False, False

        # ("name", ident)
        ident = root[1]
        class_id, method = _resolve_local_root(caller_id, ident, module_id, owner_class_id, guard)
        if class_id is not None:
            return class_id, method, False, False

        target, rmethod = _resolve(module_id, ident, EntityKind.CLASS, caller_id, "receiver_type", record=False)
        if target is not None:
            target_entity = entity_registry.by_id.get(target) or external_registry.get(target)
            if target_entity is not None and (
                target_entity.kind in _TYPE_LIKE_KINDS or target_entity.metadata.get("external")
            ):
                return target, rmethod, True, False
        return None, None, False, False

    def _resolve_chain(
        module_id: str, owner_class_id: str | None, caller_id: str,
        root: tuple, steps: list[tuple], guard: frozenset[str] = frozenset(),
    ) -> dict[str, Any]:
        """The composable expression-chain resolver (spec 2/4/8/10/16): the
        single shared primitive every semantic path in this module goes
        through -- CALLS, non-call REFERENCES (spec 8), and local-variable
        assignment typing (`_resolve_local_root`'s `local_chains` branch)
        all call this same function rather than each having its own
        special-cased walk. It advances one hop at a time -- a `("field",
        name)` step via inheritance-aware field lookup, a `("call", name,
        arg_sig)` step via inheritance-aware, overload-narrowed method
        lookup -- and the moment a hop can't be pinned down to a single
        known class, it stops right there rather than skipping ahead and
        guessing the final target from the last step's name alone (spec
        10). This is exactly how `service.get_user().profile.save()`
        resolves without any resolver written specifically for that shape:
        each hop is just another call into the same two primitives.

        Returns a dict:
            target          concrete entity id the chain resolves to (a
                            METHOD/CONSTRUCTOR for a trailing "call" step, a
                            FIELD for a trailing "field" step), or None
            method          resolution_method for `target`, or None
            continuing_type the class_id the chain's *value* has after the
                            last step (used when this chain is itself an
                            assignment's right-hand side), or None
            failed_index    0-based index into `steps` where resolution
                            stopped, or -1 if the root itself failed, or
                            None if fully resolved
            candidates      ambiguous candidate ids at the failure point
            reason          an UnresolvedReason value, or None
            is_static_root  True when the root resolved to a class/type
                            itself rather than an instance (spec 7)
        """
        def _fail(index: int, reason: str, candidates: list[str] | None = None) -> dict[str, Any]:
            return {
                "target": None, "method": None, "continuing_type": None,
                "failed_index": index, "candidates": candidates or [], "reason": reason,
                "is_static_root": False,
            }

        if root[0] == "unsupported":
            return _fail(-1, UR.UNSUPPORTED_CONSTRUCT.value)

        class_id, method, is_static_root, is_bare = _resolve_root_step(
            root, module_id, owner_class_id, caller_id, guard,
        )
        is_pure_self = root[0] in ("self", "this")

        if class_id is None and not is_bare:
            return _fail(-1, UR.RECEIVER_TYPE_UNKNOWN.value)

        n = len(steps)
        for i, step in enumerate(steps):
            is_last = i == n - 1
            kind = step[0]

            if kind == "field":
                field_name = step[1]
                if class_id is None:
                    return _fail(i, UR.RECEIVER_TYPE_UNKNOWN.value)
                field_id, _depth = _find_field_entity(class_id, field_name)
                if field_id is None:
                    return _fail(i, UR.METHOD_NOT_FOUND.value if is_last else UR.RECEIVER_TYPE_UNKNOWN.value)
                if is_last:
                    return {
                        "target": field_id, "method": RM.FIELD_TYPE.value,
                        "continuing_type": _field_entity_type(field_id, module_id, caller_id),
                        "failed_index": None, "candidates": [], "reason": None,
                        "is_static_root": is_static_root,
                    }
                next_class = _field_entity_type(field_id, module_id, caller_id)
                if next_class is None:
                    return _fail(i, UR.RECEIVER_TYPE_UNKNOWN.value)
                class_id = next_class
                method = RM.FIELD_TYPE.value
                is_pure_self = False

            elif kind == "call":
                simple, arg_sig = step[1], step[2]
                if simple in _BUILTIN_CALL_NAMES:
                    return _fail(i, UR.UNRESOLVED_CALL.value)

                if class_id is None:
                    if is_bare and i == 0:
                        target_fn, bare_method = _resolve_bare_call(module_id, simple)
                        if target_fn is None:
                            return _fail(i, UR.UNRESOLVED_CALL.value, by_simple_name.get(simple, []))
                        if is_last:
                            return {
                                "target": target_fn, "method": bare_method,
                                "continuing_type": _method_return_type(target_fn, module_id, caller_id),
                                "failed_index": None, "candidates": [], "reason": None,
                                "is_static_root": False,
                            }
                        next_class = _method_return_type(target_fn, module_id, caller_id)
                        if next_class is None:
                            return _fail(i, UR.RECEIVER_TYPE_UNKNOWN.value)
                        class_id = next_class
                        method = RM.RETURN_TYPE.value
                        is_pure_self = False
                        continue
                    return _fail(i, UR.RECEIVER_TYPE_UNKNOWN.value)

                matches: list[str] = []
                resolved_method = method
                ambiguous_candidates: list[str] = []
                for depth, cid in enumerate(_mro(class_id)):
                    class_matches = _methods_named(cid, simple)
                    if not class_matches:
                        continue
                    if len(class_matches) == 1:
                        matches = class_matches
                        if is_pure_self:
                            resolved_method = RM.SELF_RECEIVER.value if depth == 0 else RM.INHERITED_METHOD.value
                        break
                    narrowed = _filter_by_arguments(class_matches, arg_sig)
                    if len(narrowed) == 1:
                        matches = narrowed
                        resolved_method = RM.ARGUMENT_MATCHED_OVERLOAD.value
                    else:
                        matches = narrowed
                        ambiguous_candidates = narrowed
                    break

                if len(matches) == 1:
                    target = matches[0]
                    if is_last:
                        return {
                            "target": target, "method": resolved_method,
                            "continuing_type": _method_return_type(target, module_id, caller_id),
                            "failed_index": None, "candidates": [], "reason": None,
                            "is_static_root": is_static_root,
                        }
                    next_class = _method_return_type(target, module_id, caller_id)
                    if next_class is None:
                        return _fail(i, UR.RECEIVER_TYPE_UNKNOWN.value)
                    class_id = next_class
                    method = RM.RETURN_TYPE.value
                    is_pure_self = False
                    continue

                if len(matches) > 1:
                    reason = UR.AMBIGUOUS_OVERLOAD.value if is_pure_self else UR.AMBIGUOUS_METHOD.value
                    return _fail(i, reason, matches)

                return _fail(i, UR.METHOD_NOT_FOUND.value, ambiguous_candidates)

        # No steps at all: a bare root used on its own isn't a reference to
        # resolve (spec 18) -- nothing to report as either resolved or
        # unresolved.
        return _fail(-1, UR.UNRESOLVED_SYMBOL.value)

    def _methods_named(class_id: str, simple: str) -> list[str]:
        """This class's own directly-contained METHOD/CONSTRUCTOR entities
        with this simple name -- via the CONTAINS index (spec 30/32), not a
        string-prefix scan of the whole registry: a nested class's
        same-named method must never be picked up as if it belonged to the
        outer class."""
        return sorted(
            eid for eid in _direct_children.get(class_id, [])
            if entity_registry.by_id[eid].name == simple
            and entity_registry.by_id[eid].kind in (EntityKind.METHOD, EntityKind.CONSTRUCTOR)
        )

    # Coarse argument-literal-type -> parameter-type-name compatibility.
    # Deliberately permissive in the "unknown" direction (an unknown arg or
    # an untyped parameter never rules a candidate out) and strict in the
    # "known" direction (a known arg type that doesn't match a known
    # parameter type rules that candidate out). JS/TS's single "number"
    # literal kind is compatible with any numeric parameter type, since the
    # language itself can't distinguish int/float at the call site.
    _ARG_TYPE_COMPATIBLE_PARAM_NAMES = {
        "int": {"int", "integer", "long", "short", "byte"},
        "float": {"double", "float"},
        "string": {"string", "str"},
        "boolean": {"boolean", "bool"},
        "char": {"char", "character"},
        "number": {"int", "integer", "long", "short", "byte", "double", "float", "number"},
    }

    def _arg_compatible(arg_type: str | None, param_type_name: str | None) -> bool:
        if arg_type is None or not param_type_name:
            return True  # unknown on either side never eliminates a candidate
        allowed = _ARG_TYPE_COMPATIBLE_PARAM_NAMES.get(arg_type)
        if allowed is None:
            return True  # arg literal kind we don't have a mapping for -- don't guess a mismatch
        return param_type_name.lower() in allowed

    def _filter_by_arguments(candidates: list[str], arg_sig: tuple) -> list[str]:
        """Narrow an overload candidate set using call-site argument types
        (spec 8/9/42). Only ever narrows -- if the narrowed set would be
        empty (the coarse type mapping was too strict for this case), the
        original candidate set is returned unchanged rather than trusting a
        possibly-wrong elimination down to nothing."""
        if not arg_sig:
            return candidates
        narrowed = []
        for cid in candidates:
            entity = entity_registry.by_id.get(cid)
            if entity is None:
                continue
            params = entity.parameters
            has_variadic = any(p.is_variadic for p in params)
            if not has_variadic and len(params) != len(arg_sig):
                continue
            if has_variadic and len(params) > len(arg_sig) + 1:
                continue
            ok = True
            for i, arg_type in enumerate(arg_sig):
                if i >= len(params):
                    break  # extra args absorbed by a variadic tail -- already length-checked above
                param_type_name = params[i].type.name if params[i].type else None
                if not _arg_compatible(arg_type, param_type_name):
                    ok = False
                    break
            if ok:
                narrowed.append(cid)
        return narrowed if narrowed else candidates

    def _resolve_call_target_silent(
        module_id: str, owner_class_id: str | None, receiver_kind: str | None,
        simple: str | None, arg_sig: tuple,
    ) -> str | None:
        """Best-effort resolution of a bare/self call to its target
        function or method entity, used only for return-type propagation
        (spec 26). Mirrors the "bare"/"self" rules the main CALLS pass uses
        below (module-local/import lookup, MRO + overload narrowing), but
        never records an unresolved reference on failure: this is a
        speculative lookup to type a local variable, not a real reference
        the person wrote, so a miss here is silently dropped rather than
        surfaced as noise."""
        if not simple or simple in _BUILTIN_CALL_NAMES:
            return None

        if receiver_kind == "self" and owner_class_id is not None:
            for class_id in _mro(owner_class_id):
                matches = _methods_named(class_id, simple)
                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    narrowed = _filter_by_arguments(matches, arg_sig)
                    return narrowed[0] if len(narrowed) == 1 else None
            return None

        if receiver_kind == "bare":
            for qn in import_candidates_by_module.get(module_id, {}).get(simple) or []:
                hit = _qualified_lookup(qn, module_language.get(module_id))
                if hit is not None:
                    return hit
            module_local = sorted(
                eid for eid in by_simple_name.get(simple, [])
                if eid.startswith(module_id + ".") or eid == module_id
            )
            if len(module_local) == 1:
                return module_local[0]
            return None

        return None

    def _resolve_return_type(
        module_id: str, owner_class_id: str | None, caller_id: str, call_ref: dict[str, Any],
    ) -> str | None:
        """`x = some_func(...)` / `x = self.some_method(...)` (spec 26):
        resolve the call the same speculative way `_resolve_call_target_silent`
        does, then -- only if the callee's own declared return type names a
        real class/interface/enum -- treat that as `x`'s type. Never
        inferred from the callee's *name*, only from its recorded
        `return_type`; a callee with no declared return type (or one that
        doesn't resolve to a type-like entity) yields nothing rather than a
        guess."""
        receiver_kind = call_ref.get("receiver_kind")
        simple = call_ref.get("simple")
        arg_sig = tuple(call_ref.get("arg_signature") or ())

        target_fn = _resolve_call_target_silent(module_id, owner_class_id, receiver_kind, simple, arg_sig)
        if target_fn is None:
            return None
        target_entity = entity_registry.by_id.get(target_fn)
        if target_entity is None:
            return None
        type_ref = target_entity.return_type
        if type_ref is None:
            return None
        type_name = type_ref.qualified_name or type_ref.name
        if not type_name:
            return None
        return _resolve_type_name(module_id, type_name, caller_id)[0]

    def _chain_label(root: tuple, steps: tuple) -> str:
        """Human-readable rendering of a (root, steps) chain for
        unresolved-reference provenance (spec 12/14) -- e.g.
        `service.get_user().profile.save()`, `self.a.b.c()`."""
        if root[0] in ("self", "this"):
            parts = ["self"]
        elif root[0] == "bare":
            parts = []
        else:  # "name" or "unsupported"
            parts = [root[1]]
        for step in steps:
            parts.append(step[1] if step[0] == "field" else f"{step[1]}()")
        return ".".join(parts) if parts else ""

    # CALLS (spec 2/4/10/16): every call site -- bare, self/this, a single
    # field hop, a multi-hop field chain, a call in the middle of a chain,
    # everything -- goes through the one shared `_resolve_chain` primitive.
    # There is no per-shape branching left here: the composability lives in
    # `_resolve_chain` itself, not in this loop.
    for module_id, caller_id, owner_class_id, root, steps in pending_calls:
        last_step = steps[-1] if steps else None
        if last_step is not None and last_step[0] == "call" and last_step[1] in _BUILTIN_CALL_NAMES:
            continue

        result = _resolve_chain(module_id, owner_class_id, caller_id, root, tuple(steps))
        label = _chain_label(root, steps)

        if result["target"] is not None:
            relationship_registry.add(
                Relationship(
                    source_id=caller_id, target_id=result["target"], kind=RelationshipKind.CALLS,
                    metadata=_meta(module_id, caller_id, result["method"]),
                )
            )
            continue

        candidates = result["candidates"]
        if not candidates and last_step is not None and last_step[0] == "call":
            candidates = by_simple_name.get(last_step[1], [])
        _record_unresolved(
            caller_id, "calls", label, result["reason"] or UR.UNRESOLVED_CALL.value, candidates,
        )

    # Non-call member references (spec 8): `return self.repository`,
    # `return service.user.profile` -- the *same* chain engine, just ending
    # in a "field" step instead of a "call" step, so a resolvable field
    # target becomes a REFERENCES edge and an unresolvable one is reported
    # exactly like an unresolved call would be, never guessed at.
    for module_id, caller_id, owner_class_id, root, steps in pending_member_refs:
        result = _resolve_chain(module_id, owner_class_id, caller_id, root, tuple(steps))
        label = _chain_label(root, steps)

        if result["target"] is not None:
            relationship_registry.add(
                Relationship(
                    source_id=caller_id, target_id=result["target"], kind=RelationshipKind.REFERENCES,
                    metadata=_meta(module_id, caller_id, result["method"]),
                )
            )
            continue

        _record_unresolved(
            caller_id, "references", label, result["reason"] or UR.RECEIVER_TYPE_UNKNOWN.value, result["candidates"],
        )

    # Object instantiation. Whether `User()` in Python is a *creation* is not
    # decidable from syntax, so the extractor only proposes it: the edge
    # becomes CREATES only when resolution lands on something that really is
    # a type. A capitalized factory *function* resolves to a FUNCTION and
    # becomes a CALLS edge instead -- no capitalization heuristic survives
    # into the final graph. (`new X()` in Java/JS is unambiguous and simply
    # passes the same check.)
    for module_id, caller_id, created_name in pending_creates:
        if created_name in _BUILTIN_CALL_NAMES:
            continue
        target, method = _resolve(module_id, created_name, EntityKind.CLASS, caller_id, "creates")
        if not target:
            continue
        target_entity = entity_registry.by_id.get(target) or external_registry.get(target)
        is_type_like = (
            target_entity is not None
            and (target_entity.kind in _TYPE_LIKE_KINDS or target_entity.metadata.get("external"))
        )
        kind = RelationshipKind.CREATES if is_type_like else RelationshipKind.CALLS
        relationship_registry.add(
            Relationship(source_id=caller_id, target_id=target, kind=kind,
                         metadata=_meta(module_id, caller_id, method))
        )

    for e in external_registry.values():
        entity_registry.add(e)

    metadata: dict[str, Any] = {
        "files_by_language": files_by_language,
        "parse_errors": parse_errors,
        "external_entity_count": len(external_registry),
        "external_entity_ids": sorted(external_registry),
        "unresolved_references": unresolved_references,
        "identity_collisions": entity_registry.collisions,
    }

    # Deterministic output ordering: entity/relationship insertion order
    # already follows the sorted file order above, but sort explicitly by id
    # so equal *content* always yields byte-identical serialized output
    # regardless of any incidental ordering differences upstream.
    entities_sorted = sorted(
        entity_registry.values(),
        key=lambda e: e.id,
    )

    relationships_sorted = sorted(
        relationship_registry.values(),
        key=lambda r: (
            r.source_id,
            r.target_id,
            r.kind.value,
        ),
    )

    entities_sorted, relationships_sorted, metadata = _namespace_repository_graph(
        repository_name=legacy.name,
        entities=entities_sorted,
        relationships=relationships_sorted,
        metadata=metadata,
    )

    return RepositoryModel(
        name=legacy.name,
        entities=entities_sorted,
        relationships=relationships_sorted,
        metadata=metadata,
    )