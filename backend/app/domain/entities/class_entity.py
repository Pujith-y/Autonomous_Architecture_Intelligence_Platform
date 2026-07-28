from dataclasses import dataclass
from app.domain.entities.named_entity import NamedEntity

@dataclass
class ClassEntity(NamedEntity):

    package: str