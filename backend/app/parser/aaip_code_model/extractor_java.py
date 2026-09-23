"""
Java -> Entity/Relationship extraction, via tree-sitter.

Returns the same plain-dict shape as extractor_python.extract_file --
see that module's docstring for the key list and the pending_calls tuple
shape (caller_id, enclosing_class_id_or_None, receiver_kind, receiver, name).

Module identity comes from the `package` declaration when present; a file
with no package falls back to its repo-relative *directory* (so
`test/User.java` still yields `java:test.User`). Either way the id is a
function of repository content only -- never an absolute path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from app.repository_model import Entity, EntityKind, Relationship, RelationshipKind, Parameter
from app.parser.aaip_code_model.common import (
    make_id, module_qualified_name, parse_type_reference, location, text_of,
    signature_suffix, normalize_relative_path, find_parse_errors, join_qualified,
)

LANGUAGE = "java"
_parser = get_parser("java")

_TYPE_DECL_KINDS = {
    "class_declaration": EntityKind.CLASS,
    "interface_declaration": EntityKind.INTERFACE,
    "enum_declaration": EntityKind.ENUM,
    "record_declaration": EntityKind.CLASS,
    "annotation_type_declaration": EntityKind.INTERFACE,
}


def _modifiers_node(node: Node) -> Node | None:
    # `modifiers` is not a named field on declaration nodes in this grammar,
    # just an optional leading child -- find it positionally.
    for c in node.children:
        if c.type == "modifiers":
            return c
    return None


def _package_name(root: Node, source: bytes) -> str | None:
    for child in root.children:
        if child.type == "package_declaration":
            for c in child.children:
                if c.type in ("scoped_identifier", "identifier"):
                    return text_of(c, source)
    return None


def _params(node: Node, source: bytes) -> list[Parameter]:
    out: list[Parameter] = []
    for child in node.children:
        if child.type == "formal_parameter":
            type_node = child.child_by_field_name("type")
            name_node = child.child_by_field_name("name")
            out.append(
                Parameter(
                    name=text_of(name_node, source) if name_node else "?",
                    type=parse_type_reference(text_of(type_node, source) if type_node else None),
                )
            )
        elif child.type == "spread_parameter":
            type_node = child.children[0]
            decl = child.child_by_field_name("declarator") or (child.children[-1] if child.children else None)
            name = text_of(decl, source) if decl is not None and decl.type == "identifier" else "args"
            out.append(
                Parameter(name=name, type=parse_type_reference(text_of(type_node, source)), is_variadic=True)
            )
    return out


def _literal_arg_type(node: Node) -> str | None:
    """Coarse type of a call argument, only for simple literals -- see
    extractor_python's version of this function for the rationale."""
    t = node.type
    if t in ("decimal_integer_literal", "hex_integer_literal", "octal_integer_literal", "binary_integer_literal"):
        return "int"
    if t in ("decimal_floating_point_literal", "hex_floating_point_literal"):
        return "float"
    if t == "string_literal":
        return "string"
    if t in ("true", "false"):
        return "boolean"
    if t == "character_literal":
        return "char"
    if t == "unary_expression":
        for c in node.children:
            if c.type in ("decimal_integer_literal", "decimal_floating_point_literal"):
                return _literal_arg_type(c)
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
    """Java locals are explicitly typed, so this is higher-confidence than
    the Python/JS equivalent: `Type name = ...;` gives the declared type
    directly. `var name = new ClassName(...)` (type inference) falls back to
    reading the constructor call's type, same as Python/JS.

    Also returns a conservative alias map (spec 8): `var account = user;`
    or a plain reassignment `account = user;` where the right-hand side is a
    bare identifier -> {"account": "user"}, chased by the orchestrator back
    to whatever type `user` is known to have. A declared, non-`var` type
    already gives a direct answer and is never treated as an alias.

    A third map of recorded call references (spec 26): `var user =
    repository.findUser();` / `var user = findUser();` (no declared, non-var
    type) records the call shape so the orchestrator can resolve it itself
    and, only if that callee has a known declared return type, treat the
    local as having that type.

    And a fourth, general composable map (spec 2/3): `var z = service.user;`
    / `var a = service.user.profile;` / `var c =
    service.getUser().profile;` -- any right-hand side `_flatten_expression`
    reduces to a non-trivial `(root, steps)` chain rooted at a plain
    name -- resolved by the orchestrator's shared chain engine, the same one
    used for call receivers and non-call member references.

    Declarations and plain reassignments are walked together in document
    order, last-write-wins across all four maps (spec 9) -- see
    extractor_python's version for why that's an acceptable approximation
    without real control-flow analysis."""
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

    def record(var_name: str, declared_type: str | None, value_node: Node | None) -> None:
        if declared_type and declared_type != "var":
            _clear(var_name)
            types[var_name] = declared_type
            return
        if value_node is None:
            return
        if value_node.type == "object_creation_expression":
            ctor_type = value_node.child_by_field_name("type")
            if ctor_type is not None:
                _clear(var_name)
                types[var_name] = text_of(ctor_type, source).split("<")[0].strip()
        elif value_node.type == "identifier":
            source_name = text_of(value_node, source)
            if source_name != var_name:
                _clear(var_name)
                aliases[var_name] = source_name
        elif value_node.type == "field_access":
            # `var a = service.user;` / `var b = service.user.profile;`
            _record_chain(var_name, value_node)
        elif value_node.type == "method_invocation":
            name_node = value_node.child_by_field_name("name")
            obj_node = value_node.child_by_field_name("object")
            if name_node is None:
                _clear(var_name)
                return
            simple = text_of(name_node, source)
            arg_sig = _arg_signature(value_node, source)
            if obj_node is None:
                _clear(var_name)
                call_types[var_name] = {
                    "receiver_kind": "bare", "receiver": None,
                    "simple": simple, "arg_signature": list(arg_sig),
                }
            elif obj_node.type == "this":
                _clear(var_name)
                call_types[var_name] = {
                    "receiver_kind": "self", "receiver": None,
                    "simple": simple, "arg_signature": list(arg_sig),
                }
            else:
                # `var c = service.getUser().profile;` / `var d =
                # repository.findUser(id).getProfile();` -- the general
                # composable chain (spec 2/4), not just a single hop.
                _record_chain(var_name, value_node)
        else:
            _clear(var_name)

    def walk(n: Node) -> None:
        if n.type == "local_variable_declaration":
            type_node = n.child_by_field_name("type")
            declared_type = text_of(type_node, source).split("<")[0].strip() if type_node else None
            for decl in n.children:
                if decl.type != "variable_declarator":
                    continue
                name_node = decl.child_by_field_name("name")
                value_node = decl.child_by_field_name("value")
                if name_node is None:
                    continue
                record(text_of(name_node, source), declared_type, value_node)
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
    """The composable expression-chain flattener (spec 2/16), Java's
    equivalent of extractor_python._flatten_expression -- see that
    docstring for the shared (root, steps) shape and rationale. Handles
    `this`, plain identifiers, `field_access` (`object`/`field`) and
    `method_invocation` (`object`/`name`/`arguments`) in any combination,
    so `service.getUser().profile.save()` and `this.a.b.c()` both fall out
    of the same two recursive cases rather than needing dedicated
    resolvers. Returns None for expression shapes with no statically-known
    structure (an array access, a cast, a lambda, ...)."""
    if node.type == "this":
        return ("self",), []
    if node.type == "identifier":
        return ("name", text_of(node, source)), []
    if node.type == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return _flatten_expression(inner, source) if inner is not None else None
    if node.type == "field_access":
        obj = node.child_by_field_name("object")
        field = node.child_by_field_name("field")
        if obj is None or field is None:
            return None
        base = _flatten_expression(obj, source)
        if base is None:
            return None
        root, steps = base
        return root, [*steps, ("field", text_of(field, source))]
    if node.type == "method_invocation":
        name_node = node.child_by_field_name("name")
        obj_node = node.child_by_field_name("object")
        if name_node is None:
            return None
        arg_sig = _arg_signature(node, source)
        simple = text_of(name_node, source)
        if obj_node is None:
            return ("bare",), [("call", simple, arg_sig)]
        base = _flatten_expression(obj_node, source)
        if base is None:
            return None
        root, steps = base
        return root, [*steps, ("call", simple, arg_sig)]
    return None


