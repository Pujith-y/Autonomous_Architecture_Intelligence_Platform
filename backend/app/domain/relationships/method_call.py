from dataclasses import dataclass

@dataclass
class MethodCall:

    caller: str
    callee: str