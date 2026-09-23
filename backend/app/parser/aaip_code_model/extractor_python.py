"""
Python -> Entity/Relationship extraction, via tree-sitter.

Returns a plain dict (not a new model class) with keys:
    entities, relationships, module_id, module_qualified_name, language,
    symbols, imports_by_simple_name, import_candidates_by_simple_name,
    pending_bases, pending_implements, pending_decorators, pending_calls,
    pending_creates, pending_member_refs, parse_errors

`orchestrator.py` consumes this same shape from every language extractor.

pending_calls / pending_member_refs entries are 4-tuples:
    (caller_id, enclosing_class_id_or_None, root, steps)

`root` and `steps` are the composable expression-chain shape produced by
`_flatten_expression` (spec 2): `root` is `("self",)`, `("bare",)` (no
receiver -- a plain function call), `("name", identifier)`, or
`("unsupported", raw_text)` for a chain whose base has no static structure
(a call result being subscripted, etc. -- recorded so it's still visible as
an unresolved reference, spec 12/24, rather than silently dropped). `steps`
is an ordered tuple of `("field", name)` / `("call", name, arg_signature)`
hops. For pending_calls the last step is always a `"call"`; for
pending_member_refs it is always a `"field"` (spec 8 -- a reference with no
invocation). The extractor's only job is producing this syntactic shape;
every semantic question ("what type is `service`", "does `Service` have a
field named `user`", "is this call ambiguous") is answered entirely by the
orchestrator's shared chain-resolution engine (spec 16) -- there is no
per-shape special-casing left in this module.

IMPORTS
-------
`imports_by_simple_name` keeps the as-written qualified name (back-compat).
`import_candidates_by_simple_name` is the ordered list the orchestrator
actually resolves against, so that in a repository laid out as

    python/base.py
    python/user.py        # from base import BaseUser

the import resolves to the *repository* entity `python.base.BaseUser`
rather than degrading to a bare simple-name lookup for `BaseUser` (which
would be ambiguous the moment another language also defines that name).
Explicit relative imports (`from .base import X`, `from ..common.types
import Y`) are resolved against the importing module's own package and
yield exactly one candidate. Nothing is invented: a candidate that matches
no repository entity is simply skipped by the orchestrator.
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
    join_qualified, is_python_package_init, python_import_candidates,
)

LANGUAGE = "python"
_parser = get_parser("python")


def _params(node: Node, source: bytes) -> list[Parameter]:
    out: list[Parameter] = []
    seen_star = False
    for child in node.children:
        if child.type in ("(", ")", ","):
            continue
        if child.type == "list_splat_pattern":
            seen_star = True
            name_node = child.children[-1]
            out.append(Parameter(name=text_of(name_node, source), is_variadic=True))
        elif child.type == "dictionary_splat_pattern":
            name_node = child.children[-1]
            out.append(Parameter(name=text_of(name_node, source), is_variadic=True, is_keyword_only=True))
        elif child.type == "*":
            seen_star = True  # bare keyword-only marker
        elif child.type == "identifier":
            out.append(Parameter(name=text_of(child, source), is_keyword_only=seen_star))
        elif child.type == "typed_parameter":
            name = text_of(child.children[0], source)
            type_node = child.child_by_field_name("type")
            out.append(Parameter(name=name, type=parse_type_reference(text_of(type_node, source) if type_node else None), is_keyword_only=seen_star))
        elif child.type == "default_parameter":
            name = text_of(child.child_by_field_name("name"), source)
            default = child.child_by_field_name("value")
            out.append(Parameter(name=name, default_value=text_of(default, source) if default else None, is_keyword_only=seen_star))
        elif child.type == "typed_default_parameter":
            name = text_of(child.child_by_field_name("name"), source)
            type_node = child.child_by_field_name("type")
            default = child.child_by_field_name("value")
            out.append(
                Parameter(
                    name=name,
                    type=parse_type_reference(text_of(type_node, source) if type_node else None),
                    default_value=text_of(default, source) if default else None,
                    is_keyword_only=seen_star,
                )
            )
    return out


def _literal_arg_type(node: Node) -> str | None:
    """Coarse type of a call argument, only for simple literals where the
    type is unambiguous from syntax alone. Anything else (a variable, an
    expression, a call) yields None -- overload resolution only narrows on
    arguments it can classify with confidence, never a guess."""
    if node.type == "keyword_argument":
        return None  # keyword args don't participate in positional overload matching here
    if node.type == "integer":
        return "int"
    if node.type == "float":
        return "float"
    if node.type == "string":
        return "string"
    if node.type in ("true", "false"):
        return "boolean"
    if node.type == "unary_operator":
        # -1, -1.5 etc. -- same coarse type as the operand.
        for c in node.children:
            if c.type in ("integer", "float"):
                return _literal_arg_type(c)
    return None


def _arg_signature(call_node: Node, source: bytes) -> tuple[str | None, ...]:
    args_node = call_node.child_by_field_name("arguments")
    if args_node is None:
        return ()
    out: list[str | None] = []
    for c in args_node.children:
        if c.type in ("(", ")", ","):
            continue
        out.append(_literal_arg_type(c))
    return tuple(out)


def _flatten_expression(node: Node, source: bytes) -> tuple[tuple, list[tuple]] | None:
    """The composable expression-chain flattener (spec 2/16): recursively
    reduces any supported Python expression to a generic

        (root, steps)

    shape the orchestrator's inference engine consumes uniformly, instead of
    the extractor pre-classifying "self call" vs "field call" vs "chained
    call" as separate special cases. `root` is `("self",)`, `("bare",)` (no
    receiver at all -- a plain function call) or `("name", identifier)`.
    `steps` is an ordered list of `("field", name)` or `("call", name,
    arg_signature)` hops, e.g.:

        service.user.profile          -> ("name","service"), [field user, field profile]
        self.a.b.c()                  -> ("self",),           [field a, field b, call c]
        service.get_user().profile    -> ("name","service"), [call get_user, field profile]
        get_user().profile.save()     -> ("bare",),           [call get_user, field profile, call save]

    Returns None for expression shapes with no statically-known structure (a
    subscript, a binary operator, a literal, a lambda, ...) -- extraction
    stays syntax-focused (spec 16) and simply doesn't offer a chain for the
    resolver to reason about; that is the conservative, correct outcome
    (spec 10/18), not a bug to work around with a guess.
    """
    if node.type == "identifier":
        name = text_of(node, source)
        return (("self",) if name == "self" else ("name", name)), []
    if node.type == "parenthesized_expression":
        inner = node.named_children[0] if node.named_children else None
        return _flatten_expression(inner, source) if inner is not None else None
    if node.type == "attribute":
        obj = node.child_by_field_name("object")
        attr = node.child_by_field_name("attribute")
        if obj is None or attr is None:
            return None
        base = _flatten_expression(obj, source)
        if base is None:
            return None
        root, steps = base
        return root, [*steps, ("field", text_of(attr, source))]
    if node.type == "call":
        fn = node.child_by_field_name("function")
        if fn is None:
            return None
        arg_sig = _arg_signature(node, source)
        if fn.type == "identifier":
            # A bare `name(...)` is the root of a fresh chain (there is no
            # object to recurse into) -- resolved against module-local /
            # imported symbols by the orchestrator, same evidence a
            # standalone "bare" call already used.
            return ("bare",), [("call", text_of(fn, source), arg_sig)]
        if fn.type == "attribute":
            obj = fn.child_by_field_name("object")
            attr = fn.child_by_field_name("attribute")
            if obj is None or attr is None:
                return None
            base = _flatten_expression(obj, source)
            if base is None:
                return None
            root, steps = base
            return root, [*steps, ("call", text_of(attr, source), arg_sig)]
        return None
    return None


def _collect_calls_and_creates(
    body: Node, source: bytes
) -> tuple[set[tuple[tuple, tuple]], set[str], set[tuple[tuple, tuple]]]:
    """Returns ({(root, steps)} for calls, {created_names}, {(root, steps)}
    for non-call member references -- spec 8).

    Every call site is flattened through the single shared
    `_flatten_expression` primitive; there is deliberately no per-shape
    branching here beyond "is this call's function a bare name or an
    attribute chain" (needed only to keep the existing CREATES heuristic,
    which is specifically about *bare* capitalized calls, spec 15/37 of the
    original extraction task). Everything about *what the chain means* --
    receiver typing, field propagation, return-type propagation, static vs.
    instance -- is left entirely to the orchestrator (spec 16).
    """
    calls: set[tuple[tuple, tuple]] = set()
    creates: set[str] = set()
    member_refs: set[tuple[tuple, tuple]] = set()

    def walk(n: Node) -> None:
        if n.type == "call":
            fn = n.child_by_field_name("function")
            arg_sig = _arg_signature(n, source)
            if fn is not None and fn.type == "identifier":
                name = text_of(fn, source)
                # Python has no `new`, so a bare call to a CapitalizedName is
                # *offered* as a possible instantiation. It is only turned into
                # a CREATES edge if repository resolution lands on an entity
                # that really is a class (see orchestrator.py); a capitalized
                # factory *function* resolves to a FUNCTION and becomes a CALLS
                # edge instead. The syntax alone never decides.
                if name[:1].isupper():
                    creates.add(name)
                else:
                    calls.add((("bare",), (("call", name, arg_sig),)))
            elif fn is not None and fn.type == "attribute":
                obj = fn.child_by_field_name("object")
                attr = fn.child_by_field_name("attribute")
                if obj is None or attr is None:
                    return
                flattened = _flatten_expression(n, source)
                if flattened is not None:
                    root, steps = flattened
                    calls.add((root, tuple(steps)))
                else:
                    # The base of the chain has no static structure (e.g.
                    # `get_list()[0].save()`) -- recorded as an explicitly
                    # unsupported construct (spec 12/24) rather than either
                    # dropped silently or guessed at.
                    simple = text_of(attr, source)
                    calls.add((("unsupported", text_of(obj, source)), (("call", simple, arg_sig),)))
        for c in n.children:
            walk(c)

    def collect_member_refs(n: Node) -> None:
        # Conservatively scoped (spec 8/18): only a `return`-statement value
        # that is a plain member-access chain with no trailing call (`return
        # self.repository`, `return service.user.profile`) is offered as a
        # candidate non-call reference. This is a common, high-signal shape
        # (a getter/accessor exposing a field) without walking every
        # expression statement in the body looking for incidental attribute
        # access, which would risk noisy/duplicate extraction against
        # chains already captured above.
        if n.type == "return_statement":
            value = None
            for c in n.named_children:
                value = c
                break
            if value is not None and value.type == "attribute":
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


def _local_constructor_types(
    body: Node, source: bytes
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """`x = ClassName(...)` (optionally `x: ClassName = ClassName(...)`) at
    any point in the function body -> {"x": "ClassName"}. Deliberately
    conservative: only a direct call to a Capitalized name on the right-hand
    side counts as high-confidence evidence of the local's type (spec 5/37).

    Also returns a second, conservative alias map (spec 8): `account = user`
    (a bare identifier-to-identifier assignment) records
    {"account": "user"} so the orchestrator can chase it back to whatever
    type `user` is known to have -- only when the assignment is an
    unambiguous single identifier, never through any expression.

    And a third map of recorded call references (spec 26): `x = get_user()`
    or `x = self.find_user()` records enough of the call shape (receiver
    kind, callee simple name, argument signature -- the same shape a
    pending_calls entry carries) for the orchestrator to resolve the call
    itself and, only if *that* callee has a known declared return type,
    treat `x` as having that type. Nothing about `x`'s type is inferred
    from the callee's name here or in the orchestrator.

    And a fourth, general "local_chains" map (spec 2/3): the composable
    counterpart of the above three, covering any right-hand side that
    `_flatten_expression` can reduce to a non-trivial (root, steps) chain --
    `z = service.user`, `a = service.user.profile`, `c =
    service.get_user().profile`. The simpler, higher-confidence maps above
    are populated first and take priority (a bare constructor call or a
    single-identifier alias is exactly as trustworthy as before and isn't
    duplicated here); `local_chains` only fills in the genuinely new
    composable cases -- a chain whose root is a plain local/parameter name
    and whose steps are non-empty. A chain rooted at `self` or at a bare
    call isn't a *local variable's* alias target and is intentionally left
    out.

    All four maps use last-write-wins in document order (spec 9): a name
    that is reassigned -- to a constructor call, an alias, a plain call, a
    chain, or anything else -- drops its earlier entry in every map rather
    than keeping stale type information, and no scope/control-flow-sensitive
    analysis is attempted beyond that."""
    types: dict[str, str] = {}
    aliases: dict[str, str] = {}
    call_types: dict[str, dict[str, Any]] = {}
    chains: dict[str, dict[str, Any]] = {}

    def _clear(name: str) -> None:
        types.pop(name, None)
        aliases.pop(name, None)
        call_types.pop(name, None)
        chains.pop(name, None)

    for n in _walk_all(body):
        if n.type != "assignment":
            continue
        left = n.child_by_field_name("left")
        right = n.child_by_field_name("right")
        if left is None or right is None or left.type != "identifier":
            continue
        target = text_of(left, source)
        if right.type == "call":
            fn = right.child_by_field_name("function")
            arg_sig = _arg_signature(right, source)
            if fn is not None and fn.type == "identifier":
                name = text_of(fn, source)
                _clear(target)
                if name[:1].isupper():
                    types[target] = name
                else:
                    call_types[target] = {
                        "receiver_kind": "bare", "receiver": None,
                        "simple": name, "arg_signature": list(arg_sig),
                    }
                continue
            if fn is not None and fn.type == "attribute":
                obj = fn.child_by_field_name("object")
                attr = fn.child_by_field_name("attribute")
                if (
                    obj is not None and attr is not None
                    and obj.type == "identifier" and text_of(obj, source) == "self"
                ):
                    _clear(target)
                    call_types[target] = {
                        "receiver_kind": "self", "receiver": None,
                        "simple": text_of(attr, source), "arg_signature": list(arg_sig),
                    }
                    continue
            # Some other call shape (e.g. `x = obj.thing()` or a chained
            # call `x = obj.a().b()`) -- try the general composable chain
            # before giving up on `target` entirely.
            flattened = _flatten_expression(right, source)
            if flattened is not None and flattened[0][0] == "name" and flattened[1]:
                _clear(target)
                root, steps = flattened
                chains[target] = {"root": list(root), "steps": [list(s) for s in steps]}
                continue
            _clear(target)
        elif right.type == "identifier":
            source_name = text_of(right, source)
            if source_name != target:
                _clear(target)
                aliases[target] = source_name
            # `x = x` (a no-op) leaves whatever was already known alone.
        elif right.type == "attribute":
            # `z = service.user`, `a = service.user.profile` (spec 3) -- a
            # pure field-access chain with no call in it at all.
            flattened = _flatten_expression(right, source)
            if flattened is not None and flattened[0][0] == "name" and flattened[1]:
                _clear(target)
                root, steps = flattened
                chains[target] = {"root": list(root), "steps": [list(s) for s in steps]}
            else:
                _clear(target)
        else:
            _clear(target)
    return types, aliases, call_types, chains


def _relative_import_parts(module_name_node: Node, source: bytes) -> tuple[int, str | None]:
    """`relative_import` -> (number of leading dots, dotted tail or None).

    `from . import x`          -> (1, None)
    `from .base import X`      -> (1, "base")
    `from ..common.types im..` -> (2, "common.types")
    """
    level = 0
    tail: str | None = None
    for child in module_name_node.children:
        if child.type == "import_prefix":
            level = text_of(child, source).count(".")
        elif child.type == "dotted_name":
            tail = text_of(child, source)
    return (level or 1), tail


def extract_file(relative_path: Path, source_bytes: bytes) -> dict[str, Any]:
    relative_path = normalize_relative_path(relative_path)
    source = source_bytes
    tree = _parser.parse(source)
    root = tree.root_node
    parse_errors = find_parse_errors(root, relative_path)

    module_qn = module_qualified_name(LANGUAGE, relative_path)
    module_id = make_id(LANGUAGE, module_qn)
    is_package = is_python_package_init(relative_path)

    entities: list[Entity] = [
        Entity(
            id=module_id,
            kind=EntityKind.MODULE,
            name=relative_path.stem,
            qualified_name=module_qn,
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

    def record_import(alias: str, candidates: list[str], node: Node) -> None:
        """One imported name -> its ordered candidate qualified names, plus the
        IMPORT *declaration* entity (which is a distinct concept from the
        imported target -- spec 25)."""
        if not candidates:
            return
        import_candidates[alias] = candidates
        imports_by_simple_name.setdefault(alias, candidates[0])
        display = candidates[0]
        imp_id = make_id(LANGUAGE, f"{module_qn}::import::{display}")
        entities.append(
            Entity(
                id=imp_id, kind=EntityKind.IMPORT, name=display, qualified_name=display,
                language=LANGUAGE, location=location(LANGUAGE, relative_path, node),
                metadata={"alias": alias, "candidates": list(candidates)},
            )
        )
        contains(module_id, imp_id)
        relationships.append(Relationship(source_id=module_id, target_id=imp_id, kind=RelationshipKind.IMPORTS))

    def handle_decorators(entity_id: str, decorator_nodes: list[Node]) -> None:
        for d in decorator_nodes:
            # decorator: "@" <expression>
            expr = d.children[-1]
            text = text_of(expr, source)
            # `@app.route("/x")` -- the decorator *reference* is `app.route`.
            if "(" in text:
                text = text.split("(", 1)[0]
            pending_decorators.append((entity_id, text.strip()))

    def visit_function(
        owner_qn: str, owner_id: str, node: Node, is_method: bool,
        class_fields: set[str] | None = None,
    ) -> None:
        name = text_of(node.child_by_field_name("name"), source)
        params_node = node.child_by_field_name("parameters")
        return_node = node.child_by_field_name("return_type")
        params = _params(params_node, source) if params_node else []

        if is_method and params and params[0].name in {"self", "cls"}:
            params = params[1:]

        is_ctor = is_method and name == "__init__"
        # Constructors use <init>(...) as the canonical name segment, same
        # convention as Java, so the two normalize the same way downstream.
        segment = f"<init>{signature_suffix(params)}" if is_ctor else f"{name}{signature_suffix(params)}"
        fn_qn = join_qualified(owner_qn, segment)
        fn_id = make_id(LANGUAGE, fn_qn)
        kind = EntityKind.CONSTRUCTOR if is_ctor else (EntityKind.METHOD if is_method else EntityKind.FUNCTION)

        fn_entity = Entity(
            id=fn_id,
            kind=kind,
            name=name,
            qualified_name=fn_qn,
            language=LANGUAGE,
            location=location(LANGUAGE, relative_path, node),
            parameters=params,
            return_type=parse_type_reference(text_of(return_node, source) if return_node else None),
        )
        entities.append(fn_entity)
        contains(owner_id, fn_id)
        if not is_method:
            symbols.setdefault(name, fn_id)

        body = node.child_by_field_name("body")
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
                # High-confidence local variable types (spec 5/37): `x =
                # ClassName(...)` in this same function body. Kept on the
                # function/method entity itself (not a new pending-list
                # shape) so the orchestrator can look it up the same way it
                # already looks up `caller.parameters` for typed receivers.
                fn_entity.metadata["local_constructor_types"] = local_types
            if local_aliases:
                # Conservative alias map (spec 8): `account = user`. Chased
                # by the orchestrator only when it leads to an already-known
                # type; never guessed at on its own.
                fn_entity.metadata["local_aliases"] = local_aliases
            if local_call_types:
                # Recorded call shapes (spec 26): `x = get_user()` /
                # `x = self.find_user()`. The orchestrator resolves the call
                # itself and only adopts a type for `x` if the callee has a
                # known declared return type.
                fn_entity.metadata["local_call_types"] = local_call_types
            if local_chains:
                # General composable chain assignments (spec 2/3): `z =
                # service.user`, `a = service.user.profile`, `c =
                # service.get_user().profile`. Resolved by the orchestrator's
                # shared chain engine -- the same one that resolves call
                # receivers and non-call member references.
                fn_entity.metadata["local_chains"] = local_chains

            if is_method:
                seen_fields = class_fields if class_fields is not None else set()
                for stmt in _walk_all(body):
                    if stmt.type == "assignment":
                        left = stmt.child_by_field_name("left")
                        if left is not None and left.type == "attribute":
                            obj = left.child_by_field_name("object")
                            attr = left.child_by_field_name("attribute")
                            # `self.name = name` inside an instance method is a
                            # field; a local variable (plain `name = ...`) is not.
                            if obj is not None and attr is not None and text_of(obj, source) == "self":
                                fname = text_of(attr, source)
                                if fname not in seen_fields:
                                    seen_fields.add(fname)
                                    field_qn = join_qualified(owner_qn, fname)
                                    field_id = make_id(LANGUAGE, field_qn)
                                    type_node = stmt.child_by_field_name("type")
                                    entities.append(
                                        Entity(
                                            id=field_id,
                                            kind=EntityKind.FIELD,
                                            name=fname,
                                            qualified_name=field_qn,
                                            language=LANGUAGE,
                                            location=location(LANGUAGE, relative_path, left),
                                            return_type=parse_type_reference(
                                                text_of(type_node, source) if type_node else None
                                            ),
                                            metadata={"assigned_in": name},
                                        )
                                    )
                                    contains(owner_id, field_id)

    def visit_class(node: Node, owner_qn: str, owner_id: str) -> None:
        """`owner_qn`/`owner_id` are the enclosing scope: the module for a
        top-level class, or the containing class's (qn, id) for a nested one
        -- this is what makes `Outer.Inner` come out qualified instead of
        `Inner` silently losing its containing type."""
        name = text_of(node.child_by_field_name("name"), source)
        class_qn = join_qualified(owner_qn, name)
        class_id = make_id(LANGUAGE, class_qn)
        entities.append(
            Entity(
                id=class_id,
                kind=EntityKind.CLASS,
                name=name,
                qualified_name=class_qn,
                language=LANGUAGE,
                location=location(LANGUAGE, relative_path, node),
            )
        )
        contains(owner_id, class_id)
        symbols.setdefault(name, class_id)

        superclasses = node.child_by_field_name("superclasses")
        if superclasses is not None:
            for base in superclasses.children:
                if base.type == "keyword_argument":
                    # e.g. class Foo(metaclass=Meta) -- not a real base, skip.
                    continue
                if base.type in ("(", ")", ","):
                    continue
                pending_bases.append((class_id, text_of(base, source)))

        seen_fields: set[str] = set()
        block = node.child_by_field_name("body")
        for stmt in block.children if block else []:
            actual = stmt
            decorators: list[Node] = []
            if stmt.type == "decorated_definition":
                decorators = [c for c in stmt.children if c.type == "decorator"]
                actual = stmt.child_by_field_name("definition")
            if actual is None:
                continue

            if actual.type in ("function_definition", "async_function_definition"):
                visit_function(class_qn, class_id, actual, is_method=True, class_fields=seen_fields)
                if decorators:
                    mname = text_of(actual.child_by_field_name("name"), source)
                    params_node = actual.child_by_field_name("parameters")
                    params = _params(params_node, source) if params_node else []

                    if params and params[0].name in {"self", "cls"}:
                        params = params[1:]
                    is_ctor = mname == "__init__"
                    seg = f"<init>{signature_suffix(params)}" if is_ctor else f"{mname}{signature_suffix(params)}"
                    handle_decorators(make_id(LANGUAGE, join_qualified(class_qn, seg)), decorators)
            elif actual.type == "class_definition":
                # Nested class -- recurse with this class as the new owner scope.
                visit_class(actual, class_qn, class_id)
                if decorators:
                    nested_name = text_of(actual.child_by_field_name("name"), source)
                    handle_decorators(make_id(LANGUAGE, join_qualified(class_qn, nested_name)), decorators)
            elif actual.type == "assignment":
                left = actual.child_by_field_name("left")
                type_node = actual.child_by_field_name("type")
                if left is not None and left.type == "identifier":
                    fname = text_of(left, source)
                    if fname not in seen_fields:
                        seen_fields.add(fname)
                        field_qn = join_qualified(class_qn, fname)
                        field_id = make_id(LANGUAGE, field_qn)
                        entities.append(
                            Entity(
                                id=field_id,
                                kind=EntityKind.FIELD,
                                name=fname,
                                qualified_name=field_qn,
                                language=LANGUAGE,
                                location=location(LANGUAGE, relative_path, actual),
                                return_type=parse_type_reference(text_of(type_node, source) if type_node else None),
                            )
                        )
                        contains(class_id, field_id)

    def visit_import_statement(actual: Node) -> None:
        for child in actual.children:
            if child.type == "dotted_name":
                dotted = text_of(child, source)
                alias = dotted.split(".", 1)[0]
                record_import(
                    alias,
                    python_import_candidates(module_qn, is_package, 0, dotted, None),
                    actual,
                )
                # `import a.b.c` also makes the leaf reachable as `a.b.c`
                leaf = dotted.rsplit(".", 1)[-1]
                if leaf != alias:
                    import_candidates.setdefault(
                        leaf, python_import_candidates(module_qn, is_package, 0, dotted, None)
                    )
            elif child.type == "aliased_import":
                dotted = text_of(child.child_by_field_name("name"), source)
                alias = text_of(child.child_by_field_name("alias"), source)
                record_import(
                    alias,
                    python_import_candidates(module_qn, is_package, 0, dotted, None),
                    actual,
                )

    def visit_import_from_statement(actual: Node) -> None:
        module_name_node = actual.child_by_field_name("module_name")
        level = 0
        from_module: str | None = None
        if module_name_node is not None:
            if module_name_node.type == "relative_import":
                level, from_module = _relative_import_parts(module_name_node, source)
            else:
                from_module = text_of(module_name_node, source)

        for name_node in actual.children_by_field_name("name"):
            if name_node.type == "dotted_name":
                simple = text_of(name_node, source)
                alias = simple
            elif name_node.type == "aliased_import":
                simple = text_of(name_node.child_by_field_name("name"), source)
                alias = text_of(name_node.child_by_field_name("alias"), source)
            else:
                continue  # wildcard_import: no named symbol to bind
            record_import(
                alias,
                python_import_candidates(module_qn, is_package, level, from_module, simple),
                actual,
            )

    for top in root.children:
        actual = top
        decorators: list[Node] = []
        if top.type == "decorated_definition":
            decorators = [c for c in top.children if c.type == "decorator"]
            actual = top.child_by_field_name("definition")
        if actual is None:
            continue

        if actual.type == "class_definition":
            visit_class(actual, module_qn, module_id)
            if decorators:
                name = text_of(actual.child_by_field_name("name"), source)
                handle_decorators(make_id(LANGUAGE, join_qualified(module_qn, name)), decorators)
        elif actual.type in ("function_definition", "async_function_definition"):
            visit_function(module_qn, module_id, actual, is_method=False)
            if decorators:
                name = text_of(actual.child_by_field_name("name"), source)
                params_node = actual.child_by_field_name("parameters")
                params = _params(params_node, source) if params_node else []
                seg = f"{name}{signature_suffix(params)}"
                handle_decorators(make_id(LANGUAGE, join_qualified(module_qn, seg)), decorators)
        elif actual.type == "import_statement":
            visit_import_statement(actual)
        elif actual.type == "import_from_statement":
            visit_import_from_statement(actual)

    return {
        "entities": entities,
        "relationships": relationships,
        "module_id": module_id,
        "module_qualified_name": module_qn,
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


def _walk_all(node: Node):
    yield node
    for c in node.children:
        yield from _walk_all(c)