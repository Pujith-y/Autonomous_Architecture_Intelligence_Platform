"""
Semantic-resolution vocabulary (spec: AAIP Semantic Resolution v2, section 1
and 11). `ResolutionMethod` and `UnresolvedReason` give every resolved or
unresolved reference an explicit, centralized label instead of ad-hoc string
literals scattered across the orchestrator -- so "how was this edge found"
and "why couldn't this be resolved" are a fixed, typo-proof vocabulary that
downstream tooling (and this codebase) can rely on.

Both are `str` enums so they serialize into `Relationship.metadata` and
`unresolved_references` entries as plain strings with no adapter needed --
existing JSON output shape is unchanged, only how the values are produced.

This module intentionally does NOT introduce a `ResolutionResult` dataclass
that replaces the orchestrator's `(target_id, method)` / `(target_id, None)`
return convention. That convention already carries the same information
(target found + how, or nothing + recorded elsewhere) and is used in ~15
call sites across a 700+ line file; swapping the return type is a mechanical
but risky rewrite that isn't needed for the enums here to do their job.
Revisit only if a caller actually needs the richer shape (e.g. a confidence
score) that a two-tuple can't carry.
"""

from __future__ import annotations

from enum import Enum


class ResolutionMethod(str, Enum):
    """How a reference was resolved to a repository (or external) entity."""

    # Exact structural match, no ambiguity possible.
    EXPLICIT_IMPORT = "explicit_import"        # the importing module named this exact symbol
    QUALIFIED_NAME = "qualified_name"           # the reference is itself a repo-wide-unique qualified name
    SAME_MODULE = "same_module"                 # resolved relative to the referrer's own module
    ENCLOSING_SCOPE = "enclosing_scope"         # resolved relative to an enclosing class/namespace scope
    QUALIFIED_SUFFIX = "qualified_suffix"       # unique match on a dotted suffix of some repo qualified name

    # Receiver-typed member/call resolution.
    TYPED_RECEIVER = "typed_receiver"           # receiver's type came from a parameter annotation
    LOCAL_CONSTRUCTOR = "local_constructor"     # receiver's type came from `x = ClassName(...)` in the same body
    LOCAL_ALIAS = "local_alias"                 # receiver's type came from chasing `x = y` to an already-typed `y`
    FIELD_TYPE = "field_type"                   # receiver's type came from a field declared on the enclosing class (self.field/this.field)
    SELF_RECEIVER = "self_receiver"             # `self.`/`this.` call resolved on the enclosing class itself
    INHERITED_METHOD = "inherited_method"       # resolved on a base class reached via the inheritance chain (MRO)
    ARGUMENT_MATCHED_OVERLOAD = "argument_matched_overload"  # >1 same-name method, narrowed by call-site argument types
    RETURN_TYPE = "return_type"                 # receiver's type came from a callee's declared return type (spec 26)

    MODULE_LOCAL = "module_local"               # unique match among declarations in the referrer's own module

    # Weakest resolved methods -- still never a guess among multiple
    # candidates, just less context to lean on.
    UNIQUE_SIMPLE_NAME = "unique_simple_name"   # exactly one repo-wide entity has this simple name

    EXTERNAL = "external"                       # positively known to originate outside the repository


class UnresolvedReason(str, Enum):
    """Why a reference could NOT be turned into a relationship. Recorded in
    `metadata["unresolved_references"]` -- never silently dropped."""

    AMBIGUOUS_SIMPLE_NAME = "ambiguous_simple_name"      # >1 repo entity shares the simple name, no way to pick
    AMBIGUOUS_QUALIFIED_NAME = "ambiguous_qualified_name"  # >1 repo entity shares a dotted-suffix match
    AMBIGUOUS_OVERLOAD = "ambiguous_overload"            # >1 same-name method/constructor, argument info didn't narrow it to one
    AMBIGUOUS_METHOD = "ambiguous_method"                # >1 same-name method on a typed receiver's class/MRO chain
    RECEIVER_TYPE_UNKNOWN = "receiver_type_unknown"      # obj.method() where obj's type has no confident source
    METHOD_NOT_FOUND = "method_not_found"                # receiver type is known but has no member of that name
    UNRESOLVED_CALL = "unresolved_call"                  # bare/self call, no import/module-local/self match at all
    UNRESOLVED_SYMBOL = "unresolved_symbol"              # base/implements/decorator reference matched nothing, no import evidence
    UNSUPPORTED_CONSTRUCT = "unsupported_construct"      # syntax recognized but deliberately not resolved (reserved for future use)