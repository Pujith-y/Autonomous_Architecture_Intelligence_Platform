from app.knowledge_graph.graph_repository import GraphRepository


class GraphBuilder:

    def __init__(self):
        self.repository = GraphRepository()

    def build(self, parsed):

        for package in parsed.packages:
            self.repository.create_package(package)

        for cls in parsed.classes:
            self.repository.create_class(cls)

        for interface in parsed.interfaces:
            self.repository.create_interface(interface)

        for method in parsed.methods:
            self.repository.create_method(method)

        for field in parsed.fields:
            self.repository.create_field(field)

        for package in parsed.packages:

            for cls in parsed.classes:
                self.repository.create_package_contains_class(
                    package,
                    cls,
                )

            for interface in parsed.interfaces:
                self.repository.create_package_contains_interface(
                    package,
                    interface,
                )

        for method in parsed.methods:
            self.repository.create_class_declares_method(method)
            self.repository.create_interface_declares_method(method)

        for field in parsed.fields:
            self.repository.create_class_has_field(field)

        for inheritance in parsed.extends:
            self.repository.create_extends_relationship(
                inheritance
            )

        for implementation in parsed.implements:
            self.repository.create_implements_relationship(
                implementation
            )

        for method_call in parsed.method_calls:
            self.repository.create_calls_relationship(method_call)

        for object_creation in parsed.object_creations:
            self.repository.create_creates_relationship(object_creation)