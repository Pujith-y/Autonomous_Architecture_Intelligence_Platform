from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.repository_model import TypeReference, SourceLocation


def make_id(language: str, qualified_name: str) -> str:
    return f"{language}:{qualified_name}"


def join_qualified(owner: str | None, name: str) -> str:
    if not owner:
        return name
    return f"{owner}.{name}"


def module_qualified_name(language: str, relative_path: Path) -> str:

    relative_path = normalize_relative_path(relative_path)
    if language == "python":
        parts = list(relative_path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else relative_path.stem
    if language == "java":
        parts = [p for p in relative_path.parent.parts if p not in ("", ".")]
        return ".".join(parts) if parts else ""
    return relative_path.with_suffix("").as_posix()


def is_python_package_init(relative_path: Path) -> bool:
    return normalize_relative_path(relative_path).stem == "__init__"



_OPTIONAL_MARKERS = {"None", "null", "undefined", "NoneType"}
_COLLECTION_NAMES = {
    "list", "List", "set", "Set", "frozenset", "FrozenSet", "tuple", "Tuple",
    "dict", "Dict", "Map", "Array", "ArrayList", "Collection", "Sequence",
    "Iterable", "Mapping", "HashMap", "HashSet",
}

_TYPING_MODULES = ("typing_extensions", "typing", "t", "tp")
_TYPING_PREFIX_RE = re.compile(r"^(?:%s)\." % "|".join(_TYPING_MODULES))


def _strip_typing_prefix(text: str) -> str:
    return _TYPING_PREFIX_RE.sub("", text, count=1)


def _split_top_level(text: str, sep: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in text:
        if ch in "<[(":
            depth += 1
        elif ch in ">])":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def parse_type_reference(text: str | None) -> TypeReference | None:
    if not text:
        return None
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if not text:
        return None

    text = _strip_typing_prefix(text)

    # T | U | null 
    if "|" in text and not text.startswith("|"):
        alts = _split_top_level(text, "|")
        if len(alts) > 1:
            is_optional = any(a in _OPTIONAL_MARKERS for a in alts)
            real = [a for a in alts if a not in _OPTIONAL_MARKERS]
            if len(real) == 1:
                inner = parse_type_reference(real[0])
                if inner is not None:
                    return TypeReference(
                        name=inner.name,
                        qualified_name=inner.qualified_name,
                        generic_arguments=inner.generic_arguments,
                        is_optional=is_optional,
                        is_collection=inner.is_collection,
                    )
            return TypeReference(
                name="Union",
                union_types=tuple(t for t in (parse_type_reference(r) for r in real) if t),
                is_optional=is_optional,
            )

    # Optional[T]  /  typing.Optional[T]
    m = re.fullmatch(r"Optional\s*\[(.+)\]", text, re.S)
    if m:
        inner = parse_type_reference(m.group(1))
        if inner is not None:
            return TypeReference(
                name=inner.name,
                qualified_name=inner.qualified_name,
                generic_arguments=inner.generic_arguments,
                is_optional=True,
                is_collection=inner.is_collection,
            )

    # Union[A, B, ...]  /  typing.Union[A, B, ...]
    m = re.fullmatch(r"Union\s*\[(.+)\]", text, re.S)
    if m:
        args = _split_top_level(m.group(1), ",")
        is_optional = any(a in _OPTIONAL_MARKERS for a in args)
        real = [a for a in args if a not in _OPTIONAL_MARKERS]
        if len(real) == 1:
            inner = parse_type_reference(real[0])
            if inner is not None:
                return TypeReference(
                    name=inner.name,
                    qualified_name=inner.qualified_name,
                    generic_arguments=inner.generic_arguments,
                    is_optional=is_optional,
                    is_collection=inner.is_collection,
                )
        return TypeReference(
            name="Union",
            union_types=tuple(t for t in (parse_type_reference(a) for a in real) if t),
            is_optional=is_optional,
        )

    # T[]  or  T[][]  (TS array shorthand)
    if text.endswith("[]"):
        inner = parse_type_reference(text[:-2])
        if inner is not None:
            return TypeReference(name="Array", generic_arguments=(inner,), is_collection=True)

    # Name<Args>  or   Name[Args]  
    m = re.fullmatch(r"([\w.$]+)\s*[<\[](.+)[>\]]", text, re.S)
    if m:
        base, inner_text = _strip_typing_prefix(m.group(1)), m.group(2)
        args = [a for a in (parse_type_reference(p) for p in _split_top_level(inner_text, ",")) if a]
        simple = base.rsplit(".", 1)[-1]
        return TypeReference(
            name=simple,
            qualified_name=base if "." in base else None,
            generic_arguments=tuple(args),
            is_collection=simple in _COLLECTION_NAMES,
        )

    simple = text.rsplit(".", 1)[-1]
    return TypeReference(
        name=simple,
        qualified_name=text if "." in text else None,
        is_collection=simple in _COLLECTION_NAMES,
    )


def location(language: str, relative_path: Path, node: Any) -> SourceLocation:
    return SourceLocation(
        file=normalize_relative_path(relative_path),
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        start_column=node.start_point[1],
        end_column=node.end_point[1],
    )


def text_of(node: Any, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _render_type_name(t: TypeReference | None) -> str:
    if t is None:
        return "?"
    if t.union_types:
        rendered = "|".join(_render_type_name(u) for u in t.union_types)
        return f"{rendered}?" if t.is_optional else rendered
    base = t.name
    if t.generic_arguments:
        base = f"{base}<{','.join(_render_type_name(a) for a in t.generic_arguments)}>"
    return f"{base}?" if t.is_optional else base


def signature_suffix(parameters: list[Any]) -> str:
    rendered = []
    for p in parameters:
        name = _render_type_name(p.type)
        rendered.append(f"...{name}" if p.is_variadic else name)
    return "(" + ",".join(rendered) + ")"

def normalize_reference(original: str) -> str:
    text = original.strip()
    for cut in ("<", "["):
        idx = text.find(cut)
        if idx != -1:
            text = text[:idx]
    return text.strip().rstrip(".")


def simple_name_of(normalized: str) -> str:
    return normalized.rsplit(".", 1)[-1].rsplit("::", 1)[-1].rsplit("/", 1)[-1]


def normalize_relative_path(path: Path) -> Path:
    posix = Path(path).as_posix()
    while posix.startswith("./"):
        posix = posix[2:]
    posix = posix.lstrip("/")
    return Path(posix)


# ---------------------------------------------------------------------
# Import candidate lists
#
# An import names a *symbol*, and only the repository-wide index knows which
# qualified name that symbol actually has. So an extractor emits an ordered
# list of plausible qualified names and the orchestrator picks the first one
# that really exists. Nothing is invented: a candidate that matches no
# repository entity is simply skipped.
# ---------------------------------------------------------------------

def package_parts_of(module_qn: str, is_package: bool) -> list[str]:
    """The dotted package that *contains* this module.

    "python.users.user" (a plain module) -> ["python", "users"]
    "python.users"      (a package __init__) -> ["python", "users"]
    """
    parts = [p for p in module_qn.split(".") if p]
    if is_package:
        return parts
    return parts[:-1]


def python_import_candidates(
    module_qn: str, is_package: bool, level: int, from_module: str | None, symbol: str | None
) -> list[str]:
    """Ordered candidate qualified names for one imported symbol.

    level 0 (absolute, `from base import BaseUser`):
        as written ("base.BaseUser"), then progressively-shorter enclosing
        package prefixes ("python.base.BaseUser" for an importer at
        "python/user.py"). The repository index decides which exists, so a
        repo laid out as `python/base.py` resolves correctly without the
        parser ever hard-coding a root.

    level >= 1 (explicit relative, `from .base import X` / `from ..a.b import X`):
        resolved against the importing module's own package -- exactly one
        candidate, because the language semantics are unambiguous.
    """
    tail = [p for p in (from_module or "").split(".") if p]
    if symbol:
        tail = tail + [symbol]
    if not tail:
        return []

    pkg = package_parts_of(module_qn, is_package)

    if level >= 1:
        up = level - 1
        if up > len(pkg):
            return []  # escapes the repository root -- refuse to invent a target
        base = pkg[: len(pkg) - up] if up else pkg
        return [".".join(base + tail)]

    candidates = [".".join(tail)]
    for i in range(len(pkg), 0, -1):
        candidate = ".".join(pkg[:i] + tail)
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")


def js_module_candidates(importer_relative_path: Path, specifier: str) -> list[str]:
    """`"./base.js"` imported from `js/user.ts` -> ["js/base"]; `"./base"` ->
    ["js/base", "js/base/index"]. Returns [] for bare package specifiers
    ("react", "@scope/pkg"), which are not repository-relative and must not
    be guessed into a repo path.

    Both the plain module and its `index` form are offered because only the
    repository contents can decide between `base.js` and `base/index.js`
    (spec 11) -- the orchestrator keeps whichever actually exists.
    """
    if not (specifier.startswith("./") or specifier.startswith("../")):
        return []
    combined = (normalize_relative_path(importer_relative_path).parent / specifier).as_posix()
    parts: list[str] = []
    for part in combined.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/".join(parts)
    if not normalized:
        return []

    had_extension = False
    for ext in JS_EXTENSIONS:
        if normalized.endswith(ext):
            normalized = normalized[: -len(ext)]
            had_extension = True
            break

    candidates = [normalized]
    if not had_extension:
        # "./base" may be base.js|.ts|.jsx|... (same module qn) or base/index.*
        candidates.append(f"{normalized}/index")
    if specifier.endswith("/"):
        candidates = [f"{normalized}/index", normalized]
    return candidates


def find_parse_errors(root: Any, relative_path: Path) -> list[dict[str, Any]]:
    """Tree-sitter is error-tolerant: a malformed file still parses, it just
    gets ERROR nodes (or MISSING tokens) spliced in. A file parsing without a
    Python exception does NOT mean it was syntactically valid -- callers must
    surface this, not silently emit a partial/misleading graph.

    Reporting is per-fault and non-fatal: whatever valid structure surrounds
    the ERROR subtree is still extracted (spec 30)."""
    errors: list[dict[str, Any]] = []
    if not root.has_error:
        return errors

    relative_path = normalize_relative_path(relative_path)

    def walk(n: Any) -> None:
        if n.type == "ERROR" or n.is_missing:
            errors.append(
                {
                    "file": relative_path.as_posix(),
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "start_column": n.start_point[1],
                    "end_column": n.end_point[1],
                    "node_type": n.type,
                    "kind": "missing" if n.is_missing else "error",
                    "message": (
                        f"missing {n.type}" if n.is_missing else "unparseable syntax"
                    ),
                }
            )
            return  # don't descend into an ERROR subtree, one report per fault is enough
        for c in n.children:
            walk(c)

    walk(root)
    return errors