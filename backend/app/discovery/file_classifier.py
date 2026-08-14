from enum import Enum

from pathlib import Path

from app.discovery.classification.loader import (
    ClassificationDefinitions,
)


class FileCategory(str, Enum):
    SOURCE = "source"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    TEST = "test"
    ASSET = "asset"
    GENERATED = "generated"
    BUILD = "build"
    UNKNOWN = "unknown"



class FileClassifier:

    def __init__(
        self,
        definitions: ClassificationDefinitions,
    ):
        self.definitions = definitions

    def classify(
        self,
        path: Path,
        language: str | None,
        is_binary: bool,
    ) -> FileCategory:

        if self._matches(
            path,
            "generated",
        ):
            return FileCategory.GENERATED

        if self._matches(
            path,
            "build",
        ):
            return FileCategory.BUILD

        if is_binary:
            return FileCategory.ASSET

        if self._matches(
            path,
            "documentation",
        ):
            return FileCategory.DOCUMENTATION

        if self._matches(
            path,
            "test",
        ):
            return FileCategory.TEST

        if self._matches(
            path,
            "configuration",
        ):
            return FileCategory.CONFIGURATION

        if language is not None:
            return FileCategory.SOURCE

        return FileCategory.UNKNOWN

    def _matches(
        self,
        path: Path,
        category: str,
    ) -> bool:

        definition = self.definitions.get(
            category
        )

        name = path.name.lower()

        parts = {
            part.lower()
            for part in path.parts
        }

        if name in {
            item.lower()
            for item in definition.get(
                "filenames",
                [],
            )
        }:
            return True

        if parts.intersection(
            {
                item.lower()
                for item in definition.get(
                    "directories",
                    [],
                )
            }
        ):
            return True

        for value in definition.get(
            "filename_contains",
            [],
        ):
            if value.lower() in name:
                return True

        for value in definition.get(
            "filename_prefixes",
            [],
        ):
            if name.startswith(
                value.lower()
            ):
                return True

        for value in definition.get(
            "filename_suffixes",
            [],
        ):
            if name.endswith(
                value.lower()
            ):
                return True

        return False