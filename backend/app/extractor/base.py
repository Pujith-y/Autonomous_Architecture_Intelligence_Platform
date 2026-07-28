class BaseExtractor:

    def __init__(self):
        self.result = []

    def visit(self, node):
        raise NotImplementedError