from app.extractor.base import BaseExtractor

from app.domain.entities.field import Field

class FieldExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()
        self.current_class = None

    def visit(self, node):
        if node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_class = name.text.decode()

        elif node.type == "field_declaration":
            declarator = node.child_by_field_name("declarator")
            if declarator:
                name = declarator.child_by_field_name("name")
                if name:
                    self.result.append(
                        Field(
                            parent=self.current_class,
                            name=name.text.decode()
                        )
                    )