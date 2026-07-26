from app.parser.java_parser import JavaParser

parser = JavaParser()

parsed = parser.parse("app/parser/User.java")

print(parsed)