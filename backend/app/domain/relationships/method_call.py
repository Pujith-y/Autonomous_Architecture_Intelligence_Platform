from dataclasses import dataclass

@dataclass
class MethodCall:
    caller_parent: str
    caller: str
    callee_parent: str
    callee: str