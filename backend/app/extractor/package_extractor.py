from app.extractor.base import BaseExtractor

from app.domain.entities.package import Package

class PackageExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type == "package_declaration" and node.named_children:
            self.result.append(
                Package(
                    name=node.named_children[0].text.decode()
                )
            )