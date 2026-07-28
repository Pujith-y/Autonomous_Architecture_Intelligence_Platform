from app.extractor.base import BaseExtractor
from app.domain.relationships.method_call import MethodCall

class MethodCallExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()
        self.current_class = None
        self.current_method = None

    def visit(self, node):

        if node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_class = name.text.decode()

        elif node.type == "method_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.current_method = name.text.decode()

        elif node.type == "method_invocation":
            name = node.child_by_field_name("name")
            if name:
                self.result.append(
                    MethodCall(
                        caller_parent=self.current_class,
                        caller=self.current_method,
                        callee_parent=None,   # we'll resolve this later
                        callee=name.text.decode()
                    )
                )