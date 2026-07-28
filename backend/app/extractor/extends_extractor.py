from app.extractor.base import BaseExtractor

from app.domain.relationships.inheritance import Inheritance


class ExtendsExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type != "class_declaration":
            return

        class_name = node.child_by_field_name("name")
        superclass = node.child_by_field_name("superclass")

        if superclass:
            parent = superclass.named_children[0]

            self.result.append(
                Inheritance(
                    child_class=class_name.text.decode(),
                    parent_class=parent.text.decode()
                )
            )