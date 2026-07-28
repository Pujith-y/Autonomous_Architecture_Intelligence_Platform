from app.extractor.base import BaseExtractor


class FieldExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type != "field_declaration":
            return
        declarator = node.child_by_field_name("declarator")
        if declarator:
            name = declarator.child_by_field_name("name")
            if name:
                self.result.append(name.text.decode())