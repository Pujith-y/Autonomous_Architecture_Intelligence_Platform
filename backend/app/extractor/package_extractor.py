from app.extractor.base import BaseExtractor


class PackageExtractor(BaseExtractor):

    def __init__(self):
        super().__init__()

    def visit(self, node):
        if node.type == "package_declaration" and node.named_children:
            self.result.append(node.named_children[0].text.decode())