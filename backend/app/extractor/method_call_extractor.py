from app.extractor.base import BaseExtractor

class MethodCallExtractor(BaseExtractor):

    def __init__(self):
        self.calls = []
        self.current_method = None

    def visit(self, node):
        