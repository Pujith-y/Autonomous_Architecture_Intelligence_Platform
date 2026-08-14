from dataclasses import dataclass, field
from collections import Counter

from app.discovery.file_classifier import FileCategory
from app.discovery.models import DiscoveredFile, DiscoveredDirectory


@dataclass
class RepositoryMetadata:
    total_files: int = 0
    total_directories: int = 0

    source_files: int = 0
    configuration_files: int = 0
    documentation_files: int = 0
    test_files: int = 0
    asset_files: int = 0
    generated_files: int = 0
    build_files: int = 0
    unknown_files: int = 0

    languages: dict[str, int] = field(default_factory=dict)

    binary_files: int = 0
    large_files: int = 0
    hidden_files: int = 0
    symlink_files: int = 0


class RepositoryAnalyzer:

    def analyze(
        self,
        files: list[DiscoveredFile],
        directories: list[DiscoveredDirectory],
    ) -> RepositoryMetadata:

        metadata = RepositoryMetadata()

        metadata.total_files = len(files)
        metadata.total_directories = len(directories)

        language_counter = Counter()

        for file in files:

            if file.language:
                language_counter[file.language] += 1

            if file.is_binary:
                metadata.binary_files += 1

            if file.is_large:
                metadata.large_files += 1

            if file.is_hidden:
                metadata.hidden_files += 1

            if file.is_symlink:
                metadata.symlink_files += 1

            if file.category == FileCategory.SOURCE:
                metadata.source_files += 1

            elif file.category == FileCategory.CONFIGURATION:
                metadata.configuration_files += 1

            elif file.category == FileCategory.DOCUMENTATION:
                metadata.documentation_files += 1

            elif file.category == FileCategory.TEST:
                metadata.test_files += 1

            elif file.category == FileCategory.ASSET:
                metadata.asset_files += 1

            elif file.category == FileCategory.GENERATED:
                metadata.generated_files += 1

            elif file.category == FileCategory.BUILD:
                metadata.build_files += 1

            elif file.category == FileCategory.UNKNOWN:
                metadata.unknown_files += 1

        metadata.languages = dict(language_counter)

        return metadata