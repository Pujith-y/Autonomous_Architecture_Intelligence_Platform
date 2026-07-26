from app.extractor.base import BaseExtractor


class ImplementsExtractor(BaseExtractor):

    def __init__(self):
        self.implements = []

    def visit(self, node):
        if node.type != "class_declaration":
            return

        class_name = node.child_by_field_name("name")
        interfaces = node.child_by_field_name("interfaces")

        if not class_name or not interfaces:
            return

        for interface in interfaces.named_children[0].named_children:
            self.implements.append(
                (
                    class_name.text.decode(),
                    interface.text.decode()
                )
            )