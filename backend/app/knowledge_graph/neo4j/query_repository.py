from app.knowledge_graph.neo4j.client import driver
from app.knowledge_graph.neo4j.namespace import _namespace

class Neo4jQueryRepository:

    def find_entity(
        self,
        user_id: int,
        repository_id: int,
        entity_name: str,
    ):
        namespace = (
            f"user:{user_id}::repo:{repository_id}"
        )

        with driver.session() as session:
            result = session.run(
                """
                MATCH (entity:Entity)
                WHERE entity.id = $exact_id
                   OR entity.name = $entity_name
                   OR entity.qualified_name = $entity_name
                RETURN
                    entity.id AS id,
                    entity.name AS name,
                    entity.qualified_name AS qualified_name,
                    labels(entity) AS labels,
                    entity.language AS language
                ORDER BY entity.id
                """,
                exact_id=f"{namespace}::{entity_name}",
                entity_name=entity_name,
            )

            return result.data()

    def find_callers(
        self,
        user_id: int,
        repository_id: int,
        entity_id: str,
    ) -> list[dict]:

        target_id = _namespace(
            user_id,
            repository_id,
            entity_id,
        )

        with driver.session() as session:
            result = session.run(
                """
                MATCH (caller:Entity)-[r:calls]->(target:Entity)
                WHERE target.id = $target_id

                RETURN
                    caller.id AS id,
                    caller.name AS name,
                    caller.qualified_name AS qualified_name,
                    labels(caller) AS labels,
                    caller.language AS language,
                    properties(r) AS relationship
                ORDER BY caller.id
                """,
                target_id=target_id,
            )

            return result.data()

    def find_callees(
        self,
        user_id: int,
        repository_id: int,
        entity_id: str,
    ) -> list[dict]:

        source_id = _namespace(
            user_id,
            repository_id,
            entity_id,
        )

        with driver.session() as session:
            result = session.run(
                """
                MATCH (source:Entity)-[r:calls]->(callee:Entity)
                WHERE source.id = $source_id

                RETURN
                    callee.id AS id,
                    callee.name AS name,
                    callee.qualified_name AS qualified_name,
                    labels(callee) AS labels,
                    callee.language AS language,
                    properties(r) AS relationship
                ORDER BY callee.id
                """,
                source_id=source_id,
            )

            return result.data()

    