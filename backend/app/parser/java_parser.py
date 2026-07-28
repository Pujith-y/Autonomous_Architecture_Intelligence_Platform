from tree_sitter import Parser

from app.parser.ast_walker import ASTWalker

from app.models.parsed_file import ParsedFile

from app.extractor.extractor_manager import ExtractorManager

from app.parser.language_loader import JAVA_LANGUAGE

class JavaParser:

    def __init__(self):
        self.parser = Parser(JAVA_LANGUAGE)

    def parse(self, file_path: str):

        with open(file_path, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)
        root = tree.root_node

        manager = ExtractorManager()

        return manager.extract(root)

