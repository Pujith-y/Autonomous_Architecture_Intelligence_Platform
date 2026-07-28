from app.extractor.class_extractor import ClassExtractor
from app.extractor.method_extractor import MethodExtractor
from app.extractor.package_extractor import PackageExtractor
from app.extractor.import_extractor import ImportExtractor
from app.extractor.field_extractor import FieldExtractor
from app.extractor.method_call_extractor import MethodCallExtractor
from app.extractor.object_creation_extractor import ObjectCreationExtractor
from app.extractor.extends_extractor import ExtendsExtractor
from app.extractor.implements_extractor import ImplementsExtractor
from app.extractor.interface_extractor import InterfaceExtractor

from app.parser.ast_walker import ASTWalker
from app.models.parsed_file import ParsedFile

class ExtractorManager:

    def __init__(self):

        self.extractors = {
            "package": PackageExtractor(),
            "import": ImportExtractor(),
            "class": ClassExtractor(),
            "method": MethodExtractor(),
            "field": FieldExtractor(),
            "interface" : InterfaceExtractor(),
            "calls": MethodCallExtractor(),
            "objects": ObjectCreationExtractor(),
            "extends": ExtendsExtractor(),
            "implements": ImplementsExtractor(),
        }

    def extract(self, root):

        walker = ASTWalker()
        walker.walk(root, self.extractors.values())

        return ParsedFile(
            packages=self.extractors["package"].result,
            imports=self.extractors["import"].result,

            classes=self.extractors["class"].result,
            methods=self.extractors["method"].result,
            fields=self.extractors["field"].result,
            interfaces=self.extractors["interface"].result,

            method_calls=self.extractors["calls"].result,
            object_creations=self.extractors["objects"].result,

            extends=self.extractors["extends"].result,
            implements=self.extractors["implements"].result,
        )