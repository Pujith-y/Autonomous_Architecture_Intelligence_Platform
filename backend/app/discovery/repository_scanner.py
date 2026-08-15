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
from app.discovery.scan_limits import ScanLimits


class RepositoryScanner:

    def __init__(
        self,
        ignore_rules: IgnoreRules | None = None,
        follow_symlinks: bool = False,
        language_detector: LanguageDetector | None = None,
        file_classifier: FileClassifier | None = None,
        limits: ScanLimits | None = None,
    ):
        self.ignore_rules = ignore_rules
        self.follow_symlinks = follow_symlinks
        self.language_detector = language_detector or LanguageDetector()
        self.file_classifier = file_classifier or FileClassifier()
        self.limits = limits or ScanLimits()

    def handle_walk_error(self, error):
        logger.warning(
            f"Unable to access directory during repository scan: {error}"
        )

    def _is_symlink_cycle(
        self,
        current_path: Path,
        candidate: Path,
    ) -> bool:

        if not candidate.is_symlink():
            return False

        try:
            current_real = current_path.resolve()
            candidate_real = candidate.resolve()

            try:
                current_real.relative_to(candidate_real)
                return True
            except ValueError:
                return False

        except OSError as e:
            logger.warning(
                f"Unable to resolve symlink: {candidate}: {e}"
            )
            return True

    def scan(
        self,
        repository: Repository
    ) -> tuple[list[DiscoveredFile], list[DiscoveredDirectory]]:

        files = []
        directories = []

        total_size = 0

        root = repository.path

        for current_root, dir_names, file_names in os.walk(
            root,
            followlinks=self.follow_symlinks,
            onerror=self.handle_walk_error,
        ):

            current_path = Path(current_root)

            filtered_directories = []

            for name in dir_names:

                path = current_path / name

                if self.ignore_rules.should_ignore(path):
                    continue

                if not self.follow_symlinks and path.is_symlink():
                    continue

                if self._is_symlink_cycle(
                    current_path,
                    path,
                ):
                    logger.warning(
                        f"Skipping symlink cycle: {path}"
                    )
                    continue

                filtered_directories.append(name)

            dir_names[:] = filtered_directories

            for directory_name in dir_names:

                path = current_path / directory_name

                if (
                    self.limits.max_directories is not None
                    and len(directories) >= self.limits.max_directories
                ):
                    logger.warning(
                        "Maximum directory limit reached during repository scan"
                    )
                    return files, directories

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

                if (
                    self.limits.max_files is not None
                    and len(files) >= self.limits.max_files
                ):
                    logger.warning(
                        "Maximum file limit reached during repository scan"
                    )
                    return files, directories

                if (
                    self.limits.max_total_size is not None
                    and total_size + size > self.limits.max_total_size
                ):
                    logger.warning(
                        "Maximum repository size limit reached during scan"
                    )
                    return files, directories

                total_size += size

                language = self.language_detector.detect(path)

                is_binary = is_binary_file(path)

                category = self.file_classifier.classify(
                    path=path,
                    language=language,
                    is_binary=is_binary,
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
                        is_binary=is_binary,
                        is_large = (
                            self.limits.max_file_size is not None
                            and size > self.limits.max_file_size
                        ),
                        language = language,
                        category = category
                    )
                )

        return files, directories