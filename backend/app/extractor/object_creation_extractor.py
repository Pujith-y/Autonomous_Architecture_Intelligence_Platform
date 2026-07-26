from app.extractor.base import BaseExtractor

class ObjectCreationExtractor(BaseExtractor):

    def __init__(self):
        self.created_objects = []
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
                owner = self.current_method if self.current_method else self.current_class
                self.created_objects.append((owner, name.text.decode()))