from app.knowledge_graph.neo4j.client import driver


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