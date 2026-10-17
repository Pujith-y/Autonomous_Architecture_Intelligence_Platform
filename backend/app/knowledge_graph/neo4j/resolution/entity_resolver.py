from dataclasses import dataclass

from app.knowledge_graph.neo4j.query_repository import (
    EntityNotFoundError,
    GraphQueryError,
    Neo4jQueryRepository,
)


class AmbiguousEntityError(GraphQueryError):
    def __init__(self, candidates: list[dict]):
        super().__init__("Entity name is ambiguous")
        self.candidates = candidates


@dataclass
class EntityResolution:
    entity: dict | None = None
    candidates: list[dict] | None = None

    @property
    def resolved(self) -> bool:
        return self.entity is not None

    @property
    def ambiguous(self) -> bool:
        return self.entity is None and bool(self.candidates)

    @property
    def match_kind(self) -> str | None:
        """Tier that produced the result (id / qualified_name / ... / name)."""
        if self.entity is not None:
            return self.entity.get("match_kind")
        if self.candidates:
            return self.candidates[0].get("match_kind")
        return None


class EntityResolver:
    """Priority: exact id > exact qualified name > qualified-name suffix > simple name.

    find_entity returns only the best non-empty tier, so a unique higher-priority
    match is never made ambiguous by lower-priority matches. Multiple matches in
    the same tier are returned as ``candidates``; nothing is ever guessed.
    """

    def __init__(self, query_repository: Neo4jQueryRepository):
        self.query_repository = query_repository

    def resolve(self, user_id: int, repository_id: int, entity_name: str,
                *, kinds=None, exclude_kinds=None) -> EntityResolution:
        result = self.query_repository.find_entity(
            user_id=user_id,
            repository_id=repository_id,
            entity_name=entity_name,
            kinds=kinds,
            exclude_kinds=exclude_kinds,
        )
        if len(result) == 1:
            return EntityResolution(entity=result[0])
        if len(result) > 1:
            return EntityResolution(candidates=result)
        return EntityResolution()

    def require_id(self, user_id: int, repository_id: int, entity_name: str, **kw) -> str:
        """Namespaced id of the unique match; raises on missing/ambiguous."""
        r = self.resolve(user_id, repository_id, entity_name, **kw)
        if r.resolved:
            return r.entity["id"]
        if r.ambiguous:
            raise AmbiguousEntityError(r.candidates)
        raise EntityNotFoundError("Entity not found")