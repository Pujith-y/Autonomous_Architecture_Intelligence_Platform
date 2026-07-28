from app.parser.java_parser import JavaParser

from app.knowledge_graph.graph_builder import GraphBuilder

parser = JavaParser()

parsed = parser.parse("app/parser/User.java")

print(parsed)

builder = GraphBuilder()

builder.build(parsed)

print("Graph created successfully!")