def _collect_calls_and_creates(body: Node, source: bytes):
    """Returns ({(root, steps)} for calls, {created_type_names}, {(root,
    steps)} for non-call member references -- spec 8). See
    extractor_python._collect_calls_and_creates for the shared (root,
    steps) shape; identical shape here, Java-specific node types."""
    calls: set[tuple[tuple, tuple]] = set()
    creates: set[str] = set()
    member_refs: set[tuple[tuple, tuple]] = set()

    def walk(n: Node) -> None:
        if n.type == "method_invocation":
            flattened = _flatten_expression(n, source)
            if flattened is not None:
                root, steps = flattened
                calls.add((root, tuple(steps)))
            else:
                name_node = n.child_by_field_name("name")
                obj_node = n.child_by_field_name("object")
                if name_node is not None and obj_node is not None:
                    # `receiver.method()` where receiver has no static
                    # structure (an array access, a cast, ...) -- recorded
                    # as an explicitly unsupported construct (spec 12/24)
                    # rather than dropped silently or guessed at.
                    simple = text_of(name_node, source)
                    arg_sig = _arg_signature(n, source)
                    calls.add((("unsupported", text_of(obj_node, source)), (("call", simple, arg_sig),)))
        elif n.type == "object_creation_expression":
            type_node = n.child_by_field_name("type")
            if type_node is not None:
                creates.add(text_of(type_node, source).split("<")[0].strip())
        for c in n.children:
            walk(c)

    def collect_member_refs(n: Node) -> None:
        # Conservatively scoped (spec 8/18) -- see extractor_python's
        # version of this pass for the rationale: only `return`-statement
        # values that are a plain field-access chain, no trailing call.
        if n.type == "return_statement":
            value = None
            for c in n.named_children:
                value = c
                break
            if value is not None and value.type == "field_access":
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
    source = source_bytes
    tree = _parser.parse(source)
    root = tree.root_node
    parse_errors = find_parse_errors(root, relative_path)

    package = _package_name(root, source)
    module_qn = package or module_qualified_name(LANGUAGE, relative_path)
    module_id = make_id(LANGUAGE, module_qn) if module_qn else make_id(LANGUAGE, "<default>")

    entities: list[Entity] = [
        Entity(
            id=module_id,
            kind=EntityKind.PACKAGE if package else EntityKind.MODULE,
            name=(package.rsplit(".", 1)[-1] if package else (module_qn.rsplit(".", 1)[-1] if module_qn else "<default>")),
            qualified_name=module_qn or "<default>",
            language=LANGUAGE,
            location=location(LANGUAGE, relative_path, root),
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

    def handle_annotations(entity_id: str, modifiers_node: Node | None) -> None:
        if modifiers_node is None:
            return
        for c in modifiers_node.children:
            if c.type in ("annotation", "marker_annotation"):
                name_node = c.child_by_field_name("name")
                if name_node is not None:
                    pending_decorators.append((entity_id, text_of(name_node, source)))

    def visit_method(owner_qn: str, owner_id: str, node: Node, is_constructor: bool) -> None:
        name_node = node.child_by_field_name("name")
        name = text_of(name_node, source) if name_node else "<init>"
        params_node = node.child_by_field_name("parameters")
        type_node = node.child_by_field_name("type")
        params = _params(params_node, source) if params_node else []

        # Parameter *types* are part of the canonical identity, so
        # add(int,int) and add(double,double) are two distinct entities and
        # relationship dedup can never merge them.
        segment = f"<init>{signature_suffix(params)}" if is_constructor else f"{name}{signature_suffix(params)}"
        fn_qn = join_qualified(owner_qn, segment)
        fn_id = make_id(LANGUAGE, fn_qn)

        entities.append(
            Entity(
                id=fn_id,
                kind=EntityKind.CONSTRUCTOR if is_constructor else EntityKind.METHOD,
                name=name,
                qualified_name=fn_qn,
                language=LANGUAGE,
                location=location(LANGUAGE, relative_path, node),
                parameters=params,
                return_type=parse_type_reference(text_of(type_node, source) if type_node else None),
            )
        )
        fn_entity = entities[-1]
        contains(owner_id, fn_id)
        handle_annotations(fn_id, _modifiers_node(node))

        body = node.child_by_field_name("body")
        if body is not None:
            calls, creates, member_refs = _collect_calls_and_creates(body, source)
            for root, steps in sorted(calls, key=lambda c: (c[0], c[1])):
                pending_calls.append((fn_id, owner_id, root, steps))
            for root, steps in sorted(member_refs, key=lambda c: (c[0], c[1])):
                pending_member_refs.append((fn_id, owner_id, root, steps))
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

    def visit_field(owner_qn: str, owner_id: str, node: Node) -> None:
        type_node = node.child_by_field_name("type")
        type_ref = parse_type_reference(text_of(type_node, source) if type_node else None)
        for decl in node.children:
            if decl.type != "variable_declarator":
                continue
            name_node = decl.child_by_field_name("name")
            if name_node is None:
                continue
            fname = text_of(name_node, source)
            field_qn = join_qualified(owner_qn, fname)
            field_id = make_id(LANGUAGE, field_qn)
            entities.append(
                Entity(
                    id=field_id, kind=EntityKind.FIELD, name=fname, qualified_name=field_qn,
                    language=LANGUAGE, return_type=type_ref,
                    location=location(LANGUAGE, relative_path, decl),
                )
            )
            contains(owner_id, field_id)
            handle_annotations(field_id, _modifiers_node(node))

    def visit_enum_constant(owner_qn: str, owner_id: str, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        fname = text_of(name_node, source)
        field_qn = join_qualified(owner_qn, fname)
        field_id = make_id(LANGUAGE, field_qn)
        entities.append(
            Entity(
                id=field_id, kind=EntityKind.FIELD, name=fname, qualified_name=field_qn,
                language=LANGUAGE, location=location(LANGUAGE, relative_path, node),
                metadata={"enum_constant": True},
            )
        )
        contains(owner_id, field_id)

    def visit_member(type_qn: str, type_id: str, member: Node) -> None:
        if member.type == "method_declaration":
            visit_method(type_qn, type_id, member, is_constructor=False)
        elif member.type == "constructor_declaration":
            visit_method(type_qn, type_id, member, is_constructor=True)
        elif member.type == "field_declaration":
            visit_field(type_qn, type_id, member)
        elif member.type == "enum_constant":
            visit_enum_constant(type_qn, type_id, member)
        elif member.type in _TYPE_DECL_KINDS:  # nested class/interface/enum/record
            visit_type(member, type_qn, type_id)
        elif member.type in ("enum_body_declarations",):
            for m2 in member.children:
                visit_member(type_qn, type_id, m2)

    def visit_type(node: Node, owner_qn: str, owner_id: str) -> None:
        """`owner_qn`/`owner_id` are the enclosing scope -- the package/module for a
        top-level type, or the containing type's (qn, id) for a nested one. This is
        what makes `Outer.Inner` come out fully qualified instead of just `Inner`,
        so ownership context is never flattened away."""
        kind = _TYPE_DECL_KINDS[node.type]
        name_node = node.child_by_field_name("name")
        name = text_of(name_node, source)
        type_qn = join_qualified(owner_qn, name)
        type_id = make_id(LANGUAGE, type_qn)
        entities.append(
            Entity(
                id=type_id, kind=kind, name=name, qualified_name=type_qn,
                language=LANGUAGE, location=location(LANGUAGE, relative_path, node),
            )
        )
        contains(owner_id, type_id)
        symbols.setdefault(name, type_id)
        handle_annotations(type_id, _modifiers_node(node))

        superclass = node.child_by_field_name("superclass")
        if superclass is not None:
            type_id_node = superclass.child_by_field_name("type") or (
                superclass.children[-1] if superclass.children else None
            )
            if type_id_node is not None:
                pending_bases.append((type_id, text_of(type_id_node, source).split("<")[0].strip()))

        # `interfaces` on a class = implements; on an interface the grammar
        # exposes the same field for `extends`, which is semantically
        # inheritance, so route it accordingly.
        interfaces = node.child_by_field_name("interfaces")
        if interfaces is not None:
            type_list = interfaces.children[-1]
            sink = pending_bases if kind == EntityKind.INTERFACE else pending_implements
            for c in type_list.children:
                if c.type not in ("(", ")", ","):
                    sink.append((type_id, text_of(c, source).split("<")[0].strip()))

        # Interfaces may also expose `extends` under its own field name.
        extends_iface = node.child_by_field_name("extends_interfaces")
        if extends_iface is not None:
            for c in extends_iface.children:
                if c.type == "type_list":
                    for t in c.children:
                        if t.type not in ("(", ")", ","):
                            pending_bases.append((type_id, text_of(t, source).split("<")[0].strip()))

        body_field = node.child_by_field_name("body") or node.child_by_field_name("interface_body")
        for member in (body_field.children if body_field else []):
            visit_member(type_qn, type_id, member)

    for top in root.children:
        if top.type in _TYPE_DECL_KINDS:
            visit_type(top, module_qn, module_id)
        elif top.type == "import_declaration":
            is_wildcard = any(c.type == "asterisk" or text_of(c, source) == "*" for c in top.children)
            name_node = None
            for c in top.children:
                if c.type in ("scoped_identifier", "identifier"):
                    name_node = c
            if name_node is None:
                continue
            dotted = text_of(name_node, source)
            simple = dotted.rsplit(".", 1)[-1]
            if not is_wildcard:
                # A wildcard import names no symbol, so it must not be bound
                # to the package's last segment as if it were a type.
                imports_by_simple_name[simple] = dotted
                import_candidates[simple] = [dotted]
            imp_id = make_id(LANGUAGE, f"{module_qn}::import::{dotted}{'.*' if is_wildcard else ''}")
            entities.append(
                Entity(
                    id=imp_id, kind=EntityKind.IMPORT, name=dotted, qualified_name=dotted,
                    language=LANGUAGE, location=location(LANGUAGE, relative_path, top),
                    metadata={"wildcard": is_wildcard},
                )
            )
            contains(module_id, imp_id)
            relationships.append(Relationship(source_id=module_id, target_id=imp_id, kind=RelationshipKind.IMPORTS))

    return {
        "entities": entities,
        "relationships": relationships,
        "module_id": module_id,
        "module_qualified_name": module_qn or "<default>",
        "language": LANGUAGE,
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