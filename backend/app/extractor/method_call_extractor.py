from app.extractor.base import BaseExtractor

class MethodCallExtractor(BaseExtractor):

    def __init__(self):
        self.calls = []
        self.current_method = None

    def visit(self, node):
        if node.type == "method_declaration":
            name = node.child_by_field_name("name")
            self.current_method = name.text.decode()

        elif node.type == "method_invocation":
            name = node.child_by_field_name("name")
            self.calls.append((self.current_method,name.text.decode()))