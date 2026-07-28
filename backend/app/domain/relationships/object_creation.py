from dataclasses import dataclass

@dataclass
class ObjectCreation:
    owner_parent: str
    owner_name: str
    owner_type: str
    object_type: str