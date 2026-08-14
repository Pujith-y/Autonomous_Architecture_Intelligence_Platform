from pathlib import Path

from app.discovery.dependencies.models import Dependency
from app.discovery.dependencies.parsers import ManifestParsers
from app.discovery.dependencies.registry import ManifestRegistry


class DependencyExtractor:

    def __init__(
        self,
        registry: ManifestRegistry,
    ):
        self.registry = registry

        self.parsers = {
            "json": ManifestParsers.json,
            "pyproject": ManifestParsers.pyproject,
            "requirements": ManifestParsers.requirements,
            "maven": ManifestParsers.maven,
            "gradle": ManifestParsers.gradle,
            "cargo": ManifestParsers.cargo,
            "gomod": ManifestParsers.gomod,
        }

    def extract(
        self,
        path: Path,
    ) -> list[Dependency]:

        definition = self.registry.find(
            path.name
        )

        if definition is None:
            return []

        parser = self.parsers.get(
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