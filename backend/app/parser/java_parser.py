from tree_sitter import Language, Parser
import tree_sitter_java

JAVA_LANGUAGE = Language(tree_sitter_java.language())

parser = Parser(JAVA_LANGUAGE)


def parse_java(source_code: str):
    return parser.parse(source_code.encode("utf-8"))