from app.knowledge_graph.neo4j.query_repository import (
    EntityNotFoundError,
    Neo4jQueryRepository,
)
from app.knowledge_graph.neo4j.resolution.entity_resolver import (
    AmbiguousEntityError,
    EntityResolver,
)


class CodeGraphTools:
    """High-level tools for inspecting a repository's code graph."""

    def __init__(
        self,
        query_repository: Neo4jQueryRepository,
        entity_resolver: EntityResolver,
        user_id: int,
        repository_id: int,
    ):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")

        if isinstance(repository_id, bool) or not isinstance(repository_id, int):
            raise ValueError("repository_id must be an integer")

        self.query_repository = query_repository
        self.entity_resolver = entity_resolver
        self.user_id = user_id
        self.repository_id = repository_id

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")

        if not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")

    @staticmethod
    def _validate_depth(max_depth: int) -> None:
        if isinstance(max_depth, bool) or not isinstance(max_depth, int):
            raise ValueError("max_depth must be an integer")

        if not 1 <= max_depth <= 10:
            raise ValueError("max_depth must be between 1 and 10")

    def find_entity(self, entity_name: str) -> dict:
        """Resolve an entity name to one unambiguous graph entity."""
        result = self.entity_resolver.resolve(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_name=entity_name,
        )

        if result.ambiguous:
            raise AmbiguousEntityError(result.candidates)

        if not result.resolved:
            raise EntityNotFoundError("Entity not found")

        return result.entity

    def inspect_entity(self, entity_name: str, limit: int = 100) -> dict:
        """Return an entity and its direct incoming/outgoing relationships."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        relationships = self.query_repository.find_relationships(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            direction="both",
            limit=limit,
        )

        return {
            "entity": entity,
            "relationships": relationships,
            "relationship_count": len(relationships),
        }

    def find_callers(self, entity_name: str, limit: int = 100) -> dict:
        """Find entities that call the specified entity."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        results = self.query_repository.find_callers(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            limit=limit,
        )

        return {"entity": entity, "callers": results, "count": len(results)}

    def find_callees(self, entity_name: str, limit: int = 100) -> dict:
        """Find entities called by the specified entity."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        results = self.query_repository.find_callees(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            limit=limit,
        )

        return {"entity": entity, "callees": results, "count": len(results)}

    def find_dependencies(self, entity_name: str, limit: int = 100) -> dict:
        """Find entities this entity depends on."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        results = self.query_repository.find_dependencies(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            limit=limit,
        )

        return {
            "entity": entity,
            "dependencies": results,
            "count": len(results),
        }

    def find_dependents(self, entity_name: str, limit: int = 100) -> dict:
        """Find entities that depend on this entity."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        results = self.query_repository.find_dependents(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            limit=limit,
        )

        return {
            "entity": entity,
            "dependents": results,
            "count": len(results),
        }

    def find_implementations(
        self, entity_name: str, limit: int = 100
    ) -> dict:
        """Find concrete types that implement an interface."""
        self._validate_limit(limit)
        entity = self.find_entity(entity_name)

        results = self.query_repository.find_implementations(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            limit=limit,
        )

        return {
            "entity": entity,
            "implementations": results,
            "count": len(results),
        }

    def analyze_impact(
        self,
        entity_name: str,
        max_depth: int = 3,
        limit: int = 100,
    ) -> dict:
        """Analyze the potential impact of changing an entity."""
        self._validate_limit(limit)
        self._validate_depth(max_depth)
        entity = self.find_entity(entity_name)

        result = self.query_repository.analyze_impact(
            user_id=self.user_id,
            repository_id=self.repository_id,
            entity_id=entity["id"],
            max_depth=max_depth,
            limit=limit,
        )

        return {"entity": entity, "impact": result}
