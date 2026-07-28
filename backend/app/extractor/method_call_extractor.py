from app.extractor.base import BaseExtractor
from app.domain.relationships.method_call import MethodCall

class MethodCallExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()
        self.current_method = None

    def visit(self, node):
        if node.type == "method_declaration":
            name = node.child_by_field_name("name")
            self.current_method = name.text.decode()

        elif node.type == "method_invocation":
            name = node.child_by_field_name("name")
            self.result.append(
                MethodCall(
                    caller=self.current_method,
                    callee=name.text.decode()
                )
            )