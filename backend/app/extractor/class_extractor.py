from app.extractor.base import BaseExtractor

class ClassExtractor(BaseExtractor):

    def __init__(self):
        self.classes = []

    def visit(self, node):
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                self.classes.append(name_node.text.decode())