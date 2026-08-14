from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str
    source_file: str


@dataclass(frozen=True)
class FrameworkDefinition:
    name: str
    ecosystem: str

    dependencies: frozenset[str] = field(
        default_factory=frozenset
    )

    dependency_prefixes: frozenset[str] = field(
        default_factory=frozenset
    )