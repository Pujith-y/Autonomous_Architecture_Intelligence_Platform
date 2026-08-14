import json
from pathlib import Path

from app.discovery.frameworks.models import FrameworkDefinition


class FrameworkRegistry:

    def __init__(self, definitions_path: Path):

        self.definitions = self._load(
            definitions_path
        )

    def _load(
        self,
        path: Path
    ) -> list[FrameworkDefinition]:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return [
            FrameworkDefinition(
                name=item["name"],
                ecosystem=item["ecosystem"],
                dependencies=frozenset(
                    dependency.lower()
                    for dependency in item.get(
                        "dependencies",
                        []
                    )
                ),
                dependency_prefixes=frozenset(
                    prefix.lower()
                    for prefix in item.get(
                        "dependency_prefixes",
                        []
                    )
                ),
            )
            for item in data
        ]