from dataclasses import dataclass


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str
    source_file: str


@dataclass(frozen=True)
class ManifestDefinition:
    filename: str
    ecosystem: str
    parser: str