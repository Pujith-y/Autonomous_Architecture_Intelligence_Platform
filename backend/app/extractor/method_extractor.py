from app.extractor.base import BaseExtractor

from app.domain.entities.method import Method

class MethodExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()
        self.current_class = None

    def visit(self, node):
        if node.type == "class_declaration" or node.type == "interface_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_class = name.text.decode()
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                self.result.append(
                    Method(
                        parent=self.current_class,
                        name=name_node.text.decode()
                    )
                )