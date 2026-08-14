from pathlib import Path

from app.discovery.dependencies.extractor import (
    DependencyExtractor,
)

from app.discovery.dependencies.registry import (
    ManifestRegistry,
)

from app.discovery.frameworks.matcher import (
    FrameworkMatcher,
)

from app.discovery.frameworks.registry import (
    FrameworkRegistry,
)


class FrameworkDetector:

    def __init__(
        self,
        manifest_definitions: Path,
        framework_definitions: Path,
    ):

        manifest_registry = ManifestRegistry(
            manifest_definitions
        )

        self.extractor = DependencyExtractor(
            manifest_registry
        )

        self.framework_registry = (
            FrameworkRegistry(
                framework_definitions
            )
        )

        self.matcher = FrameworkMatcher()

    def detect(self, files):

        dependencies = []

        for file in files:

            dependencies.extend(
                self.extractor.extract(
                    file.path
                )
            )

        return self.matcher.match(
            dependencies=dependencies,
            definitions=(
                self.framework_registry
                .definitions
            ),
        )