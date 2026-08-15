from pathlib import Path

from app.discovery.dependencies.models import Dependency
from app.discovery.dependencies.parsers import ManifestParsers
from app.discovery.dependencies.registry import ManifestRegistry
from app.discovery.dependencies.parser_registry import ParserRegistry


class DependencyExtractor:

    def __init__(
        self,
        registry: ManifestRegistry,
        parser_registry: ParserRegistry | None = None,
    ):
        self.registry = registry

        self.parser_registry = (
            parser_registry
            or ParserRegistry()
        )

    def extract(
        self,
        path: Path,
    ) -> list[Dependency]:

        definition = self.registry.find(
            path.name
        )

        if definition is None:
            return []

        parser = self.parser_registry.get(
            definition.parser
        )

        if parser is None:
            return []

        dependency_names = parser(path)

        return [
            Dependency(
                name=name,
                ecosystem=definition.ecosystem,
                source_file=str(path),
            )
            for name in dependency_names
        ]