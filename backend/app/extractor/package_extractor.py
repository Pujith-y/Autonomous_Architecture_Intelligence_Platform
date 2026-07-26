from app.extractor.base import BaseExtractor


class PackageExtractor(BaseExtractor):

    def __init__(self):
        self.packages = []

    def visit(self, node):
        if node.type == "package_declaration" and node.named_children:
            self.packages.append(node.named_children[0].text.decode())