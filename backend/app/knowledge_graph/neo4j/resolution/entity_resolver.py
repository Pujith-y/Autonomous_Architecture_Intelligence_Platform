from dataclasses import dataclass

from app.knowledge_graph.neo4j.query_repository import (
    Neo4jQueryRepository,
)


@dataclass
class EntityResolution:
    entity: dict | None = None
    candidates: list[dict] | None = None

    @property
    def resolved(self) -> bool:
        return self.entity is not None

    @property
    def ambiguous(self) -> bool:
        return (
            self.entity is None
            and bool(self.candidates)
        )


class EntityResolver:

    def __init__(
        self,
        query_repository: Neo4jQueryRepository,
    ):
        self.query_repository = query_repository

    def resolve(
        self,
        user_id: int,
        repository_id: int,
        entity_name: str,
    ) -> EntityResolution:

        result = self.query_repository.find_entity(
            user_id=user_id,
            repository_id=repository_id,
            entity_name=entity_name,
        )

        if len(result) == 1:
            return EntityResolution(
                entity=result[0],
            )

        if len(result) > 1:
            return EntityResolution(
                candidates=result,
            )

        return EntityResolution()