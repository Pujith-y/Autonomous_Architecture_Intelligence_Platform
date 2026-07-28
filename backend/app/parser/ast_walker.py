class ASTWalker:

    def walk(self, node, extractors):
        if node is None:
            return
        
        for extractor in extractors:
            extractor.visit(node)

        for child in node.named_children:
            self.walk(child, extractors)