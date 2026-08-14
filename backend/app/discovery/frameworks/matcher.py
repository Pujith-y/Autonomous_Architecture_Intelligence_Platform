from app.discovery.frameworks.models import (
    Dependency,
    FrameworkDefinition,
)


class FrameworkMatcher:

    def match(
        self,
        dependencies: list[Dependency],
        definitions: list[FrameworkDefinition],
    ) -> list[str]:

        detected = set()

        for definition in definitions:

            ecosystem_dependencies = {
                dependency.name.lower()
                for dependency in dependencies
                if dependency.ecosystem
                == definition.ecosystem
            }

            if (
                definition.dependencies
                & ecosystem_dependencies
            ):
                detected.add(
                    definition.name
                )
                continue

            for dependency in ecosystem_dependencies:

                if any(
                    dependency.startswith(prefix)
                    for prefix in definition.dependency_prefixes
                ):
                    detected.add(
                        definition.name
                    )
                    break

        return sorted(detected)