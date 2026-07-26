from app.extractor.base import BaseExtractor

class ImportExtractor(BaseExtractor):

    def __init__(self):
        self.imports = []

    def visit(self, node):
        if node.type == "import_declaration" and node.named_children[0]:
            self.imports.append(node.named_children[0].text.decode())
