from app.knowledge_graph.neo4j.client import driver
from app.repository_model.model import RepositoryModel
import json
from dataclasses import asdict

class Neo4jRepository:

    def _namespace(
        self,
        user_id: int,
        repository_id: int,
        entity_id: str,
    ) -> str:

        namespace = f"user:{user_id}::repo:{repository_id}"

        if entity_id.startswith("repository::"):
            return namespace

        return f"{namespace}::{entity_id}"

    def save(
        self,
        model: RepositoryModel,
        user_id: int,
        repository_id: int,
    ) -> None:

        

        self._save_entities(
            model,
            user_id,
            repository_id,
        )

        self._save_relationships(
            model,
            user_id,
            repository_id,
        )

    def _save_entities(self, model: RepositoryModel, user_id: int, repository_id: int) -> None:
        entities = [
            {
                "id": self._namespace(
                    user_id=user_id,
                    repository_id=repository_id,
                    entity_id=entity.id,
                ),
                "name": entity.name,
                "qualified_name": entity.qualified_name,
                "language": entity.language,
                "kind": entity.kind.value,

                "file": str(entity.location.file) if entity.location else None,
                "start_line": entity.location.start_line if entity.location else None,
                "end_line": entity.location.end_line if entity.location else None,
                "start_column": entity.location.start_column if entity.location else None,
                "end_column": entity.location.end_column if entity.location else None,

                "parameters": json.dumps(
                    [asdict(parameter) for parameter in entity.parameters]
                ),

                "return_type": json.dumps(
                    asdict(entity.return_type)
                ) if entity.return_type else None,

                "generic_parameters": json.dumps(
                    [asdict(parameter) for parameter in entity.generic_parameters]
                ),

                "metadata": json.dumps(entity.metadata),
            }
            for entity in model.entities
        ]

        if not entities:
            return

        with driver.session() as session:
            session.execute_write(
                self._create_entities,
                entities,
            )

    @staticmethod
    def _create_entities(tx, entities):
        query = """
        UNWIND $entities AS entity

        MERGE (n:Entity {
            id: entity.id
        })

        SET n.name = entity.name,
            n.qualified_name = entity.qualified_name,
            n.language = entity.language,
            n.file = entity.file,
            n.start_line = entity.start_line,
            n.end_line = entity.end_line,
            n.start_column = entity.start_column,
            n.end_column = entity.end_column,
            n.parameters = entity.parameters,
            n.return_type = entity.return_type,
            n.generic_parameters = entity.generic_parameters,
            n.metadata = entity.metadata,
            n:$(entity.kind)
        """

        tx.run(
            query,
            entities=entities,
        )

    def _save_relationships(self, model: RepositoryModel, user_id: int, repository_id: int) -> None:
        relationships = [
            {
                "source_id": self._namespace(
                    user_id=user_id,
                    repository_id=repository_id,
                    entity_id=relationship.source_id
                ),

                "target_id": self._namespace(
                    user_id=user_id,
                    repository_id=repository_id,
                    entity_id=relationship.target_id
                ),

                "kind": relationship.kind.value,
                "metadata": relationship.metadata,
            }
            for relationship in model.relationships
        ]

        if not relationships:
            return

        with driver.session() as session:
            session.execute_write(
                self._create_relationships,
                relationships,
            )

    @staticmethod
    def _create_relationships(tx, relationships):
        query = """
        UNWIND $relationships AS relationship

        MATCH (source:Entity {
            id: relationship.source_id
        })

        MATCH (target:Entity {
            id: relationship.target_id
        })

        MERGE (source)-[r:$(relationship.kind)]->(target)

        SET r += relationship.metadata
        """

        tx.run(
            query,
            relationships=relationships,
        )

    def delete_repository(
        self,
        user_id: int,
        repository_id: int,
    ) -> None:

        namespace = f"user:{user_id}::repo:{repository_id}"

        with driver.session() as session:
            session.execute_write(
                self._delete_repository,
                namespace,
            )

    @staticmethod
    def _delete_repository(tx, namespace: str):

        query = """
        MATCH (n:Entity)
        WHERE n.id = $namespace
        OR n.id STARTS WITH $prefix
        DETACH DELETE n
        """

        tx.run(
            query,
            namespace=namespace,
            prefix=f"{namespace}::",
        )