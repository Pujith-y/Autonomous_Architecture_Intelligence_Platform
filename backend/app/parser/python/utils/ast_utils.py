from pathlib import Path
import ast

from app.repository_model import SourceLocation


def location(
    path: Path,
    node,
) -> SourceLocation:

    start_line = getattr(
        node,
        "lineno",
        1,
    )

    end_line = getattr(
        node,
        "end_lineno",
        start_line,
    )

    return SourceLocation(
        file=path,
        start_line=start_line,
        end_line=end_line,
        start_column=getattr(
            node,
            "col_offset",
            None,
        ),
        end_column=getattr(
            node,
            "end_col_offset",
            None,
        ),
    )

def attribute_name(
        node,
    ) -> str:

        parts = []

        while isinstance(
            node,
            ast.Attribute,
        ):

            parts.append(node.attr)
            node = node.value

        if isinstance(node, ast.Name):

            parts.append(node.id)

        parts.reverse()

        return ".".join(parts)
