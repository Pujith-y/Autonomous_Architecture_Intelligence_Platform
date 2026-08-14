import json
from pathlib import Path


class ClassificationDefinitions:

    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        with self.path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def get(self, category: str) -> dict:
        return self.data.get(category, {})