import os
from pathlib import Path

from app.ingestion.models import Repository
from app.discovery.models import (
    DiscoveredFile,
    DiscoveredDirectory,
)
from app.discovery.ignore import IgnoreRules
from app.core.logger import logger
from app.discovery.file_detector import is_binary_file
from app.discovery.language_detector import LanguageDetector
from app.discovery.file_classifier import FileClassifier, FileCategory


class RepositoryScanner:

    def __init__(
        self,
        ignore_rules: IgnoreRules | None = None,
        follow_symlinks: bool = False,
        language_detector: LanguageDetector | None = None,
        file_classifier: FileClassifier | None = None,
    ):
        self.ignore_rules = ignore_rules
        self.follow_symlinks = follow_symlinks
        self.language_detector = language_detector or LanguageDetector()
        self.file_classifier = file_classifier or FileClassifier()
        self.max_file_size = 10 * 1024 * 1024  # 10 MB

    def handle_walk_error(self, error):
        logger.warning(
            f"Unable to access directory during repository scan: {error}"
        )

    def scan(
        self,
        repository: Repository
    ) -> tuple[list[DiscoveredFile], list[DiscoveredDirectory]]:

        files = []
        directories = []

        root = repository.path

        for current_root, dir_names, file_names in os.walk(
            root,
            followlinks=self.follow_symlinks,
            onerror=self.handle_walk_error,
        ):

            current_path = Path(current_root)

            dir_names[:] = [
                name
                for name in dir_names
                if not self.ignore_rules.should_ignore(
                    current_path / name
                )
                and (
                    self.follow_symlinks
                    or not (current_path / name).is_symlink()
                )
            ]

            for directory_name in dir_names:

                path = current_path / directory_name

                directories.append(
                    DiscoveredDirectory(
                        path=path,
                        relative_path=path.relative_to(root),
                        name=directory_name,
                        is_hidden=directory_name.startswith("."),
                    )
                )

            for file_name in file_names:

                path = current_path / file_name

                if self.ignore_rules.should_ignore(path):
                    continue

                try:
                    size = path.lstat().st_size
                except OSError as e:
                    logger.warning(
                        f"Unable to read file metadata: {path}: {e}"
                    )
                    continue

                language = self.language_detector.detect(path)

                category = self.file_classifier.classify(
                    path=path,
                    language=language,
                    is_binary=is_binary_file(path),
                )

                files.append(
                    DiscoveredFile(
                        path=path,
                        relative_path=path.relative_to(root),
                        name=file_name,
                        extension=path.suffix,
                        size=size,
                        is_hidden=file_name.startswith("."),
                        is_symlink=path.is_symlink(),
                        is_binary=is_binary_file(path),
                        is_large = size > self.max_file_size,
                        language = language,
                        category = category
                    )
                )

        return files, directories