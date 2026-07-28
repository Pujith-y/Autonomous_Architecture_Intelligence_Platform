from app.knowledge_graph.graph_repository import GraphRepository


class GraphBuilder:

    def __init__(self):
        self.repository = GraphRepository()

    def build(self, parsed):

        for package in parsed.packages:
            self.repository.create_package(package)

        for cls in parsed.classes:
            self.repository.create_class(cls)

        for package in parsed.packages:
            for cls in parsed.classes:
                self.repository.create_contains_relationship(
                    package,
                    cls,
                )