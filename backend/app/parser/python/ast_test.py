import ast

source = """
from app.models import User

class UserService(BaseService):

    def get_user(self, user_id: int) -> User:
        return self.repository.find(user_id)
"""

tree = ast.parse(source)

print(ast.dump(tree, indent=4))

print(type(tree))
print(len(tree.body))

for node in tree.body:
    print(type(node).__name__)

for node in tree.body:

    if isinstance(node, ast.ClassDef):
        print("CLASS:", node.name)

        for base in node.bases:
            print(
                "BASE:",
                type(base).__name__,
                getattr(base, "id", None),
            )

        for child in node.body:
            print(
                type(child).__name__,
                getattr(child, "name", None),
            )

