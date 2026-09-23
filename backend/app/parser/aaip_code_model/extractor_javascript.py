"""
JavaScript / TypeScript (and JSX/TSX) -> Entity/Relationship extraction, via
tree-sitter. Returns the same plain-dict shape as extractor_python.extract_file
(see that module's docstring for the pending_calls tuple shape).

Grammar is picked from the file extension: .ts/.tsx use the TypeScript
grammars (tsx grammar for .tsx so JSX syntax parses), everything else
(.js/.jsx/.mjs/.cjs) uses javascript.

CLASS HERITAGE -- the two grammars genuinely differ, and assuming one shape
was the inheritance bug. Verified against the installed grammars:

    javascript:  class_declaration
                   class_heritage
                     extends          <- anonymous keyword token
                     identifier       <- the base, a *direct* child

    typescript:  class_declaration
                   class_heritage
                     extends_clause
                       extends
                       identifier     <- also reachable via field "value"
                     implements_clause
                       implements
                       type_identifier, ",", generic_type, ...

So `_heritage_refs` handles both: a wrapped `extends_clause`/
`implements_clause` when present, and the bare post-`extends` expression
when not. It never assumes a node shape that only one grammar produces.

IMPORTS
-------
Relative specifiers ("./base", "./base.js", "../lib/x") are resolved against
the importing file's own repo-relative path into the *same*
module-qualified-name space used for the MODULE entity id
(module_qualified_name), e.g. "./base.js" imported from "js/user.ts"
resolves to "js/base" -- so an imported symbol maps to the *real*
module-qualified name of the module that exports it ("js/base.BaseUser"),
not an invented string built from the raw specifier text
("./base.js.BaseUser"). Extensionless specifiers yield both the plain and
the `/index` candidate; the repository index -- not this extractor -- picks
whichever actually exists (spec 11). Bare package specifiers ("react",
"@scope/pkg") are not repo-relative, produce no candidate, and correctly
fall through to an external stub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from app.repository_model import Entity, EntityKind, Relationship, RelationshipKind, Parameter
from app.parser.aaip_code_model.common import (
    make_id, module_qualified_name, parse_type_reference, location, text_of,
    signature_suffix, normalize_relative_path, find_parse_errors,
    join_qualified, js_module_candidates, JS_EXTENSIONS,
)

LANGUAGE = "javascript"

_parsers = {
    "js": get_parser("javascript"),
    "tsx": get_parser("tsx"),
    "ts": get_parser("typescript"),
}

_JS_EXTENSIONS = JS_EXTENSIONS

_CLASS_NODE_TYPES = ("class_declaration", "class", "abstract_class_declaration")
_HERITAGE_KEYWORDS = ("extends", "implements", ",", "class_heritage")


def _parser_and_language_for(relative_path: Path) -> tuple[Any, str]:
    ext = relative_path.suffix.lower()
    if ext in (".tsx",):
        return _parsers["tsx"], "typescript"
    if ext in (".ts", ".mts", ".cts"):
        return _parsers["ts"], "typescript"
    return _parsers["js"], "javascript"


def _strip_type_annotation(node: Node | None, source: bytes) -> str | None:
    """`type_annotation` nodes are literally ": <type>" -- drop the colon."""
    if node is None:
        return None
    inner = [c for c in node.children if c.type != ":"]
    if not inner:
        return None
    return text_of(inner[0], source)


def _unwrap_export(node: Node) -> Node:
    if node.type == "export_statement":
        decl = node.child_by_field_name("declaration") or node.child_by_field_name("value")
        if decl is not None:
            return decl
    return node


def _ref_text(node: Node, source: bytes) -> str:
    """The base/interface expression as a resolvable reference: generic
    arguments are noise here ("Comparable<User>" -> "Comparable")."""
    return text_of(node, source).split("<")[0].strip()


def _heritage_refs(class_node: Node, source: bytes) -> tuple[list[str], list[str]]:
    """(base class references, implemented interface references).

    Works for both the JavaScript and the TypeScript grammar shapes -- see
    the module docstring. Returns references as written in source; deciding
    *which* BaseUser in the repository they mean is the orchestrator's job.
    """
    bases: list[str] = []
    implemented: list[str] = []

    def read_clause(clause: Node, sink: list[str]) -> None:
        value = clause.child_by_field_name("value")
        if value is not None:
            sink.append(_ref_text(value, source))
            return
        for c in clause.children:
            if c.type in _HERITAGE_KEYWORDS or c.type == "type_arguments":
                continue
            if not c.is_named:
                continue
            sink.append(_ref_text(c, source))

    for child in class_node.children:
        if child.type != "class_heritage":
            continue
        saw_clause = False
        for h in child.children:
            if h.type == "extends_clause":
                saw_clause = True
                read_clause(h, bases)
            elif h.type == "implements_clause":
                saw_clause = True
                read_clause(h, implemented)
        if saw_clause:
            continue
        # Plain JavaScript grammar: `class_heritage -> "extends" <expression>`
        # with no wrapper clause node. The base is a direct named child.
        for h in child.children:
            if not h.is_named or h.type in _HERITAGE_KEYWORDS or h.type == "type_arguments":
                continue
            bases.append(_ref_text(h, source))

    return bases, implemented


def _interface_extends(node: Node, source: bytes) -> list[str]:
    """TS `interface A extends B, C {}` -> ["B", "C"]."""
    out: list[str] = []
    for child in node.children:
        if child.type in ("extends_type_clause", "extends_clause"):
            for c in child.children:
                if c.is_named and c.type not in ("type_arguments",):
                    out.append(_ref_text(c, source))
    return out


def _params(node: Node, source: bytes) -> list[Parameter]:
    out: list[Parameter] = []
    for child in node.children:
        if child.type in ("(", ")", ","):
            continue
        if child.type in ("required_parameter", "optional_parameter"):
            pattern = child.child_by_field_name("pattern")
            type_node = child.child_by_field_name("type")
            value_node = child.child_by_field_name("value")
            is_rest = pattern is not None and pattern.type == "rest_pattern"
            name = text_of(pattern.children[-1] if is_rest else pattern, source) if pattern else "?"
            out.append(
                Parameter(
                    name=name,
                    type=parse_type_reference(_strip_type_annotation(type_node, source)),
                    default_value=text_of(value_node, source) if value_node else None,
                    is_variadic=is_rest,
                )
            )
        elif child.type == "identifier":
            # Plain JS `formal_parameters` hold bare identifiers with no
            # wrapper node -- untyped, which signature_suffix renders as "?".
            out.append(Parameter(name=text_of(child, source)))
        elif child.type == "rest_pattern":
            out.append(Parameter(name=text_of(child.children[-1], source), is_variadic=True))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            right = child.child_by_field_name("right")
            out.append(
                Parameter(
                    name=text_of(left, source) if left else "?",
                    default_value=text_of(right, source) if right else None,
                )
            )
    return out


def _literal_arg_type(node: Node) -> str | None:
    """Coarse type of a call argument, only for simple literals. JS/TS has a
    single numeric literal kind (no separate int/float syntax), so numeric
    overload disambiguation is naturally coarser here than Python/Java --
    still enough to distinguish e.g. a `(number)` overload from a
    `(string)` one."""
    t = node.type
    if t == "number":
        return "number"
    if t == "string":
        return "string"
    if t in ("true", "false"):
        return "boolean"
    if t == "unary_expression":
        for c in node.children:
            if c.type == "number":
                return "number"
    return None


def _arg_signature(node_with_arguments: Node, source: bytes) -> tuple[str | None, ...]:
    args_node = node_with_arguments.child_by_field_name("arguments")
    if args_node is None:
        return ()
    out: list[str | None] = []
    for c in args_node.children:
        if c.type in ("(", ")", ","):
            continue
        out.append(_literal_arg_type(c))
    return tuple(out)


def _local_constructor_types(
    body: Node, source: bytes
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """`const/let/var x = new ClassName(...)` in the function body ->
    {"x": "ClassName"} (spec 5/37). A `: Type` annotation on the declarator
    is trusted directly when present (TS, higher confidence than inferring
    from the constructor call); otherwise falls back to the `new` call's
    type.

    Also returns a conservative alias map (spec 8): `const account = user;`
    or a plain reassignment `account = user;` with a bare identifier on the
    right -> {"account": "user"}, chased by the orchestrator back to
    whatever type `user` is known to have.

    A third map of recorded call references (spec 26): `const user =
    repo.findUser();` (no `: Type` annotation) records the call shape so the
    orchestrator can resolve it itself and, only if that callee has a known
    declared return type, treat the local as having that type.

    And a fourth, general composable map (spec 2/3): `const z =
    service.user;` / `const a = service.user.profile;` / `const c =
    service.getUser().profile;` -- any right-hand side
    `_flatten_expression` reduces to a non-trivial `(root, steps)` chain
    rooted at a plain name -- resolved by the orchestrator's shared chain
    engine, the same one used for call receivers and non-call member
    references.

    Same last-write-wins approximation, in document order across all four
    maps, as the Python/Java versions (spec 9)."""
    types: dict[str, str] = {}
    aliases: dict[str, str] = {}
    call_types: dict[str, dict[str, Any]] = {}
    chains: dict[str, dict[str, Any]] = {}

    def _clear(name: str) -> None:
        types.pop(name, None)
        aliases.pop(name, None)
        call_types.pop(name, None)
        chains.pop(name, None)

    def _record_chain(var_name: str, value_node: Node) -> None:
        flattened = _flatten_expression(value_node, source)
        if flattened is not None and flattened[0][0] == "name" and flattened[1]:
            _clear(var_name)
            root, steps = flattened
            chains[var_name] = {"root": list(root), "steps": [list(s) for s in steps]}
        else:
            _clear(var_name)

    def record(var_name: str, declared: str | None, value_node: Node | None) -> None:
        if declared:
            _clear(var_name)
            types[var_name] = declared.split("<")[0].strip()
            return
        if value_node is None:
            return
        if value_node.type == "new_expression":
            ctor = value_node.child_by_field_name("constructor")
            if ctor is not None:
                _clear(var_name)
                types[var_name] = _ref_text(ctor, source)
        elif value_node.type == "identifier":
            source_name = text_of(value_node, source)
            if source_name != var_name:
                _clear(var_name)
                aliases[var_name] = source_name
        elif value_node.type == "member_expression":
            # `const a = service.user;` / `const b = service.user.profile;`
            _record_chain(var_name, value_node)
        elif value_node.type == "call_expression":
            fn = value_node.child_by_field_name("function")
            arg_sig = _arg_signature(value_node, source)
            if fn is None:
                _clear(var_name)
                return
            if fn.type == "identifier":
                _clear(var_name)
                call_types[var_name] = {
                    "receiver_kind": "bare", "receiver": None,
                    "simple": text_of(fn, source), "arg_signature": list(arg_sig),
                }
            elif fn.type == "member_expression":
                obj = fn.child_by_field_name("object")
                prop = fn.child_by_field_name("property")
                if obj is not None and prop is not None and obj.type == "this":
                    _clear(var_name)
                    call_types[var_name] = {
                        "receiver_kind": "self", "receiver": None,
                        "simple": text_of(prop, source), "arg_signature": list(arg_sig),
                    }
                else:
                    # `const c = service.getUser().profile;` -- the general
                    # composable chain (spec 2/4), not just a single hop.
                    _record_chain(var_name, value_node)
            else:
                _clear(var_name)
        else:
            _clear(var_name)

    def walk(n: Node) -> None:
        if n.type == "variable_declarator":
            name_node = n.child_by_field_name("name")
            type_node = n.child_by_field_name("type")
            value_node = n.child_by_field_name("value")
            if name_node is not None and name_node.type == "identifier":
                declared = _strip_type_annotation(type_node, source) if type_node else None
                record(text_of(name_node, source), declared, value_node)
        elif n.type == "assignment_expression":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            if left is not None and left.type == "identifier" and right is not None:
                record(text_of(left, source), None, right)
        for c in n.children:
            walk(c)

    walk(body)
    return types, aliases, call_types, chains


def _flatten_expression(node: Node, source: bytes) -> tuple[tuple, list[tuple]] | None:
    """The composable expression-chain flattener (spec 2/16), JS/TS's
    equivalent of extractor_python._flatten_expression -- see that
    docstring for the shared (root, steps) shape and rationale. Handles
    `this`, plain identifiers, `member_expression` (`object`/`property`)
    and `call_expression` (`function`/`arguments`) in any combination, so
    `service.getUser().profile.save()` and `this.a.b.c()` both fall out of
    the same two recursive cases. Returns None for expression shapes with
    no statically-known structure (an element access, optional chaining,
    an arrow function, ...)."""
    if node.type == "this":
        return ("self",), []
    if node.type == "identifier":
        return ("name", text_of(node, source)), []
    if node.type == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return _flatten_expression(inner, source) if inner is not None else None
    if node.type == "member_expression":
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is None or prop is None:
            return None
        base = _flatten_expression(obj, source)
        if base is None:
            return None
        root, steps = base
        return root, [*steps, ("field", text_of(prop, source))]
    if node.type == "call_expression":
        fn = node.child_by_field_name("function")
        if fn is None:
            return None
        arg_sig = _arg_signature(node, source)
        if fn.type == "identifier":
            return ("bare",), [("call", text_of(fn, source), arg_sig)]
        if fn.type == "member_expression":
            obj = fn.child_by_field_name("object")
            prop = fn.child_by_field_name("property")
            if obj is None or prop is None:
                return None
            base = _flatten_expression(obj, source)
            if base is None:
                return None
            root, steps = base
            return root, [*steps, ("call", text_of(prop, source), arg_sig)]
        return None
    return None


def _collect_calls_and_creates(body: Node, source: bytes):
    """Returns ({(root, steps)} for calls, {created_names}, {(root, steps)}
    for non-call member references -- spec 8). See
    extractor_python._collect_calls_and_creates for the shared (root,
    steps) shape; identical shape here, JS/TS-specific node types."""
    calls: set[tuple[tuple, tuple]] = set()
    creates: set[str] = set()
    member_refs: set[tuple[tuple, tuple]] = set()

    def walk(n: Node) -> None:
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            arg_sig = _arg_signature(n, source)
            if fn is not None and fn.type == "identifier":
                calls.add((("bare",), (("call", text_of(fn, source), arg_sig),)))
            elif fn is not None and fn.type == "member_expression":
                obj = fn.child_by_field_name("object")
                prop = fn.child_by_field_name("property")
                if obj is None or prop is None:
                    return
                flattened = _flatten_expression(n, source)
                if flattened is not None:
                    root, steps = flattened
                    calls.add((root, tuple(steps)))
                else:
                    # The base of the chain has no static structure (an
                    # element access, optional chaining, ...) -- recorded as
                    # an explicitly unsupported construct (spec 12/24)
                    # rather than dropped silently or guessed at.
                    simple = text_of(prop, source)
                    calls.add((("unsupported", text_of(obj, source)), (("call", simple, arg_sig),)))
        elif n.type == "new_expression":
            # `new X()` is unambiguous instantiation syntax -- unlike Python,
            # no capitalization heuristic is needed.
            ctor = n.child_by_field_name("constructor")
            if ctor is not None:
                creates.add(_ref_text(ctor, source))
        for c in n.children:
            walk(c)

    def collect_member_refs(n: Node) -> None:
        # Conservatively scoped (spec 8/18) -- see extractor_python's
        # version of this pass for the rationale: only `return`-statement
        # values that are a plain member-access chain, no trailing call.
        if n.type == "return_statement":
            value = None
            for c in n.named_children:
                value = c
                break
            if value is not None and value.type == "member_expression":
                flattened = _flatten_expression(value, source)
                if flattened is not None:
                    root, steps = flattened
                    if steps and steps[-1][0] == "field":
                        member_refs.add((root, tuple(steps)))
        for c in n.children:
            collect_member_refs(c)

    walk(body)
    collect_member_refs(body)
    return calls, creates, member_refs


def extract_file(relative_path: Path, source_bytes: bytes) -> dict[str, Any]:
    relative_path = normalize_relative_path(relative_path)
    parser, language = _parser_and_language_for(relative_path)
    source = source_bytes
    tree = parser.parse(source)
    root = tree.root_node
    parse_errors = find_parse_errors(root, relative_path)

    module_qn = module_qualified_name(language, relative_path)
    module_id = make_id(language, module_qn)

    entities: list[Entity] = [
        Entity(
            id=module_id, kind=EntityKind.MODULE, name=relative_path.stem,
            qualified_name=module_qn, language=language,
            location=location(language, relative_path, root),
        )
    ]
    relationships: list[Relationship] = []
    symbols: dict[str, str] = {}
    imports_by_simple_name: dict[str, str] = {}
    import_candidates: dict[str, list[str]] = {}
    pending_bases: list[tuple[str, str]] = []
    pending_implements: list[tuple[str, str]] = []
    pending_decorators: list[tuple[str, str]] = []
    pending_calls: list[tuple[str, str | None, tuple, tuple]] = []
    pending_creates: list[tuple[str, str]] = []
    pending_member_refs: list[tuple[str, str | None, tuple, tuple]] = []

    def contains(parent_id: str, child_id: str) -> None:
        relationships.append(Relationship(source_id=parent_id, target_id=child_id, kind=RelationshipKind.CONTAINS))

    def anon_name(node: Node) -> tuple[str, dict[str, Any]]:
        # Tree-sitter can hand us a class/class_declaration with no `name`
        # field (`export default class {}`, `foo(class {})`). Give it a
        # deterministic identity tied to its source location instead of a
        # shared "<anonymous>" that would collide with every other anonymous
        # class in the file. Line/column are repo-relative facts, so the id
        # is stable across machines and runs.
        label = f"<anon-class>@{node.start_point[0] + 1}:{node.start_point[1]}"
        return label, {"anonymous": True}

    def record_import(alias: str, candidates: list[str]) -> None:
        if not candidates:
            return
        import_candidates[alias] = candidates
        imports_by_simple_name.setdefault(alias, candidates[0])

    def visit_function_like(owner_qn: str, owner_id: str, name: str, params_node: Node | None,
                            return_type_node: Node | None, body: Node | None, is_method: bool,
                            location_node: Node, is_constructor: bool = False) -> str:
        params = _params(params_node, source) if params_node else []
        segment = f"{name}{signature_suffix(params)}"
        fn_qn = join_qualified(owner_qn, segment)
        fn_id = make_id(language, fn_qn)
        kind = EntityKind.CONSTRUCTOR if is_constructor else (EntityKind.METHOD if is_method else EntityKind.FUNCTION)
        entities.append(
            Entity(
                id=fn_id, kind=kind, name=name, qualified_name=fn_qn, language=language,
                location=location(language, relative_path, location_node),
                parameters=params,
                return_type=parse_type_reference(_strip_type_annotation(return_type_node, source)),
            )
        )
        fn_entity = entities[-1]
        contains(owner_id, fn_id)
        if not is_method:
            symbols.setdefault(name, fn_id)
        if body is not None:
            calls, creates, member_refs = _collect_calls_and_creates(body, source)
            owner_class_id = owner_id if is_method else None
            for root, steps in sorted(calls, key=lambda c: (c[0], c[1])):
                pending_calls.append((fn_id, owner_class_id, root, steps))
            for root, steps in sorted(member_refs, key=lambda c: (c[0], c[1])):
                pending_member_refs.append((fn_id, owner_class_id, root, steps))
            for c in sorted(creates):
                pending_creates.append((fn_id, c))

            local_types, local_aliases, local_call_types, local_chains = _local_constructor_types(body, source)
            if local_types:
                fn_entity.metadata["local_constructor_types"] = local_types
            if local_aliases:
                fn_entity.metadata["local_aliases"] = local_aliases
            if local_call_types:
                fn_entity.metadata["local_call_types"] = local_call_types
            if local_chains:
                fn_entity.metadata["local_chains"] = local_chains
        return fn_id

    def visit_field(owner_qn: str, owner_id: str, node: Node) -> None:
        # JS grammar names this child field "property"; TS's
        # public_field_definition names it "name". Try both -- assuming only
        # one meant JS class fields were never extracted at all.
        name_node = node.child_by_field_name("name") or node.child_by_field_name("property")
        if name_node is None:
            return
        fname = text_of(name_node, source).lstrip("#")
        type_node = node.child_by_field_name("type")
        field_qn = join_qualified(owner_qn, fname)
        field_id = make_id(language, field_qn)
        entities.append(
            Entity(
                id=field_id, kind=EntityKind.FIELD, name=fname, qualified_name=field_qn,
                language=language, location=location(language, relative_path, node),
                return_type=parse_type_reference(_strip_type_annotation(type_node, source)),
            )
        )
        contains(owner_id, field_id)

    def visit_class(node: Node, owner_qn: str, owner_id: str, name_override: str | None = None) -> str:
        name_node = node.child_by_field_name("name")
        extra_meta: dict[str, Any] = {}
        if name_override is not None:
            name = name_override
            if name_node is None:
                # `const Foo = class {}` -- syntactically anonymous, but the
                # binding gives it a stable, meaningful name. Recorded so the
                # distinction isn't lost.
                extra_meta = {"anonymous_class_expression": True}
        elif name_node is not None:
            name = text_of(name_node, source)
        else:
            name, extra_meta = anon_name(node)
        class_qn = join_qualified(owner_qn, name)
        class_id = make_id(language, class_qn)
        entities.append(
            Entity(id=class_id, kind=EntityKind.CLASS, name=name, qualified_name=class_qn,
                   language=language, location=location(language, relative_path, node), metadata=extra_meta)
        )
        contains(owner_id, class_id)
        symbols.setdefault(name, class_id)

        bases, implemented = _heritage_refs(node, source)
        for b in bases:
            pending_bases.append((class_id, b))
        for i in implemented:
            pending_implements.append((class_id, i))

        for d in (c for c in node.children if c.type == "decorator"):
            text = text_of(d.children[-1], source)
            if "(" in text:
                text = text.split("(", 1)[0]
            pending_decorators.append((class_id, text.strip()))

        body = node.child_by_field_name("body")
        for member in (body.children if body else []):
            if member.type in ("method_definition", "method_signature", "abstract_method_signature"):
                mname_node = member.child_by_field_name("name")
                mname = text_of(mname_node, source) if mname_node else "?"
                visit_function_like(
                    class_qn, class_id, mname,
                    member.child_by_field_name("parameters"),
                    member.child_by_field_name("return_type"),
                    member.child_by_field_name("body"),
                    is_method=True, location_node=member, is_constructor=(mname == "constructor"),
                )
            elif member.type in ("public_field_definition", "field_definition", "property_signature"):
                visit_field(class_qn, class_id, member)
            elif member.type in _CLASS_NODE_TYPES:
                visit_class(member, class_qn, class_id)
        return class_id

    def visit_interface(node: Node, owner_qn: str, owner_id: str) -> None:
        name_node = node.child_by_field_name("name")
        name = text_of(name_node, source) if name_node else anon_name(node)[0]
        iface_qn = join_qualified(owner_qn, name)
        iface_id = make_id(language, iface_qn)
        entities.append(
            Entity(id=iface_id, kind=EntityKind.INTERFACE, name=name, qualified_name=iface_qn,
                   language=language, location=location(language, relative_path, node))
        )
        contains(owner_id, iface_id)
        symbols.setdefault(name, iface_id)

        for base in _interface_extends(node, source):
            pending_bases.append((iface_id, base))

        body = node.child_by_field_name("body")
        for member in (body.children if body else []):
            if member.type == "method_signature":
                mname_node = member.child_by_field_name("name")
                mname = text_of(mname_node, source) if mname_node else "?"
                visit_function_like(
                    iface_qn, iface_id, mname,
                    member.child_by_field_name("parameters"),
                    member.child_by_field_name("return_type"),
                    None, is_method=True, location_node=member,
                )
            elif member.type == "property_signature":
                visit_field(iface_qn, iface_id, member)

    def visit_import(node: Node) -> None:
        source_node = node.child_by_field_name("source")
        from_path = text_of(source_node, source).strip("\"'") if source_node else ""
        module_candidates = js_module_candidates(relative_path, from_path)

        clause = next((c for c in node.children if c.type == "import_clause"), None)
        for c in (clause.children if clause else []):
            if c.type == "identifier":  # default import
                simple = text_of(c, source)
                record_import(simple, [f"{m}.{simple}" for m in module_candidates] + [f"{m}.default" for m in module_candidates])
            elif c.type == "named_imports":
                for spec in c.children:
                    if spec.type != "import_specifier":
                        continue
                    name_node = spec.child_by_field_name("name")
                    alias_node = spec.child_by_field_name("alias")
                    simple = text_of(name_node, source) if name_node else None
                    if simple is None:
                        continue
                    alias = text_of(alias_node, source) if alias_node else simple
                    record_import(alias, [f"{m}.{simple}" for m in module_candidates])
            elif c.type == "namespace_import":
                alias_node = c.children[-1]
                record_import(text_of(alias_node, source), list(module_candidates))

        # The IMPORT *declaration* entity is keyed by the specifier as written
        # -- it represents the line of source, not the thing it points at
        # (spec 25). The semantic dependency is the resolved relationship.
        imp_id = make_id(language, f"{module_qn}::import::{from_path}")
        entities.append(
            Entity(
                id=imp_id, kind=EntityKind.IMPORT, name=from_path, qualified_name=from_path,
                language=language, location=location(language, relative_path, node),
                metadata={"module_candidates": list(module_candidates)},
            )
        )
        contains(module_id, imp_id)
        relationships.append(Relationship(source_id=module_id, target_id=imp_id, kind=RelationshipKind.IMPORTS))

    def visit_top(node: Node) -> None:
        node = _unwrap_export(node)
        if node.type in _CLASS_NODE_TYPES:
            visit_class(node, module_qn, module_id)
        elif node.type in ("interface_declaration",):
            visit_interface(node, module_qn, module_id)
        elif node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            name = text_of(name_node, source) if name_node else anon_name(node)[0]
            visit_function_like(
                module_qn, module_id, name,
                node.child_by_field_name("parameters"),
                node.child_by_field_name("return_type"),
                node.child_by_field_name("body"),
                is_method=False, location_node=node,
            )
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for decl in node.children:
                if decl.type != "variable_declarator":
                    continue
                name_node = decl.child_by_field_name("name")
                value_node = decl.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                if value_node.type in _CLASS_NODE_TYPES:
                    # `const Foo = class extends BaseUser {}`
                    visit_class(value_node, module_qn, module_id, name_override=text_of(name_node, source))
                elif value_node.type in ("arrow_function", "function_expression", "function"):
                    fname = text_of(name_node, source)
                    visit_function_like(
                        module_qn, module_id, fname,
                        value_node.child_by_field_name("parameters"),
                        value_node.child_by_field_name("return_type"),
                        value_node.child_by_field_name("body"),
                        is_method=False, location_node=decl,
                    )
        elif node.type == "import_statement":
            visit_import(node)

    for top in root.children:
        visit_top(top)

    return {
        "entities": entities,
        "relationships": relationships,
        "module_id": module_id,
        "module_qualified_name": module_qn,
        "language": language,
        "symbols": symbols,
        "imports_by_simple_name": imports_by_simple_name,
        "import_candidates_by_simple_name": import_candidates,
        "pending_bases": pending_bases,
        "pending_implements": pending_implements,
        "pending_decorators": pending_decorators,
        "pending_calls": pending_calls,
        "pending_creates": pending_creates,
        "pending_member_refs": pending_member_refs,
        "parse_errors": parse_errors,
    }