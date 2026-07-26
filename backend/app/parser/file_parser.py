from pathlib import Path

from app.parser.java_parser import parse_java

from app.parser.walker import ASTWalker

from app.extractor.class_extractor import ClassExtractor
from app.extractor.method_extractor import MethodExtractor
from app.extractor.package_extractor import PackageExtractor
from app.extractor.import_extractor import ImportExtractor
from app.extractor.field_extractor import FieldExtractor


def parse_java_file(file_path: str):
    path = Path(file_path)

    source_code = path.read_text(encoding="utf-8")

    return parse_java(source_code)

tree = parse_java_file("app/parser/User.java")

root = tree.root_node

walker = ASTWalker()

classextractor = ClassExtractor()
methodextractor = MethodExtractor()
packageextractor = PackageExtractor()
importextarctor = ImportExtractor()
fieldextractor = FieldExtractor()

walker.walk(root,classextractor)
walker.walk(root,methodextractor)
walker.walk(root,packageextractor)
walker.walk(root,importextarctor)
walker.walk(root,fieldextractor)

print(classextractor.classes)
print(methodextractor.methods)
print(packageextractor.packages)
print(importextarctor.imports)
print(fieldextractor.fields)

# # print(root.type)
# # print(root.start_point)
# # print(root.end_point)
# # print(root.child_count)

# # class_node = root.children[0]

# # print(class_node.type)

# # for child in class_node.children:
# #     print(child.type)

# # print(class_node.children)
# # print(class_node.named_children)

# # def print_tree(node, level=0):
# #     print("  " * level + node.type)

# #     for child in node.named_children:
# #         print_tree(child, level + 1)

# # def count_nodes(node):
# #     count = 1
# #     for child in node.named_children:
# #             count += count_nodes(child)
# #     return count


# # print_tree(root,0)
# # print(count_nodes(root))

# # def find_classes(node):
# #     if node.type == "class_declaration":
# #         print(node)

# #     for child in node.named_children:
# #         find_classes(child)

# # find_classes(root)

# class_node = root.named_children[0]

# print(class_node.text.decode("utf-8"))

# # for child in class_node.named_children:
# #     print(child.type)
# #     print(child.text.decode("utf-8"))
# #     print("------")

# def extract_class_names(node):
#     classes = []

#     if node.type == "class_declaration":
#         for child in node.named_children:
#             if child.type == "identifier":
#                 classes.append(child.text.decode())

#     for child in node.named_children:
#         classes.extend(extract_class_names(child))

#     return classes

# print(root)
# print(extract_class_names(root))

# def extract_method_names(node):
#     methods = []

#     if node.type == "method_declaration":
#         for child in node.named_children:
#             if child.type == "identifier":
#                 methods.append(child.text.decode())

#     for child in node.named_children:
#         methods.extend(extract_method_names(child))

#     return methods

# print(extract_method_names(root))


# def extract_package_names(node):
#     packages = []

#     if node.type == "package_declaration":
#         for child in node.named_children:
#             if child.type == "scoped_identifier":
#                 packages.append(child.text.decode())

#     for child in node.named_children:
#         packages.extend(extract_package_names(child))

#     return packages

# print(extract_package_names(root))

# def extract_import_names(node):
#     imports = []

#     if node.type == "import_declaration":
#         for child in node.named_children:
#             if child.type == "scoped_identifier":
#                 imports.append(child.text.decode())

#     for child in node.named_children:
#         imports.extend(extract_import_names(child))

#     return imports

# print(extract_import_names(root))

# def extract_field_names(node):
#     fields = []

#     if node.type == "field_declaration":
#         for child in node.named_children:
#             if child.type == "variable_declarator":
#                 fields.append(child.text.decode())

#     for child in node.named_children:
#         fields.extend(extract_field_names(child))

#     return fields

# print(extract_field_names(root))
