from app.database.neo4j import driver


class GraphRepository:

    def create_package(self, name: str):

        query = """
        MERGE (p:Package {name: $name})
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(query, name=name)
            )

    def create_class(self, name: str):

        query = """
        MERGE (c:Class {name: $name})
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(query, name=name)
            )

    def create_contains_relationship(
        self,
        package_name: str,
        class_name: str,
    ):
        query = """
        MATCH (p:Package {name: $package_name})
        MATCH (c:Class {name: $class_name})

        MERGE (p)-[:CONTAINS]->(c)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    package_name=package_name,
                    class_name=class_name,
                )
            )