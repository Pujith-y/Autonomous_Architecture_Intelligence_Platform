from app.extractor.base import BaseExtractor


class ExtendsExtractor(BaseExtractor):

    def __init__(self):
        self.extends = []

    def visit(self, node):
        if node.type != "class_declaration":
            return

        child = node.child_by_field_name("superclass")
        if child:
            class_name = node.child_by_field_name("name")
            self.extends.append(
                (
                    class_name.text.decode(),
                    child.text.decode()
                )
            )