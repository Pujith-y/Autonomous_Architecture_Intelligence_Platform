from app.extractor.base import BaseExtractor

from app.domain.entities.interface import Interface

class InterfaceExtractor(BaseExtractor) :

    def __init__(self):
        super().__init__()
        self.current_package = None

    def visit(self, node):
        if node.type == "package_declaration" and node.named_children:
            self.current_package = node.named_children[0].text.decode()
        if node.type == "interface_declaration":
            name = node.child_by_field_name("name")
            if name:
                self.result.append(
                    Interface(
                        package=self.current_package,
                        name=name.text.decode()
                    )
                )