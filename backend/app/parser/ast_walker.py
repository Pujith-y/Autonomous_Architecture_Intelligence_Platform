class ASTWalker:

    def walk(self, node, extractor):
        if node is None:
            return
        extractor.visit(node)

        for child in node.named_children:
            self.walk(child, extractor)