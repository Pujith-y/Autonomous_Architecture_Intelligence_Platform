from app.extractor.base import BaseExtractor

from app.domain.relationships.implementation import Implementation

class ImplementsExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type != "class_declaration":
            return

        class_name = node.child_by_field_name("name")
        interfaces = node.child_by_field_name("interfaces")

        if not class_name or not interfaces:
            return

        for interface in interfaces.named_children[0].named_children:
            self.result.append(
                Implementation(
                    class_name=class_name.text.decode(),
                    interface_name=interface.text.decode()
                )
            )