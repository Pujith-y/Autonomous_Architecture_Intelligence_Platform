import json
from pathlib import Path

from app.discovery.dependencies.models import ManifestDefinition


class ManifestRegistry:

    def __init__(self, definitions_path: Path):

        self.definitions = self._load(
            definitions_path
        )

    def _load(
        self,
        path: Path,
    ) -> list[ManifestDefinition]:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return [
            ManifestDefinition(
                filename=item["filename"],
                ecosystem=item["ecosystem"],
                parser=item["parser"],
            )
            for item in data
        ]

    def find(
        self,
        filename: str,
    ) -> ManifestDefinition | None:

        for definition in self.definitions:

            if definition.filename == filename:
                return definition

        return None