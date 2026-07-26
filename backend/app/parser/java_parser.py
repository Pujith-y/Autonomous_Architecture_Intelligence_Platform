from tree_sitter import Parser

from app.parser.ast_walker import ASTWalker

from app.models.parsed_file import ParsedFile

from app.extractor.class_extractor import ClassExtractor
from app.extractor.method_extractor import MethodExtractor
from app.extractor.package_extractor import PackageExtractor
from app.extractor.import_extractor import ImportExtractor
from app.extractor.field_extractor import FieldExtractor
from app.extractor.method_call_extractor import MethodCallExtractor
from app.extractor.object_creation_extractor import ObjectCreationExtractor
from app.extractor.extends_extractor import ExtendsExtractor
from app.extractor.implements_extractor import ImplementsExtractor

from app.parser.language_loader import JAVA_LANGUAGE

class JavaParser:

    def __init__(self):
        self.parser = Parser(JAVA_LANGUAGE)

    def parse(self, file_path: str):

        with open(file_path, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)
        root = tree.root_node
        extractors = {
            "package": PackageExtractor(),
            "import": ImportExtractor(),
            "class": ClassExtractor(),
            "method": MethodExtractor(),
            "field": FieldExtractor(),
            "calls": MethodCallExtractor(),
            "objects": ObjectCreationExtractor(),
            "extends": ExtendsExtractor(),
            "implements": ImplementsExtractor(),
        }

        walker = ASTWalker()

        for extractor in extractors.values():
            walker.walk(root, extractor)

        return ParsedFile(
            packages=extractors["package"].packages,
            imports=extractors["import"].imports,

            classes=extractors["class"].classes,
            methods=extractors["method"].methods,
            fields=extractors["field"].fields,

            method_calls=extractors["calls"].calls,
            object_creations=extractors["objects"].created_objects,

            extends=extractors["extends"].extends,
            implements=extractors["implements"].implements,
        )
