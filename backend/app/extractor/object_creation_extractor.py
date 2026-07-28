from app.extractor.base import BaseExtractor

from app.domain.relationships.object_creation import ObjectCreation

class ObjectCreationExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()
        self.current_method = None
        self.current_class = None

    def visit(self, node):
        if node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_class = name.text.decode()

        elif node.type == "method_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_method = name.text.decode()
    
        elif node.type == "object_creation_expression":
            name = node.child_by_field_name("type")
            if name:
                if self.current_method:
                    owner_type = "method"
                    owner_name = self.current_method
                else:
                    owner_type = "class"
                    owner_name = self.current_class
                self.result.append(
                    ObjectCreation(
                        owner_type=owner_type,
                        owner_name=owner_name,
                        object_type=name.text.decode()
                    )
                )