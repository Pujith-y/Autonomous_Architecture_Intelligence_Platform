from app.database.neo4j import driver


class GraphRepository:

    def create_package(self, package):
        query = """
        MERGE (p:Package {
            name: $name
        })
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    name=package.name
                )
            )

    def create_class(self, cls):
        query = """
        MERGE (c:Class {
            package: $package,
            name: $name
        })
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    package=cls.package,
                    name=cls.name
                )
            )

    def create_interface(self, interface):
        query = """
        MERGE (i:Interface {
            package: $package,
            name: $name
        })
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    package=interface.package,
                    name=interface.name
                )
            )

    def create_method(self, method):
        query = """
        MERGE (m:Method {
            parent: $parent,
            name: $name
        })
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=method.parent,
                    name=method.name
                )
            )

    def create_field(self, field):
        query = """
        MERGE (f:Field {
            parent: $parent,
            name: $name
        })
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=field.parent,
                    name=field.name
                )
            )

    def create_package_contains_class(
        self,
        package,
        cls,
    ):
        query = """
        MATCH (p:Package {name: $package})

        MATCH (c:Class {
            package: $package,
            name: $class_name
        })

        MERGE (p)-[:CONTAINS]->(c)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    package=package.name,
                    class_name=cls.name,
                )
            )

    def create_package_contains_interface(
        self,
        package,
        interface,
    ):
        query = """
        MATCH (p:Package {name: $package})

        MATCH (i:Interface {
            package: $package,
            name: $interface_name
        })

        MERGE (p)-[:CONTAINS]->(i)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    package=package.name,
                    interface_name=interface.name,
                )
            )

    def create_class_declares_method(self, method):
        query = """
        MATCH (c:Class {
            name: $parent
        })

        MATCH (m:Method {
            parent: $parent,
            name: $method
        })

        MERGE (c)-[:DECLARES]->(m)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=method.parent,
                    method=method.name,
                )
            )

    def create_interface_declares_method(self, method):
        query = """
        MATCH (i:Interface {
            name: $parent
        })

        MATCH (m:Method {
            parent: $parent,
            name: $method
        })

        MERGE (i)-[:DECLARES]->(m)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=method.parent,
                    method=method.name,
                )
            )

    def create_class_has_field(self, field):
        query = """
        MATCH (c:Class {
            name: $parent
        })

        MATCH (f:Field {
            parent: $parent,
            name: $field
        })

        MERGE (c)-[:HAS_FIELD]->(f)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=field.parent,
                    field=field.name,
                )
            )

    def create_extends_relationship(self, inheritance):

        query = """
        MATCH (child:Class {
            name: $child
        })

        MATCH (parent:Class {
            name: $parent
        })

        MERGE (child)-[:EXTENDS]->(parent)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    parent=inheritance.parent_class,
                    child=inheritance.child_class
                )
            )

    def create_implements_relationship(self, implementation):

        query = """
        MATCH (c:Class {
            name: $class_name
        })

        MATCH (i:Interface {
            name: $interface
        })

        MERGE (c)-[:IMPLEMENTS]->(i)
        """
        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    class_name=implementation.class_name,
                    interface=implementation.interface_name
                )
            )

    def create_calls_relationship(self, method_call):
        query = """
        MATCH (caller:Method {
            parent: $caller_parent,
            name: $caller
        })

        MATCH (callee:Method {
            name: $callee
        })

        MERGE (caller)-[:CALLS]->(callee)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    caller_parent=method_call.caller_parent,
                    caller=method_call.caller,
                    callee=method_call.callee
                )
            )

    def create_creates_relationship(self, object_creation):
        query = """
        MATCH (owner:Method {
            parent: $owner_parent,
            name: $owner_name
        })

        MATCH (created:Class {
            name: $object_type
        })

        MERGE (owner)-[:CREATES]->(created)
        """

        with driver.session() as session:
            session.execute_write(
                lambda tx: tx.run(
                    query,
                    owner_parent=object_creation.owner_parent,
                    owner_name=object_creation.owner_name,
                    object_type=object_creation.object_type
                )
            )
        