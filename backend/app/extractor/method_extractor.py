from app.extractor.base import BaseExtractor

class MethodExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                self.result.append(name_node.text.decode())